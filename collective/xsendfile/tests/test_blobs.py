# -*- coding: utf-8 -*-
import os
import unittest
from ZPublisher.BaseRequest import DefaultPublishTraverse
from plone.app.testing import applyProfile
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
from collective.xsendfile.interfaces import IxsendfileSettings
from collective.xsendfile.testing import INTEGRATION_TESTING
try:
    import plone.namedfile
    plone.namedfile  # Just to fool flake8
    HAS_NAMEDFILE = True
except:
    HAS_NAMEDFILE = False


class BlobTestCase(unittest.TestCase):
    layer = INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.request = self.layer['request']

    def _traverse(self, path):
        pass

    def test_plone_app_blob_image(self):
        request = self.portal.REQUEST
        view = self.portal['image'].unrestrictedTraverse('@@images')
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
        self.assertEqual(content_type, 'image/gif')

        xsendfile = request.RESPONSE.getHeader('X-SENDFILE')
        self.assertTrue(xsendfile is not None)

    def test_at_download(self):
        request = self.portal.REQUEST
        os.environ['XSENDFILE_RESPONSEHEADER'] = 'X-SENDFILE'
        request.set('HTTP_X_FORWARDED_FOR', '0.0.0.0')

        view = self.portal['file']
        view.index_html(request, request.RESPONSE)

        xsendfile = request.RESPONSE.getHeader('X-SENDFILE')
        self.assertTrue(xsendfile is not None)

    def test_substitute(self):
        request = self.portal.REQUEST
        os.environ['XSENDFILE_RESPONSEHEADER'] = 'X-SENDFILE'
        request.set('HTTP_X_FORWARDED_FOR', '0.0.0.0')
        os.environ['XSENDFILE_PATHREGEX_SEARCH'] = r'(.*)'
        os.environ['XSENDFILE_PATHREGEX_SUBSTITUTE'] = r'/xsendfile/\1'

        view = self.portal['file']
        view.index_html(request, request.RESPONSE)

        xsendfile = request.RESPONSE.getHeader('X-SENDFILE')
        self.assertTrue(xsendfile is not None)
        self.assertTrue('/xsendfile/' in xsendfile)

    def test_fallback(self):
        request = self.portal.REQUEST
        os.environ['XSENDFILE_RESPONSEHEADER'] = 'X-SENDFILE'
        os.environ["XSENDFILE_ENABLE_FALLBACK"] = 'True'
        view = self.portal['file']
        view.index_html(request, request.RESPONSE)

        xsendfile = request.RESPONSE.getHeader('X-SENDFILE')
        self.assertTrue(xsendfile is None)

    def test_not_configured(self):
        request = self.portal.REQUEST
        view = self.portal['file']
        view.index_html(request, request.RESPONSE)

        xsendfile = request.RESPONSE.getHeader('X-SENDFILE')
        self.assertTrue(xsendfile is None)

    def test_registry(self):
        request = self.portal.REQUEST
        request.set('HTTP_X_FORWARDED_FOR', '0.0.0.0')

        applyProfile(self.portal, 'plone.app.registry:default')
        applyProfile(self.portal, 'collective.xsendfile:default')
        registry = getUtility(IRegistry)
        settings = registry.forInterface(IxsendfileSettings)
        settings.xsendfile_responseheader = 'X-Sendfile'

        view = self.portal['file']
        view.index_html(request, request.RESPONSE)

        xsendfile = request.RESPONSE.getHeader('X-Sendfile')
        self.assertTrue(xsendfile is not None)


if HAS_NAMEDFILE:
    class NamedFileTestCase(unittest.TestCase):
        layer = INTEGRATION_TESTING

        def setUp(self):
            self.portal = self.layer['portal']
            self.request = self.layer['request']

        def test_plone_namedfile(self):
            """ @@download/fieldname/filename
            """

            request = self.portal.REQUEST
            os.environ['XSENDFILE_RESPONSEHEADER'] = 'X-SENDFILE'
            request.set('HTTP_X_FORWARDED_FOR', '0.0.0.0')
            xsendfile = request.RESPONSE.getHeader('X-SENDFILE')
            self.assertIsNone(xsendfile)

            view = self.portal['file'].unrestrictedTraverse('@@download')
            file = view.publishTraverse(request, 'file')
            file()

            xsendfile = request.RESPONSE.getHeader('X-SENDFILE')
            self.assertIsNotNone(xsendfile)

        def test_plone_namedfile_filename(self):
            """ @@download/fieldname/filename
            """

            request = self.portal.REQUEST
            os.environ['XSENDFILE_RESPONSEHEADER'] = 'X-SENDFILE'
            request.set('HTTP_X_FORWARDED_FOR', '0.0.0.0')

            view = self.portal['file'].unrestrictedTraverse('@@download')
            file = view.publishTraverse(request, 'file')
            filename = file.publishTraverse(request, 'filename')
            filename()

            xsendfile = request.RESPONSE.getHeader('X-SENDFILE')
            self.assertIsNotNone(xsendfile)
