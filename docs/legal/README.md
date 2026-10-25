# Legal templates (draft)

> **Template drafts — not legal advice.** These documents were prepared from BreachSim's documented
> product behaviour and code as of 2026-10-23. They must be reviewed and adapted by qualified
> counsel for each jurisdiction before they are published, offered to customers or signed.

## Where the documents live

The canonical Markdown files are in [`frontend/content/legal/`](../../frontend/content/legal), not in
`docs/`, so that the frontend Docker build (whose context is `frontend/`) includes them;
`frontend/Dockerfile` copies the directory into the runtime image. They are rendered at `/legal`
(index) and `/legal/<slug>` by `frontend/app/legal/` using the renderer in
`frontend/lib/legal-markdown.tsx`.

| Slug | Document |
|---|---|
| `privacy` | Privacy notice for participants and operators |
| `terms` | Terms of service (customer agreement) |
| `dpa` | Data processing agreement (customer = controller, BreachSim = processor) |
| `subprocessors` | Subprocessor list |
| `simulation-authorization` | Simulation authorization form signed before any campaign |
| `employee-notice` | Notice customers send to their staff |

Do not rename slugs: the login footer links to `/legal/privacy`, `/legal/terms` and `/legal`, and
the training page, simulation debrief and employee portal link to `/legal/privacy` and
`/legal/employee-notice`.

## Editing rules

- Frontmatter keys: `title`, `status`, `last_reviewed`, `audience`, `summary`. Any status other
  than `approved` shows the "Draft — pending legal review" banner, and draft pages are `noindex`.
- Supported Markdown: `##`–`####` headings, paragraphs, `-` and `1.` lists (not nested), block
  quotes and `> [!WARNING]` / `> [!NOTE]` callouts, `---` rules, pipe tables, `**bold**`,
  `` `code` ``, links to `/legal/...`, `https://` or `mailto:`, and `[Placeholders]`, which are
  highlighted on the page. Raw HTML is shown as text; other syntax is not supported.
- Each document must open with the `> [!WARNING]` template-draft banner.
  `frontend/lib/legal-markdown.test.ts` enforces the banner, the draft status, safe links and that
  internal links point at existing slugs.
- After review: fill in the placeholders, delete the "Drafting note" callouts, set
  `status: approved` and `last_reviewed`, and remove the banner only if counsel agrees.

## What counsel must review or supply

- **Entity and contacts:** [Company legal name], [Registered address], [Jurisdiction of
  incorporation], [Company registration number], [Privacy contact email], [Data protection
  officer], [EU/UK representative], [Legal contact email], [Support channels and hours],
  [Operations contact], [Subprocessor notification contact], plus the customer-side placeholders in
  the employee notice and authorization form.
- **Vendors and hosting:** [Primary Azure region], [Secondary Azure region], [Evidence storage
  secondary region] (Terraform defaults are `westeurope` and `northeurope`; confirm the deployed
  regions), [Microsoft contracting entity], [Together AI contracting entity], [Together AI
  processing location], and written confirmation that zero data retention is enabled on the
  production Together AI account.
- **Legal positions:** controller/processor characterisation and any controller activities;
  [Lawful basis]; [Transfer mechanism]; works-council and employee-representative consultation;
  the commitment that results are not the sole basis for disciplinary action; [Notice period] and
  [Remedy] for subprocessor changes; [Breach notification timeframe]; [Forwarding period];
  [Deletion period]; [Evidence retention period]; [Retention period]; [Response time] for deletion
  requests; audit rights; fees, term, SLA, warranties, liability cap, indemnities, confidentiality,
  ownership of generated content and governing law.
- **Hosting topology:** the drafts describe the Terraform topology (Azure Container Apps, managed
  PostgreSQL and Redis). If the single-VM Compose alternative in `docs/production-deployment.md`
  is used, revise the subprocessor, location, backup and retention statements for that host.
- **Figures taken from configuration** (confirm against the deployed environment): 90-day Log
  Analytics/Application Insights retention, 35-day geo-redundant database backups, 2,555-day
  immutable evidence storage, 30-day simulation link expiry, 30-minute idle / 8-hour session
  defaults, 365-day default retention setting, and the RPO 15 minutes / RTO 4 hours targets, which
  have not yet been validated by the disaster-recovery exercise required in
  `docs/production-deployment.md`.

## Known product gaps that qualify the drafts

The drafts describe current behaviour and flag these points instead of promising more:

1. **Retention is not enforced.** `organizations.retention_days` (default 365) is stored and
   editable, but no job purges participant data, events, delivery records, links or risk history.
   `media_store.sweep_expired()` is never scheduled.
2. **Erasure leaves copies.** `delete_employee()` (`backend/app/services/deletion.py`) does not
   reach: audit-log details, where `employee.update` stores the submitted fields (for example name,
   email, phone, context notes) in plaintext JSON, `employee.consent` stores consent notes and
   `user.create` stores the operator's email, in an append-only hash-chained log;
   `campaign_runs.scenario_snapshot`, which copies scenario text that can contain the name of the
   participant whose profile generated it; evidence exports in the immutable container (named-mode
   exports contain names and emails); and backups.
3. **Erasure probably fails on PostgreSQL** for anyone who received a QR campaign or has a
   reconciled provider event: `delete_employee()` does not delete `qr_asset_tokens` (foreign key to
   `landing_tokens`) or `provider_event_receipts` (foreign key to `delivery_attempts`), and the
   models declare no `ON DELETE CASCADE`. Found by code inspection only — the SQLite test database
   does not enforce foreign keys and there is no deletion test.
4. **Deprovisioning is not deletion.** SCIM `DELETE /Users/{id}` only marks the participant
   inactive. There is no tenant-deletion tooling, operator accounts can be deactivated but not
   deleted, and offboarding deletion is a manual runbook step.
5. **Names appear outside pseudonymous reporting.** `GET /employees` (any signed-in operator)
   returns names, emails and individual risk scores, and `GET /employees/{id}/report` (admin,
   campaign manager, auditor) shows named risk history and events whatever the reporting mode
   (access-logged). The privacy notice and DPA disclose this; consider restricting it.
6. **Safeguards are configurable.** An administrator can switch off "Respect employee opt-out"
   (`policies.opt_out_respected`); opted-out and deletion-requested participants are then not
   suppressed. The scenario two-person rule follows `policies.second_approval_required`, and campaign
   dual approval is a per-campaign flag. The terms and authorization form require them to stay on;
   consider enforcing that for live campaigns.
7. **Deletion requests are only flags.** The portal sets `redaction_requested`, writes an audit
   entry and stops future sends; no administrator is notified (although the portal says the
   organisation "has been notified") and nothing is deleted until an administrator deletes the
   participant. The console does not show consent-change history, which access requests need.
8. **Portal access is link-based.** The employee portal is opened with the participant's exercise
   link (expires after 30 days). Anyone holding a forwarded link can see the first name,
   participation status, trend and training, and can opt out or request deletion.
9. **Emergency stop limits.** Suspending an organisation blocks console access but does not pause
   campaign runs or disable public links (neither checks `suspended_at`); cancelling a run does not
   revoke delivered links; platform operators have no control to pause another organisation's run.
10. **AI redaction is pattern-based.** `_sanitize_external_text` (`backend/app/services/llm.py`)
    replaces the target's name, company, department, role, persona and email/phone patterns; other
    personal data typed into a theme or instructions would reach Together AI. Zero data retention
    is an account setting the code cannot check.
11. **Edge logs contain more than application logs.** Front Door/WAF diagnostics (`allLogs`, 90 days
    in Log Analytics) normally record client IP, user agent and the full request URL, including the
    `/l/` and `/q/` link tokens that the application's own request log redacts.
12. **Not field-encrypted:** consent-record notes, role titles, department names, audit-log details
    and scenario/campaign-run text rely on database encryption at rest only.
13. **Launch scope is partly configuration.** SMS is refused in production by code. Refusal of
    voice/video cloning providers in production (unless `SYNTHETIC_MEDIA_PRODUCTION_APPROVED=true`)
    was an uncommitted working-tree change, documented in `docs/production-deployment.md`, when
    these drafts were written; confirm it ships.

## Sources checked

`README.md`, `docs/security/privacy-model.md`, `docs/security/threat-model.md`, `docs/channels.md`,
`docs/features.md`, `docs/foundation.md`, `docs/production-deployment.md`, `docs/runbooks/*.md`,
`backend/app/core/config.py`, `backend/app/models/entities.py`, `backend/app/services/llm.py`,
`backend/app/services/deletion.py`, `backend/app/services/campaign_runs.py`,
`backend/app/services/email_rendering.py`, `backend/app/api/routes/` (public, employee portal,
employees, scim, audit, analytics, platform), `frontend/components/employee-portal.tsx` and
`infra/terraform/*.tf`. Re-check the drafts whenever these change.
