from datetime import datetime
from webdav.common import rfc1123_date
from zope import component
from Products.Archetypes.utils import contentDispositionHeader
from plone.i18n.normalizer.interfaces import IUserPreferredFileNameNormalizer
import logging

def index_html(self, instance=None, REQUEST=None, RESPONSE=None, disposition='inline'):
    """ Inject X-Sendfile and X-Accel-Redirect headers into response. """

    logger = logging.getLogger('collective.xsendfile')

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
    
    if REQUEST.get('HTTP_X_FORWARDED_FOR') == '':
        logger.log(logging.WARNING, "Falling back to sending object %s.%s via Zope - no HTTP_X_FORWARDED_FOR header found."%(repr(instance),repr(self), )) 
        return zodb_blob.open().read()
    else:
        logger.log(logging.INFO, "Sending object %s.%s with xsendfile headers, path: %s"%(repr(instance),repr(self), repr(file_path))) 
        RESPONSE.setHeader("X-Accel-Redirect", "/xsendfile"+file_path)
        RESPONSE.setHeader("X-Sendfile", file_path )
        return file_path
