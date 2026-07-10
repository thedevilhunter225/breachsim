# Threat Model Summary

## Unauthorized admin actions

- Threat: a user without launch permissions changes policy or launches a campaign.
- Mitigations: RBAC checks on every protected route, approval workflow, audit logging, read-only auditor role, future support for step-up auth.

## Leaked tokens

- Threat: tracking or session tokens are replayed.
- Mitigations: signed JWT access tokens with short expiry, distinct landing tokens, token rotation, token hashing in logs where practical, HTTPS/TLS assumption.

## Stored data exposure

- Threat: database snapshot exposes employee phones or approved context.
- Mitigations: field-level encryption for sensitive columns, encryption at rest assumption for storage volumes, data minimization, retention and purge workflows.

## Malicious scenario content

- Threat: generated content violates ethics or policy.
- Mitigations: constrained theme/channel policy engine, prohibited topic validation, explicit no-credential-capture rule, admin approval before launch, sandbox-only adapters by default.

## Analytics tampering

- Threat: forged events skew risk scores or reports.
- Mitigations: signed landing tokens, normalized event ingestion, server-side scoring, pseudonymous event IDs, append-only audit trail of exports and launches.

## Tenant isolation issues

- Threat: one organization's user reads another organization's data.
- Mitigations: organization scoping in repository layer, tenant-scoped foreign keys, seeded demo organization only for local MVP, tests for access boundaries.

## Abuse of delivery adapters

- Threat: the platform is used for real-world abuse.
- Mitigations: sandbox mode by default, provider integrations disabled unless explicitly configured, approved training domains only, clear UI labels, no live vishing implementation.
