# Developer Guide

## Backend

- FastAPI serves the REST API from `backend/app/main.py`.
- SQLAlchemy models live in `backend/app/models/entities.py`.
- Core services are split by concern under `backend/app/services/`.
- `init_db()` creates tables and seeds demo data automatically for local MVP usage.

## Frontend

- Next.js App Router lives under `frontend/app/`.
- `frontend/lib/api.ts` fetches backend data and falls back to demo content if the API is unavailable.
- Shared visual primitives are in `frontend/components/`.

## Local workflow

1. Start backend: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
2. Start frontend: `node node_modules/next/dist/bin/next dev --hostname 0.0.0.0 --port 3000`
3. Run backend tests: `python3 -m pytest -s tests`
4. Build frontend: `node node_modules/next/dist/bin/next build`

## Seeded users

- Admin: `admin@breachsim-lab.com` / `Admin123!`
- Second admin reviewer: `reviewer@breachsim-lab.com` / `Reviewer123!`
- Campaign manager: `manager@breachsim-lab.com` / `Manager123!`
- Auditor: `auditor@breachsim-lab.com` / `Auditor123!`
