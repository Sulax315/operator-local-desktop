# Access Hardening Findings

Date: 2026-04-14 (UTC)  
Scope: `metabase.bratek.io`, `controltower.bratek.io`

## 1) Infrastructure discovery snapshot

- Services:
  - `nginx.service`: active/running
  - `cloudflared.service`: active/running
- Relevant config paths discovered:
  - `/etc/nginx/nginx.conf`
  - `/etc/nginx/sites-available/operator-stack`
  - `/etc/nginx/sites-available/controltower.bratek.io`
  - `/etc/cloudflared/config.yml`
  - `/etc/letsencrypt/live/{metabase.bratek.io,controltower.bratek.io}/`
- Enabled nginx site symlinks include both:
  - `/etc/nginx/sites-enabled/operator-stack` (metabase)
  - `/etc/nginx/sites-enabled/controltower.bratek.io`

## 2) Listener and exposure model

Observed from `ss -tulpn`:

- Public listeners:
  - `0.0.0.0:80` and `[::]:80` via `nginx`
  - `0.0.0.0:443` and `[::]:443` via `nginx`
  - `0.0.0.0:22` / `[::]:22` via `sshd`
- Internal-only listeners:
  - `127.0.0.1:8787` (control tower app)
  - `127.0.0.1:8082` (metabase upstream)
  - `127.0.0.1:20241` (cloudflared metrics)
  - additional app ports are loopback-bound via docker-proxy

UFW status:

- Active
- Explicit allow shown for `22/tcp`
- `iptables -S` policy is `INPUT DROP`, with explicit user allow observed for `22/tcp`

## 3) DNS / public edge / tunnel model

For both hostnames:

- `dig +short` returns Cloudflare anycast IPs (`172.67.142.77`, `104.21.49.61`, plus Cloudflare IPv6)
- `curl -vkI https://<hostname>` responses include `server: cloudflare`

This confirms Cloudflare is in front of both public hostnames.

Cloudflared ingress (`/etc/cloudflared/config.yml`) currently maps:

- `controltower.bratek.io` -> `http://127.0.0.1:8787`
- `metabase.bratek.io` -> `https://127.0.0.1:443` with explicit origin request settings

Validated with:

- `cloudflared --config /etc/cloudflared/config.yml tunnel ingress validate` -> `OK`
- `cloudflared --config /etc/cloudflared/config.yml tunnel ingress rule https://metabase.bratek.io` -> matched metabase ingress rule
- `cloudflared --config /etc/cloudflared/config.yml tunnel ingress rule https://controltower.bratek.io` -> matched controltower ingress rule

## 4) Nginx mapping and TLS references

`metabase.bratek.io` (`/etc/nginx/sites-available/operator-stack`):

- HTTP server block redirects to HTTPS
- HTTPS server block proxies `/` to `http://127.0.0.1:8082`
- Cert refs: `/etc/letsencrypt/live/metabase.bratek.io/fullchain.pem` and `privkey.pem`

`controltower.bratek.io` (`/etc/nginx/sites-available/controltower.bratek.io`):

- HTTP server block redirects to HTTPS
- HTTPS server block proxies `/` to `http://127.0.0.1:8787`
- Cert refs: `/etc/letsencrypt/live/controltower.bratek.io/fullchain.pem` and `privkey.pem`
- Security headers present: `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `HSTS`

Global nginx TLS protocol setting (before hardening change):

- `ssl_protocols TLSv1 TLSv1.1 TLSv1.2 TLSv1.3;`

## 5) Direct origin exposure checks

Public origin IP identified as: `161.35.177.158`

Direct-origin tests against VM public IP:

- `curl -I -H "Host: metabase.bratek.io" http://161.35.177.158` -> `301` to HTTPS
- `curl -I -k -H "Host: metabase.bratek.io" https://161.35.177.158` -> `200` (metabase response)
- `curl -I -H "Host: controltower.bratek.io" http://161.35.177.158` -> `301` to HTTPS
- `curl -I -k -H "Host: controltower.bratek.io" https://161.35.177.158` -> `303` login redirect

Conclusion:

- Both apps are Cloudflare-fronted publicly.
- Nginx is configured to serve both hostnames on public listeners (`0.0.0.0:80/443`).
- Host-local tests against the VM public IP succeeded with matching `Host` headers.
- External direct-origin reachability is not proven from this host-only vantage because firewall policy is `INPUT DROP`; this must be externally verified from a network outside the VM.

## 6) Certificate-chain checks (public)

For both hostnames:

- `openssl s_client -connect <hostname>:443 -servername <hostname>` verifies full chain (`Verify return code: 0 (ok)`)
- Edge certificate presented has subject `CN=bratek.io`, issuer `Let's Encrypt E7`, valid chain to ISRG Root X1

## 7) Findings summary

- Good:
  - Cloudflare edge is active for both target hostnames.
  - Cloudflare Tunnel is active with ingress rules for both hostnames.
  - Upstream app ports are loopback-bound (not directly internet-exposed).
  - Public TLS chain is valid for both hostnames.
- Risk / hardening opportunities:
  - Nginx is publicly bound on `80/443`; enforce/verify network-layer allowlisting so only intended ingress paths can reach origin.
  - Metabase cloudflared ingress had disabled TLS verification to origin before remediation.
  - Nginx global TLS protocols included legacy `TLSv1/TLSv1.1` before remediation.
