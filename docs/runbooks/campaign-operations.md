# Campaign operations

Before approval, confirm an approved scenario/template, active recipient/sender/landing
domains, a healthy provider, current authorization, opt-outs/exclusions, working hours,
and the rolling 30-day per-employee frequency cap before publishing delivery work.
Customer administrators manage pre-campaign exclusions in **Launch setup**; only a keyed
email digest is persisted, and removing an exclusion deactivates it without destroying audit history.
schedule and hourly limit. The creator and approver must be separate where policy requires.

Launch with a newly generated `Idempotency-Key`. Watch queued, processing, accepted, bounced,
suppressed, failed, cancelled and unknown separately. Provider acceptance is not delivery.

- Pause stops new claims; already submitted requests may finish.
- Resume republishes only queued attempts.
- Cancel marks unsent attempts cancelled; do not imply recall of accepted mail.
- Retry-failed applies only to explicit failures. Never retry unknown submissions without
  reconciliation or an operator decision that accepts duplicate risk.

Escalate connection revocation, sustained 401/403, 429 exhaustion, dead letters, unknown-rate
growth, unexpected recipient-domain suppression or Front Door hostname failures. Export and
retain the immutable evidence reference after reconciliation completes.
