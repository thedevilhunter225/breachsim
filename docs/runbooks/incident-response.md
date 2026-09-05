# Incident response

1. Declare severity and preserve Application Insights, Service Bus, Front Door, identity and
   hash-chained audit evidence.
2. Contain within tenant scope: pause active runs, revoke the affected provider/SCIM/SSO
   connection, suspend the organization if boundary confidence is lost, and block compromised
   landing hostnames at Front Door.
3. Rotate exposed Key Vault material and revoke application sessions. Unknown provider
   submissions remain unknown until reconciled; do not resend automatically.
4. Determine affected tenants, recipients, data classes and timestamps without expanding
   named reporting access. Notify customer security contacts under the agreed policy.
5. Recover from reviewed images/configuration, verify audit-chain continuity, queue state,
   suppression state and public-token hostname binding.
6. Record timeline, cause, control failures, customer communications and corrective actions.

Never include passwords, MFA codes, Together/Google/Microsoft tokens or decrypted employee
data in tickets or logs.
