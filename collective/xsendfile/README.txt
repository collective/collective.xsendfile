collective.xsendfile Package Readme
=========================

Here's a nginx.conf, take a closer look at the server locations, that's where the magic happens.

8<--------schnipp--------

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

Okay, and here's a small apache2.conf that does the trick, apache on port :8082, the backend plone is 8080:

8<--------schnipp--------
Listen 8082

LoadModule xsendfile_module   modules/mod_xsendfile.so

<VirtualHost *:8082>

    ServerName test

    XSendFile on
    XSendFilePath /

    RewriteEngine On
    RewriteRule (.*) http://127.0.0.1:8080/VirtualHostBase/http/test:8082/VirtualHostRoot/$1 [L,P]

</VirtualHost>
--------schnapp-------->8

Georg Gogo. BERNHARD
gogo@bluedynamics.com

