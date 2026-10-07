# -*- coding: utf-8 -*-
from setuptools import find_namespace_packages
from setuptools import setup


version = '2.0.0.dev0'

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
    long_description_content_type='text/x-rst',
    # Get more strings from https://pypi.org/classifiers/
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Plone',
        'Framework :: Plone :: Addon',
        'Framework :: Plone :: 6.0',
        'Framework :: Plone :: 6.1',
        'Framework :: Plone :: 6.2',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Development Status :: 5 - Production/Stable',
    ],
    keywords='sendfile httpaccel zodb blob',
    author='BlueDynamics Alliance',
    author_email='dev@bluedynamics.com',
    url='https://github.com/collective/collective.xsendfile',
    project_urls={
        'Source': 'https://github.com/collective/collective.xsendfile',
        'Issues': 'https://github.com/collective/collective.xsendfile/issues',
        'Changelog': 'https://github.com/collective/collective.xsendfile/blob/master/CHANGES.rst',
    },
    license_expression='GPL-2.0-or-later',
    license_files=['LICENSE'],
    packages=find_namespace_packages(include=['collective.*']),
    include_package_data=True,
    zip_safe=False,
    python_requires='>=3.10',
    install_requires=[
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
