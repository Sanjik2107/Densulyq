import hashlib
import hmac
import secrets
from typing import Optional

from config import PASSWORD_ITERATIONS, PASSWORD_SCHEME


def hash_password(password: str, *, salt: Optional[str] = None, iterations: int = PASSWORD_ITERATIONS):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"{PASSWORD_SCHEME}${iterations}${salt}${digest.hex()}"


def verify_password(password: str, encoded: Optional[str]):
    if not encoded:
        return False
    try:
        scheme, iterations_raw, salt, stored_digest = encoded.split("$", 3)
        if scheme != PASSWORD_SCHEME:
            return False
        candidate = hash_password(password, salt=salt, iterations=int(iterations_raw))
        return hmac.compare_digest(candidate, encoded)
    except Exception:
        return False
