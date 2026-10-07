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
import os
import shutil
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

    class PresignedUrlTestCase(unittest.TestCase):
        """``_presigned_url`` against zodb-s3blobs with a moto bucket."""

        def setUp(self):
            import boto3
            import tempfile
            from moto import mock_aws
            from ZODB.MappingStorage import MappingStorage
            from zodb_s3blobs.cache import S3BlobCache
            from zodb_s3blobs.s3client import S3Client
            from zodb_s3blobs.storage import S3BlobStorage

            moto = mock_aws()
            moto.start()
            self.addCleanup(moto.stop)
            boto3.client('s3', region_name='us-east-1').create_bucket(
                Bucket='bucket')
            self.tmp = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, self.tmp, True)

            def make_storage(**client_kw):
                client = S3Client(
                    bucket_name='bucket', region_name='us-east-1', **client_kw)
                return S3BlobStorage(
                    MappingStorage(), client,
                    S3BlobCache(os.path.join(self.tmp, 'cache'), 10 ** 7),
                    temp_dir=os.path.join(self.tmp, 'staging'),
                )

            self.make_storage = make_storage
            self.storage = make_storage(prefix='pfx')

        def _store(self, storage, commit=True):
            import transaction
            from ZODB.utils import p64
            from ZODB.utils import z64

            path = os.path.join(self.tmp, 'blob')
            with open(path, 'wb') as f:
                f.write(b'data')
            txn = transaction.get()
            self.addCleanup(transaction.abort)
            storage.tpc_begin(txn)
            storage.storeBlob(p64(1), z64, b'pickle', path, '', txn)
            if not commit:
                return None
            storage.tpc_vote(txn)
            return storage.tpc_finish(txn)

        def _query(self, url):
            from urllib.parse import parse_qs
            from urllib.parse import urlparse

            parsed = urlparse(url)
            return parsed.path, parse_qs(parsed.query)

        def test_url_for_committed_blob(self):
            from collective.xsendfile.utils import _presigned_url
            from ZODB.utils import p64

            tid = self._store(self.storage)
            path, query = self._query(_presigned_url(self.storage, p64(1), tid))
            self.assertTrue(
                path.endswith('/pfx/' + self.storage._s3_key(p64(1), tid)))
            self.assertNotIn('response-content-type', query)
            self.assertNotIn('response-content-disposition', query)

        def test_response_headers(self):
            from collective.xsendfile.utils import _presigned_url
            from ZODB.utils import p64

            tid = self._store(self.storage)
            _path, query = self._query(_presigned_url(
                self.storage, p64(1), tid, content_type='application/pdf',
                filename='Résumé "final"\r\n.pdf', disposition='attachment',
            ))
            self.assertEqual(
                query['response-content-type'], ['application/pdf'])
            self.assertEqual(
                query['response-content-disposition'],
                ["attachment; filename*=UTF-8''"
                 "R%C3%A9sum%C3%A9%20%22final%22%0D%0A.pdf"],
            )

        def test_none_without_committed_revision(self):
            from collective.xsendfile.utils import _presigned_url
            from ZODB.utils import p64
            from ZODB.utils import z64

            for oid, serial in [(None, p64(1)), (p64(1), None), (p64(1), z64)]:
                self.assertIsNone(_presigned_url(self.storage, oid, serial))

        def test_none_for_blob_being_committed(self):
            from collective.xsendfile.utils import _presigned_url
            from ZODB.utils import p64

            self._store(self.storage, commit=False)
            self.assertIsNone(_presigned_url(self.storage, p64(1), p64(2)))

        def test_none_with_sse_c(self):
            import base64
            from collective.xsendfile.utils import _presigned_url
            from ZODB.utils import p64

            storage = self.make_storage(
                sse_customer_key=base64.b64encode(b'k' * 32).decode())
            self.assertIsNone(_presigned_url(storage, p64(1), p64(2)))

        def test_none_if_signing_fails(self):
            from collective.xsendfile.utils import _presigned_url
            from ZODB.utils import p64

            def fail(*args, **kwargs):
                raise RuntimeError('boom')

            self.storage._s3_client._client.generate_presigned_url = fail
            with self.assertLogs('collective.xsendfile', 'WARNING'):
                self.assertIsNone(
                    _presigned_url(self.storage, p64(1), p64(2)))

else:

    class ImageScaleS3TestCase(unittest.TestCase):
        # No layer here: the [s3blobs] extra is not installed, so there is no
        # S3 storage to build. Report a skip rather than an empty module.
        @unittest.skip('requires the collective.xsendfile[s3blobs] extra')
        def test_image_delegates_to_s3(self):
            pass
