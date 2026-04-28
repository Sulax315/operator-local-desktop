# Access Hardening Runbook

Date: 2026-04-14 (UTC)  
Scope: `metabase.bratek.io`, `controltower.bratek.io`

## Current-state summary

- Cloudflare edge is active for both hostnames (Cloudflare anycast DNS answers and `server: cloudflare` responses).
- `nginx` serves public `80/443` and reverse-proxies both apps to loopback-only upstreams.
- `cloudflared` is running and has ingress routes for both hostnames.
- Public cert chain validates for both hostnames.
- Nginx is publicly bound on `80/443`; host-local public-IP tests resolve to target vhosts with matching `Host` headers.

## What is already correct

- App upstream ports for metabase/controltower are loopback-bound.
- Target hostnames have valid HTTPS cert chain from public perspective.
- Nginx server blocks are scoped by `server_name` for both domains.
- Cloudflare Tunnel ingress entries exist and validate.

## What was wrong

- `metabase.bratek.io` tunnel origin used `noTLSVerify: true`, disabling certificate verification between cloudflared and origin.
- Nginx global TLS protocol list included legacy `TLSv1` and `TLSv1.1`.

## What was changed

1) `/etc/cloudflared/config.yml`

- Changed metabase ingress origin request from:
  - `noTLSVerify: true`
- To:
  - `originServerName: metabase.bratek.io`

Purpose: keep TLS enabled while restoring hostname validation against origin certificate.

Backup created:

- `/etc/cloudflared/config.yml.bak.20260414T172924Z`

2) `/etc/nginx/nginx.conf`

- Changed:
  - `ssl_protocols TLSv1 TLSv1.1 TLSv1.2 TLSv1.3;`
- To:
  - `ssl_protocols TLSv1.2 TLSv1.3;`

Purpose: remove legacy protocol support and align with modern enterprise TLS hygiene.

Backup created:

- `/etc/nginx/nginx.conf.bak.20260414T174604Z`

## Validation commands (exact)

Run in order:

```bash
cloudflared --config /etc/cloudflared/config.yml tunnel ingress validate
nginx -t
systemctl reload nginx
systemctl restart cloudflared
systemctl status nginx --no-pager
systemctl status cloudflared --no-pager
ss -tulpn
curl -I http://127.0.0.1:8787
curl -I http://127.0.0.1:8082
curl -I -H "Host: metabase.bratek.io" http://127.0.0.1
curl -I -H "Host: controltower.bratek.io" http://127.0.0.1
curl -vkI https://metabase.bratek.io
curl -vkI https://controltower.bratek.io
openssl s_client -connect metabase.bratek.io:443 -servername metabase.bratek.io </dev/null
openssl s_client -connect controltower.bratek.io:443 -servername controltower.bratek.io </dev/null
```

Host-local origin behavior check:

```bash
PUBIP=$(ip -4 route get 1.1.1.1 | awk '/src/ {for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')
curl -I -H "Host: metabase.bratek.io" "http://$PUBIP"
curl -I -k -H "Host: metabase.bratek.io" "https://$PUBIP"
curl -I -H "Host: controltower.bratek.io" "http://$PUBIP"
curl -I -k -H "Host: controltower.bratek.io" "https://$PUBIP"
```

## What still must be verified manually in Cloudflare dashboard

1) DNS proxy state (orange-cloud) for both records

- `metabase.bratek.io`: Proxied = ON
- `controltower.bratek.io`: Proxied = ON

2) Tunnel route target consistency

- Ensure the DNS records for these hostnames point to the intended tunnel route (not stale origin A records).
- Confirm the tunnel in Zero Trust shows healthy connectors and includes both hostnames in public hostnames/ingress mappings.

3) SSL/TLS mode

- SSL/TLS encryption mode should be `Full (strict)` for the zone.

4) Optional origin lock-down (strongly recommended if no direct-origin requirement)

- Restrict inbound `80/443` at host/network firewall to Cloudflare IP ranges only, while keeping SSH/admin access explicit.
- After this change, verify from an external network (not from the VM itself) that direct-origin access is blocked.

## Rollback notes

Rollback cloudflared change:

```bash
cp /etc/cloudflared/config.yml.bak.20260414T172924Z /etc/cloudflared/config.yml
systemctl restart cloudflared
```

Rollback nginx TLS protocol change:

```bash
cp /etc/nginx/nginx.conf.bak.20260414T174604Z /etc/nginx/nginx.conf
nginx -t && systemctl reload nginx
```
