from setuptools import setup, find_packages
import os

version = '1.1b2'

setup(name='collective.xsendfile',
      version=version,
      description="Offload ZODB BLOB download to front end web server using XSendfile protocol",
      long_description=open("README.rst").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
      # Get more strings from
      # http://pypi.python.org/pypi?:action=list_classifiers
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Plone",
        ],
      keywords='',
      author='Mikko Ohtamaa',
      author_email='mikko@mfabrik.com',
      url='https://github.com/collective/collective.xsendfile',
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
          # 'z3c.form',
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
