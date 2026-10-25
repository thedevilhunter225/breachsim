---
title: Subprocessors
status: draft
last_reviewed: "[Last reviewed date]"
audience: Customer organisations, their privacy teams and auditors
summary: The third parties that process customer personal data for BreachSim, the services customers connect themselves, and providers that are not used in the initial launch.
---

> [!WARNING]
> **Template draft — not legal advice.** This subprocessor list is a template draft prepared from BreachSim's documented product behaviour and deployment configuration. It is not legal advice and must be reviewed and adapted by qualified counsel for each jurisdiction in which it will be used, with each entry confirmed against signed contracts, before it is published. Text in square brackets, such as [Primary Azure region], marks information that still has to be supplied.

**Effective date:** [Effective date]

[Company legal name] ("BreachSim") uses the subprocessors below to provide the BreachSim service. Their use is governed by the [data processing agreement](/legal/dpa), which explains how customers are notified of changes and how they can object.

## Current subprocessors

| Subprocessor | Purpose | Location | Status |
| --- | --- | --- | --- |
| Microsoft Azure ([Microsoft contracting entity]) | Hosting, database, storage, messaging, networking, secrets and monitoring | [Primary Azure region]; disaster recovery in [Secondary Azure region]; global edge network | In use |
| Together AI ([Together AI contracting entity]) | Drafting simulation text from placeholder-based requests | [Together AI processing location] | In use |

### Microsoft Azure

- **Services:** Azure Front Door Premium with web application firewall, Azure Container Apps, Azure Database for PostgreSQL Flexible Server, Azure Service Bus, Azure Managed Redis, Azure Key Vault, Azure Blob Storage, Azure Container Registry, Azure Monitor (Log Analytics and Application Insights).
- **Personal data:** all customer data held in the service — participant and operator records, interaction events, risk and training data, generated simulation content, evidence exports and audit logs — plus connection data such as IP addresses in edge and platform logs.
- **Location:** [Primary Azure region], with a database replica and geo-redundant backups in [Secondary Azure region] and evidence storage replicated to [Evidence storage secondary region]. Azure Front Door terminates connections at Microsoft edge locations worldwide.
- **Retention notes:** platform diagnostic logs up to 90 days; database backups 35 days; evidence exports in write-once storage for [Evidence retention period].

### Together AI

- **Service:** serverless inference API, model `openai/gpt-oss-120b`.
- **Data sent:** placeholders such as `{{first_name}}`, `{{company_name}}`, `{{department}}` and `{{role_title}}`; the channel, theme and difficulty; and an operator's free-text instructions after BreachSim has replaced the participant's name, the organisation's name, department and role, and any email addresses or phone numbers with placeholders. Participant profiles, context notes, contact details and risk or training history are not sent.
- **Safeguards:** BreachSim requires zero data retention on its Together AI account, so prompts and outputs are not stored or used for training. [Confirm the account setting and record the date confirmed.] Generated text is validated, and personalised only inside BreachSim. If Together AI is unavailable, a built-in generator runs inside the service instead.

## Services the customer connects

These services act under the customer's own agreements with their providers and are not engaged by BreachSim as subprocessors. [Counsel to confirm this characterisation.]

| Service | What BreachSim does with it |
| --- | --- |
| Microsoft 365 (Microsoft Graph) | Sends simulations from a dedicated mailbox in the customer's tenant, using the application permission Mail.Send that the customer's administrator grants and limits to that mailbox. |
| Google Workspace (Gmail API) | Sends simulations from a dedicated mailbox in the customer's domain, using domain-wide delegation that the customer's administrator limits to the gmail.send scope. |
| Customer identity provider (Microsoft Entra ID or Google) | Signs operators in with single sign-on and, if the customer enables it, provisions participants through SCIM. |

## Not used in the initial launch

The following providers are not used in the initial launch. Each would require a written amendment to the customer's agreement, and the explicit consent of every person whose data, voice or likeness it would process, before it could be enabled.

| Provider | Capability it would add |
| --- | --- |
| ElevenLabs | Voice cloning and synthesised speech for voice and voice-note simulations |
| D-ID | Talking-head video for synthetic-media simulations |
| SMS gateway or carrier (A2P) provider | Sending simulated text messages |
| Telephony provider | Placing real outbound calls for voice simulations |

## Changes to this list

BreachSim will give notice of a new or replacement subprocessor at least [Notice period] before it begins processing customer personal data, as described in the data processing agreement. To receive notices, contact [Subprocessor notification contact].
