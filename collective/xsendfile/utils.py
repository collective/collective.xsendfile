# -*- coding: utf-8 -*-
"""
    XSendFile download support for BLOBs
"""
from Acquisition import aq_inner
from ZODB.blob import Blob
from ZODB.interfaces import BlobError
from ZODB.interfaces import IBlob
from ZODB.utils import z64
from collective.xsendfile.interfaces import IxsendfileSettings
from plone.registry.interfaces import IRegistry
from urllib.parse import quote
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

    Uses the connection's storage (``jar._storage``): when S3BlobStorage
    provides ``IMVCCStorage`` each connection has its own instance, which
    holds that connection's pending blobs. Without ``IMVCCStorage`` it is a
    ZODB ``MVCCAdapterInstance`` and the S3 path isn't used.
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


def _presigned_url(storage, oid, serial, content_type=None, filename=None,
                   disposition='inline', expires_in=60):
    """Return a presigned S3 GET URL for a committed blob, or None.

    ``content_type`` and ``filename`` set the response's Content-Type and
    Content-Disposition (blobs are stored in S3 without metadata); they are
    signed with the URL. Returns None, for the caller to stream the blob,
    when there is no committed revision to sign (no oid or serial, or a blob
    being committed in this transaction), with SSE-C (the proxy can't send
    the key) or if signing fails.

    Relies on zodb-s3blobs internals (as of 1.1.0): the storage's key layout,
    pending blobs and S3 client. Keep that access to this function.
    """
    if oid is None or serial in (None, z64):
        return None
    s3_client = storage._s3_client
    if oid in storage._pending_blobs or s3_client._sse_extra_args:
        return None
    params = {
        'Bucket': s3_client.bucket_name,
        'Key': s3_client._full_key(storage._s3_key(oid, serial)),
    }
    if content_type:
        params['ResponseContentType'] = content_type
    if filename:
        params['ResponseContentDisposition'] = "%s; filename*=UTF-8''%s" % (
            disposition, quote(filename))
    try:
        return s3_client._client.generate_presigned_url(
            'get_object', Params=params, ExpiresIn=expires_in)
    except Exception:
        logger.warning(
            'xsendfile: failed to presign S3 URL for oid=%r serial=%r',
            oid, serial, exc_info=True,
        )
        return None

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
    # isinstance before providedBy: providedBy unghosts the blob, which loads
    # its data (on zodb-s3blobs, downloads it).
    if isinstance(blob, Blob):
        return blob
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
    try:
        return zodb_blob.committed()
    except BlobError:
        # An on-the-fly generated scale is uncommitted while the generating
        # request is still running, so committed() raises "Uncommitted
        # changes". Return False so the caller falls back to streaming rather
        # than propagating a 500.
        return False


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
        logger.debug(
            'xsendfile precondition FAIL: xsendfile_responseheader is unset '
            '(settings=%r). Configure @@xsendfile-settings or set '
            'XSENDFILE_RESPONSEHEADER env var.', settings,
        )
        return False
    if settings.xsendfile_enable_fallback and not request.get('HTTP_X_FORWARDED_FOR'):
        logger.debug(
            'xsendfile precondition FAIL: enable_fallback=True and request '
            'has no HTTP_X_FORWARDED_FOR (path=%s). Request did not come '
            'through a front-end proxy, or proxy is not setting the header.',
            request.get('PATH_INFO', '?'),
        )
        return False
    return True


def _committed_serial(zodb_blob, storage):
    """Return the serial of the blob's committed revision.

    A ghost's ``_p_serial`` isn't set until it is unghosted, so load the
    blob's record instead; that reads its state, not its data.
    """
    if zodb_blob._p_changed is None:  # ghost
        return storage.load(zodb_blob._p_oid)[1]
    return zodb_blob._p_serial


def _set_s3_xsendfile_header(request, response, zodb_blob, storage_info,
                             settings, file=None, disposition='inline'):
    """Emit xsendfile headers for a blob backed by S3BlobStorage.

    Routes via nginx's /s3-internal/ location; the presigned URL is passed
    out-of-band in X-S3-Url so nginx can use it verbatim in proxy_pass
    without URI-encoding mangling the query string signature.

    ``file`` is the owning NamedBlob/Image (or similar) whose
    ``contentType`` and ``filename`` are forwarded into the presigned URL
    as response-content-type / response-content-disposition. Blobs are
    uploaded to S3 without metadata, so without this override S3 would
    serve them as ``binary/octet-stream``.

    Doesn't unghost ``zodb_blob``: unghosting a blob downloads it from S3.
    """
    storage, _s3_client = storage_info
    oid = zodb_blob._p_oid
    if oid is None or zodb_blob._p_changed:
        # Not committed yet, or changed in this transaction.
        return False
    serial = _committed_serial(zodb_blob, storage)

    content_type = None
    filename = None
    if file is not None:
        content_type = get_contenttype(file) if HAS_NAMEDFILE else \
            getattr(file, 'contentType', None) or \
            getattr(file, 'content_type', None)
        filename = getattr(file, 'filename', None)

    presigned_url = _presigned_url(
        storage, oid, serial,
        content_type=content_type, filename=filename,
        disposition=disposition,
    )
    if presigned_url is None:
        logger.warning(
            'xsendfile S3 SKIP: no presigned URL (oid=%r serial=%r) — blob '
            'likely pending or S3 error',
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


def set_xsendfile_header(request, response, blob, file=None,
                         disposition='inline'):
    """ set the xsendheader response header if enabled
        Inject X-Sendfile and X-Accel-Redirect headers into response.
        return True if set

        ``file`` is the owning NamedBlob/Image (when distinct from
        ``blob``); used on the S3 path to override S3's stored
        Content-Type and Content-Disposition via signed query params.
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
        ok = _set_s3_xsendfile_header(
            request, response, zodb_blob, storage_info, settings,
            file=file if file is not None else blob,
            disposition=disposition,
        )
        logger.debug('xsendfile: route=s3 set=%s path=%s', ok, path)
        return ok
    ok = _set_local_xsendfile_header(request, response, blob, settings)
    logger.debug('xsendfile: route=local set=%s path=%s', ok, path)
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
    if set_xsendfile_header(request, response, self.blob, file=self):
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
            from plone.namedfile.browser import DisplayFile
            filename = None
            if not isinstance(self, DisplayFile):
                filename = self.filename or getattr(file, 'filename', None) \
                    or self.fieldname or 'file.ext'
            # Inline for DisplayFile (image previews), attachment for downloads.
            disposition = 'inline' if isinstance(self, DisplayFile) else 'attachment'
            if set_xsendfile_header(self.request, response, zodb_blob,
                                    file=file, disposition=disposition):
                # Avoid self.set_headers(file): it calls file.getSize() which
                # on S3-backed blobs without a cached size opens the blob and
                # downloads it — exactly what xsendfile is trying to avoid.
                # Replicate just the bits we need; nginx/S3 sets Content-Length.
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
        if set_xsendfile_header(self.request, response, zodb_blob,
                                file=file_, disposition='attachment'):
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

        # As in the Download.__call__ patch, let set_xsendfile_header decide.
        # Don't check _p_blob_committed first: it is only set once the blob
        # is unghosted, and on S3BlobStorage the blob isn't a local file.
        # set_xsendfile_header returns False for a blob that isn't committed
        # (e.g. a scale generated in this request), which is then streamed.
        response = self.request.response
        if set_xsendfile_header(self.request, response, zodb_blob,
                                file=self.data, disposition='inline'):
            # Avoid set_headers(self.data): it calls getSize() which on an
            # S3-backed blob without a cached size opens (downloads) the blob.
            # nginx/S3 supplies Content-Length instead.
            set_headers_no_length(self.data, response)
            return 'collective.xsendfile - proxy missing?'
        set_headers(self.data, response)
        return stream_data(self.data)


# TODO Patch plone.app.blob.scale.BlobImageScaleHandler
# need a better version of ImageScale that doesn't open the blob
# looks very hard however since scales currently use Image class
# which reads sizes from the data which kind of defeats the purpose
