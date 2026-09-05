from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.crypto import blind_index
from app.db.session import get_db
from app.models.entities import ConsentRecord, Department, Employee, OrganizationDomain, ScimCredential
from app.models.enums import ConsentStatus, DomainPurpose, EmployeeStatus, VerificationStatus
from app.services.public_tokens import token_secret_matches

router = APIRouter()
scim_bearer = HTTPBearer(auto_error=False)
SCIM_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_GROUP_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:Group"


def _scim_error(detail: str, status_code: int):
    raise HTTPException(
        status_code=status_code,
        detail={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
            "status": str(status_code),
            "detail": detail,
        },
    )


def get_scim_credential(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(scim_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> ScimCredential:
    if not credentials:
        _scim_error("Bearer token required", status.HTTP_401_UNAUTHORIZED)
    raw = credentials.credentials
    candidates = db.query(ScimCredential).filter(
        ScimCredential.token_prefix == raw[:12],
        ScimCredential.revoked_at.is_(None),
    ).all()
    credential = next((row for row in candidates if token_secret_matches(raw, row.token_hash)), None)
    if not credential:
        _scim_error("Invalid SCIM bearer token", status.HTTP_401_UNAUTHORIZED)
    credential.last_used_at = datetime.now(timezone.utc)
    db.flush()
    return credential


def _primary_email(payload: dict) -> str:
    emails = payload.get("emails") or []
    preferred = next((row for row in emails if row.get("primary")), emails[0] if emails else None)
    email = (preferred or {}).get("value", "").strip().casefold()
    if "@" not in email:
        _scim_error("A valid primary email is required", status.HTTP_400_BAD_REQUEST)
    return email


def _verify_recipient_domain(db: Session, organization_id, email: str) -> None:
    email_domain = email.rpartition("@")[2]
    domains = db.query(OrganizationDomain).filter(
        OrganizationDomain.organization_id == organization_id,
        OrganizationDomain.purpose == DomainPurpose.RECIPIENT,
        OrganizationDomain.status == VerificationStatus.ACTIVE,
    ).all()
    if not any(email_domain == row.hostname or email_domain.endswith(f".{row.hostname}") for row in domains):
        _scim_error("Email is outside the organization's verified recipient domains", status.HTTP_409_CONFLICT)


def _scim_user(employee: Employee) -> dict:
    return {
        "schemas": [SCIM_USER_SCHEMA],
        "id": str(employee.id),
        "externalId": employee.external_id,
        "userName": employee.email,
        "name": {"formatted": employee.full_name},
        "displayName": employee.full_name,
        "title": employee.role_title,
        "active": employee.status == EmployeeStatus.ACTIVE,
        "emails": [{"value": employee.email, "primary": True, "type": "work"}],
        "meta": {
            "resourceType": "User",
            "created": employee.created_at.isoformat(),
            "lastModified": employee.updated_at.isoformat(),
        },
    }


def _display_name(payload: dict, fallback: str) -> str:
    name = payload.get("name") or {}
    return (payload.get("displayName") or name.get("formatted") or fallback).strip()


def _member_ids(payload: dict) -> list[uuid.UUID]:
    values: list[uuid.UUID] = []
    for row in payload.get("members", []):
        try:
            values.append(uuid.UUID(str(row.get("value"))))
        except (TypeError, ValueError):
            _scim_error("Group member IDs must be valid UUIDs", status.HTTP_400_BAD_REQUEST)
    return values


@router.get("/Users")
def list_scim_users(
    db: Annotated[Session, Depends(get_db)],
    credential=Depends(get_scim_credential),
    filter: str | None = Query(default=None),
    startIndex: int = Query(default=1, ge=1),
    count: int = Query(default=100, ge=1, le=1000),
):
    query = db.query(Employee).filter(Employee.organization_id == credential.organization_id)
    employees = query.all()
    if filter and filter.startswith('userName eq "') and filter.endswith('"'):
        expected = filter.removeprefix('userName eq "').removesuffix('"').casefold()
        employees = [employee for employee in employees if employee.email.casefold() == expected]
    total = len(employees)
    page = employees[startIndex - 1 : startIndex - 1 + count]
    db.commit()
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": total,
        "startIndex": startIndex,
        "itemsPerPage": len(page),
        "Resources": [_scim_user(employee) for employee in page],
    }


@router.post("/Users", status_code=status.HTTP_201_CREATED)
def create_scim_user(
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    credential=Depends(get_scim_credential),
):
    email = _primary_email(payload)
    _verify_recipient_domain(db, credential.organization_id, email)
    email_hash = blind_index(email, namespace="employee-email")
    if db.query(Employee).filter(
        Employee.organization_id == credential.organization_id,
        Employee.email_blind_index == email_hash,
    ).first():
        _scim_error("User already exists", status.HTTP_409_CONFLICT)
    external_id = str(payload.get("externalId") or uuid.uuid4())
    employee = Employee(
        organization_id=credential.organization_id,
        employee_id=f"SCIM-{external_id}"[:64],
        full_name=_display_name(payload, email.split("@", 1)[0]),
        email=email,
        email_blind_index=email_hash,
        role_title=str(payload.get("title") or "Employee")[:255],
        consent_status=ConsentStatus.PENDING,
        status=EmployeeStatus.ACTIVE if payload.get("active", True) else EmployeeStatus.INACTIVE,
        directory_source="scim",
        external_id=external_id,
    )
    db.add(employee)
    db.flush()
    db.add(ConsentRecord(employee_id=employee.id, status=employee.consent_status, source="scim"))
    db.commit()
    db.refresh(employee)
    return _scim_user(employee)


@router.get("/Users/{user_id}")
def get_scim_user(
    user_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    credential=Depends(get_scim_credential),
):
    employee = db.query(Employee).filter(
        Employee.id == user_id,
        Employee.organization_id == credential.organization_id,
    ).first()
    if not employee:
        _scim_error("User not found", status.HTTP_404_NOT_FOUND)
    db.commit()
    return _scim_user(employee)


@router.put("/Users/{user_id}")
def replace_scim_user(
    user_id: uuid.UUID,
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    credential=Depends(get_scim_credential),
):
    employee = db.query(Employee).filter(
        Employee.id == user_id,
        Employee.organization_id == credential.organization_id,
    ).first()
    if not employee:
        _scim_error("User not found", status.HTTP_404_NOT_FOUND)
    email = _primary_email(payload)
    _verify_recipient_domain(db, credential.organization_id, email)
    employee.email = email
    employee.email_blind_index = blind_index(email, namespace="employee-email")
    employee.full_name = _display_name(payload, employee.full_name)
    employee.role_title = str(payload.get("title") or employee.role_title)[:255]
    employee.status = EmployeeStatus.ACTIVE if payload.get("active", True) else EmployeeStatus.INACTIVE
    employee.external_id = str(payload.get("externalId") or employee.external_id or "")
    db.commit()
    db.refresh(employee)
    return _scim_user(employee)


@router.patch("/Users/{user_id}")
def patch_scim_user(
    user_id: uuid.UUID,
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    credential=Depends(get_scim_credential),
):
    employee = db.query(Employee).filter(
        Employee.id == user_id,
        Employee.organization_id == credential.organization_id,
    ).first()
    if not employee:
        _scim_error("User not found", status.HTTP_404_NOT_FOUND)
    for operation in payload.get("Operations", []):
        action = str(operation.get("op") or "").casefold()
        path = str(operation.get("path") or "").casefold()
        value = operation.get("value")
        if action not in {"add", "replace", "remove"}:
            _scim_error("Unsupported PATCH operation", status.HTTP_400_BAD_REQUEST)
        if path == "active":
            employee.status = EmployeeStatus.ACTIVE if bool(value) and action != "remove" else EmployeeStatus.INACTIVE
        elif path in {"displayname", "name.formatted"}:
            if action != "remove" and value:
                employee.full_name = str(value)[:255]
        elif path == "title":
            employee.role_title = str(value or "Employee")[:255]
        elif path in {"username", "emails"}:
            email = str(value if path == "username" else _primary_email({"emails": value or []})).casefold()
            _verify_recipient_domain(db, credential.organization_id, email)
            employee.email = email
            employee.email_blind_index = blind_index(email, namespace="employee-email")
        elif not path and isinstance(value, dict):
            if "active" in value:
                employee.status = EmployeeStatus.ACTIVE if value["active"] else EmployeeStatus.INACTIVE
            if value.get("displayName"):
                employee.full_name = str(value["displayName"])[:255]
            if value.get("title"):
                employee.role_title = str(value["title"])[:255]
        else:
            _scim_error(f"Unsupported PATCH path: {path}", status.HTTP_400_BAD_REQUEST)
    db.commit()
    db.refresh(employee)
    return _scim_user(employee)


@router.delete("/Users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_scim_user(
    user_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    credential=Depends(get_scim_credential),
):
    employee = db.query(Employee).filter(
        Employee.id == user_id,
        Employee.organization_id == credential.organization_id,
    ).first()
    if not employee:
        _scim_error("User not found", status.HTTP_404_NOT_FOUND)
    employee.status = EmployeeStatus.INACTIVE
    db.commit()
    return None


def _scim_group(department: Department, member_count: int = 0) -> dict:
    return {
        "schemas": [SCIM_GROUP_SCHEMA],
        "id": str(department.id),
        "externalId": department.external_id,
        "displayName": department.name,
        "members": [],
        "meta": {
            "resourceType": "Group",
            "created": department.created_at.isoformat(),
            "lastModified": department.updated_at.isoformat(),
            "memberCount": member_count,
        },
    }


@router.get("/Groups")
def list_scim_groups(
    db: Annotated[Session, Depends(get_db)],
    credential=Depends(get_scim_credential),
):
    groups = db.query(Department).filter(Department.organization_id == credential.organization_id).all()
    db.commit()
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": len(groups),
        "startIndex": 1,
        "itemsPerPage": len(groups),
        "Resources": [_scim_group(group) for group in groups],
    }


@router.post("/Groups", status_code=status.HTTP_201_CREATED)
def create_scim_group(
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    credential=Depends(get_scim_credential),
):
    name = str(payload.get("displayName") or "").strip()
    if not name:
        _scim_error("displayName is required", status.HTTP_400_BAD_REQUEST)
    external_id = str(payload.get("externalId") or uuid.uuid4())
    department = Department(
        organization_id=credential.organization_id,
        name=name[:255],
        code=f"SCIM-{external_id}"[:64],
        directory_source="scim",
        external_id=external_id,
    )
    db.add(department)
    db.flush()
    member_ids = _member_ids(payload)
    if member_ids:
        db.query(Employee).filter(
            Employee.organization_id == credential.organization_id,
            Employee.id.in_(member_ids),
        ).update({Employee.department_id: department.id}, synchronize_session=False)
    db.commit()
    db.refresh(department)
    return _scim_group(department, len(member_ids))


@router.put("/Groups/{group_id}")
def replace_scim_group(
    group_id: uuid.UUID,
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    credential=Depends(get_scim_credential),
):
    department = db.query(Department).filter(
        Department.id == group_id,
        Department.organization_id == credential.organization_id,
    ).first()
    if not department:
        _scim_error("Group not found", status.HTTP_404_NOT_FOUND)
    department.name = str(payload.get("displayName") or department.name)[:255]
    member_ids = _member_ids(payload)
    db.query(Employee).filter(
        Employee.organization_id == credential.organization_id,
        Employee.department_id == department.id,
    ).update({Employee.department_id: None}, synchronize_session=False)
    if member_ids:
        db.query(Employee).filter(
            Employee.organization_id == credential.organization_id,
            Employee.id.in_(member_ids),
        ).update({Employee.department_id: department.id}, synchronize_session=False)
    db.commit()
    db.refresh(department)
    return _scim_group(department, len(member_ids))


@router.get("/Groups/{group_id}")
def get_scim_group(
    group_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    credential=Depends(get_scim_credential),
):
    department = db.query(Department).filter(
        Department.id == group_id,
        Department.organization_id == credential.organization_id,
    ).first()
    if not department:
        _scim_error("Group not found", status.HTTP_404_NOT_FOUND)
    member_count = db.query(Employee).filter(Employee.department_id == department.id).count()
    db.commit()
    return _scim_group(department, member_count)


@router.patch("/Groups/{group_id}")
def patch_scim_group(
    group_id: uuid.UUID,
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    credential=Depends(get_scim_credential),
):
    department = db.query(Department).filter(
        Department.id == group_id,
        Department.organization_id == credential.organization_id,
    ).first()
    if not department:
        _scim_error("Group not found", status.HTTP_404_NOT_FOUND)
    for operation in payload.get("Operations", []):
        action = str(operation.get("op") or "").casefold()
        path = str(operation.get("path") or "").casefold()
        value = operation.get("value")
        if path == "displayname" and action in {"add", "replace"}:
            department.name = str(value or department.name)[:255]
            continue
        if path.startswith("members") or (not path and isinstance(value, dict) and "members" in value):
            members_payload = {"members": value.get("members", [])} if isinstance(value, dict) else {"members": value or []}
            if action == "remove" and not members_payload["members"]:
                matched = re.search(r'members\[value eq "([^"]+)"\]', path, flags=re.IGNORECASE)
                if matched:
                    members_payload = {"members": [{"value": matched.group(1)}]}
            member_ids = _member_ids(members_payload)
            member_query = db.query(Employee).filter(
                Employee.organization_id == credential.organization_id,
                Employee.id.in_(member_ids),
            )
            if action == "remove":
                member_query.filter(Employee.department_id == department.id).update(
                    {Employee.department_id: None}, synchronize_session=False
                )
            elif action in {"add", "replace"}:
                if action == "replace":
                    db.query(Employee).filter(
                        Employee.organization_id == credential.organization_id,
                        Employee.department_id == department.id,
                    ).update({Employee.department_id: None}, synchronize_session=False)
                member_query.update({Employee.department_id: department.id}, synchronize_session=False)
            else:
                _scim_error("Unsupported PATCH operation", status.HTTP_400_BAD_REQUEST)
            continue
        _scim_error(f"Unsupported PATCH path: {path}", status.HTTP_400_BAD_REQUEST)
    db.commit()
    db.refresh(department)
    member_count = db.query(Employee).filter(Employee.department_id == department.id).count()
    return _scim_group(department, member_count)


@router.delete("/Groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scim_group(
    group_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    credential=Depends(get_scim_credential),
):
    department = db.query(Department).filter(
        Department.id == group_id,
        Department.organization_id == credential.organization_id,
    ).first()
    if not department:
        _scim_error("Group not found", status.HTTP_404_NOT_FOUND)
    db.query(Employee).filter(
        Employee.organization_id == credential.organization_id,
        Employee.department_id == department.id,
    ).update({Employee.department_id: None}, synchronize_session=False)
    db.delete(department)
    db.commit()
    return None
