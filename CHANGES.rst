Changelog
=========

2.0.0 (unreleased)
------------------

- Breaking: require Python 3.10 or later. Plone 6.0, 6.1 and 6.2 are
  supported; Python 2 and Plone 4.3 to 5.2 are no longer supported.
  [instification]
- Switch to semantic versioning and prepare for release on PyPI: add
  ``python_requires`` and accurate classifiers, fix ``MANIFEST.in``,
  remove buildout and Travis CI leftovers, and test against Plone 6.0 too.
  [instification]
- Add support for Plone 6.2
  [instification]
- Don't monkeypatch ZODB blobs if ZODB <= 5.2.2
  [instification]
- Support Python 3 & Plone >= 5.2
  [frapell, instification]


1.4 (2022-06-13)
----------------

- Log OSError on creating blob directory.
  [enfold]


1.3 (2021-08-11)
----------------

- Do not use binary mode for reading/writing the .layout
  [frapell]


1.2 (2021-07-01)
----------------

- Plone 5.2 / Python 3
  [frapell]

- Add suport for image scales
  [frapell]


1.1 (2021-06-24)
----------------

- add function `disable_xsendfile` to disable x-sendfile via code
  [enfold]

- rebuilt code so it works with namedfile as well as plone.app.blob
  [djay]

- added tests
  [djay]


1.1b1 (no pypi release)
-----------------------

- Can use environment variables to globally set xsendfile for all sites
  [djay]


1.0dev (no pypi release)
------------------------

- Initial release
