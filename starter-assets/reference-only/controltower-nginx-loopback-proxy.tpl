server {
    listen 80;
    listen [::]:80;
    server_name __DOMAIN__;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name __DOMAIN__;

    ssl_certificate __TLS_CERTIFICATE__;
    ssl_certificate_key __TLS_CERTIFICATE_KEY__;
    include __TLS_OPTIONS_INCLUDE__;
    ssl_dhparam __TLS_DHPARAM__;

    access_log /var/log/nginx/__DOMAIN__.access.log;
    error_log /var/log/nginx/__DOMAIN__.error.log;
    client_max_body_size 25m;

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;

    location / {
        proxy_pass http://127.0.0.1:__PORT__;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        proxy_redirect off;
        proxy_connect_timeout 5s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
