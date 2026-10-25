# Azure production deployment

The supported enterprise topology is Azure Front Door Premium/WAF, private Azure Container
Apps, Service Bus Premium, Azure Managed Redis, PostgreSQL Flexible Server, Key Vault and
immutable Blob evidence storage. `docker-compose.yml` is for local development only. The
single-host Compose file is retained as a restricted evaluation reference and is not the
50,000-recipient production architecture (see [section 7](#7-single-vm-compose-alternative)).

## 1. Prerequisites and secrets

- Terraform 1.9+, Azure CLI, a production subscription and permission to create role
  assignments/private endpoints.
- Two Azure regions, a delegated DNS zone, and immutable API/frontend images in ACR.
- Protected CI state storage with locking. Never store Terraform state locally in routine
  operations because state contains generated connection material.
- A Together AI key whose account has Zero Data Retention enabled.

Supply secrets through protected `TF_VAR_*` values. Use a random 32+ byte application secret,
a Fernet encryption key, a 24+ character PostgreSQL bootstrap password, and the Together key.
Do not put secrets in `terraform.tfvars`.

The API, workers and migration job refuse to start in production
(`validate_production_settings` in `backend/app/core/config.py`) when, among other checks:

- `ENCRYPTION_KEY` is the Fernet key committed in the initial commit (`2578f4b`, removed in
  `fba4490`). Only its SHA-256 fingerprint is kept (`COMPROMISED_ENCRYPTION_KEY_SHA256`);
  non-production instances using it log a `SECURITY` warning at startup. Any environment that
  ever used that key needs a new key and a re-encryption plan (see
  [key rotation](runbooks/lifecycle.md)).
- `TRUSTED_HOSTS` or a `CORS_ORIGINS` host is `localhost`, `127.0.0.1`, `::1`/`[::1]`,
  `0.0.0.0`, `testserver`, another loopback address or a `*.localhost` name. Health probes must
  therefore send a `Host` header that is listed in `TRUSTED_HOSTS`.
- `VOICE_CLONE_PROVIDER` or `VIDEO_CLONE_PROVIDER` is not `none`. ElevenLabs/D-ID cloning is
  excluded from the initial launch, and `ELEVENLABS_ALLOW_VOICE_CLONING` defaults to `false`.
  To enable synthetic media later, first revise and sign off the launch policy, then set
  `SYNTHETIC_MEDIA_PRODUCTION_APPROVED=true` together with the provider, its API key and, for
  voice cloning, `ELEVENLABS_ALLOW_VOICE_CLONING=true`.

## 2. Provision Azure

```powershell
cd infra/terraform
Copy-Item terraform.tfvars.example terraform.tfvars
terraform init -backend-config=<protected-backend-config>
terraform fmt -check -recursive
terraform validate
terraform plan -out production.tfplan
terraform apply production.tfplan
```

After the first apply:

1. Approve both Front Door private endpoint requests on the Container Apps environment.
2. Create the `_dnsauth` TXT records printed in `custom_domain_validation_tokens` and CNAME
   `app.<platform-domain>` plus the wildcard tenant record to the Front Door endpoint.
3. Wait for every managed certificate and Front Door route to become healthy. Alert on
   wildcard certificate validation/rotation failures.
4. Run `alembic upgrade head` as a one-shot Container Apps job, then run
   `python scripts/bootstrap_production.py`. Remove bootstrap passwords and TOTP secrets from
   the deployment secret store immediately afterward.
5. Confirm `/health/ready`, operator MFA, cookie/CSRF behavior, and an authenticated evidence
   export before onboarding a customer.

Terraform is intentionally prevented from destroying PostgreSQL, Key Vault and evidence
storage. Production changes require reviewed plans.

## 3. Customer email and identity setup

Follow [customer onboarding](runbooks/customer-onboarding.md). Important external controls:

- Microsoft Graph requires customer admin consent for application `Mail.Send` and an Exchange
  Online Application RBAC policy restricting the app to the dedicated sender mailbox. A 202
  response is recorded as **accepted**, not delivered.
- Google Workspace requires domain-wide delegation only for
  `https://www.googleapis.com/auth/gmail.send`, impersonating the configured sender mailbox.
  In Launch setup, choose **Workspace authorization** to open the Admin Console and copy the
  non-secret OAuth client ID and exact scope returned by the platform. Domain-wide delegation
  is an Admin Console grant, so there is intentionally no Google OAuth callback endpoint.
- Entra OIDC must use the exact customer tenant GUID issuer. Google identities must provide a
  verified email. Operators must already exist through invitation or SCIM; SSO never creates
  an administrator.
- SCIM bearer tokens are shown once and must be rotated. Recipient domains must be verified
  before SCIM can provision users from them.

## 4. Customer landing domains

Every tenant receives `<tenant>.<platform-domain>`. Optional custom domains are sales-led:

1. Add the hostname in the tenant launch console and publish the displayed ownership TXT.
2. Add it to Terraform `additional_custom_domains` and apply so Front Door requests managed
   TLS and attaches the hostname to both routes.
3. Point its CNAME to the Front Door endpoint.
4. A platform operator calls the domain **activate-edge** action. The API verifies ownership,
   CNAME, HTTPS readiness and hostname binding before campaigns may select it.

Campaign authors choose only from active domains. The backend creates a unique opaque,
expiring `/q/{token}` or `/l/{token}` for each recipient; arbitrary destination URLs are not
accepted. QR images use the separate non-tracking `/qr-assets/{token}.png` endpoint, so image
proxy fetches do not become scan events.

## 5. Provider reconciliation

Each email connection has a Key Vault HMAC secret reference. Configure the provider/event
adapter to POST canonical JSON to
`/api/v1/provider-webhooks/{provider}/{connection-id}` with `X-BreachSim-Timestamp` (Unix
seconds) and `X-BreachSim-Signature` (`sha256=<hex HMAC of timestamp + '.' + raw body>`).
Replayed event IDs are ignored. Hard bounces enter the tenant suppression list; ambiguous
submissions stay **unknown** and are never blindly retried.

After creating a connection, platform operations must generate a random HMAC value in Key
Vault using the exact `reconciliation_secret_ref` returned by the API. Add/manage that secret
through protected infrastructure configuration; tenant users never receive the value.

## 6. Release gates

Do not call the service production-ready until all of these are signed off:

- Gmail web/mobile and Outlook web/desktop inline-QR matrix.
- One Microsoft 365 and one Google Workspace pilot at 1,000, 10,000 and 50,000 recipients.
- No-duplicate 50,000-recipient load/recovery test with the customer's real throttles.
- SAST, dependency/container/secret scans, cross-tenant tests and an independent penetration
  test.
- A disaster-recovery exercise proving RPO <=15 minutes and RTO <=4 hours.

See [campaign operations](runbooks/campaign-operations.md),
[incident response](runbooks/incident-response.md),
[key rotation/offboarding/retention](runbooks/lifecycle.md), and
[disaster recovery](runbooks/disaster-recovery.md).

## 7. Single-VM Compose alternative

`docker-compose.production.yml` runs the API, frontend, PostgreSQL, Redis, the Service Bus
delivery worker and the outbox dispatcher (the same `app.workers.service_bus_worker` and
`app.workers.outbox_dispatcher` entrypoints as the Container Apps Jobs) on one host behind
Caddy. It must pass the same startup check, so it still needs Azure Service Bus, Key Vault,
Blob evidence storage and a Front Door profile in front of the host (public campaign links
require Front Door's `X-Azure-FDID`), plus a service principal (`AZURE_TENANT_ID`,
`AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`) for `DefaultAzureCredential`.

Copy `.env.production.example` to `.env.production` and replace every example value:
`SECRET_KEY`, `ENCRYPTION_KEY`, `TOGETHER_API_KEY` (or set `AI_PROVIDER=rule_based`), `DOMAIN`,
`PLATFORM_TRAINING_DOMAIN`, the Front Door, Service Bus, Key Vault and evidence-storage values,
`POSTGRES_PASSWORD`, `REDIS_PASSWORD`, the service principal, and the `BOOTSTRAP_*` values
for the first run. Start it with
`docker compose --env-file .env.production -f docker-compose.production.yml up -d`.
`TRUSTED_HOSTS` is `DOMAIN` plus the internal `backend` name (the backend healthcheck sends
`Host: backend`), and synthetic media is pinned off.
