# Deployment notes

`docker-compose.yml` is the local development/demo stack. It exposes PostgreSQL and Redis and
may use the SMTP adapter only for allowlisted test mailboxes. It is not an enterprise delivery
topology.

The supported production topology is defined in `infra/terraform`: Front Door Premium/WAF,
private Container Apps, Service Bus Premium workers, Azure Managed Redis, PostgreSQL Flexible
Server HA/replica, Key Vault and immutable evidence storage. Follow
[production-deployment.md](production-deployment.md) and the runbooks under `docs/runbooks`.

`docker-compose.production.yml` is retained only as a single-host evaluation reference. It
does not satisfy the 99.9% availability, 15-minute RPO, four-hour RTO, managed-secret,
multi-tenant custom-domain or 50,000-recipient launch requirements and must not be presented
to customers as the production service.
