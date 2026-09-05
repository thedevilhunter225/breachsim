# Disaster recovery

Quarterly, simulate loss of the primary region. Record the PostgreSQL replay point before
promotion and prove data loss is no more than 15 minutes. Promote the cross-region Flexible
Server replica, deploy reviewed Container Apps images in the recovery region, restore private
DNS/connectivity, and switch Front Door only after `/health/ready` and tenant-host binding pass.

Verify Service Bus dead letters/scheduled work, Redis rate-limit reset behavior, Key Vault
access, immutable evidence readability, authentication/session revocation and a QR token from
an active campaign. Measure declaration-to-service time; it must be no more than four hours.
Fail back only through a reviewed runbook and preserve the exercise report as audit evidence.
