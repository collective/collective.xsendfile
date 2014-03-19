from unittest import TestSuite, makeSuite
from plone.app.blob.tests.base import ReplacementTestCase
from plone.app.blob.tests.base import ReplacementFunctionalTestCase
from plone.app.imaging.tests.base import ImagingTestCaseMixin
from plone.app.imaging.scaling import ImageScaling
from re import match


class ImageTraverseTests(ReplacementTestCase, ImagingTestCaseMixin):

    def afterSetUp(self):
        self.data = self.getImage()
        self.image = self.folder[self.folder.invokeFactory('Image', id='foo',
            image=self.data)]
        field = self.image.getField('image')
        self.available = field.getAvailableSizes(self.image)

    def traverse(self, path=''):
        view = self.image.unrestrictedTraverse('@@images')
        stack = path.split('/')
        name = stack.pop(0)
        tag = view.traverse(name, stack)
        base = self.image.absolute_url()
        expected = r'<img src="%s/@@images/([-0-9a-f]{36}).(jpeg|gif|png)" ' \
            r'alt="foo" title="foo" height="(\d+)" width="(\d+)" />' % base
        groups = match(expected, tag).groups()
        self.assertTrue(groups, tag)
        uid, ext, height, width = groups
        return uid, ext, int(width), int(height)

    def testImageThumb(self):
        self.assertTrue('thumb' in self.available.keys())
        uid, ext, width, height = self.traverse('image/thumb')
        self.assertEqual((width, height), self.available['thumb'])
        self.assertEqual(ext, 'jpeg')

    def testCustomSizes(self):
        # set custom image sizes
        iprops = self.portal.portal_properties.imaging_properties
        iprops.manage_changeProperties(allowed_sizes=['foo 23:23'])
        # make sure traversing works with the new sizes
        uid, ext, width, height = self.traverse('image/foo')
        self.assertEqual(width, 23)
        self.assertEqual(height, 23)

    def testScaleInvalidation(self):
        # first view the thumbnail of the original image
        uid1, ext, width1, height1 = self.traverse('image/thumb')
        # now upload a new one and make sure the thumbnail has changed
        self.image.update(image=self.getImage('image.jpg'))
        uid2, ext, width2, height2 = self.traverse('image/thumb')
        self.assertNotEqual(uid1, uid2, 'thumb not updated?')
        # the height also differs as the original image had a size of 200, 200
        # whereas the updated one has 500, 200...
        self.assertEqual(width1, width2)
        self.assertNotEqual(height1, height2)

    def testCustomSizeChange(self):
        # set custom image sizes & view a scale
        iprops = self.portal.portal_properties.imaging_properties
        iprops.manage_changeProperties(allowed_sizes=['foo 23:23'])
        uid1, ext, width, height = self.traverse('image/foo')
        self.assertEqual(width, 23)
        self.assertEqual(height, 23)
        # now let's update the scale dimensions, after which the scale
        # should also have been updated...
        iprops.manage_changeProperties(allowed_sizes=['foo 42:42'])
        uid2, ext, width, height = self.traverse('image/foo')
        self.assertEqual(width, 42)
        self.assertEqual(height, 42)
        self.assertNotEqual(uid1, uid2, 'scale not updated?')

    def testDefaultPublish(self):
        request = self.folder.REQUEST
        view = self.image.unrestrictedTraverse('@@images')
        image = view.publishTraverse(request, 'image')
        size = image.get_size()

        # Rewrap image scale to leave out the image class
        # implementation. We do this to test the situation where we do
        # not have class-supported publishing (e.g. with schema
        # extension).
        image = image.aq_base.__of__(self.folder)

        from ZPublisher.BaseRequest import DefaultPublishTraverse
        adapter = DefaultPublishTraverse(image, request)
        ob2 = adapter.publishTraverse(request, 'index_html')
        ob2()
        content_type = request.RESPONSE.getHeader('content-type')
        content_length = request.RESPONSE.getHeader('content-length')
        self.assertEqual(content_type, 'image/gif')
        self.assertEqual(content_length, str(size))
