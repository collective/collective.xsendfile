# -*- coding: utf-8 -*-
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.registry.interfaces import IRegistry
from plone.testing import z2
from plone.testing.z2 import ZSERVER_FIXTURE
from zope.component import getUtility
from zope.configuration import xmlconfig
import collective.xsendfile



class TestLayer(PloneSandboxLayer):
    defaultBases = (PLONE_FIXTURE, )

    def setUpZope(self, app, configurationContext):
        # Load ZCML for this package

        xmlconfig.file('configure.zcml', collective.xsendfile,
                       context=configurationContext)
#        xmlconfig.file('configure.zcml', plone.app.event,
#                       context=configurationContext)
#        z2.installProduct(app, 'Products.DateRecurringIndex')


    def tearDownZope(self, app):
        # Uninstall products installed above
        pass

    def setUpPloneSite(self, portal):
#        applyProfile(portal, 'plone.app.contenttypes:default')
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
