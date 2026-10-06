# BreachSim architecture overview

BreachSim is a multi-tenant service-oriented monolith with separate API, web and delivery-job
processes. Azure Front Door Premium terminates managed TLS, applies WAF policy and routes only
approved hostnames. The FastAPI API resolves every authenticated and public operation to an
organization; public recipient tokens are additionally bound to the requested landing
hostname.

## Tenant and identity boundary

Platform operators provision/suspend/offboard organizations through a sales-only console.
Tenant administrators use one-time invitations, tenant-specific Entra/Google OIDC and SCIM
2.0. Browser authentication is a revocable server session held in `Secure`, `HttpOnly`,
`SameSite` cookies with a separate CSRF token, rotation and idle/absolute expiry. Platform
operators and break-glass accounts require MFA. Employee PII and provider delivery details are
field-encrypted; reports are pseudonymous unless a named identity viewer role is present.

## Durable campaign path

A launch creates an immutable `CampaignRun` snapshot of scenario, branding, provider, landing
host, policy and reporting mode. The same transaction creates one attempt and opaque,
expiring token per eligible employee plus outbox batches. A scheduled dispatcher publishes to
Service Bus Premium. Event-driven Container Apps jobs atomically claim attempts and enforce
tenant/provider/sender minute and campaign-hour limits in Managed Redis.

Microsoft Graph and Gmail implementations share the provider-neutral email interface.
Timeouts after submission become `unknown`, never an automatic retry. Explicit 429/5xx errors
use bounded exponential backoff and `Retry-After`. Signed reconciliation events update known
bounces/failures and hard-bounce suppression lists. Provider acceptance is never labelled as
guaranteed delivery.

## QR and tracking path

Each QR encodes the recipient's tenant-bound `/q/{opaque-token}` route. The email references a
320px+ PNG on `/qr-assets/{asset-token}.png`; that endpoint validates an independent signed
asset token, sets proxy-safe caching and records no engagement. Only opening the encoded
`/q` URL records `scanned_qr`, idempotently, before redirecting to an approved in-platform
training page. This prevents Gmail/Outlook image proxy fetches from inflating scans.

## Data and AI boundary

PostgreSQL Flexible Server is authoritative, with zone-redundant HA, point-in-time recovery
and a cross-region replica. Audit entries are hash chained; generated evidence is written to
immutable RA-GZRS Blob storage. Key Vault and managed identities hold provider material.

Together AI (`openai/gpt-oss-120b`) sits behind a provider interface. It receives only template
placeholders such as `{{first_name}}`, `{{company_name}}` and `{{department}}`; raw employee
PII, performance history and complete tracking URLs never leave the backend. Responses are
schema/safety validated and personalized locally. The deployment assumes account-level Zero
Data Retention is enabled.
