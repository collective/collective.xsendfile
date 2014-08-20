# -*- coding: utf-8 -*-
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.testing.z2 import ZSERVER_FIXTURE
from zope.configuration import xmlconfig
import collective.xsendfile
from plone.app.testing import setRoles
from plone.app.testing import login
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import TEST_USER_ID
from plone.app.imaging.tests.utils import getData


class TestLayer(PloneSandboxLayer):
    defaultBases = (PLONE_FIXTURE, )

    def setUpZope(self, app, configurationContext):
        # Load ZCML for this package

        xmlconfig.file('configure.zcml', collective.xsendfile,
                       context=configurationContext)
        import plone.app.registry
        xmlconfig.file('configure.zcml', plone.app.registry, context=configurationContext)

    def tearDownZope(self, app):
        # Uninstall products installed above
        pass

    def setUpPloneSite(self, portal):
        setRoles(portal, TEST_USER_ID, ['Manager'])
        login(portal, TEST_USER_NAME)

        data = getData('image.gif')
        portal[portal.invokeFactory('Image', id='image', image=data)]
        portal[portal.invokeFactory('File', id='file', file=data)]


FIXTURE = TestLayer()

INTEGRATION_TESTING = IntegrationTesting(
    bases=(FIXTURE,),
    name='collective.xsendfile:Integration')
FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(FIXTURE,),
    name='collective.xsendfile:Functional')

ROBOT_TESTING = FunctionalTesting(
    bases=(FIXTURE,
           REMOTE_LIBRARY_BUNDLE_FIXTURE,
           ZSERVER_FIXTURE),
    name='collective.xsendfile:Robot')
