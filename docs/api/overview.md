# API Overview

Browser authentication uses a `Secure`, `HttpOnly`, `SameSite=Strict` session cookie plus a
double-submit CSRF token. The bearer value is not returned to or retained by the browser.
Non-browser API clients may explicitly request a short-lived bearer response by sending
`X-BreachSim-API-Client: bearer` to login/refresh. Every credential maps to a revocable
database session, and protected routes enforce RBAC at the dependency layer.

Primary route groups:

- `auth`: login, current user, logout
- `users`: admin-only operator creation, roles, activation and password rotation
- `orgs` and `departments`: tenant metadata and department directory
- `employees`: directory CRUD, profile updates, approved-context profiles, CSV-style imports
- `policies`: organization guardrails and policy versioning
- `scenarios`: policy-constrained generation, versioned edits, approval and rejection
- `campaigns`: creation, approval request, launch, pause, delivery log access
- `public`: safe landing token lookups and event tracking
- `training`: module listing, assignment listing, completion
- `analytics`: dashboard KPIs, risk distribution, department insights
- `audit`: append-only audit logs, access logs, report exports
- `integrations` and `media`: governed provider configuration and consent-gated media assets
- `employee-portal`: self-view, history, opt-out, redaction request
