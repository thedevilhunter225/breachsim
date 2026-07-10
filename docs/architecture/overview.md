# BreachSim Architecture Overview

BreachSim follows a clean service-oriented monolith design for the MVP. The FastAPI backend exposes a versioned REST API and contains domain services for policy enforcement, scenario generation, sandbox delivery, event ingestion, risk analytics, micro-training assignment, and governance controls. Background jobs are queued through Redis and processed by an RQ worker for delivery simulation, report export, and deferred retest scheduling. PostgreSQL is the source of truth for transactional and analytical tables. The Next.js frontend consumes the REST API through a thin typed client layer and renders admin, analyst, manager, and employee experiences.

Key design choices:

- Multi-tenant but single-organization demo seed to keep the FYP demo simple.
- AI generation is mediated by a strict policy validation layer; invalid content is blocked or regenerated.
- All delivery adapters are sandbox-first and provider integrations remain disabled by default.
- Sensitive employee context is encrypted at the field level, while event analytics prefer pseudonymous identifiers.
- Auditability is first-class: approval flow, policy changes, data access, and export actions are append-only logged.
