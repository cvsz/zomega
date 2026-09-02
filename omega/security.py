import hashlib, hmac, secrets
from datetime import datetime, timezone
from .config import settings

def generate_api_key() -> str:
    return "omega_" + secrets.token_urlsafe(36)

def digest_api_key(raw: str) -> str:
    return hmac.new(
        settings.omega_api_key_pepper.encode(),
        raw.encode(),
        hashlib.sha256,
    ).hexdigest()

def request_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()

def utcnow():
    return datetime.now(timezone.utc)
