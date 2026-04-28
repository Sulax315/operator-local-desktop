# Bratek Zero Trust App Deployment Protocol

This protocol standardizes internal app publication behind Cloudflare Zero Trust.

## Architecture

`App (127.0.0.1:PORT) -> nginx vhost (80/443) -> cloudflared tunnel -> Cloudflare edge -> Cloudflare Access -> browser`

## Nginx Standard

- `server_name` must equal target hostname.
- Port `80` redirects to `https://$host$request_uri`.
- Port `443` terminates TLS and proxies to `http://127.0.0.1:PORT`.
- Proxy headers must include host, forwarding chain, and scheme.

## Certificate Handling

- Prefer hostname-specific certs at `/etc/letsencrypt/live/<hostname>/`.
- Bootstrap mode may temporarily reuse known-good cert files only to unblock scaffolding.
- Real certificate issuance remains mandatory:

```bash
certbot --nginx -d <hostname>
```

## Cloudflare Requirements (Manual)

1. Tunnel route:
   - `<hostname> -> https://127.0.0.1:443`
   - `originServerName -> <hostname>`
2. DNS:
   - CNAME/Tunnel record target `controltower`, proxied on.
3. Access:
   - Self-hosted app for `<hostname>`.
   - Attach existing allow policy.

## Safety Rules

- Do not modify cloudflared config automatically.
- Do not mutate Cloudflare remotely from local scaffolding tools.
- Do not issue certificates automatically.
- Do not reload nginx automatically during scaffold generation.

## Operator Validation Checklist

1. `nginx -t`
2. `systemctl reload nginx`
3. `curl -kI -H "Host: <hostname>" https://127.0.0.1`
4. `certbot --nginx -d <hostname>`
5. Validate Cloudflare tunnel, DNS, and Access policy wiring.
