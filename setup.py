# -*- coding: utf-8 -*-
from setuptools import find_packages
from setuptools import setup


version = '1.1.dev0'

setup(
    name='collective.xsendfile',
    version=version,
    description="Offload ZODB BLOB download to front end web server using "
                "XSendfile/HTTP-Accel protocol",
    long_description=(
        open("README.rst").read() +
        "\n" +
        open("CHANGES.rst").read()
    ),
    # Get more strings from
    # http://pypi.python.org/pypi?:action=list_classifiers
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Plone',
        'Framework :: Plone :: 4.3',
        'Framework :: Plone :: 5.0',
        'Framework :: Plone :: 5.1',

    ],
    keywords='sendfile httpaccel zodb blob',
    author='BlueDynamics Alliance',
    author_email='dev@bluedynamics.com',
    url='https://github.com/collective/collective.xsendfile',
    license='GPL',
    packages=find_packages(exclude=['ez_setup']),
    namespace_packages=['collective'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'setuptools',
        # -*- Extra requirements: -*-
        'Plone',
        'collective.monkeypatcher',
    ],
    extras_require={
        'test': [
            'plone.app.testing',
            'plone.app.robotframework'
        ],
    },
    entry_points="""
    # -*- Entry points: -*-
    [z3c.autoinclude.plugin]
    target = plone
    """,
    )