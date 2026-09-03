import hashlib
import secrets
from datetime import datetime, timezone
from .config import settings

def generate_api_key() -> str:
    return "omega_" + secrets.token_urlsafe(36)

def digest_api_key(raw: str) -> str:
    """Return a keyed, non-reversible API-key digest for database lookup."""
    return hashlib.blake2b(
        raw.encode(),
        key=settings.omega_api_key_pepper.encode(),
        digest_size=64,
    ).hexdigest()

def request_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()

def utcnow():
    return datetime.now(timezone.utc)
