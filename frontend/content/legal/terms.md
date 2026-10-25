---
title: Terms of service
status: draft
last_reviewed: "[Last reviewed date]"
audience: Customer organisations subscribing to BreachSim
summary: The customer agreement for the BreachSim service, including the authorized-use rules that apply to every simulation campaign.
---

> [!WARNING]
> **Template draft — not legal advice.** These terms are a template draft prepared from BreachSim's documented product behaviour. They are not legal advice and must be reviewed and adapted by qualified counsel for each jurisdiction in which they will be used before they are offered to or signed by any customer. Text in square brackets, such as [Company legal name], marks information that still has to be supplied.

**Effective date:** [Effective date]

These terms of service ("Terms") are an agreement between [Company legal name], registered in [Jurisdiction of incorporation] under number [Company registration number], with its registered office at [Registered address] ("BreachSim", "we", "us"), and the organisation named in the order form ("Customer", "you"). If there is a conflict, the order form prevails over the [data processing agreement](/legal/dpa) ("DPA"), and the DPA prevails over these Terms on matters of personal data. [Confirm the order of precedence.]

## 1. Definitions

- **Service** — the hosted BreachSim platform: the operator console, simulation and training pages, the employee portal, related documentation and support.
- **Order form** — the document that identifies the Customer and sets out the subscription scope, fees and term.
- **Operator** — a person the Customer authorizes to use the console.
- **Participant** — an employee or other person the Customer enrols in its awareness programme.
- **Customer Data** — data submitted to the Service by or for the Customer, its operators and participants, and data the Service generates for the Customer, including personal data.
- **Simulation** — a simulated phishing message and the training page that follows it. A **campaign** is a set of simulations sent to selected participants.
- **Authorization Form** — a signed [simulation authorization form](/legal/simulation-authorization) covering a campaign or programme.

## 2. The Service

2.1 BreachSim is a platform for authorized security-awareness simulations. It lets the Customer manage a participant directory, generate and approve simulation scenarios, send campaigns, show training after each simulation, analyse risk and export reports and evidence.

2.2 In the initial release, simulations are sent by email, either with a unique link or with a QR code shown in the message, from a dedicated mailbox in the Customer's own Microsoft 365 (through Microsoft Graph) or Google Workspace (through the Gmail API) tenant. SMS, voice-call and synthetic-media (cloned voice or video) simulations are not part of the Service and will be offered only under a written amendment.

2.3 Sandbox previews run a campaign through the platform without sending any message.

2.4 We may improve and change the Service, but we will not materially reduce the security and data-protection measures described in the DPA during a subscription term. [Describe notice of material changes.]

## 3. Authorized use

3.1 **Authorization first.** You may run simulations only against people and email domains that you are entitled to test, and only within the scope of an Authorization Form signed by a person with authority to bind you. No live campaign may be launched before the relevant Authorization Form has been signed and provided to us.

3.2 **Platform safeguards.** The Service enforces technical limits: live campaigns are sent only to participants whose email domain you have verified, from a verified sender domain, through a healthy mail connection you authorized, with links on the landing domain chosen for the campaign; and participants who are inactive, opted out, suppressed, excluded or over the frequency limit are left out. You must not try to circumvent these limits.

3.3 **Safeguards you must keep enabled.** Unless we agree otherwise in writing, for every live campaign you must keep enabled: the setting that respects participant opt-outs; two-person approval of scenarios and campaigns; and the working hours and frequency limit stated in the Authorization Form. Named (non-pseudonymous) reporting may be used only if the Authorization Form permits it.

3.4 **Prohibited uses.** You must not use the Service to:

- collect real passwords, multi-factor authentication codes, payment details or other secrets;
- target anyone outside your organisation, such as customers, suppliers, the public or our personnel;
- impersonate real third-party brands, public authorities, law enforcement, healthcare providers or real individuals;
- send content that is threatening, harassing, discriminatory, sexual or likely to cause serious distress, or that uses topics your policy prohibits;
- deliver malware, attachments or links to destinations other than the Service's own training pages;
- use simulation results as the sole basis for disciplinary action or other decisions with significant effects on a participant [confirm];
- upload special categories of personal data, or data about children, into the Service, or put personal data in free-text scenario instructions; or
- probe, load-test or attack the Service, or attempt to access another customer's data.

3.5 **Your legal obligations.** You are responsible for complying with the laws that apply to your programme, including employment, privacy, electronic-communications and anti-spam laws; for informing participants, for example with the [employee notice template](/legal/employee-notice); and for consulting works councils or other employee representatives where required.

## 4. Your responsibilities

4.1 **Mail connection.** You authorize BreachSim to send simulations through a dedicated sender mailbox that you control. For Microsoft 365, this means administrator consent to the application permission Mail.Send, limited by an Exchange Online application RBAC assignment to that mailbox. For Google Workspace, this means domain-wide delegation limited to the gmail.send scope for that mailbox. You may revoke this access at any time; revoking it stops delivery.

4.2 **Domains and deliverability.** You must publish the DNS verification records we provide and keep SPF, DKIM and DMARC correctly configured. Acceptance by your mail provider is not proof of delivery, inbox placement is not guaranteed, and a message that has been accepted cannot be recalled.

4.3 **Operator accounts.** You must keep operator accounts accurate, grant roles on a least-privilege basis, keep multi-factor authentication enabled, keep credentials and provisioning tokens confidential and remove access promptly when it is no longer needed. Two-person approval depends on having at least two active administrators.

4.4 **Participant data.** You must have a lawful basis for the participant data you provide, keep it accurate and limited to what the programme needs, configure your retention period and reporting mode as stated in the Authorization Form, and act promptly on participants' opt-out and deletion requests.

4.5 **Availability during campaigns.** The emergency contact named in the Authorization Form must be reachable while a campaign is running.

## 5. Our responsibilities

5.1 We will provide the Service in accordance with these Terms and its documentation, using the technical and organisational measures described in the DPA.

5.2 Our personnel will access Customer Data only to operate, support and secure the Service, or as required by law.

5.3 Support: [Support channels and hours]. Service levels: [Service level commitment, if any].

## 6. Data protection

For participant and operator personal data, you are the controller and we are your processor. The DPA, which forms part of these Terms, governs that processing. Our current subprocessors are listed on the [subprocessors page](/legal/subprocessors).

## 7. AI-generated content

7.1 We use Together AI to draft the narrative text of simulations. Requests contain placeholders instead of participant details, as described in the [privacy notice](/legal/privacy). If the AI provider is unavailable, a built-in generator is used.

7.2 Generated content is a draft. The Service checks it against your policy, including allowed themes and prohibited words and topics, but your administrators must review and approve it before use, and you are responsible for content you approve.

7.3 We do not use Customer Data to train AI models, and we require zero data retention from our AI provider.

## 8. Fees and payment

[Fees, invoicing, payment terms and taxes.]

## 9. Confidentiality

Each party will keep the other's confidential information confidential, use it only to perform this agreement and disclose it only to people who need to know it and are bound by equivalent obligations, or where required by law. [Complete the confidentiality terms.]

## 10. Intellectual property

10.1 We own the Service, its software and documentation. You own Customer Data and grant us the rights needed to process it to provide the Service in accordance with the DPA.

10.2 Simulation content generated for you: [Ownership and licence of generated simulation content].

10.3 If you give us feedback, we may use it without obligation to you.

## 11. Third-party services

Your Microsoft 365 or Google Workspace tenant and your identity provider are governed by your own agreements with those providers. We are not responsible for their availability, or for what happens to a message after your provider has accepted it.

## 12. Suspension

We may suspend your organisation's access or pause your campaigns if we reasonably believe that a simulation is unauthorized or unlawful, that there is a security risk to the Service or to others, or that [Other suspension grounds, such as non-payment]. We will give notice where practicable and restore access once the issue is resolved.

## 13. Term and termination

13.1 Term and renewal: [Term and renewal].

13.2 Either party may terminate for material breach that is not remedied within [Cure period] of written notice. [Other termination rights.]

13.3 On termination, access to the Service ends. You should export the reports and evidence you need beforehand. We will delete Customer Data as set out in the DPA, subject to the exceptions it describes.

## 14. Warranties and disclaimers

[Warranties and disclaimers.]

## 15. Limitation of liability

[Liability cap and exclusions.]

## 16. Indemnities

[Indemnities, including the Customer's indemnity for simulations run without authorization or in breach of section 3.]

## 17. Changes to these Terms

[How changes to these Terms are notified and take effect.]

## 18. General

18.1 Governing law and jurisdiction: [Governing law and jurisdiction].

18.2 Notices: [Notice addresses].

18.3 [Assignment, force majeure, entire agreement, severability and other general terms.]

## 19. Contact

Questions about these Terms: [Legal contact email], [Registered address].
