from fastapi import HTTPException
from sqlalchemy import select

from .audit import record_audit
from .db import session_scope
from .key_service import create_api_key_record, revoke_api_key
from .models import Organization, OrganizationMember, ServiceAccount

ROLES = {"owner", "admin", "developer", "viewer", "billing"}
ROLE_SCOPES = {
    "owner": ["agents:run", "skills:run", "billing:read", "billing:write", "runs:read", "runs:cancel", "keys:read", "keys:write", "audit:read", "orgs:read", "orgs:write", "private_skills:read", "private_skills:write", "marketplace:read", "marketplace:write"],
    "admin": ["agents:run", "skills:run", "billing:read", "runs:read", "runs:cancel", "keys:read", "keys:write", "audit:read", "orgs:read", "orgs:write", "private_skills:read", "private_skills:write", "marketplace:read"],
    "developer": ["agents:run", "skills:run", "runs:read", "orgs:read", "private_skills:read", "private_skills:write"],
    "viewer": ["billing:read", "runs:read", "orgs:read", "private_skills:read", "marketplace:read"],
    "billing": ["billing:read", "billing:write", "orgs:read", "marketplace:read"],
}

def create_organization(tenant_id: str, actor_key_id: str, name: str) -> dict:
    with session_scope() as db:
        org = Organization(tenant_id=tenant_id, name=name)
        db.add(org)
        db.flush()
        org_id = org.id
    record_audit(tenant_id, "api_key", actor_key_id, "organization.created", "organization", org_id, {"name": name})
    return {"id": org_id, "name": name}

def list_organizations(tenant_id: str) -> list[dict]:
    with session_scope() as db:
        rows = db.execute(
            select(Organization).where(Organization.tenant_id == tenant_id).order_by(Organization.created_at)
        ).scalars().all()
        return [{"id": row.id, "name": row.name, "created_at": row.created_at} for row in rows]

def add_member(tenant_id: str, actor_key_id: str, org_id: str, subject: str, role: str) -> dict:
    if role not in ROLES:
        raise HTTPException(400, "Unknown role")
    with session_scope() as db:
        org = db.execute(
            select(Organization).where(Organization.id == org_id, Organization.tenant_id == tenant_id)
        ).scalar_one_or_none()
        if not org:
            raise HTTPException(404, "Organization not found")
        member = OrganizationMember(organization_id=org_id, subject=subject, role=role)
        db.add(member)
        db.flush()
        member_id = member.id
    record_audit(tenant_id, "api_key", actor_key_id, "organization.member_added", "organization_member", member_id, {"organization_id": org_id, "subject": subject, "role": role})
    return {"id": member_id, "organization_id": org_id, "subject": subject, "role": role}

def list_members(tenant_id: str, org_id: str) -> list[dict]:
    with session_scope() as db:
        org = db.execute(
            select(Organization).where(Organization.id == org_id, Organization.tenant_id == tenant_id)
        ).scalar_one_or_none()
        if not org:
            raise HTTPException(404, "Organization not found")
        rows = db.execute(
            select(OrganizationMember)
            .where(OrganizationMember.organization_id == org_id)
            .order_by(OrganizationMember.created_at)
        ).scalars().all()
        return [{"id": r.id, "subject": r.subject, "role": r.role, "created_at": r.created_at} for r in rows]

def create_service_account(
    tenant_id: str,
    actor_key_id: str,
    org_id: str | None,
    name: str,
    role: str,
) -> dict:
    if role not in ROLE_SCOPES:
        raise HTTPException(400, "Unknown role")
    if org_id:
        with session_scope() as db:
            org = db.execute(
                select(Organization).where(Organization.id == org_id, Organization.tenant_id == tenant_id)
            ).scalar_one_or_none()
            if not org:
                raise HTTPException(404, "Organization not found")

    with session_scope() as db:
        key, raw = create_api_key_record(
            db,
            tenant_id=tenant_id,
            name=f"svc:{name}",
            scopes=ROLE_SCOPES[role],
        )
        sa = ServiceAccount(
            tenant_id=tenant_id,
            organization_id=org_id,
            api_key_id=key.id,
            name=name,
            status="active",
        )
        db.add(sa)
        db.flush()
        service_account_id = sa.id
        key_id = key.id
        scopes = list(key.scopes)
    record_audit(tenant_id, "api_key", actor_key_id, "service_account.created", "service_account", service_account_id, {"organization_id": org_id, "role": role, "api_key_id": key_id})
    return {
        "service_account_id": service_account_id,
        "organization_id": org_id,
        "role": role,
        "id": key_id,
        "api_key": raw,
        "scopes": scopes,
        "warning": "This service-account API key is returned once. Store it securely.",
    }

def disable_service_account(tenant_id: str, actor_key_id: str, service_account_id: str) -> dict:
    with session_scope() as db:
        sa = db.execute(
            select(ServiceAccount)
            .where(ServiceAccount.id == service_account_id, ServiceAccount.tenant_id == tenant_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not sa:
            raise HTTPException(404, "Service account not found")
        api_key_id = sa.api_key_id
        sa.status = "disabled"
    revoke_api_key(tenant_id, actor_key_id, api_key_id)
    record_audit(tenant_id, "api_key", actor_key_id, "service_account.disabled", "service_account", service_account_id, {})
    return {"id": service_account_id, "status": "disabled"}
