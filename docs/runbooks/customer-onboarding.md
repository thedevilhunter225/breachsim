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

   For a Google Workspace pilot, the customer administrator must own the Workspace domain
   and provision a dedicated sender mailbox. A platform operator stores the Google service
   account JSON in the protected secret store, then the customer administrator authorizes
   its OAuth client ID in **Google Admin console → Security → Access and data control → API
   controls → Manage domain-wide delegation** with only
   `https://www.googleapis.com/auth/gmail.send`. The platform's **Settings → Launch setup**
   shows the client ID and scope after a connection has been created. Use the connection
   health check and a test message to an approved mailbox before an actual campaign.
   The service account JSON and administrator credentials must not go into the repository.
   See [Google's credential setup](https://developers.google.com/workspace/guides/create-credentials)
   and [Gmail scope reference](https://developers.google.com/workspace/gmail/api/auth/scopes).
5. Verify provider health and sender SPF, DKIM and DMARC readiness. These checks do not
   guarantee inbox placement.
6. Configure tenant-specific Entra/Google OIDC and SCIM; rotate the displayed-once SCIM token
   into the customer's directory secret store.
7. Import a pilot group, add any organization exclusions in **Launch setup**, verify
   pseudonymous reporting and opt-outs, then run the
   1,000-recipient launch gate before expanding scope.

Record the customer's authorization, approved recipient domains, sender mailbox, landing
hostnames, privacy mode, hourly limit, working hours and incident contacts in the sales case.

## Optional Twilio lab pilot

SMS remains a local/demo channel for the initial release. A Twilio trial can validate
account access and its own guided test flow, but currently restricts sends to verified
recipients and Twilio-provided message templates. A paid account is needed to test this
application's custom campaign SMS body. Obtain an SMS-capable Twilio sender number and
a recipient number authorized for the controlled test.
In **Settings → SMS**, select Lab mode, enter the Account SID, Auth Token, sender number,
and one explicitly allowed test recipient, then enable the provider. The auth token is
stored encrypted by the backend and is not shown again. Save and launch only an approved
SMS sandbox/lab campaign to that allowlisted number. Do not enable SMS on an internet-facing
production deployment: the production API refuses it in this release. See the
[Twilio SMS quickstart](https://www.twilio.com/docs/messaging/quickstart) and
[trial restrictions](https://www.twilio.com/docs/usage/tutorials/how-to-use-your-free-trial-account).

## Personal Gmail local demo

If the customer does not have a Google Workspace domain, the personal Gmail SMTP
adapter can still run a local, allowlisted demonstration. This is not the enterprise
Google Workspace connection and does not exercise Gmail domain-wide delegation.
In **Settings → Email**, keep the provider in Lab mode, use `smtp.gmail.com` on port
`587`, and enter the Gmail app password in the password field. Limit recipients to
mailboxes the operator controls. Send one test message and inspect the inbox, spam
folder, link destination and click event separately; SMTP acceptance does not prove
inbox delivery. Public QR links still require a verified HTTPS landing hostname
reachable from the recipient's phone. Keep secrets in Settings or the deployment
secret store, never in the repository or chat.
