# Deployment Notes

## Local Docker stack

- `docker-compose.yml` starts PostgreSQL, Redis, the FastAPI API, the RQ worker, and the Next.js frontend.
- Backend defaults to SQLite for bare local runs, but Docker uses PostgreSQL.

## Environment

- Copy `.env.example` to `.env` and adjust secrets before any non-demo use.
- Replace `SECRET_KEY` and `ENCRYPTION_KEY` outside the lab environment.
- Keep lab-only provider integrations disabled unless explicitly testing in a controlled environment.

## Production hardening follow-ups

- Move secrets to a dedicated secret manager.
- Terminate TLS at an ingress or reverse proxy.
- Add object storage for report exports.
- Add real background scheduling and retry policies.
- Add database encryption and backup policies aligned with organization rules.
