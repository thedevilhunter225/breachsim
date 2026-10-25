---
title: Simulation authorization form
status: draft
last_reviewed: "[Last reviewed date]"
audience: Customer signatories, security teams and BreachSim operations
summary: The written authorization a customer signs before any campaign runs — signatory, people and domains in scope, permitted channels, dates, exclusions, emergency stop contact and acknowledgements.
---

> [!WARNING]
> **Template draft — not legal advice.** This authorization form is a template draft prepared from BreachSim's documented product behaviour. It is not legal advice and must be reviewed and adapted by qualified counsel for each jurisdiction in which it will be used before any customer signs it. Text in square brackets, such as [Customer legal name], marks information that still has to be supplied.

**Form reference:** [Form reference] · **Version:** [Version]

No live simulation campaign may be launched until this form has been completed, signed by an authorized signatory of the customer and returned to BreachSim. Campaigns must stay within the scope recorded here; a change of scope needs an updated, signed form. This form forms part of the agreement between the customer and [Company legal name] ("BreachSim") under the [terms of service](/legal/terms) and the [data processing agreement](/legal/dpa).

## 1. Customer

- Customer legal name: [Customer legal name]
- Registered address: [Customer address]
- BreachSim workspace (organisation) identifier: [Workspace identifier]
- Privacy contact for participants: [Customer privacy contact]

## 2. Authorizing signatory

- Name: ______________________
- Job title: ______________________
- Email: ______________________
- Telephone: ______________________

The signatory confirms that they have authority to authorize security-awareness testing of the customer's personnel, mailboxes and domains named in this form, and that any internal approvals required by the customer's policies have been obtained.

## 3. Scope: people

- Participant groups in scope (for example all staff, named departments or a pilot group): ______________________
- Approximate number of participants: ______________________
- How participant data will be provided: ☐ CSV import ☐ Directory provisioning (SCIM) ☐ Manual entry
- Approved context notes will be added for participants: ☐ No ☐ Yes — describe the content allowed: ______________________

Only active participants whose email domain the customer has verified in BreachSim can receive live simulations.

## 4. Scope: domains and sender

- Recipient email domains (each must be verified in BreachSim): ______________________
- Sender mailbox (a dedicated mailbox in the customer's tenant): ______________________
- Mail platform: ☐ Microsoft 365 (Microsoft Graph, application permission Mail.Send limited to the sender mailbox) ☐ Google Workspace (Gmail API, domain-wide delegation limited to the gmail.send scope)
- Landing domain for simulation links: ☐ BreachSim platform subdomain ______________________ ☐ Verified custom domain ______________________

## 5. Permitted channels

- ☐ **Email** — a simulated message with a unique link to a BreachSim training page.
- ☐ **QR code** — a simulated email showing a QR code that opens a BreachSim training page.

SMS, voice-call and synthetic-media (cloned voice or video) simulations are not available in the initial launch. They cannot be authorized on this form; each would require a written amendment and the explicit consent of any person whose voice or likeness would be used.

## 6. Date window and limits

- Start date and time: ______________________
- End date and time: ______________________
- Time zone: ______________________
- Sending hours each day (working-hours window): from ______ to ______
- Maximum simulations per participant in any rolling 30-day period (platform default: 2): ______
- Maximum messages sent per hour for a campaign: ______

## 7. Content

- Allowed themes: ______________________
- Allowed difficulty levels: ☐ Low ☐ Medium ☐ High
- Prohibited words and topics, in addition to BreachSim's defaults: ______________________
- Simulations must not impersonate real third-party brands, public authorities, law enforcement, healthcare providers or real individuals.
- Two-person approval stays enabled: a scenario is approved by an administrator other than its author, and each campaign is approved by two different administrators.
- Customer administrators authorized to approve content and campaigns: ______________________

## 8. Exclusions

- People or groups to exclude (for example people on leave, in a sensitive personal situation or under investigation): ______________________
- Exclusions are entered in BreachSim's launch setup before the campaign, where they are stored as keyed one-way hashes of email addresses rather than in plain text.
- Participants who have opted out or asked for their data to be deleted through the employee portal are left out automatically; the customer will keep the "Respect employee opt-out" setting enabled.
- Addresses that hard-bounced in earlier campaigns are suppressed automatically.

## 9. Reporting and retention

- Reporting mode: ☐ Pseudonymous (default) ☐ Named — names appear in analytics, reports and exports only for operators holding the risk identity viewer role.
- Operators who will hold the risk identity viewer role (named mode only): ______________________
- Retention period configured for the workspace: ______ days (platform default setting: 365)

## 10. Emergency stop

- Customer emergency contact (reachable throughout the date window): name ______________________, telephone ______________________, email ______________________
- Secondary contact: ______________________
- BreachSim operations contact: [Operations contact]

The customer's administrators and campaign managers can pause or cancel a campaign at any time from the BreachSim console. Pausing stops further messages from being claimed for sending, although messages already submitted may still complete; cancelling marks unsent messages as cancelled. The customer can also revoke BreachSim's mail access in its Microsoft 365 or Google Workspace tenant at any time, which stops further sending. If the emergency contact asks BreachSim to stop a campaign, BreachSim operations will act under [Operations stop procedure and response time].

A message that the mail provider has already accepted cannot be recalled, and its link stays usable until it expires (30 days by default) unless BreachSim operations revokes the links or blocks the landing hostname.

## 11. Acknowledgements

The customer acknowledges that:

- ☐ **No credentials are captured.** BreachSim simulation and training pages never ask for, collect or store passwords, multi-factor authentication codes or payment details. They record only that an interaction happened and which option the participant chose.
- ☐ BreachSim records delivery status reported by the customer's mail provider, link opens, QR scans, training-page choices and training completion, and calculates risk scores from them, as described in the [privacy notice](/legal/privacy).
- ☐ Simulation text may be drafted by BreachSim's AI subprocessor using placeholders instead of participant data, and every scenario is reviewed and approved by customer administrators before use.
- ☐ Acceptance by the mail provider is not proof of delivery, and accepted messages cannot be recalled.
- ☐ The customer has informed participants about the programme (for example with the [employee notice template](/legal/employee-notice)) and has consulted employee representatives where the law or its agreements require it.
- ☐ Simulation results will not be used as the sole basis for disciplinary action [confirm].
- ☐ The customer is responsible for the lawfulness of the programme in each jurisdiction where participants work.

## 12. Signatures

**For the customer**

- Signature: ______________________
- Name: ______________________
- Title: ______________________
- Date: ______________________

**Received for BreachSim**

- Signature: ______________________
- Name: ______________________
- Title: ______________________
- Date: ______________________

BreachSim keeps a record of this authorization together with the customer's approved recipient domains, sender mailbox, landing hostnames, reporting mode, hourly limit, working hours and incident contacts.
