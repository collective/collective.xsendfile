# -*- coding: utf-8 -*-
"""Deterministic S3 gate for the image-scale xsendfile patch.

On ``S3BlobStorage`` a committed blob has no local committed *path*
(``_p_blob_committed`` is falsy), so the old ``ImageScale.index_html`` guard
tripped on every S3-backed image and streamed the bytes through Zope instead of
delegating. This exercises that exact production shape: with the guard present
the response carries no xsendfile header (fails); with the guard removed the S3
path sets ``X-Accel-Redirect`` + ``X-S3-Url`` (passes).

Skips unless the ``[s3blobs]`` extra is installed.
"""
import unittest


try:
    from collective.xsendfile.tests.s3_testing import S3_INTEGRATION_TESTING
    HAS_S3BLOBS = True
except ImportError:
    HAS_S3BLOBS = False


# Only define the layer-bound test case when the [s3blobs] extra is installed.
# A class with ``layer = None`` would break zope-testrunner's layer discovery,
# so absence of the extra means this module simply contributes no tests.
if HAS_S3BLOBS:

    class ImageScaleS3TestCase(unittest.TestCase):
        layer = S3_INTEGRATION_TESTING

        def setUp(self):
            self.portal = self.layer['portal']
            self.request = self.layer['request']

        def _serve_image(self, name='image'):
            scales = self.portal['image'].unrestrictedTraverse('@@images')
            scale = scales.publishTraverse(self.request, name)
            scale.index_html()
            return self.request.RESPONSE

        def test_image_delegates_to_s3(self):
            response = self._serve_image()
            # The S3 xsendfile path routes via nginx's internal S3 location and
            # passes the presigned URL out-of-band in X-S3-Url.
            self.assertEqual(
                response.getHeader('X-Accel-Redirect'), '/s3-internal/',
            )
            self.assertIsNotNone(response.getHeader('X-S3-Url'))

else:

    class ImageScaleS3TestCase(unittest.TestCase):
        # No layer here: the [s3blobs] extra is not installed, so there is no
        # S3 storage to build. Report a skip rather than an empty module.
        @unittest.skip('requires the collective.xsendfile[s3blobs] extra')
        def test_image_delegates_to_s3(self):
            pass
