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

    def _download_body(self, **headers):
        for name, value in headers.items():
            self.request.environ['HTTP_' + name.upper().replace('-', '_')] = value
        view = self.portal['file'].unrestrictedTraverse('@@download')
        result = view.publishTraverse(self.request, 'file')()
        # A handoff returns a placeholder string instead of the file
        body = result if isinstance(result, (bytes, str)) else b''.join(result)
        if hasattr(result, 'close'):
            result.close()
        return self.request.RESPONSE, body

    def test_range_when_not_delegated(self):
        """Zope serves the range, as plone.namedfile does."""
        from collective.xsendfile.testing import getData

        data = getData('image.gif')
        response, body = self._download_body(range='bytes=2-5')
        self.assertIsNone(response.getHeader('X-SENDFILE'))
        self.assertEqual(response.getStatus(), 206)
        self.assertEqual(
            response.getHeader('Content-Range'), 'bytes 2-5/%d' % len(data))
        self.assertEqual(body, data[2:6])

    def test_if_range_when_not_delegated(self):
        from collective.xsendfile.testing import getData

        data = getData('image.gif')
        response, body = self._download_body(
            range='bytes=2-5', if_range='"some-etag"')
        self.assertEqual(response.getStatus(), 200)
        self.assertIsNone(response.getHeader('Content-Range'))
        self.assertEqual(body, data)

    def test_range_when_delegated(self):
        """The proxy serves the range from the file, so Zope doesn't."""
        os.environ['XSENDFILE_RESPONSEHEADER'] = 'X-SENDFILE'
        self.request.set('HTTP_X_FORWARDED_FOR', '0.0.0.0')

        response, _body = self._download_body(range='bytes=2-5')
        self.assertIsNotNone(response.getHeader('X-SENDFILE'))
        self.assertEqual(response.getStatus(), 200)
        self.assertIsNone(response.getHeader('Content-Range'))

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

    def _generate_image_scale(self, scalename):
        # Traverse @@images/image/<scalename>. Unlike _image_scale (which
        # serves the pre-generated default field scale), <scalename> has not
        # been generated by the layer, so this both generates and serves it
        # within the same, still-uncommitted transaction -- reproducing the
        # on-the-fly generation an acceptance/prod first-access request hits.
        scales = self.portal['image'].unrestrictedTraverse('@@images')
        self.request['TraversalRequestNameStack'] = [scalename]
        scale = scales.publishTraverse(self.request, 'image')
        scale.index_html()
        return self.request.RESPONSE

    def test_image_scale_on_the_fly_generation(self):
        # A scale generated on-the-fly is uncommitted while the generating
        # request is still running, so Blob.committed() raises BlobError. The
        # xsendfile ImageScale patch must detect that and fall back to
        # streaming rather than propagating a 500. Before the fix this call
        # raises ZODB.interfaces.BlobError: Uncommitted changes.
        os.environ['XSENDFILE_RESPONSEHEADER'] = 'X-SENDFILE'
        self.request.set('HTTP_X_FORWARDED_FOR', '0.0.0.0')

        response = self._generate_image_scale('preview')
        # Uncommitted blob -> no delegation, streamed by Zope instead.
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
