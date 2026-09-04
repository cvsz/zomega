import hashlib
import secrets
from datetime import datetime, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .config import settings

_ARGON2 = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

def generate_api_key() -> str:
    locator = secrets.token_hex(12)
    secret = secrets.token_urlsafe(32)
    return f"zomega_{locator}_{secret}"

def parse_api_key(raw: str) -> tuple[str, str]:
    if not raw.startswith("zomega_"):
        raise ValueError("Invalid zomega API key format")
    parts = raw.split("_", 2)
    if len(parts) != 3:
        raise ValueError("Invalid zomega API key format")
    _, locator, secret = parts
    if len(locator) != 24 or any(ch not in "0123456789abcdef" for ch in locator):
        raise ValueError("Invalid zomega API key locator")
    if len(secret) < 32:
        raise ValueError("zomega API key secret is too short")
    return locator, secret

def _argon2_material(secret: str) -> str:
    return f"{secret}:{settings.zomega_api_key_pepper}"

def hash_api_key_secret(secret: str) -> str:
    return _ARGON2.hash(_argon2_material(secret))

def verify_api_key_secret(stored_hash: str, secret: str) -> bool:
    try:
        return _ARGON2.verify(stored_hash, _argon2_material(secret))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False

def api_key_needs_rehash(stored_hash: str) -> bool:
    try:
        return _ARGON2.check_needs_rehash(stored_hash)
    except InvalidHashError:
        return True

def request_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()

def utcnow():
    return datetime.now(timezone.utc)
