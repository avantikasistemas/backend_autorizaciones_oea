import jwt
from fastapi import Depends, Header, HTTPException, Request
from jwt import PyJWKClient
from pydantic import EmailStr, TypeAdapter, ValidationError

from app.config import get_settings
from app.storage.roles import get_user_roles, has_any_role


_jwk_client: PyJWKClient | None = None
EMAIL_ADAPTER = TypeAdapter(EmailStr)


def normalize_email(value: str | None) -> str:
    if not value:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        return str(EMAIL_ADAPTER.validate_python(value.strip())).lower()
    except (ValueError, ValidationError):
        raise HTTPException(status_code=401, detail="No autenticado") from None


def get_jwk_client() -> PyJWKClient:
    global _jwk_client
    settings = get_settings()
    if not settings.cf_access_team_domain:
        raise HTTPException(status_code=500, detail="Cloudflare Access no está configurado")

    if _jwk_client is None:
        team_domain = settings.cf_access_team_domain.rstrip("/")
        _jwk_client = PyJWKClient(f"{team_domain}/cdn-cgi/access/certs")
    return _jwk_client


async def get_current_user(
    request: Request,
    cf_access_jwt_assertion: str | None = Header(default=None),
) -> dict:
    settings = get_settings()

    if settings.allow_dev_auth and settings.env != "production":
        user = {
            "email": normalize_email(request.headers.get("x-dev-user-email", settings.dev_auth_email)),
            "name": request.headers.get("x-dev-user-name", settings.dev_auth_name),
            "groups": [],
        }
        return {**user, "roles": get_user_roles(user)}

    if not cf_access_jwt_assertion:
        raise HTTPException(status_code=401, detail="No autenticado")

    if not settings.cf_access_audience or not settings.cf_access_team_domain:
        raise HTTPException(status_code=500, detail="Cloudflare Access no está configurado")

    try:
        signing_key = get_jwk_client().get_signing_key_from_jwt(cf_access_jwt_assertion)
        payload = jwt.decode(
            cf_access_jwt_assertion,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.cf_access_audience,
            issuer=settings.cf_access_team_domain.rstrip("/"),
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="No autenticado") from None

    groups = payload.get("groups") or payload.get("identity_groups") or []
    if isinstance(groups, str):
        groups = [groups]

    email = normalize_email(payload.get("email") or payload.get("sub"))
    user = {
        "email": email,
        "name": payload.get("name") or email,
        "groups": groups,
    }
    return {**user, "roles": get_user_roles(user)}


def require_roles(roles: list[str]):
    def dependency(user: dict = Depends(get_current_user)) -> dict:
        if not has_any_role(user, roles):
            raise HTTPException(status_code=403, detail="No autorizado")
        return user

    return dependency
