# API Overview

Authentication uses a bearer JWT returned by `POST /api/v1/auth/login`. Protected routes enforce RBAC at the dependency layer.

Primary route groups:

- `auth`: login, current user, logout
- `orgs` and `departments`: tenant metadata and department directory
- `employees`: directory CRUD, profile updates, approved-context profiles, CSV-style imports
- `policies`: organization guardrails and policy versioning
- `scenarios`: policy-constrained generation, versioned edits, approval and rejection
- `campaigns`: creation, approval request, launch, pause, delivery log access
- `public`: safe landing token lookups and event tracking
- `training`: module listing, assignment listing, completion
- `analytics`: dashboard KPIs, risk distribution, department insights
- `audit`: append-only audit logs, access logs, report exports
- `employee-portal`: self-view, history, opt-out, redaction request
