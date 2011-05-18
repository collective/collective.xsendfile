from setuptools import setup, find_packages
import os

version = '1.0'

setup(name='collective.xsendfile',
      version=version,
      description="This product enables the delivery of Blob Binaries from filesystem instead of the ZODB via XSendfile",
      long_description=open("README.txt").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
      # Get more strings from
      # http://pypi.python.org/pypi?:action=list_classifiers
      classifiers=[
        "Programming Language :: Python",
        ],
      keywords='',
      author='',
      author_email='',
      url='http://svn.plone.org/svn/collective/',
      license='GPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['collective'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          # -*- Extra requirements: -*-
          'collective.monkeypatcher',
          'plone.app.registry',
          'plone.registry',
          'ore.bigfile',
          'z3c.form',
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
