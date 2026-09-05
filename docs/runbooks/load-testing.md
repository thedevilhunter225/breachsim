# 50,000-recipient launch gate

Use synthetic employees on verified test domains and provider sandboxes/test tenants. Launch
one 50,000-recipient campaign with an idempotency key, inject worker termination, Service Bus
redelivery, provider 429/5xx/timeouts and a connection revocation, then resume and reconcile.

Pass criteria: one attempt per target; no duplicate accepted submissions; hourly/minute limits
never exceeded; API p95 remains responsive; dead letters are visible and recoverable; unknown
submissions are not retried; final status totals equal target count; QR assets decode from email
screenshots; image proxy fetches create zero scan events. Repeat at 1,000 and 10,000 before the
full gate, and retain raw test results and configuration as release evidence.
