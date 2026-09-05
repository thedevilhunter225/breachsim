# Key rotation, retention and offboarding

Rotate Together, Graph, Google, OIDC, reconciliation and SCIM secrets through new Key Vault
versions. Health-test the new version before revoking the old one; session/encryption-key
rotation requires a migration plan because existing encrypted fields must remain decryptable.

Retention jobs must apply the tenant policy to employee PII, delivery details, tokens and
generated media. Audit/evidence objects use immutable Blob retention and must follow the
contractual/legal schedule. Keep reporting pseudonymous unless a current
`risk_identity_viewer` needs named data.

For offboarding: suspend the organization; pause/cancel runs; revoke provider, SSO and SCIM
connections; revoke public tokens; remove custom Front Door domains only after all active
tokens expire or aliases are migrated; export authorized evidence; delete customer PII after
the retention/legal-hold check; then record completion in the platform audit log.
