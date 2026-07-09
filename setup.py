# -*- coding: utf-8 -*-
from setuptools import find_namespace_packages
from setuptools import setup


version = '1.5.dev0'

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
        'Framework :: Plone :: 5.2',
        'Framework :: Plone :: 6.0',
        'Framework :: Plone :: 6.1',
        'Framework :: Plone :: 6.2',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Development Status :: 5 - Production/Stable',
    ],
    keywords='sendfile httpaccel zodb blob',
    author='BlueDynamics Alliance',
    author_email='dev@bluedynamics.com',
    url='https://github.com/collective/collective.xsendfile',
    license='GPL',
    packages=find_namespace_packages(exclude=['ez_setup']),
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
            'zope.testrunner',
            'coverage',
        ],
        'lint': [
            'flake8',
            'black',
            'zpretty',
        ],
        # Optional S3 blob delivery support. Not pulled in by the base
        # package: install via ``collective.xsendfile[s3blobs]``. Bundles the
        # runtime dependency (zodb-s3blobs) together with the tooling its test
        # layer needs (moto for a mock S3, relstorage[sqlite3] as an in-process
        # storage that exposes the commit TID the way production's does).
        's3blobs': [
            'zodb-s3blobs',
            'moto[s3]',
            'relstorage[sqlite3]',
        ],
    },
    entry_points="""
    # -*- Entry points: -*-
    [z3c.autoinclude.plugin]
    target = plone
    [plone.autoinclude.plugin]
    target = plone
    module = collective.xsendfile
    """,
    )
