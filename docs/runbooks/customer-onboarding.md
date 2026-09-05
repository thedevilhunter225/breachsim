# Customer onboarding

1. Platform operations provisions the organization, sends the one-time admin invitation and
   confirms MFA/SSO ownership.
2. Customer publishes recipient, sender and landing-domain TXT records. Platform subdomains
   are available by default; custom landing domains also require Front Door managed TLS and
   CNAME activation by platform operations.
3. Configure branding, privacy notice, legal footer and approved templates.
4. Connect one dedicated sender mailbox:
   - Microsoft: tenant admin consent, application `Mail.Send`, then Exchange Application RBAC
     scoped to only that mailbox.
   - Google: domain-wide delegated service account restricted to `gmail.send`, with the
     delegated subject equal to the sender mailbox.
5. Verify provider health and sender SPF, DKIM and DMARC readiness. These checks do not
   guarantee inbox placement.
6. Configure tenant-specific Entra/Google OIDC and SCIM; rotate the displayed-once SCIM token
   into the customer's directory secret store.
7. Import a pilot group, add any organization exclusions in **Launch setup**, verify
   pseudonymous reporting and opt-outs, then run the
   1,000-recipient launch gate before expanding scope.

Record the customer's authorization, approved recipient domains, sender mailbox, landing
hostnames, privacy mode, hourly limit, working hours and incident contacts in the sales case.
