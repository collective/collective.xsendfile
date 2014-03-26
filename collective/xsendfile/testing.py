# -*- coding: utf-8 -*-
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.testing.z2 import ZSERVER_FIXTURE
from zope.configuration import xmlconfig
import collective.xsendfile


class TestLayer(PloneSandboxLayer):
    defaultBases = (PLONE_FIXTURE, )

    def setUpZope(self, app, configurationContext):
        # Load ZCML for this package

        xmlconfig.file('configure.zcml', collective.xsendfile,
                       context=configurationContext)

    def tearDownZope(self, app):
        # Uninstall products installed above
        pass

    def setUpPloneSite(self, portal):
        pass


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
