"""
    
    XSendFile download support for BLOBs

"""
from datetime import datetime
import logging
import re
from plone.app.blob.iterators import BlobStreamIterator

from zope import component
from zope.component import ComponentLookupError
from webdav.common import rfc1123_date
from zope.component import getUtility

from Products.Archetypes.utils import contentDispositionHeader
from plone.i18n.normalizer.interfaces import IUserPreferredFileNameNormalizer
from plone.registry.interfaces import IRegistry

from collective.xsendfile.interfaces import IxsendfileSettings
import os
from Acquisition import Explicit, aq_inner
from zope.publisher.interfaces import IPublishTraverse, NotFound
from plone.namedfile.utils import safe_basename, set_headers, stream_data
from plone.namedfile.interfaces import IBlobby
from zope.component import adapter, getMultiAdapter
from z3c.form.interfaces import IFieldWidget, IFormLayer, IDataManager, NOVALUE

logger = logging.getLogger('collective.xsendfile')


def set_xsendfile_header(request, blob):
    """ set the xsendheader response header if enabled
        Inject X-Sendfile and X-Accel-Redirect headers into response.
        return True if set
    """
#    blob = self.getUnwrapped(instance, raw=True)    # TODO: why 'raw'?

    if "XSENDFILE_RESPONSEHEADER" in os.environ:
        responseheader = os.environ["XSENDFILE_RESPONSEHEADER"]
        enable_fallback = os.environ.get("XSENDFILE_ENABLE_FALLBACK", "True").lower() in ['true', 'yes']
        pathregex_search = os.environ.get('XSENDFILE_PATHREGEX_SEARCH', r'(.*)')
        pathregex_substitute = os.environ.get('XSENDFILE_PATHREGEX_SUBSTITUTE', r'\1')
        settings = True
    else:
        try:
            registry = getUtility(IRegistry)
            settings = registry.forInterface(IxsendfileSettings)
            responseheader = settings.xsendfile_responseheader
            pathregex_search = settings.xsendfile_pathregex_search
            pathregex_substitute = settings.xsendfile_pathregex_substitute
            enable_fallback = settings.xsendfile_enable_fallback
        except ComponentLookupError:
            # This happens when collective.xsendfile egg is in place
            # but add-on installer has not been run yet
            settings = None
            logger.warn("Could not load collective.xsendfile settings")


    if settings is not None:
        if IBlobby.providedBy(blob):
            zodb_blob = blob._blob
        else:
            zodb_blob = blob.getBlob()
        blob_file = zodb_blob.open()
        file_path = blob_file.name
        blob_file.close()

        if responseheader and pathregex_substitute:
            file_path = re.sub(pathregex_search,pathregex_substitute,file_path)

        fallback = False
        if not responseheader:
            fallback = True
            logger.warn("No front end web server type selected")
        if enable_fallback:
            if (not request.get('HTTP_X_FORWARDED_FOR')):
                fallback = True

    else:
        # Not yet installed through add-on installer
        fallback = True

    if fallback:
        #logger.warn("Falling back to sending object %s.%s via Zope"%(repr(instance),repr(self), ))
        return False
    else:
        #logger.debug("Sending object %s.%s with xsendfile header %s, path: %s"%(repr(instance), repr(self), repr(responseheader), repr(file_path)))
        request.RESPONSE.setHeader(responseheader, file_path)
        return True


# Patches to plone.app.blob.field.BlobWrapper
def plone_app_blob_field_BlobWrapper_getIterator(self, **kw):
    """ called at the end of BlobWrapper.index_html"""
    if IBlobby.providedBy(file) and set_xsendfile_header(self.request, self.blob):
        return "collective.xsendfile - proxy missing?"
    else:
        return BlobStreamIterator(self.blob, **kw)

# Patches to plone.namedfile.browser.Download.__call__
# url similar to ../@@download/fieldname/filename
#  and also used for ../context/@@display-file/fieldname/filename


def monkeypatch_plone_namedfile_browser_Download__call__(self):
    file = self._getFile()
    self.set_headers(file)
    if IBlobby.providedBy(file) and set_xsendfile_header(self.request, file):
        return "collective.xsendfile - proxy missing?"
    else:
        return stream_data(file)

# Patches to plone.formwidget.namedfile.widget.Download.__call__

def monkeypatch_plone_formwidget_namedfile_widget_download__call__(self):

    # TODO: Security check on form view/widget

    if self.context.ignoreContext:
        raise NotFound("Cannot get the data file from a widget with no context")

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

    set_headers(file_, self.request.response, filename=self.filename)
    if IBlobby.providedBy(file_) and set_xsendfile_header(self.request, file_):
        return "collective.xsendfile - proxy missing?"
    else:
        return stream_data(file_)

# TODO Patch plone.app.blob.scale.BlobImageScaleHandler
# need a better version of ImageScale that doesn't open the blob
# looks very hard however since scales currently use Image class
# which reads sizes from the data which kind of defeats the purpose