# Host nginx — split UI and API (same origin)

## Source

`c:\Dev\action-desk\infra\nginx\actiondesk.conf` → copied as `example-split-ui-api-same-origin.conf`.

## Why extracted

Single-file pattern for **host-level nginx** terminating TLS and sending:

- `/` and `/_next/` → frontend upstream
- `/api/` → backend upstream

Loopback upstreams match a common **Docker publish 127.0.0.1** VM layout.

## Reuse

Rename `server_name`, certificate paths, and upstream ports. Drop product-specific comments if desired.

## Confidence

**High** as a structural template. **Low** if reused without replacing domain names and cert paths from the prototype.
