from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import login
from plone.app.testing import setRoles
from plone.namedfile.file import NamedBlobFile
from plone.namedfile.file import NamedBlobImage

import collective.xsendfile
import os


def getData(filename):
    """Return contents of a file from the tests directory."""
    path = os.path.join(os.path.dirname(__file__), 'tests', filename)
    with open(path, 'rb') as f:
        return f.read()


class TestLayer(PloneSandboxLayer):
    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        self.loadZCML(package=collective.xsendfile)
        import plone.app.registry
        self.loadZCML(package=plone.app.registry)

    def setUpPloneSite(self, portal):
        setRoles(portal, TEST_USER_ID, ['Manager'])
        login(portal, TEST_USER_NAME)

        data = getData('image.gif')
        portal.invokeFactory(
            'Image', id='image',
            image=NamedBlobImage(data=data, filename='image.gif'),
        )
        portal.invokeFactory(
            'File', id='file',
            file=NamedBlobFile(data=data, filename='image.gif'),
        )

        # Pre-generate the default image scale so its blob is committed by
        # the layer fixture. Otherwise the xsendfile patch on ImageScale
        # bails out for uncommitted blobs and never sets X-SENDFILE.
        portal['image'].unrestrictedTraverse('@@images').scale(
            fieldname='image',
        )


FIXTURE = TestLayer()

INTEGRATION_TESTING = IntegrationTesting(
    bases=(FIXTURE,),
    name='collective.xsendfile:Integration')
FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(FIXTURE,),
    name='collective.xsendfile:Functional')
