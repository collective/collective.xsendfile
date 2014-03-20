"""
    
    XSendFile download support for BLOBs

"""
from datetime import datetime
import logging
import re

from zope import component
from zope.component import ComponentLookupError
from webdav.common import rfc1123_date
from zope.component import getUtility

from Products.Archetypes.utils import contentDispositionHeader
from plone.i18n.normalizer.interfaces import IUserPreferredFileNameNormalizer
from plone.registry.interfaces import IRegistry

from collective.xsendfile.interfaces import IxsendfileSettings
import os

logger = logging.getLogger('collective.xsendfile')

def index_html(self, instance=None, REQUEST=None, RESPONSE=None, disposition='inline'):
    """ Inject X-Sendfile and X-Accel-Redirect headers into response. """
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
        
        
    if REQUEST is None:
        REQUEST = instance.REQUEST
    if RESPONSE is None:
        RESPONSE = REQUEST.RESPONSE
    filename = self.getFilename(instance)
    if filename is not None:
        filename = IUserPreferredFileNameNormalizer(REQUEST).normalize(
            unicode(filename, instance.getCharset()))
        header_value = contentDispositionHeader(
            disposition=disposition,
            filename=filename)
        RESPONSE.setHeader("Content-disposition", header_value)
    
    blob = self.getUnwrapped(instance, raw=True)    # TODO: why 'raw'?
    zodb_blob = blob.getBlob()
    blob_file = zodb_blob.open()
    file_path = blob_file.name
    blob_file.close()

    RESPONSE.setHeader('Last-Modified', rfc1123_date(instance._p_mtime))        
    RESPONSE.setHeader("Content-Length", blob.get_size())
    RESPONSE.setHeader('Content-Type', self.getContentType(instance))    
    
    if settings is not None:

        if responseheader and pathregex_substitute:
            file_path = re.sub(pathregex_search,pathregex_substitute,file_path)
            
        fallback = False
        if not responseheader:
            fallback = True
            logger.warn("No front end web server type selected")
        if enable_fallback:
            if (not REQUEST.get('HTTP_X_FORWARDED_FOR')):
                fallback = True

    else:
        # Not yet installed through add-on installer
        fallback = True
            
    if fallback:
        logger.warn("Falling back to sending object %s.%s via Zope"%(repr(instance),repr(self), )) 
        return zodb_blob.open().read()
    else:
        logger.debug("Sending object %s.%s with xsendfile header %s, path: %s"%(repr(instance), repr(self), repr(responseheader), repr(file_path))) 
        RESPONSE.setHeader(responseheader, file_path)
        return "collective.xsendfile - proxy missing?"
