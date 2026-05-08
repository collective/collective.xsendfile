# -*- coding: utf-8 -*-
"""
    XSendFile download support for BLOBs
"""
from Acquisition import aq_inner
from ZODB.interfaces import IBlob
from collective.xsendfile.interfaces import IxsendfileSettings
from plone.registry.interfaces import IRegistry
from z3c.form.interfaces import IDataManager
from zope.annotation.interfaces import IAnnotations
from zope.component import getMultiAdapter
from zope.component import getUtility
from zope.publisher.interfaces import NotFound

import logging
import os
import re

try:
    from zodb_s3blobs.storage import S3BlobStorage
    HAS_S3BLOBS = True
except ImportError:
    HAS_S3BLOBS = False


def _resolve_s3_blob_storage(zodb_blob):
    """Return (storage, s3_client) if the blob's ZODB storage is an
    S3BlobStorage, else None. Import-guarded so environments without
    zodb-s3blobs installed continue to work.

    Prefers the Connection's MVCC instance of the storage (``jar._storage``)
    over ``db.storage``. ZODB's ``DB.open()`` calls ``new_instance()`` on the
    storage for each connection; S3BlobStorage keeps pending/staged state on
    the per-connection instance, so the primary may not reflect what the
    current transaction sees.
    """
    if not HAS_S3BLOBS:
        return None
    jar = getattr(zodb_blob, '_p_jar', None)
    if jar is None:
        return None
    storage = getattr(jar, '_storage', None)
    if storage is None:
        db = jar.db()
        storage = db.storage if db is not None else None
    if not isinstance(storage, S3BlobStorage):
        return None
    return storage, storage._s3_client

try:
    from plone.namedfile.utils import get_contenttype
    from plone.namedfile.utils import set_headers
    from plone.namedfile.utils import stream_data
    from plone.namedfile.interfaces import INamedBlobFile
    from plone.namedfile.interfaces import IBlobby
    from urllib.parse import quote as _urlquote
    HAS_NAMEDFILE = True
except:
    HAS_NAMEDFILE = False


def set_headers_no_length(file, response, filename=None, canonical=None):
    """Like plone.namedfile.utils.set_headers but never calls file.getSize().

    For NamedBlobFiles whose ``size`` attribute isn't cached on the instance,
    ``getSize()`` opens the blob — which on S3BlobStorage downloads the whole
    object to a temp file just to learn its byte length. When we're routing
    via xsendfile, the upstream response (nginx -> S3) already provides
    Content-Length, so we skip setting it here.
    """
    size_cached = isinstance(getattr(file, '__dict__', None), dict) \
        and 'size' in file.__dict__
    contenttype = get_contenttype(file)
    response.setHeader("Content-Type", contenttype)
    response.setHeader("Accept-Ranges", "bytes")

    if filename is not None:
        if not isinstance(filename, str):
            filename = str(filename, "utf-8", errors="ignore")
        filename = _urlquote(filename.encode("utf8"))
        response.setHeader(
            "Content-Disposition", f"attachment; filename*=UTF-8''{filename}"
        )

    if canonical is not None:
        response.setHeader(
            "Link", f'<{_urlquote(canonical, safe="/:&?=@")}>; rel="canonical"'
        )

XSENDFILE_DISABLED_KEY = 'collective.xsendfile.disabled'

logger = logging.getLogger('collective.xsendfile')


class EnvSettings(object):
    xsendfile_responseheader = None
    xsendfile_pathregex_search = None
    xsendfile_pathregex_substitute = None
    xsendfile_enable_fallback = None


def get_settings():
    if 'XSENDFILE_RESPONSEHEADER' in os.environ:
        settings = EnvSettings()
        settings.xsendfile_responseheader = os.environ['XSENDFILE_RESPONSEHEADER']
        settings.xsendfile_enable_fallback = os.environ.get('XSENDFILE_ENABLE_FALLBACK',
                                                            'True').lower() in ['true', 'yes']
        settings.xsendfile_pathregex_search = os.environ.get('XSENDFILE_PATHREGEX_SEARCH', r'(.*)')
        settings.xsendfile_pathregex_substitute = os.environ.get('XSENDFILE_PATHREGEX_SUBSTITUTE',
                                                                 r'\1')
        return settings
    else:
        try:
            registry = getUtility(IRegistry)
            settings = registry.forInterface(IxsendfileSettings)
            return settings
        except KeyError:
            # This happens when collective.xsendfile egg is in place
            # but add-on installer has not been run yet
            settings = None
            logger.warn('Could not load collective.xsendfile settings')
    # Not yet installed through add-on installer
    return None


def _get_zodb_blob(blob):
    if HAS_NAMEDFILE and INamedBlobFile.providedBy(blob) and hasattr(blob, '_blob'):
        # HACK: uses internal knowledge but INamedBlobFile provides no way method
        # to get to the underlying blob
        return blob._blob
    if IBlob.providedBy(blob):
        return blob
    return None


def get_file(blob):
    zodb_blob = _get_zodb_blob(blob)
    if zodb_blob is None:
        return False
    return zodb_blob.committed()


def disable_xsendfile(request):
    annotations = IAnnotations(request)
    annotations[XSENDFILE_DISABLED_KEY] = True


def xsendfile_is_disabled(request):
    annotations = IAnnotations(request)
    return annotations.get(XSENDFILE_DISABLED_KEY, False)


def _proxy_preconditions_ok(request, settings):
    """Common preconditions for any xsendfile path.

    Returns True if the front-end proxy is configured and the request looks
    like it really came through one. False means the caller should fall back
    to streaming via Zope.
    """
    if not settings.xsendfile_responseheader:
        logger.warning(
            'xsendfile precondition FAIL: xsendfile_responseheader is unset '
            '(settings=%r). Configure @@xsendfile-settings or set '
            'XSENDFILE_RESPONSEHEADER env var.', settings,
        )
        return False
    if settings.xsendfile_enable_fallback and not request.get('HTTP_X_FORWARDED_FOR'):
        logger.warning(
            'xsendfile precondition FAIL: enable_fallback=True and request '
            'has no HTTP_X_FORWARDED_FOR (path=%s). Request did not come '
            'through a front-end proxy, or proxy is not setting the header.',
            request.get('PATH_INFO', '?'),
        )
        return False
    return True


def _set_s3_xsendfile_header(request, response, zodb_blob, storage_info, settings):
    """Emit xsendfile headers for a blob backed by S3BlobStorage.

    Routes via nginx's /s3-internal/ location; the presigned URL is passed
    out-of-band in X-S3-Url so nginx can use it verbatim in proxy_pass
    without URI-encoding mangling the query string signature.

    Relies on the Connection.setstate patch installed by zodb_s3blobs to
    avoid downloading on Blob unghost; ``loadBlob`` itself remains eager
    (so the streaming fallback path still works as before).
    """
    storage, _s3_client = storage_info
    oid = zodb_blob._p_oid
    serial = zodb_blob._p_serial
    if oid is None or serial is None:
        return False

    presigned_url = storage.xsendfile_presigned_url(oid, serial, expires=60)
    if presigned_url is None:
        logger.warning(
            'xsendfile S3 SKIP: storage.xsendfile_presigned_url returned '
            'None (oid=%r serial=%r) — blob likely pending or S3 error',
            oid, serial,
        )
        return False

    response.setHeader('X-S3-Url', presigned_url)
    response.setHeader(settings.xsendfile_responseheader, '/s3-internal/')
    return True


def _set_local_xsendfile_header(request, response, blob, settings):
    """Emit xsendfile headers for a blob backed by local-disk storage."""
    file_path = get_file(blob)
    if not file_path:
        return False
    if settings.xsendfile_pathregex_substitute:
        file_path = re.sub(
            settings.xsendfile_pathregex_search,
            settings.xsendfile_pathregex_substitute,
            file_path,
        )
    response.setHeader(settings.xsendfile_responseheader, file_path)
    return True


def set_xsendfile_header(request, response, blob):
    """ set the xsendheader response header if enabled
        Inject X-Sendfile and X-Accel-Redirect headers into response.
        return True if set
    """
    path = request.get('PATH_INFO', '?')
    if xsendfile_is_disabled(request):
        return False

    settings = get_settings()
    if settings is None:
        logger.warning(
            'xsendfile SKIP: get_settings() returned None — registry record '
            'missing (add-on profile not installed?) and no XSENDFILE_* env '
            'vars set (path=%s)', path,
        )
        return False

    if not _proxy_preconditions_ok(request, settings):
        return False

    zodb_blob = _get_zodb_blob(blob)
    if zodb_blob is None:
        logger.warning(
            'xsendfile SKIP: _get_zodb_blob returned None for blob=%r '
            '(path=%s)', blob, path,
        )
        return False

    storage_info = _resolve_s3_blob_storage(zodb_blob)
    if storage_info is not None:
        logger.info('xsendfile: routing via S3 (path=%s)', path)
        ok = _set_s3_xsendfile_header(
            request, response, zodb_blob, storage_info, settings,
        )
        logger.info('xsendfile S3 header set=%s (path=%s)', ok, path)
        return ok
    logger.info('xsendfile: routing via local-disk (path=%s)', path)
    ok = _set_local_xsendfile_header(request, response, blob, settings)
    logger.info('xsendfile local header set=%s (path=%s)', ok, path)
    return ok


# Patches to plone.app.blob.field.BlobWrapper

def plone_app_blob_field_BlobWrapper_index_html(self, REQUEST=None,
                                                RESPONSE=None, charset='utf-8',
                                                disposition='inline'):
    # just override to ensure we store the request, then rely on getIterator
    # just in case the logic in the middle changes over time

    if REQUEST is None:
        self._v_REQUEST = self.REQUEST
    else:
        self._v_REQUEST = REQUEST

    if RESPONSE is None:
        self._v_RESPONSE = self._v_REQUEST.RESPONSE
    else:
        self._v_RESPONSE = RESPONSE

    res = self._old_index_html(REQUEST, RESPONSE, charset, disposition)

    if getattr(self, '_v_REQUEST'):
        del self._v_REQUEST
    if getattr(self, '_v_RESPONSE'):
        del self._v_RESPONSE

    return res


def plone_app_blob_field_BlobWrapper_getIterator(self, **kw):
    """ called at the end of BlobWrapper.index_html"""
    if getattr(self, '_v_REQUEST'):
        request = self._v_REQUEST
    else:
        request = self.REQUEST
    if getattr(self, '_v_RESPONSE'):
        response = self._v_RESPONSE
    else:
        response = request.RESPONSE
    if set_xsendfile_header(request, response, self.blob):
        # we have set XSENDFILE header, also send message in case proxy is missing
        return 'collective.xsendfile - proxy missing?'
    else:
        return self._old_getIterator(**kw)

# Patches to plone.namedfile.browser.Download.__call__
# url similar to ../@@download/fieldname/filename
#  and also used for ../context/@@display-file/fieldname/filename

if HAS_NAMEDFILE:
    def monkeypatch_plone_namedfile_browser_Download__call__(self):
        file = self._getFile()
        if file:
            if HAS_NAMEDFILE and IBlobby.providedBy(file):
                zodb_blob = file._blob
            else:
                zodb_blob = file
            response = self.request.response
            if set_xsendfile_header(self.request, response, zodb_blob):
                # Avoid self.set_headers(file): it calls file.getSize() which
                # on S3-backed blobs without a cached size opens the blob and
                # downloads it — exactly what xsendfile is trying to avoid.
                # Replicate just the bits we need; nginx/S3 sets Content-Length.
                from plone.namedfile.browser import DisplayFile
                filename = None
                if not isinstance(self, DisplayFile):
                    filename = self.filename or getattr(file, 'filename', None) \
                        or self.fieldname or 'file.ext'
                set_headers_no_length(file, response, filename=filename)
                return 'collective.xsendfile - proxy missing?'
            self.set_headers(file)
            return stream_data(file)

    def monkeypatch_plone_formwidget_namedfile_widget_download__call__(self):
        """ Patches to plone.formwidget.namedfile.widget.Download.__call__
        """
        if self.context.ignoreContext:
            raise NotFound('Cannot get the data file from a widget with no context')

        if self.context.form is not None:
            content = aq_inner(self.context.form.getContent())
        else:
            content = aq_inner(self.context.context)
        field = aq_inner(self.context.field)

        dm = getMultiAdapter((content, field,), IDataManager)
        file_ = dm.get()
        if file_ is None:
            raise NotFound(self, self.filename, self.request)

        if not self.filename:
            self.filename = getattr(file_, 'filename', None)

        if IBlobby.providedBy(file_):
            zodb_blob = file_._blob
        else:
            zodb_blob = file_
        response = self.request.response
        if set_xsendfile_header(self.request, response, zodb_blob):
            set_headers_no_length(file_, response, filename=self.filename)
            return 'collective.xsendfile - proxy missing?'
        set_headers(file_, response, filename=self.filename)
        return stream_data(file_)

    def plone_namedfile_scaling_ImageScale_index_html(self):
        """ download the image """
        self.validate_access()
        if IBlobby.providedBy(self.data):
            zodb_blob = self.data._blob
        else:
            zodb_blob = self.data

        # Check committed-ness without calling Blob.committed(): that
        # method explicitly calls storage.loadBlob() for its "let storage
        # know" side-effect, which on S3 would download the entire blob.
        # Replicate the BlobError condition inline using only attribute
        # access (cheap after the lazy setstate patch unghosts the Blob).
        from ZODB.blob import SAVEPOINT_SUFFIX
        committed_path = getattr(zodb_blob, '_p_blob_committed', None)
        uncommitted = getattr(zodb_blob, '_p_blob_uncommitted', None)
        if (uncommitted
                or not committed_path
                or committed_path.endswith(SAVEPOINT_SUFFIX)):
            set_headers(self.data, self.request.response)
            return stream_data(self.data)

        response = self.request.response
        if set_xsendfile_header(self.request, response, zodb_blob):
            set_headers_no_length(self.data, response)
            return 'collective.xsendfile - proxy missing?'
        set_headers(self.data, response)
        return stream_data(self.data)


# TODO Patch plone.app.blob.scale.BlobImageScaleHandler
# need a better version of ImageScale that doesn't open the blob
# looks very hard however since scales currently use Image class
# which reads sizes from the data which kind of defeats the purpose
