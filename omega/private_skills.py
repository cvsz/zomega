import hashlib
import json
import re

from fastapi import HTTPException
from sqlalchemy import select

from .audit import record_audit
from .db import session_scope
from .models import PrivateSkill

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,118}[a-z0-9]$")
REQUIRED_FIELDS = {"name", "description", "entrypoint", "permissions"}

def canonical_manifest(manifest: dict) -> bytes:
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def manifest_digest(manifest: dict) -> str:
    return hashlib.sha256(canonical_manifest(manifest)).hexdigest()

def validate_manifest(manifest: dict) -> None:
    missing = REQUIRED_FIELDS - set(manifest)
    if missing:
        raise HTTPException(400, f"Missing manifest fields: {sorted(missing)}")
    permissions = manifest.get("permissions")
    if not isinstance(permissions, list) or not all(isinstance(x, str) for x in permissions):
        raise HTTPException(400, "permissions must be a list of strings")
    if manifest.get("entrypoint") not in {"openai.responses", "workflow"}:
        raise HTTPException(400, "Unsupported private skill entrypoint")

def register_private_skill(
    tenant_id: str,
    actor_key_id: str,
    slug: str,
    version: str,
    manifest: dict,
) -> dict:
    if not SLUG_RE.match(slug):
        raise HTTPException(400, "Invalid skill slug")
    if not version or len(version) > 40:
        raise HTTPException(400, "Invalid skill version")
    validate_manifest(manifest)
    digest = manifest_digest(manifest)
    with session_scope() as db:
        row = PrivateSkill(
            tenant_id=tenant_id,
            slug=slug,
            version=version,
            manifest_json=manifest,
            manifest_hash=digest,
            status="active",
        )
        db.add(row)
        db.flush()
        skill_id = row.id
    record_audit(tenant_id, "api_key", actor_key_id, "private_skill.registered", "private_skill", skill_id, {"slug": slug, "version": version, "manifest_hash": digest})
    return {"id": skill_id, "slug": slug, "version": version, "manifest_hash": digest, "status": "active"}

def list_private_skills(tenant_id: str) -> list[dict]:
    with session_scope() as db:
        rows = db.execute(
            select(PrivateSkill)
            .where(PrivateSkill.tenant_id == tenant_id)
            .order_by(PrivateSkill.created_at.desc())
        ).scalars().all()
        return [{
            "id": r.id,
            "slug": r.slug,
            "version": r.version,
            "manifest": r.manifest_json,
            "manifest_hash": r.manifest_hash,
            "integrity_ok": manifest_digest(r.manifest_json) == r.manifest_hash,
            "status": r.status,
            "created_at": r.created_at,
        } for r in rows]

def set_private_skill_status(tenant_id: str, actor_key_id: str, skill_id: str, status: str) -> dict:
    if status not in {"active", "disabled", "revoked"}:
        raise HTTPException(400, "Invalid private skill status")
    with session_scope() as db:
        row = db.execute(
            select(PrivateSkill)
            .where(PrivateSkill.id == skill_id, PrivateSkill.tenant_id == tenant_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not row:
            raise HTTPException(404, "Private skill not found")
        if manifest_digest(row.manifest_json) != row.manifest_hash:
            raise HTTPException(409, "Private skill manifest integrity failure")
        row.status = status
    record_audit(tenant_id, "api_key", actor_key_id, "private_skill.status_changed", "private_skill", skill_id, {"status": status})
    return {"id": skill_id, "status": status}
