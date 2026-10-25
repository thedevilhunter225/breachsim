---
title: Data processing agreement
status: draft
last_reviewed: "[Last reviewed date]"
audience: Customer organisations (controller) and BreachSim (processor)
summary: How BreachSim processes personal data on a customer's behalf — instructions, security measures, subprocessors, breach notification, assistance and deletion.
---

> [!WARNING]
> **Template draft — not legal advice.** This data processing agreement is a template draft prepared from BreachSim's documented product behaviour. It is not legal advice and must be reviewed and adapted by qualified counsel for each jurisdiction in which it will be used — including any mandatory clauses or transfer mechanisms required by local law — before it is offered or signed. Text in square brackets, such as [Company legal name], marks information that still has to be supplied.

**Effective date:** [Effective date]

This data processing agreement ("DPA") forms part of the agreement for the BreachSim service, including the [terms of service](/legal/terms) (together, the "Agreement"), between [Customer legal name] ("Customer") and [Company legal name] ("BreachSim"). It applies to personal data that BreachSim processes on the Customer's behalf in providing the service ("Customer Personal Data").

## 1. Definitions

"Controller", "processor", "personal data", "processing", "data subject", "personal data breach" and "supervisory authority" have the meanings given in [Applicable data protection law]. "Subprocessor" means a third party that BreachSim engages to process Customer Personal Data. Capitalised terms not defined here have the meanings given in the Agreement.

## 2. Roles and instructions

2.1 The Customer is the controller of Customer Personal Data and BreachSim is its processor.

2.2 BreachSim processes Customer Personal Data only on the Customer's documented instructions. The Customer's instructions are: the Agreement and this DPA; each signed [simulation authorization form](/legal/simulation-authorization); and the configuration and actions of the Customer's operators in the service, such as the participants enrolled, the scenarios and campaigns approved, the reporting mode, the retention setting and any deletions.

2.3 BreachSim will inform the Customer if it believes an instruction infringes applicable data protection law, and may decline to carry out that instruction until it is confirmed or changed. BreachSim may process Customer Personal Data otherwise only where required by law, in which case it will inform the Customer unless the law prohibits this.

2.4 The Customer is responsible for having a lawful basis for the processing; for informing participants, for example with the [employee notice template](/legal/employee-notice); for the accuracy and minimisation of the data it provides, particularly free-text context notes; for keeping the safeguards required by the Terms enabled; and for not uploading special categories of personal data or data about children.

## 3. Details of the processing

The subject matter, duration, nature and purpose of the processing, and the categories of data subjects and personal data, are described in Annex 1.

## 4. Confidentiality

BreachSim ensures that the people it authorizes to process Customer Personal Data are bound by confidentiality obligations and have access only to the extent necessary to operate, support and secure the service. [Describe personnel screening and training.]

## 5. Security

5.1 BreachSim implements the technical and organisational measures described in Annex 2. BreachSim may update those measures provided the overall level of protection is not reduced.

5.2 The Customer is responsible for the security of its operator accounts and devices, its mail tenant and identity provider, and for the configuration choices it makes in the service, such as named reporting, retention and role assignments.

## 6. Subprocessors

6.1 The Customer gives BreachSim general authorization to engage the subprocessors listed on the [subprocessors page](/legal/subprocessors).

6.2 BreachSim will notify the Customer of any intended addition or replacement of a subprocessor at least [Notice period] before it begins processing Customer Personal Data. The Customer may object on reasonable data-protection grounds within that period; if the parties cannot resolve the objection, [Remedy, such as termination of the affected service with a pro-rata refund].

6.3 BreachSim imposes data-protection obligations on each subprocessor that are no less protective than this DPA and remains responsible for its subprocessors' performance.

6.4 Services the Customer contracts for itself — its Microsoft 365 or Google Workspace tenant, through which simulations are sent, and its identity provider, used for single sign-on and directory provisioning — act under the Customer's own agreements and are not BreachSim subprocessors.

6.5 SMS, voice-call and synthetic-media (cloned voice or video) features are not used. They would involve additional subprocessors and may be enabled only under a written amendment to the Agreement and, for any person whose voice or likeness would be used, with that person's explicit consent.

## 7. International transfers

BreachSim hosts Customer Personal Data on Microsoft Azure in [Primary Azure region], with disaster-recovery copies in [Secondary Azure region]. Traffic passes through Azure Front Door's global edge network. Together AI processes placeholder-based requests in [Together AI processing location]. Any transfer of Customer Personal Data to a country without an adequate level of protection is made under [Transfer mechanism].

## 8. Assistance with data subject requests

8.1 The service gives the Customer the following tools to respond to data subject requests:

- **Opt-out:** participants can opt out of future simulations through the employee portal, and operators can record an opt-out. While the opt-out setting is enabled, opted-out participants are left out when a campaign is launched.
- **Deletion requests:** participants can ask for deletion through the employee portal. The request is recorded against the participant, stops further simulations and is shown to the Customer's administrators.
- **Erasure:** an administrator can delete a participant. This erases the participant's record, consent history, context profiles, delivery records and links, interaction events, simulation responses, training records and risk history, and removes the participant's name from simulation content generated from their profile.
- **Correction:** operators can edit participant records, or the Customer can update them through directory provisioning.
- **Access:** the console shows each participant's record, current consent status, risk history, recent interactions and training. [Describe how a complete copy is produced for access requests, including the consent-change history, which the console does not currently display.]

8.2 If BreachSim receives a request directly from a data subject, it will not respond other than to direct the data subject to the Customer, and will forward the request to the Customer within [Forwarding period].

8.3 BreachSim will provide further reasonable assistance on request. [Specify any charges.]

## 9. Personal data breaches

9.1 BreachSim will notify the Customer without undue delay, and in any event within [Breach notification timeframe], after becoming aware of a personal data breach affecting Customer Personal Data.

9.2 The notice will describe, as far as then known, the nature of the breach, the categories and approximate number of data subjects and records concerned, the likely consequences, the measures taken or proposed and a contact point. Information may be provided in stages.

9.3 BreachSim's response includes containing the incident within the affected customer organisation (for example by pausing campaigns, revoking mail, single sign-on and provisioning connections, suspending the organisation or blocking compromised landing hostnames), preserving evidence including the hash-chained audit log, rotating exposed secrets and revoking sessions, identifying the affected organisations, participants, data and time window without widening access to named data, and recording the timeline, cause and corrective actions.

9.4 Notifying a breach is not an acknowledgement of fault or liability.

## 10. Audits and information

10.1 BreachSim will make available the information reasonably necessary to demonstrate compliance with this DPA. [Audit rights: reports, certifications, questionnaires and conditions for on-site audits.]

10.2 The Customer's administrators and auditors can view the organisation's audit log and access log in the service, export the audit log and check that the audit log's hash chain is intact.

## 11. Impact assessments

BreachSim will provide reasonable assistance with the Customer's data protection impact assessments and prior consultations with supervisory authorities, including by providing the information in this DPA, the [privacy notice](/legal/privacy) and the service documentation.

## 12. Deletion and return

12.1 During the term, the Customer controls deletion in the service: it can delete participants, campaigns (including their recorded evidence, if it chooses), scenarios and departments.

12.2 Before the Agreement ends, the Customer can export campaign evidence packs (HTML), per-participant outcome files (CSV) and the audit log (CSV).

12.3 After the Agreement ends, BreachSim will: suspend the Customer's organisation; pause or cancel any active campaigns; revoke mail, single sign-on and provisioning connections and simulation links; remove custom landing domains once outstanding links have expired; export any evidence the Customer has requested; and, after checking for legal holds and retention obligations, delete Customer Personal Data within [Deletion period] and record completion in the platform audit log.

12.4 The following are deleted only when their own retention ends: evidence exports already written to write-once storage, which cannot be deleted before the end of their immutability period ([Evidence retention period]; current configuration: 2,555 days); database backups, which expire after 35 days; and data that BreachSim must keep by law. This DPA continues to protect that data until it is deleted.

> [!NOTE]
> Drafting note for counsel: tenant deletion is currently a manual operations procedure, operator accounts can be deactivated but not deleted, and the per-organisation retention setting is not yet enforced automatically. Align sections 8 and 12 with the engineering plan in docs/legal/README.md before signature.

## 13. Liability, term and precedence

Each party's liability under this DPA is subject to the limitations in the Agreement [unless applicable law requires otherwise]. This DPA remains in force for as long as BreachSim processes Customer Personal Data. If this DPA conflicts with the terms of service on the processing of personal data, this DPA prevails.

## Annex 1 — Description of the processing

- **Subject matter:** provision of the BreachSim security-awareness simulation service.
- **Duration:** the term of the Agreement, plus the deletion period in section 12.
- **Nature of the processing:** collection by import, manual entry or directory provisioning; storage; personalisation of simulation content; sending simulations through the Customer's mail tenant; recording interactions; scoring, analysis and reporting; export; and erasure.
- **Purposes:** running simulations the Customer has authorized, delivering follow-up training, measuring and reporting security awareness, and operating and securing the service.
- **Data subjects:** participants the Customer enrols, and the Customer's operators.
- **Participant data:** full name, work email address, internal and directory identifiers, optional phone number, department, role or job title, status; context notes and public-profile summaries approved by the Customer and the context profile derived from them; consent status and history; delivery records; interaction events (link opened, QR code scanned, training-page choice and time); risk scores and history; training assignments and completions; simulation content personalised with the participant's name.
- **Operator data:** name, work email address, roles, password hash, encrypted multi-factor secret, hashed recovery codes, single sign-on subject identifier, session records, audit-log and access-log entries, invitation records.
- **Special categories of data:** none intended; the Customer must not upload them.
- **Frequency:** continuous for the duration of the subscription.
- **Retention:** as described in section 12 and in the [privacy notice](/legal/privacy).

## Annex 2 — Technical and organisational measures

### Access control

- Role-based access with separate administrator, campaign manager, read-only auditor and risk identity viewer roles; BreachSim platform operators provision, suspend and reactivate organisations.
- Multi-factor authentication (time-based one-time passwords) is required for administrator and platform-operator accounts in production; recovery codes are single-use and stored as hashes.
- Passwords are stored as salted PBKDF2-SHA256 hashes.
- Single sign-on through the Customer's Microsoft Entra ID or Google identity provider; single sign-on never creates an administrator account. Directory provisioning tokens are shown once and stored as hashes.
- Revocable server-side sessions in Secure, HttpOnly, SameSite=Strict cookies, with cross-site request forgery protection, idle and absolute time-outs and rotation; a password reset revokes all of the operator's sessions.
- Rate limits on sign-in and on public simulation endpoints, which fail closed in production if the rate-limit store is unavailable.
- Approval safeguards on by default: scenarios need approval from an administrator other than their author, campaigns need two different approving administrators, and administrator roles cannot be reduced below two active administrators.

### Tenant isolation

- Every record and query is scoped to a single customer organisation.
- Public simulation links are bound to the landing hostname chosen for the campaign and, in production, are accepted only through the platform's Azure Front Door profile.

### Encryption and data minimisation

- HTTPS for all traffic, with HTTP Strict Transport Security on API responses in production; the message queue and evidence storage require TLS 1.2 or later.
- Encryption at rest by the Azure services that hold the data, with infrastructure encryption enabled on evidence storage.
- Field-level encryption (Fernet: AES-128-CBC with HMAC-SHA256) of participant names, email addresses, phone numbers, approved context notes and profiles, recipient addresses on delivery records, link secrets, multi-factor secrets and integration credentials. The production service refuses to start without a dedicated encryption key.
- Keyed one-way hashes instead of plain email addresses for look-ups, suppression lists and pre-campaign exclusions; pseudonymous event identifiers.
- Analytics, campaign reports and evidence exports are pseudonymous by default; names appear in them only in named-reporting mode and only for operators with the risk identity viewer role. The participant directory and individual participant reports show names to authorized operators, and opening an individual report is recorded in the access log.
- Requests to the AI provider contain placeholders rather than participant data.
- Simulation and training pages accept only a categorical choice and never collect passwords, multi-factor codes or payment details.

### Infrastructure and network

- Azure Front Door Premium with a web application firewall in front of private Azure Container Apps.
- Database, cache, message queue, key vault and storage reached over private networking (private endpoints or a delegated subnet); public network access is disabled for the database, message queue, key vault and storage.
- Secrets held in Azure Key Vault and accessed through managed identities.

### Availability and resilience

- Zone-redundant PostgreSQL high availability, a cross-region read replica and geo-redundant backups retained for 35 days.
- Read-access geo-zone-redundant storage for evidence exports.
- Recovery objectives of at most 15 minutes of data loss and 4 hours to restore service [confirm once validated by a disaster-recovery exercise].

### Logging and monitoring

- An append-only audit log of approvals, launches, policy changes, exports, deletions and other sensitive actions, in which each entry is cryptographically chained to the previous one; an access log of views of sensitive records.
- Application request logs omit IP addresses and remove simulation link tokens.
- Platform diagnostic logs retained for 90 days; availability tests with alerting, and alerts when delivery messages cannot be processed.

### Incident response and key management

- A documented incident-response procedure (see section 9) that forbids copying passwords, multi-factor codes, provider tokens or decrypted participant data into tickets or logs.
- Secrets are rotated through new Key Vault versions, each health-tested before the previous version is revoked.

### Organisational measures

- [Personnel confidentiality agreements, background checks and security training.]
- [Vulnerability management, independent penetration testing and secure development practices.]
- [Certifications or third-party audit reports, if any.]

## Annex 3 — Subprocessors

The authorized subprocessors are listed on the [subprocessors page](/legal/subprocessors).
