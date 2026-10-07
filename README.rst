.. image:: https://github.com/collective/collective.xsendfile/actions/workflows/tests.yml/badge.svg?branch=master
    :target: https://github.com/collective/collective.xsendfile/actions/workflows/tests.yml

.. This README is meant for consumption by humans and PyPI. PyPI can render rst files so please do not use Sphinx features.
   This text does not appear on PyPI or GitHub. It is a comment.

.. contents::

==============================================================================
collective.xsendfile
==============================================================================

Introduction
==============

Offload ZODB blob downloads to the front-end web server using the X-Sendfile / X-Accel-Redirect headers.

X-Sendfile (Apache, Lighttpd) and X-Accel-Redirect (nginx) let a backend application tell the front-end web server to send a file from disk, instead of sending the file content itself.

``collective.xsendfile`` adds this to Plone:

- Plone still handles the request as normal: traversal, permission checks, response headers.

- Instead of streaming the file content through the proxy connection, Plone sends a response with a header holding the blob's file path. The front-end web server reads the file from disk and sends it to the user.

.. note ::

        Zope already streams blobs efficiently.
        This add-on goes further: the file data never passes through Zope or the proxy connection.
        The benefit depends on your use case, so you may want to run some benchmarks.

Requirements
============

- The front-end web server must be able to read the ZODB blob files, so it needs access to the blob directory on the same filesystem (or a shared mount), with permissions that let its user read the files.

- Blobs must be committed. An image scale generated on the fly for the current request is streamed by Plone as usual; later requests for it are offloaded.

Compatibility
=============

Version 2.x supports Plone 6.0, 6.1 and 6.2 on Python 3.10 or later.
For older Plone and Python versions, use version 1.4 (git tag ``1.4``) from GitHub.

Supported front-end web servers
=================================

* Apache, with mod_xsendfile (``X-Sendfile`` header)

* nginx (``X-Accel-Redirect`` header)

* Lighttpd (``X-Sendfile`` header)

Supported download urls
=======================

* ``.../@@download/fieldname/filename``

* ``.../@@display-file/fieldname/filename``

* ``.../context/form/++widget++widgetname/@@download/filename``

* ``.../@@images/fieldname`` and image scales, e.g. ``.../@@images/image/preview``

Other urls will use the normal Zope download mechanism.

Installation
==============

Adding collective.xsendfile to your project
-------------------------------------------

Install it with pip::

        pip install collective.xsendfile

or, if you use buildout, include it in the buildout.cfg::

        eggs =
             collective.xsendfile

Its ZCML is loaded automatically through ``plone.autoinclude``.

Configuration
-------------

There are two ways to configure collective.xsendfile, either site by site, or globally per Zope instance.

Per site
~~~~~~~~

* Install the add-on in your site(s) through the Plone add-on control panel

* Enable XSendFile on your front-end web server and virtual host configuration (see below)

* In the XSendFile Plone control panel, set the HTTP response header for your server and, if needed, the path rewriting

Per Zope instance
~~~~~~~~~~~~~~~~~

collective.xsendfile can also be configured globally for all Plone sites in a Zope instance using environment variables.
When ``XSENDFILE_RESPONSEHEADER`` is set, the per-site settings are ignored, and there is no need to install the add-on in your sites.

``XSENDFILE_RESPONSEHEADER``
     Activates global configuration.
     Either ``X-Sendfile`` (Apache, Lighttpd) or ``X-Accel-Redirect`` (nginx).

``XSENDFILE_ENABLE_FALLBACK``
     ``true`` (the default) or ``yes`` means the file is served by Zope as usual when the request has no ``X-Forwarded-For`` header, i.e. when it did not come through the front-end proxy.
     Any other value always uses the header.

``XSENDFILE_PATHREGEX_SEARCH``
     Regular expression applied to the blob's absolute file path.
     Defaults to ``(.*)``.

``XSENDFILE_PATHREGEX_SUBSTITUTE``
     Replacement for the matched path (Python ``re.sub`` syntax).
     Defaults to ``\1``.
     For nginx this has to produce a URL under an ``internal`` location, for example ``/xsendfile/\1``.

The per-site control panel has the same four settings.

Disabling for a request
-----------------------

Code that needs Zope to serve a file itself can disable xsendfile for the current request::

        from collective.xsendfile.utils import disable_xsendfile

        disable_xsendfile(request)

XSendFile installation for Apache on Debian/Ubuntu
====================================================

Install and enable the Apache module::

        sudo apt-get install libapache2-mod-xsendfile
        sudo a2enmod xsendfile
        sudo systemctl reload apache2

Related virtual host configuration. Limit ``XSendFilePath`` to the blob directory, so the header cannot be used to send any other file::

        <VirtualHost *:80>

            ServerName example.com

            XSendFile on
            XSendFilePath /path/to/var/blobstorage

            RewriteEngine On
            RewriteRule (.*) http://127.0.0.1:8080/VirtualHostBase/http/example.com:80/VirtualHostRoot/$1 [L,P]

        </VirtualHost>

Use the ``X-Sendfile`` header and leave the path settings at their defaults.

XSendFile installation on nginx
=================================

nginx needs an ``internal`` location that maps a URL prefix to the blob directory.
``internal`` is essential: it stops browsers from requesting that location directly::

        server {
            listen 80;
            server_name example.com;

            location / {
                proxy_pass http://127.0.0.1:8080/VirtualHostBase/http/$host:80/VirtualHostRoot/;
                proxy_set_header Host            $host;
                proxy_set_header X-Real-IP       $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            }

            location /xsendfile/ {
                internal;
                alias /path/to/var/blobstorage/;
            }
        }

Then use the ``X-Accel-Redirect`` header and rewrite the blob path into that location:

- path regex search: ``^/path/to/var/blobstorage/(.*)``
- path regex substitution: ``/xsendfile/\1``

More info
==========

* https://github.com/collective/collective.xsendfile

* https://nginx.org/en/docs/http/ngx_http_core_module.html#internal

* https://kovyrin.net/2006/11/01/nginx-x-accel-redirect-php-rails/

* https://github.com/nmaier/mod_xsendfile

* https://blog.jazkarta.com/2010/09/21/handling-large-files-in-plone-with-ore-bigfile/

Troubleshooting
===============

If you get an HTTP response like::

        OK

        The requested URL /site-images/xxx/cairo.jpg was not found on this server.

it is probably a file permission issue: the web server user cannot read the blob file.
Also check that the path in the response header, after rewriting, matches your web server configuration.

Authors
=======

- Peter Holzer (`@agitator <https://github.com/agitator>`__)
- Georg Gogo. BERNHARD (`@gogobd <https://github.com/gogobd>`__)
- Mikko Ohtamaa (`@miohtama <https://github.com/miohtama>`__)
- Jens W. Klein (`@jensens <https://github.com/jensens>`__)
- Dylan Jay (`@djay <https://github.com/djay>`__)
- Jon Pentland (`@instification <https://github.com/instification>`__)

Special thanks to Kapil Thangavelu, we extensively borrowed from his code ;-)

License
=======

GNU General Public License, version 2 or later (``GPL-2.0-or-later``). See ``LICENSE``.
