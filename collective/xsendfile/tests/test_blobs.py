import os
import unittest

from collective.xsendfile.interfaces import IxsendfileSettings
from collective.xsendfile.testing import INTEGRATION_TESTING
from plone.app.testing import applyProfile
from plone.registry.interfaces import IRegistry
from zope.component import getUtility


def clean_env():
    for e in ['XSENDFILE_RESPONSEHEADER',
              'XSENDFILE_PATHREGEX_SEARCH',
              'XSENDFILE_PATHREGEX_SUBSTITUTE',
              'XSENDFILE_ENABLE_FALLBACK']:
        if e in os.environ:
            del os.environ[e]


class BaseTestCase(unittest.TestCase):
    layer = INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.request = self.layer['request']

    def tearDown(self):
        clean_env()

    def _download(self, content_id='file', field='file'):
        view = self.portal[content_id].unrestrictedTraverse('@@download')
        field_view = view.publishTraverse(self.request, field)
        field_view()
        return self.request.RESPONSE


class DownloadTestCase(BaseTestCase):

    def test_download(self):
        os.environ['XSENDFILE_RESPONSEHEADER'] = 'X-SENDFILE'
        self.request.set('HTTP_X_FORWARDED_FOR', '0.0.0.0')

        response = self._download()
        xsendfile = response.getHeader('X-SENDFILE')
        self.assertIsNotNone(xsendfile)
        self.assertTrue(os.path.isfile(xsendfile))

    def test_download_with_filename(self):
        os.environ['XSENDFILE_RESPONSEHEADER'] = 'X-SENDFILE'
        self.request.set('HTTP_X_FORWARDED_FOR', '0.0.0.0')

        view = self.portal['file'].unrestrictedTraverse('@@download')
        field_view = view.publishTraverse(self.request, 'file')
        filename = field_view.publishTraverse(self.request, 'image.gif')
        filename()

        xsendfile = self.request.RESPONSE.getHeader('X-SENDFILE')
        self.assertIsNotNone(xsendfile)
        self.assertTrue(os.path.isfile(xsendfile))

    def test_substitute(self):
        os.environ['XSENDFILE_RESPONSEHEADER'] = 'X-SENDFILE'
        os.environ['XSENDFILE_PATHREGEX_SEARCH'] = r'(.*)'
        os.environ['XSENDFILE_PATHREGEX_SUBSTITUTE'] = r'/xsendfile/\1'
        self.request.set('HTTP_X_FORWARDED_FOR', '0.0.0.0')

        response = self._download()
        xsendfile = response.getHeader('X-SENDFILE')
        self.assertIsNotNone(xsendfile)
        self.assertIn('/xsendfile/', xsendfile)

    def test_fallback(self):
        os.environ['XSENDFILE_RESPONSEHEADER'] = 'X-SENDFILE'
        os.environ['XSENDFILE_ENABLE_FALLBACK'] = 'True'

        response = self._download()
        self.assertIsNone(response.getHeader('X-SENDFILE'))

    def test_not_configured(self):
        response = self._download()
        self.assertIsNone(response.getHeader('X-SENDFILE'))

    def _image_scale(self):
        scales = self.portal['image'].unrestrictedTraverse('@@images')
        scale = scales.publishTraverse(self.request, 'image')
        scale.index_html()
        return self.request.RESPONSE

    def test_image_scale(self):
        os.environ['XSENDFILE_RESPONSEHEADER'] = 'X-SENDFILE'
        self.request.set('HTTP_X_FORWARDED_FOR', '0.0.0.0')

        response = self._image_scale()
        xsendfile = response.getHeader('X-SENDFILE')
        self.assertIsNotNone(xsendfile)
        self.assertTrue(os.path.isfile(xsendfile))

    def test_image_scale_not_configured(self):
        self.request.set('HTTP_X_FORWARDED_FOR', '0.0.0.0')

        response = self._image_scale()
        self.assertIsNone(response.getHeader('X-SENDFILE'))

    def test_registry(self):
        self.request.set('HTTP_X_FORWARDED_FOR', '0.0.0.0')

        applyProfile(self.portal, 'plone.app.registry:default')
        applyProfile(self.portal, 'collective.xsendfile:default')
        registry = getUtility(IRegistry)
        settings = registry.forInterface(IxsendfileSettings)
        settings.xsendfile_responseheader = 'X-Sendfile'

        response = self._download()
        self.assertIsNotNone(response.getHeader('X-Sendfile'))
