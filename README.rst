.. contents::

.. image:: https://secure.travis-ci.org/collective/collective.xsendfile.png
    :target: http://travis-ci.org/collective/collective.xsendfile

Introduction
==============

XSendFile is an enhancement over HTTP front end proxy protocol
which allows offloading of file uploads and downloads to the front end web server.

``collective.xsendfile`` package adds XSendFile support for Plone.

* Plone handles HTTP request publishing, permission checks, etc. 
  still normally

* But instead of sending the file content over proxy connection Plone sends HTTP response with
  special header telling the front end web server to read the file from the disk and 
  send the file for the user

.. note ::

        Blob handling in ZODB is very effective already (async sockets, just like Apache or nginx would do ). 
        Right after the headers are written to the response, the file gets handed over to the medusa async loop and the Zope thread is freed.
        This add-on only removes the need to proxy the file data over socket connection.
        The overhead of this may depend on the use case, so you might want to run some
        benchmarks before conclusion.

XSendFile support is available as ``collective.xsendfile`` add-on for Plone.

.. warning ::

        This work is still unfinished as ZODB lacks one crucial feature.
        
* http://stackoverflow.com/questions/6168566/collective-xsendfile-zodb-blobs-and-unix-file-permissions        

Supported front-end web servers
=================================

* Apache

* Nginx

* Lighttpd

Plone Compatibility
===================

Currently the following download urls are supported (Plone 4.0-4.3)

* .../@@download/fieldname/filename

* .../context/form/++widget++widgetname/@@download/filename

* .../@@display-file/fieldname/filename

* .../at_download

* .../@images/image/index_html

* direct url to ATFile and ATImage objects

* direct url to plone.app.contenttypes File and Image objects

Other urls will use the normal zope download mechanism.

Currently image scales aren't handled as xsendfile even though they are stored as blobs.

Installation
==============

There are two ways to configure collective.xsendfile, either site by site, or globally per zope instance

Per Site:
~~~~~~~~~

* Put collective.xsendfile to your buildout

* Install the add-on to your site(s) through Plone add-on control panel

* Enable XSendFile module on your front-end web server
  and virtual host configuration
  
* In XSendFile Plone control panel, set HTTP header according to your server (Apache/Nginx)

Per Zope Instance:
~~~~~~~~~~~~~~~~~~

It is also possible to setup collective.xsendfile globablly for all your plone
sites in a plone instance by using environment variables. Note configuration this way
will disable the ability to configure per site. There is no need to activate the plugin
in your Plone instance for this to work.

* Put collective.xsendfile to your buildout

* configure you zope instance (probably via buildout) to include set the following environment variables

XSENDFILE_RESPONSEHEADER will activate global configuration. Likely values are either
  "X-Sendfile" (apache) or "X-Accel-Redirect" (nginx)


XSENDFILE_ENABLE_FALLBACK True means if HTTP_X_FORWARDED_FOR isn't found in the request
  prevent xsendfile processing from occuring

XSENDFILE_PATHREGEX_SEARCH If you need modify the full path of a blob you can extract parts
  of it here. Defaults to "(.*)"

XSENDFILE_PATHREGEX_SUBSTITUTE If you need to modify the full path of a blob you can
  use this replace parts of the path here. Defaults to "\1". If you are using
  nginx is will likely be something like "/xsendfile\1"


Enabling collective.xsendfile in buildout
====================================================

These instructions are for Github (trunk) version.

        cd src
        git clone git://github.com/collective/collective.xsendfile.git
        
Then include it in the buildout.cfg::

        eggs =
             collective.xsenfile
                
        develop =
             src/collective.xsendfile        

Plone 4.0 and older installation additions
----------------------------------------------
             
collective.xsendfile uses plone.app.registry.             
You also might need to set up proper ``extends = `` like
for Dexterity version pindowns, so that you don't
get version conflicts during running buildout.

* http://plone.org/products/dexterity/documentation/how-to/install
              
        
XSendFile installation for Apache on Debian/Ubuntu
====================================================

Install Apache module (Debian/Ubuntu)::

        # alternatively -thread-dev, depends on your apache configuration
        sudo apt-get install apt-get install apache2-prefork-dev         
        wget --no-check-certificate https://tn123.org/mod_xsendfile/mod_xsendfile.c 
        sudo apxs2 -cia mod_xsendfile.c
        
                
Enable Apache module::

        sudo a2enmod xsendfile
 
Restart Apache::

        /etc/init.d/apache2 force-reload

Related virtual host configuration file::

        Listen 8082
        
        LoadModule xsendfile_module   modules/mod_xsendfile.so
        
        <VirtualHost *:8082>
        
            ServerName test
        
            XSendFile on
            XSendFilePath /
        
            RewriteEngine On
            RewriteRule (.*) http://127.0.0.1:8080/VirtualHostBase/http/test:8082/VirtualHostRoot/$1 [L,P]
        
        </VirtualHost>
        
XSendFile installation on Nginx
=================================

Here's a nginx.conf, take a closer look at the server locations, that's where the magic happens.

nginx.conf::

        worker_processes  4;
        
        events {
            worker_connections  1024;
        }
        
        http {
        
            include /Users/bernhard/Documents/Work/tmp/XSendFile/agitator-simple-nginx/etc/mime.types;
            default_type application/octet-stream;    
        
            sendfile on;  # This enables the X-Accel-Redirect feature
        
            # For more info about content zipping see http://wiki.nginx.org/HttpGzipModule
            gzip on;
            gzip_proxied any;
            gzip_min_length 1024;
            gzip_types text/plain text/html application/x-javascript text/css text/xml application/pdf application/octet-stream;
        
            server {
        
                listen *:8081 default;
                
                access_log /Users/bernhard/Documents/Work/tmp/XSendFile/agitator-simple-nginx/log/access.log;
                error_log /Users/bernhard/Documents/Work/tmp/XSendFile/agitator-simple-nginx/log/error.log;
        
                # Add some headers to transmit more info about the client. Yes, that is kind.
                location / {
                        proxy_pass http://127.0.0.1:8080/VirtualHostBase/http/$host:9000/VirtualHostRoot/$request_uri;
                        proxy_set_header   Host             $host;
                        proxy_set_header   X-Real-IP        $remote_addr;
                        proxy_set_header   X-Forwarded-Host $server_name;
                        proxy_set_header   X-Forwarded-For  $proxy_add_x_forwarded_for;
                }
                
                # This location definition has to match the prefix in utils.py tp make it work
                # "internal" is a must for security - it prevents direct access from browsers
                #   - http://wiki.nginx.org/HttpCoreModule#internal
                # "alias" points to your blob storage root; Regex is supported
                #   - http://wiki.nginx.org/HttpCoreModule#alias
                location /xsendfile/ {
                        internal;
                        alias /;
                }
                
            }
            
        }

 
More info
==========

* https://github.com/collective/collective.xsendfile/tree/master/collective/xsendfile

* http://blog.jazkarta.com/2010/09/21/handling-large-files-in-plone-with-ore-bigfile/

* http://svn.objectrealms.net/view/public/browser/ore.bigfile/trunk/ore/bigfile/readme.txt?rev=2353

* `Apache XSendFile installation instructions (Debian/Ubuntu) <http://www.qc4blog.com/?p=547>`_

* http://kovyrin.net/2006/11/01/nginx-x-accel-redirect-php-rails/

* https://tn123.org/mod_xsendfile/

Troubleshooting
==================

If you get HTTP response like::

        OK
        
        The requested URL /site-images/xxx/cairo.jpg was not found on this server.

It means a file permission issue? - XXX

Authors
==========

Peter Holzer
peter@agitator.com

Georg Gogo. BERNHARD
gogo@bluedynamics.com

Mikko Ohtamaa
mikko@mfabrik.com 

Jens W. Klein
jens@bluedynamics.com

Dylan Jay
software@pretaweb.com

Special thanks to Kapil Thangavelu, we extensively borrowed from his code ;-)

