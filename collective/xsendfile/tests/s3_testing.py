# -*- coding: utf-8 -*-
"""Test layer that backs a full Plone site with ``S3BlobStorage`` over an
in-process ``RelStorage`` (SQLite), fronted by a moto mock S3.

This reproduces production's storage shape -- ``S3BlobStorage`` wrapping a
storage that exposes the commit TID via ``_tpc_phase`` (RelStorage) -- so the
xsendfile *S3* code path (`_resolve_s3_blob_storage` -> presigned URL) actually
fires. ``plone.app.testing`` normally stacks a ``DemoStorage`` at three levels
(Startup, PloneFixture, PloneSandboxLayer); a blob committed above such a stack
lives in that DemoStorage's local blob dir and never reaches S3, and the
connection's ``_storage`` is a ``DemoStorage`` rather than an
``S3BlobStorage``. So each of those three layers is subclassed here to skip the
DemoStorage stacking and keep the single S3-backed database as the connection
storage.

Requires the ``[s3blobs]`` extra (``zodb-s3blobs``, ``relstorage[sqlite3]``,
``moto[s3]``). Importing this module without those installed raises
``ImportError`` so dependent tests skip cleanly.
"""
import os
import shutil
import tempfile

import boto3
import transaction
from moto import mock_aws

from ZODB import DB
from relstorage.adapters.sqlite.adapter import Sqlite3Adapter
from relstorage.options import Options
from relstorage.storage import RelStorage

from zodb_s3blobs.cache import S3BlobCache
from zodb_s3blobs.s3client import S3Client
from zodb_s3blobs.storage import S3BlobStorage

from plone.app.testing import PLONE_SITE_ID
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import applyProfile
from plone.app.testing import login
from plone.app.testing import setRoles
from plone.app.testing.layers import PloneFixture
from plone.namedfile.file import NamedBlobImage
from plone.registry.interfaces import IRegistry
from plone.testing import security
from plone.testing import zca
from plone.testing import zope as pt_zope
from zope.component import getUtility
from zope.component.hooks import setSite

from collective.xsendfile.interfaces import IxsendfileSettings
from collective.xsendfile.testing import getData

import collective.xsendfile


BUCKET = 'collective-xsendfile-test'


class S3Startup(pt_zope.Startup):
    """Zope startup whose ZODB is ``S3BlobStorage(RelStorage(sqlite))`` and
    which runs a moto mock S3 for the layer's lifetime. Replaces the default
    ``DemoStorage`` so the connection storage *is* an ``S3BlobStorage``."""

    defaultBases = (zca.LAYER_CLEANUP,)

    def setUp(self):
        # moto must be active before the S3 client / storage are built and
        # stay active for every S3 op (uploads on commit, presigns in tests).
        self._moto = mock_aws()
        self._moto.start()
        boto3.client('s3', region_name='us-east-1').create_bucket(Bucket=BUCKET)
        self._s3_tmp = tempfile.mkdtemp(prefix='xsendfile-s3-')
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self._moto.stop()
        shutil.rmtree(self._s3_tmp, ignore_errors=True)

    def _make_storage(self):
        options = Options(keep_history=False, shared_blob_dir=False)
        adapter = Sqlite3Adapter(
            data_dir=os.path.join(self._s3_tmp, 'relstorage'),
            pragmas={},
            options=options,
        )
        base = RelStorage(
            adapter, name='xsendfile-test', create=True, options=options,
        )
        client = S3Client(
            bucket_name=BUCKET,
            endpoint_url=None,
            region_name='us-east-1',
            aws_access_key_id='testing',
            aws_secret_access_key='testing',
            use_ssl=False,
            addressing_style='path',
        )
        cache = S3BlobCache(
            cache_dir=os.path.join(self._s3_tmp, 'cache'),
            max_size=50 * 1024 * 1024,
        )
        return S3BlobStorage(base, client, cache)

    def setUpDatabase(self):
        # Mirrors plone.testing.zope.Startup.setUpDatabase but installs the
        # S3-backed database directly instead of stacking a DemoStorage.
        import App.config
        import Zope2.Startup.datatypes

        self['zodbDB'] = DB(self._make_storage())

        class DBFacade:
            def __init__(self, layer):
                self.__layer = layer

            @property
            def __db(self):
                return self.__layer['zodbDB']

            def __getattr__(self, name):
                return getattr(self.__db, name)

        class DBTab(Zope2.Startup.datatypes.DBTab):
            def __init__(self, db):
                self.db_factories = {'testing': None}
                self.mount_paths = {'/': 'testing'}
                self.databases = {'testing': db}

        config = App.config.getConfiguration()
        self._dbtab = getattr(config, 'dbtab', None)
        config.dbtab = DBTab(DBFacade(self))
        App.config.setConfiguration(config)

    def tearDownDatabase(self):
        import App.config

        config = App.config.getConfiguration()
        config.dbtab = self._dbtab
        App.config.setConfiguration(config)
        del self._dbtab

        transaction.abort()
        self['zodbDB'].close()
        del self['zodbDB']


S3_STARTUP = S3Startup()


class S3PloneFixture(PloneFixture):
    """PloneFixture on :data:`S3_STARTUP` that does *not* stack a DemoStorage,
    so the S3-backed database remains the connection storage."""

    defaultBases = (S3_STARTUP,)

    def setUp(self):
        # As PloneFixture.setUp, minus the DemoStorage stacking.
        self.setUpZCML()
        with pt_zope.zopeApp() as app:
            self.setUpProducts(app)
            self.setUpDefaultContent(app)
            # Without a savepoint most tests fail with a PosKeyError
            # (see Products.CMFPlone#3467).
            transaction.savepoint(optimistic=True)

    def tearDown(self):
        with pt_zope.zopeApp() as app:
            self.tearDownProducts(app)
        self.tearDownZCML()
        # NB: the database lifecycle belongs to S3_STARTUP; do not close it.


S3_PLONE_FIXTURE = S3PloneFixture()


class XSendFileS3Layer(PloneSandboxLayer):
    """Full Plone sandbox on the S3-backed database. Creates a Dexterity
    ``Image``, warms its default scale (so the scale blob is committed), and
    configures xsendfile the way production does (registry, fallback off)."""

    defaultBases = (S3_PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        self.loadZCML(package=collective.xsendfile)
        import plone.app.registry
        self.loadZCML(package=plone.app.registry)

    def setUpPloneSite(self, portal):
        setRoles(portal, TEST_USER_ID, ['Manager'])
        login(portal, TEST_USER_NAME)

        applyProfile(portal, 'collective.xsendfile:default')
        registry = getUtility(IRegistry)
        settings = registry.forInterface(IxsendfileSettings)
        settings.xsendfile_responseheader = u'X-Accel-Redirect'
        settings.xsendfile_enable_fallback = False

        data = getData('image.gif')
        portal.invokeFactory(
            'Image', id='image',
            image=NamedBlobImage(data=data, filename='image.gif'),
        )
        # Warm the default scale so its blob is committed to S3 (an
        # on-the-fly, uncommitted scale would legitimately fall back).
        portal['image'].unrestrictedTraverse('@@images').scale(fieldname='image')

    def setUp(self):
        # Mirrors PloneSandboxLayer.setUp but without stacking (or tearing
        # down) a DemoStorage -- the S3-backed database from S3_STARTUP is the
        # single database for the whole layer stack.
        from plone.app.testing.helpers import persist_profile_upgrade_versions
        from Products.PluggableAuthService.PluggableAuthService import (
            MultiPlugins,
        )

        name = self.__name__ if self.__name__ is not None else 'not-named'
        self['configurationContext'] = configurationContext = (
            zca.stackConfigurationContext(
                self.get('configurationContext'),
                name='PloneSandboxLayer-%s' % name,
            )
        )

        with pt_zope.zopeApp() as app:
            from zope.component.hooks import setHooks
            from zope.component import getSiteManager  # noqa
            setHooks()
            portal = app[PLONE_SITE_ID]

            setSite(None)
            from plone.app.testing.helpers import pushGlobalRegistry
            pushGlobalRegistry(portal)
            persist_profile_upgrade_versions(portal)
            security.pushCheckers()

            preSetupMultiPlugins = MultiPlugins[:]

            self.setUpZope(portal.getPhysicalRoot(), configurationContext)
            self.snapshotGeneratedSchemas()

            setSite(portal)
            self.setUpPloneSite(portal)
            setSite(None)

        self.snapshotMultiPlugins(preSetupMultiPlugins)

    def tearDown(self):
        from plone.app.testing.helpers import popGlobalRegistry

        with pt_zope.zopeApp() as app:
            from zope.component.hooks import setHooks
            portal = app[PLONE_SITE_ID]
            setHooks()
            setSite(portal)

            self.tearDownPloneSite(portal)
            setSite(None)

            self.tearDownGeneratedSchemas()
            security.popCheckers()
            popGlobalRegistry(portal)
            self.tearDownMultiPlugins()
            self.tearDownZope(app)

        del self['configurationContext']
        # NB: database lifecycle belongs to S3_STARTUP; do not close it.


XSENDFILE_S3_FIXTURE = XSendFileS3Layer()

from plone.app.testing import IntegrationTesting  # noqa: E402

S3_INTEGRATION_TESTING = IntegrationTesting(
    bases=(XSENDFILE_S3_FIXTURE,),
    name='collective.xsendfile:S3Integration',
)
