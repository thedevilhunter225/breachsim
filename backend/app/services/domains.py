from __future__ import annotations

import ipaddress
import re
import secrets
from datetime import datetime, timezone

import dns.resolver
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import is_production_environment, settings
from app.models.entities import Organization, OrganizationDomain
from app.models.enums import DomainKind, DomainPurpose, VerificationStatus
from app.services.public_tokens import hash_token_secret, token_secret_matches

HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def normalize_hostname(value: str, *, allow_port: bool = False) -> str:
    hostname = value.strip().rstrip(".").casefold()
    if "://" in hostname or "/" in hostname or "@" in hostname:
        raise ValueError("hostname must not include a scheme, path, or credentials")

    port = ""
    if allow_port and hostname.count(":") == 1:
        hostname, raw_port = hostname.rsplit(":", 1)
        if not raw_port.isdigit() or not 1 <= int(raw_port) <= 65535:
            raise ValueError("invalid hostname port")
        port = f":{raw_port}"
    elif ":" in hostname:
        raise ValueError("ports are not allowed on verified domains")

    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ValueError("IP addresses cannot be verified as organization domains")

    try:
        ascii_hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("invalid internationalized hostname") from exc
    if len(ascii_hostname) > 253 or len(ascii_hostname.split(".")) < 2 and ascii_hostname != "localhost":
        raise ValueError("hostname must be a valid DNS name")
    if ascii_hostname != "localhost" and any(not HOST_LABEL.fullmatch(label) for label in ascii_hostname.split(".")):
        raise ValueError("hostname contains an invalid DNS label")
    return f"{ascii_hostname}{port}"


def platform_hostname_for(org: Organization) -> str:
    root = normalize_hostname(settings.platform_training_domain, allow_port=not is_production_environment(settings.environment))
    if root.startswith("localhost"):
        return root
    return f"{org.slug}.{root}"


def ensure_platform_landing_domain(db: Session, org: Organization) -> OrganizationDomain:
    hostname = platform_hostname_for(org)
    existing = (
        db.query(OrganizationDomain)
        .filter(
            OrganizationDomain.organization_id == org.id,
            OrganizationDomain.hostname == hostname,
            OrganizationDomain.purpose == DomainPurpose.LANDING,
        )
        .first()
    )
    if existing:
        return existing
    domain = OrganizationDomain(
        organization_id=org.id,
        hostname=hostname,
        purpose=DomainPurpose.LANDING,
        kind=DomainKind.PLATFORM,
        status=VerificationStatus.ACTIVE,
        is_primary=True,
        verified_at=datetime.now(timezone.utc),
        dns_instructions={},
    )
    db.add(domain)
    db.flush()
    return domain


def create_custom_domain(
    db: Session,
    *,
    org: Organization,
    hostname: str,
    purpose: DomainPurpose,
) -> tuple[OrganizationDomain, str]:
    try:
        normalized = normalize_hostname(hostname)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    existing = (
        db.query(OrganizationDomain)
        .filter(OrganizationDomain.hostname == normalized, OrganizationDomain.purpose == purpose)
        .first()
    )
    if existing:
        if existing.organization_id == org.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Domain already exists")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Domain is claimed by another organization")

    verification_secret = secrets.token_urlsafe(24)
    txt_name = f"_breachsim-verification.{normalized}"
    txt_value = f"breachsim-verification={verification_secret}"
    instructions: dict[str, str] = {
        "txt_name": txt_name,
        "txt_value_format": "breachsim-verification=<one-time-value>",
    }
    if purpose == DomainPurpose.LANDING:
        platform_root = normalize_hostname(
            settings.platform_training_domain,
            allow_port=not is_production_environment(settings.environment),
        ).split(":", 1)[0]
        edge_target = (
            settings.front_door_endpoint_hostname
            if is_production_environment(settings.environment) and settings.front_door_endpoint_hostname
            else f"edge.{platform_root}"
            if platform_root != "localhost"
            else "localhost"
        )
        instructions.update({"cname_name": normalized, "cname_target": edge_target})

    domain = OrganizationDomain(
        organization_id=org.id,
        hostname=normalized,
        purpose=purpose,
        kind=DomainKind.CUSTOM,
        status=VerificationStatus.PENDING,
        verification_token_hash=hash_token_secret(verification_secret),
        dns_instructions=instructions,
    )
    db.add(domain)
    db.flush()
    return domain, txt_value


def verify_custom_domain(domain: OrganizationDomain, *, proof: str | None = None) -> None:
    if domain.kind == DomainKind.PLATFORM:
        domain.status = VerificationStatus.ACTIVE
        domain.verified_at = domain.verified_at or datetime.now(timezone.utc)
        return

    supplied_values: list[str]
    if proof and not is_production_environment(settings.environment):
        supplied_values = [proof]
    else:
        try:
            answers = dns.resolver.resolve(f"_breachsim-verification.{domain.hostname}", "TXT", lifetime=5)
            supplied_values = [b"".join(answer.strings).decode("utf-8") for answer in answers]
        except Exception as exc:
            domain.status = VerificationStatus.FAILED
            domain.validation_error = "Verification TXT record was not found"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Verification TXT record was not found",
            ) from exc

    secrets_to_check = [value.partition("=")[2] for value in supplied_values if value.startswith("breachsim-verification=")]
    if not any(token_secret_matches(secret, domain.verification_token_hash) for secret in secrets_to_check):
        domain.status = VerificationStatus.FAILED
        domain.validation_error = "Verification TXT value did not match"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=domain.validation_error)

    domain.status = (
        VerificationStatus.VERIFIED
        if domain.purpose == DomainPurpose.LANDING and is_production_environment(settings.environment)
        else VerificationStatus.ACTIVE
    )
    domain.verified_at = datetime.now(timezone.utc)
    domain.validation_error = None


def primary_landing_domain(db: Session, organization_id) -> OrganizationDomain | None:
    return (
        db.query(OrganizationDomain)
        .filter(
            OrganizationDomain.organization_id == organization_id,
            OrganizationDomain.purpose == DomainPurpose.LANDING,
            OrganizationDomain.status == VerificationStatus.ACTIVE,
            OrganizationDomain.is_primary.is_(True),
        )
        .first()
    )


def public_origin(hostname: str) -> str:
    return f"{settings.public_url_scheme}://{hostname}"
