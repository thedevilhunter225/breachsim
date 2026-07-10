# Privacy Model

BreachSim is intentionally designed around limited, approved, and explainable data use.

Principles:

- Use only company-supplied or explicitly approved employee context.
- Respect consent state, opt-outs, and redaction requests.
- Record awareness interactions only on platform-owned training assets.
- Never store real credentials entered on training pages.
- Prefer pseudonymous event IDs for analytics.

Controls:

- TLS assumed for transport.
- Field-level encryption for sensitive employee data such as phone and approved context notes.
- Encryption at rest assumed for database storage volumes.
- Retention settings are tenant-configurable and support future purge workflows.
