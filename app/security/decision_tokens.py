import base64
import json
import os
import time
from hashlib import sha256

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException

from app.config import get_settings


def b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def get_key() -> bytes:
    return sha256(get_settings().decision_token_secret.encode("utf-8")).digest()


def create_decision_token(
    *,
    request_id: str,
    action: str,
    approver_email: str,
    applications: list[str] | None = None,
) -> str:
    settings = get_settings()
    payload = {
        "requestId": request_id,
        "action": action,
        "approverEmail": approver_email,
        "applications": applications,
        "expiresAt": int(time.time() * 1000) + settings.decision_token_ttl_minutes * 60 * 1000,
    }
    aesgcm = AESGCM(get_key())
    nonce = os.urandom(12)
    encrypted = aesgcm.encrypt(nonce, json.dumps(payload).encode("utf-8"), None)
    return ".".join(["v2", b64url_encode(nonce), b64url_encode(encrypted)])


def verify_decision_token(token: str) -> dict:
    try:
        version, nonce, encrypted = token.split(".")
        if version != "v2":
            raise ValueError

        aesgcm = AESGCM(get_key())
        plaintext = aesgcm.decrypt(b64url_decode(nonce), b64url_decode(encrypted), None)
        decision = json.loads(plaintext.decode("utf-8"))
    except (ValueError, InvalidTag, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Token de decisión inválido") from None

    if int(time.time() * 1000) > decision["expiresAt"]:
        raise HTTPException(status_code=410, detail="El enlace de aprobación venció")

    return decision
