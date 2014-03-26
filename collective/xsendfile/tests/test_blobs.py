import os
import unittest
from plone.app.testing import setRoles, login, TEST_USER_NAME, TEST_USER_ID
from collective.xsendfile.testing import INTEGRATION_TESTING
from plone.app.imaging.tests.utils import getData
from ZPublisher.BaseRequest import DefaultPublishTraverse


class IntegrationTestCase(unittest.TestCase):
    layer = INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        login(self.portal, TEST_USER_NAME)

        self.data = getData('image.gif')
        self.image = self.portal[self.portal.invokeFactory('Image', id='foo',
            image=self.data)]
        field = self.image.getField('image')
        self.available = field.getAvailableSizes(self.image)

        self.file = self.portal[self.portal.invokeFactory('File', id='bar',
            file=self.data)]

    def _traverse(self, path):
        pass

    def test_plone_app_blob(self):
        request = self.portal.REQUEST
        view = self.image.unrestrictedTraverse('@@images')
        image = view.publishTraverse(request, 'image')

        # Rewrap image scale to leave out the image class
        # implementation. We do this to test the situation where we do
        # not have class-supported publishing (e.g. with schema
        # extension).
        image = image.aq_base.__of__(self.portal)

        adapter = DefaultPublishTraverse(image, request)
        ob2 = adapter.publishTraverse(request, 'index_html')

        os.environ['XSENDFILE_RESPONSEHEADER'] = 'X-SENDFILE'
        request.set('HTTP_X_FORWARDED_FOR', '0.0.0.0')

        ob2()
        content_type = request.RESPONSE.getHeader('content-type')
        content_length = request.RESPONSE.getHeader('content-length')
        self.assertEqual(content_type, 'image/gif')

        xsendfile = request.RESPONSE.getHeader('X-SENDFILE')
        self.assertIsNotNone(xsendfile)


    def test_plone_namedfile(self):
        #@@download/fieldname/filename

        request = self.portal.REQUEST
        os.environ['XSENDFILE_RESPONSEHEADER'] = 'X-SENDFILE'
        request.set('HTTP_X_FORWARDED_FOR', '0.0.0.0')
        xsendfile = request.RESPONSE.getHeader('X-SENDFILE')
        self.assertIsNone(xsendfile)

        view = self.file.unrestrictedTraverse('@@download')
        file = view.publishTraverse(request, 'file')
        file()

        xsendfile = request.RESPONSE.getHeader('X-SENDFILE')
        self.assertIsNotNone(xsendfile)

    def test_plone_namedfile_filename(self):
        #@@download/fieldname/filename

        request = self.portal.REQUEST
        os.environ['XSENDFILE_RESPONSEHEADER'] = 'X-SENDFILE'
        request.set('HTTP_X_FORWARDED_FOR', '0.0.0.0')

        view = self.file.unrestrictedTraverse('@@download')
        file = view.publishTraverse(request, 'file')
        filename = file.publishTraverse(request, 'filename')
        filename()

        xsendfile = request.RESPONSE.getHeader('X-SENDFILE')
        self.assertIsNotNone(xsendfile)

    def test_substitute(self):
        #@@download/fieldname/filename

        request = self.portal.REQUEST
        os.environ['XSENDFILE_RESPONSEHEADER'] = 'X-SENDFILE'
        request.set('HTTP_X_FORWARDED_FOR', '0.0.0.0')
        os.environ['XSENDFILE_PATHREGEX_SEARCH'] = r'(.*)'
        os.environ['XSENDFILE_PATHREGEX_SUBSTITUTE'] = r'/xsendfile/\1'

        view = self.file.unrestrictedTraverse('@@download')
        file = view.publishTraverse(request, 'file')
        file()

        xsendfile = request.RESPONSE.getHeader('X-SENDFILE')
        self.assertIsNotNone(xsendfile)
        self.assertIn('/xsendfile/', xsendfile)

    def test_fallback(self):
        #@@download/fieldname/filename

        request = self.portal.REQUEST
        os.environ['XSENDFILE_RESPONSEHEADER'] = 'X-SENDFILE'
        os.environ["XSENDFILE_ENABLE_FALLBACK"] = 'True'
        view = self.file.unrestrictedTraverse('@@download')
        file = view.publishTraverse(request, 'file')
        file()

        xsendfile = request.RESPONSE.getHeader('X-SENDFILE')
        self.assertIsNone(xsendfile)
