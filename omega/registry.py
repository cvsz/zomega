import base64
import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import HTTPException
from sqlalchemy import select

from .db import session_scope
from .models import Publisher, PrivateSkillVersion, PrivateSkillGrant
from .audit import record_audit

def canonical_manifest(manifest: dict) -> bytes:
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def _verify_public_key(pem: str) -> Ed25519PublicKey:
    try:
        key = load_pem_public_key(pem.encode("utf-8"))
    except Exception as exc:
        raise HTTPException(400, "Invalid publisher public key") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise HTTPException(400, "Publisher key must be Ed25519")
    return key

def create_or_update_publisher(tenant_id: str, actor_key_id: str, name: str, public_key_pem: str) -> dict:
    _verify_public_key(public_key_pem)
    with session_scope() as db:
        row = db.execute(select(Publisher).where(Publisher.tenant_id == tenant_id)).scalar_one_or_none()
        if not row:
            row = Publisher(tenant_id=tenant_id, name=name, ed25519_public_key_pem=public_key_pem, status="active")
            db.add(row)
        else:
            row.name = name
            row.ed25519_public_key_pem = public_key_pem
            row.status = "active"
        db.flush()
        publisher_id = row.id
    record_audit(tenant_id, "api_key", actor_key_id, "publisher.updated", "publisher", publisher_id, {"name": name})
    return {"id": publisher_id, "name": name, "status": "active"}

def publish_skill(
    tenant_id: str,
    actor_key_id: str,
    *,
    skill_id: str,
    version: str,
    manifest: dict,
    signature_b64: str,
) -> dict:
    body = canonical_manifest(manifest)
    digest = hashlib.sha256(body).hexdigest()
    try:
        signature = base64.b64decode(signature_b64, validate=True)
    except Exception as exc:
        raise HTTPException(400, "Invalid base64 signature") from exc

    with session_scope() as db:
        publisher = db.execute(
            select(Publisher).where(Publisher.tenant_id == tenant_id, Publisher.status == "active")
        ).scalar_one_or_none()
        if not publisher:
            raise HTTPException(404, "Publisher profile not found")
        key = _verify_public_key(publisher.ed25519_public_key_pem)
        try:
            key.verify(signature, body)
        except InvalidSignature as exc:
            raise HTTPException(400, "Manifest signature verification failed") from exc
        row = PrivateSkillVersion(
            publisher_id=publisher.id,
            skill_id=skill_id,
            version=version,
            manifest_json=manifest,
            manifest_sha256=digest,
            signature_b64=signature_b64,
            publisher_public_key_pem=publisher.ed25519_public_key_pem,
            status="active",
        )
        db.add(row)
        db.flush()
        version_id = row.id
    record_audit(
        tenant_id, "api_key", actor_key_id, "private_skill.published", "private_skill_version", version_id,
        {"skill_id": skill_id, "version": version, "manifest_sha256": digest},
    )
    return {"id": version_id, "skill_id": skill_id, "version": version, "manifest_sha256": digest, "status": "active"}

def verify_skill_version(skill_version_id: str) -> dict:
    with session_scope() as db:
        skill = db.get(PrivateSkillVersion, skill_version_id)
        if not skill:
            raise HTTPException(404, "Private skill version not found")
        body = canonical_manifest(skill.manifest_json)
        digest = hashlib.sha256(body).hexdigest()
        if digest != skill.manifest_sha256:
            return {"id": skill.id, "valid": False, "reason": "manifest_hash_mismatch"}
        try:
            signature = base64.b64decode(skill.signature_b64, validate=True)
            key = _verify_public_key(skill.publisher_public_key_pem)
            key.verify(signature, body)
        except (InvalidSignature, ValueError, HTTPException):
            return {"id": skill.id, "valid": False, "reason": "signature_invalid"}
        return {"id": skill.id, "valid": True, "manifest_sha256": digest}

def list_granted_skills(tenant_id: str) -> list[dict]:
    with session_scope() as db:
        rows = db.execute(
            select(PrivateSkillGrant, PrivateSkillVersion)
            .join(PrivateSkillVersion, PrivateSkillVersion.id == PrivateSkillGrant.skill_version_id)
            .where(PrivateSkillGrant.tenant_id == tenant_id)
            .order_by(PrivateSkillGrant.created_at.desc())
        ).all()
        return [{
            "grant_id": grant.id,
            "skill_version_id": skill.id,
            "skill_id": skill.skill_id,
            "version": skill.version,
            "manifest_sha256": skill.manifest_sha256,
            "source": grant.source,
            "created_at": grant.created_at,
        } for grant, skill in rows]
