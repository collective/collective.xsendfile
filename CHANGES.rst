Changelog
=========

2.0.1 (unreleased)
------------------

- Add a ``s3blobs`` extra: zodb-s3blobs blobs are handed to the proxy as
  presigned S3 URLs.
  [instification]


2.0.0 (2026-10-07)
------------------

- Breaking: require Python 3.10 or later. Drop support for Python 2, Plone 5
  and below.
  [instification]
- Licence changed to GPLv2 or later, was GPL
  [instification]
- Switch to semantic versioning
  [instification]
- Add support for Plone 6.2
  [instification]
- Don't monkeypatch ZODB blobs on ZODB 5.2.2 or later
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
