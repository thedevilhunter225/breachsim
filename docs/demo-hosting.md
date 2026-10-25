# Hosting BreachSim online (public demo / pilot)

This is the cheap, no‑Azure way to put BreachSim on the public internet with your own domain
and HTTPS, so campaign/landing/QR links resolve publicly for testing. It runs the real
application and delivery pipeline, just without the Azure enterprise services.

> For the full 50,000‑recipient enterprise architecture (Azure Front Door + WAF, Service Bus,
> Key Vault, immutable Blob evidence), use [production-deployment.md](production-deployment.md)
> instead. That path costs roughly $1,000+/month and requires customer Microsoft 365 / Google
> Workspace authorization for real email.

## What you need

| Item | Notes | Cost |
|---|---|---|
| A small Linux VM | 2 vCPU / 4 GB RAM / ~40 GB disk, Ubuntu 22.04+. e.g. Hetzner CX22, DigitalOcean, Vultr, Oracle Cloud free tier | ~$0–12 / month |
| A domain name | e.g. from Namecheap/Cloudflare/Porkbun | ~$1–12 / year |
| Docker + Docker Compose | Installed on the VM (steps below) | free |
| (Optional) Together AI key | For real LLM‑generated scenarios; otherwise the free rule‑based generator is used | ~cents per run |

HTTPS certificates are automatic and free (Caddy + Let's Encrypt). No Azure account is needed.

## 1. Point your domain at the server

Create a DNS **A record** for the hostname you'll use (apex `example.com` or a subdomain like
`breachsim.example.com`) pointing at the VM's public IPv4 address. Wait for it to resolve:

```bash
dig +short breachsim.example.com
```

Let's Encrypt issues the certificate over ports 80/443, so make sure the VM firewall / cloud
security group allows inbound **80** and **443** (and 22 for SSH). Nothing else needs to be
exposed — PostgreSQL and Redis stay on an internal Docker network.

## 2. Install Docker on the VM

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # then log out and back in
docker compose version          # confirm the Compose plugin is present
```

## 3. Get the code and configure

```bash
git clone <your-repo-url> breachsim && cd breachsim
cp .env.demo.example .env.demo
```

Edit `.env.demo` and set **every** value. Generate the secrets on the VM:

```bash
# SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
# ENCRYPTION_KEY (must be a brand-new Fernet key)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# POSTGRES_PASSWORD / REDIS_PASSWORD — any long URL-safe random strings
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

Set `DOMAIN` to the hostname from step 1. For real LLM scenarios, set `AI_PROVIDER=together`
and paste a `TOGETHER_API_KEY`; otherwise leave `AI_PROVIDER=rule_based`.

> If `python3` isn't on the VM, run the one-liners inside Docker instead, e.g.
> `docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(48))"`.

## 4. Launch

```bash
docker compose --env-file .env.demo -f docker-compose.demo.yml up -d --build
```

First build takes a few minutes. Watch it come up:

```bash
docker compose --env-file .env.demo -f docker-compose.demo.yml ps
docker compose --env-file .env.demo -f docker-compose.demo.yml logs -f backend caddy
```

On first start the backend creates its database schema and the four operator accounts
automatically (no migration step). Once `backend` is healthy and Caddy has a certificate,
open `https://your-domain`.

## 5. Sign in and run a campaign

Seeded operator accounts (created on first boot; no MFA in this mode):

| Role | Email | Password |
|---|---|---|
| Admin | `admin@breachsim-lab.com` | `Admin123!` |
| Second admin (reviewer) | `reviewer@breachsim-lab.com` | `Reviewer123!` |
| Campaign manager | `manager@breachsim-lab.com` | `Manager123!` |
| Auditor | `auditor@breachsim-lab.com` | `Auditor123!` |

> **Change these passwords immediately** — this instance is on the public internet. Two admin
> accounts exist because creation and approval require different people (two‑person rule).

Fastest way to get working public links to test: with the stack up, run the end‑to‑end seed
against the live API (no guardrail is bypassed):

```bash
docker compose --env-file .env.demo -f docker-compose.demo.yml exec backend \
  python scripts/demo_seed.py --run-interactive
```

It provisions governance objects, runs one campaign per enabled channel, and prints the
tokenized employee entry point for each — e.g. `https://your-domain/training/<token>` and
`https://your-domain/q/<token>`. Open those in any browser/phone to walk the real flow; the
backend records the click/scan, risk movement and evidence, which you can see under Command
Center / Risk Intelligence and export under Reports.

## 6. About real email delivery

By default this stack delivers in sandbox mode — it generates real, public, tokenized links
but does not send mail. That's the safe default for a public demo and is all you need to show
the full flow (just open the printed link).

To send **real** training emails, configure a sender **inside the app** (Governance / Launch
setup), exactly as the production product does:

- **Microsoft 365** — needs customer admin consent for Graph `Mail.Send` on a dedicated mailbox.
- **Google Workspace** — needs domain‑wide delegation for `gmail.send` on the sender mailbox.

Both require a tenant you control and verified DNS. See
[customer-onboarding.md](runbooks/customer-onboarding.md). Only run simulations against an
organization that has authorized them, and against recipients who have consented.

## 7. Operating it

```bash
# Update to new code
git pull
docker compose --env-file .env.demo -f docker-compose.demo.yml up -d --build

# Stop / start
docker compose --env-file .env.demo -f docker-compose.demo.yml down
docker compose --env-file .env.demo -f docker-compose.demo.yml up -d

# Back up the database
docker compose --env-file .env.demo -f docker-compose.demo.yml exec postgres \
  pg_dump -U breachsim breachsim > backup-$(date +%F).sql
```

Data persists in the `postgres_data`, `media_data` and `report_data` Docker volumes.
`docker compose ... down` keeps volumes; add `-v` only if you want to wipe all data.

## 8. Troubleshooting

- **No certificate / site not loading** — DNS A record not resolving yet, or ports 80/443
  blocked by the cloud firewall. Check `docker compose ... logs caddy`.
- **Backend keeps restarting / unhealthy** — check `logs backend`. Usually a missing value in
  `.env.demo` (every secret is required) or `DOMAIN` mismatch.
- **Public link shows a 404 from the frontend** — you changed the proxy rules; `/q`, `/l` and
  `/qr-assets` must route to the backend (see `infra/Caddyfile.demo`).
- **"Invalid host" on a link** — `DOMAIN` in `.env.demo` must exactly match the hostname you
  open in the browser.

## How this differs from the production stack

| | This demo stack | Production (Azure) |
|---|---|---|
| Environment mode | `development` (hardened) | `production` (fail‑closed) |
| Edge / TLS | Caddy on the VM | Front Door Premium + WAF |
| Delivery queue | In‑DB transactional outbox | Azure Service Bus |
| Secrets | `.env.demo` on the host | Azure Key Vault |
| Evidence storage | Local volume | Immutable Azure Blob |
| Schema | Auto‑created on startup | Alembic migration job |
| Real email | Configure a sender in‑app | Same, plus Front Door link serving |
