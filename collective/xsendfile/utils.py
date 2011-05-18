from datetime import datetime
from webdav.common import rfc1123_date
from zope import component
from Products.Archetypes.utils import contentDispositionHeader
from plone.i18n.normalizer.interfaces import IUserPreferredFileNameNormalizer
import logging
from zope.component import getUtility
from plone.registry.interfaces import IRegistry
from collective.xsendfile.interfaces import IxsendfileSettings
import re

def index_html(self, instance=None, REQUEST=None, RESPONSE=None, disposition='inline'):
    """ Inject X-Sendfile and X-Accel-Redirect headers into response. """

    logger = logging.getLogger('collective.xsendfile')
    registry = getUtility(IRegistry)
    settings = registry.forInterface(IxsendfileSettings)

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
    
    responseheader = settings.xsendfile_responseheader
    pathregex_search = settings.xsendfile_pathregex_search
    pathregex_substitute = settings.xsendfile_pathregex_substitute
    enable_fallback = settings.xsendfile_enable_fallback
    
    if responseheader and pathregex_substitute:
        file_path = re.sub(pathregex_search,pathregex_substitute,file_path)
    
    RESPONSE.setHeader('Last-Modified', rfc1123_date(instance._p_mtime))        
    RESPONSE.setHeader("Content-Length", blob.get_size())
    RESPONSE.setHeader('Content-Type', self.getContentType(instance))    
    
    fallback = False
    if not responseheader:
        fallback = True
    if enable_fallback:
        if (not REQUEST.get('HTTP_X_FORWARDED_FOR')):
            fallback = True
            
    if fallback:
        logger.log(logging.WARNING, "Falling back to sending object %s.%s via Zope - no HTTP_X_FORWARDED_FOR header found."%(repr(instance),repr(self), )) 
        return zodb_blob.open().read()
    else:
        logger.log(logging.INFO, "Sending object %s.%s with xsendfile header %s, path: %s"%(repr(instance), repr(self), repr(responseheader), repr(file_path))) 
        RESPONSE.setHeader(responseheader, file_path)
        return "collective.xsendfile - proxy missing?"
