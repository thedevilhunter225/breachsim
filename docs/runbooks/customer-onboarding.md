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

## Optional personal-SIM SMS delivery demo

SMS remains disabled for enterprise production campaigns. Twilio's current messaging
policy prohibits security-testing messages, including simulated phishing, so a standard
Twilio account must not be used for that purpose.

For a closed, link-free delivery demo to at most four consenting Pakistani test numbers:

1. Install [SMSGate for Android](https://docs.sms-gate.app/installation/) from its official
   release on a phone with an active SIM. Do not disable device security controls to install
   an app; use another trusted installation route if the device blocks it.
2. Put the phone and backend PC on the same trusted Wi-Fi. In SMSGate, enable **Local Server**
   and start it. Note the phone's private LAN URL and its Basic Auth username/password.
   Do not port-forward the phone's API or expose it to the internet.
3. In **Settings → SMS**, choose **Android phone (SMS-only demo)**, enter
   `http://<phone-LAN-IP>:8080`, the gateway username/password, and 1–4 consenting
   recipients in `+923xxxxxxxxx` format. Enable and save the integration. The password is
   encrypted at rest and never shown again.
4. Select a saved recipient and click **Send demo SMS**. This sends only a fixed,
   clearly identified BreachSim test message. It has no URL and does not create a
   campaign, click event or training token. A successful API response means **queued on
   the phone**, not confirmed delivered; verify the recipient handset separately. The
   backend accepts at most four demo sends per organization per UTC day.

The personal-SIM route is a local demonstration, not a carrier-approved enterprise
delivery solution. Follow the SIM operator's terms and obtain specific approval before
any realistic or scaled security-awareness messaging.

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
