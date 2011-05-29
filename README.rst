.. contents ::

Introduction
==============

XSendFile is an enhancement over HTTP front end proxy protocol
which allows offloading of file downloads to the front end web server
(Apache / Nginx).

``collective.xsendfile`` package adds XSendFile support for Plone.

* Plone handles HTTP request publishing, permission checks, etc. 
  still normally

* But instead of sending the file content itself and encoding it in 
  the Plone process (slow) Plone sends HTTP response with
  special header telling the front end web server to send the file for the user

XSendFile support is available as ``collective.xsendfile`` add-on for Plone.

Enabling collective.xsendfile in buildout
====================================================

These instructions are for Github (trunk) version.

        cd src
        git clone git://github.com/collective/collective.xsendfile.git
        

XSendFile installation for Apache on Debian/Ubuntu
====================================================

Add the apt source to ``/etc/apt/sources.list``::

        deb http://ppa.launchpad.net/damokles/ubuntu hardy main
        deb-src http://ppa.launchpad.net/damokles/ubuntu hardy main

To enable new software repository run::
        
        sudo apt-get update       

Install Apache module::

        sudo apt-get install libapache2-mod-xsendfile
        
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

* `Apache XSendFile installation instructions (Debian/Ubuntu) <http://www.qc4blog.com/?p=547>`_

* http://celebnamer.celebworld.ws/stuff/mod_xsendfile/  
  
Authors
==========

Georg Gogo. BERNHARD
gogo@bluedynamics.com

Mikko Ohtamaa
mikko@mfabrik.com 
