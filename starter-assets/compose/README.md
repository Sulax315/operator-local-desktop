# Compose — loopback app stack

## Source

`c:\Dev\action-desk\infra\compose\docker-compose.yml` → `example-app-frontend-backend-postgres.loopback.yml`.

## Why extracted

Shows **Postgres internal-only**, **API and UI published on 127.0.0.1** for a host nginx front, with **healthchecks** and **depends_on** conditions.

## Reuse

Replace service names, image build contexts, and ports. Add your own Dockerfiles or image references.

## Confidence

**High** for topology. **Not runnable** without the original application `Dockerfile`s and env files from the archived Action Desk tree (or your replacements).
