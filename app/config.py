from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


def parse_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def get_hostname(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    return parsed.hostname


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    node_env: str = "development"
    port: int = 3000
    public_app_url: str = "http://localhost:3000"
    frontend_origin: str = "http://localhost:5173"

    allow_dev_auth: bool = False
    dev_auth_email: str = "admin@example.com"
    dev_auth_name: str = "Development User"

    cf_access_team_domain: str | None = None
    cf_access_audience: str | None = None

    admin_emails: str = ""
    approver_emails: str = ""
    requester_emails: str = ""

    driver: str = "ODBC Driver 18 for SQL Server"
    db_user: str | None = None
    db_pass: str | None = None
    db_host: str | None = None
    db_port: int = 1433
    db_name: str | None = None
    encrypt: str = "yes"
    trust_certificate: str = "no"

    decision_token_secret: str = "development-only-change-me"
    decision_token_ttl_minutes: int = 4320

    mail_provider: str = "console"
    graph_tenant_id: str | None = None
    graph_client_id: str | None = None
    graph_client_secret: str | None = None
    graph_from_email: str | None = None

    @property
    def env(self) -> str:
        return self.node_env

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    @property
    def admin_email_list(self) -> list[str]:
        return parse_list(self.admin_emails)

    @property
    def approver_email_list(self) -> list[str]:
        return parse_list(self.approver_emails)

    @property
    def requester_email_list(self) -> list[str]:
        return parse_list(self.requester_emails)

    @property
    def sql_connection_string(self) -> str:
        if not all([self.db_host, self.db_name, self.db_user, self.db_pass]):
            raise RuntimeError("SQL Server environment variables are incomplete")

        return (
            f"DRIVER={{{self.driver}}};"
            f"SERVER={self.db_host},{self.db_port};"
            f"DATABASE={self.db_name};"
            f"UID={self.db_user};"
            f"PWD={self.db_pass};"
            f"Encrypt={self.encrypt};"
            f"TrustServerCertificate={self.trust_certificate};"
        )

    @property
    def allowed_hosts(self) -> list[str]:
        hosts = {
            get_hostname(self.public_app_url),
            get_hostname(self.frontend_origin),
        }
        if not self.is_production:
            hosts.update({"localhost", "127.0.0.1", "0.0.0.0"})
        return sorted(host for host in hosts if host)

    @property
    def cors_origins(self) -> list[str]:
        origins = {self.frontend_origin.rstrip("/")}
        if not self.is_production:
            origins.update({"http://localhost:5173", "http://127.0.0.1:5173"})
        return sorted(origin for origin in origins if origin)

    def validate_production_settings(self) -> None:
        if not self.is_production:
            return

        errors = []
        local_values = ("localhost", "127.0.0.1", "0.0.0.0")

        if self.allow_dev_auth:
            errors.append("ALLOW_DEV_AUTH debe estar en false")
        if not self.cf_access_team_domain or not self.cf_access_audience:
            errors.append("Cloudflare Access debe tener CF_ACCESS_TEAM_DOMAIN y CF_ACCESS_AUDIENCE")
        if self.public_app_url.startswith("http://") or any(value in self.public_app_url for value in local_values):
            errors.append("PUBLIC_APP_URL debe ser una URL HTTPS publica")
        if self.frontend_origin.startswith("http://") or any(value in self.frontend_origin for value in local_values):
            errors.append("FRONTEND_ORIGIN debe ser una URL HTTPS publica")
        if self.decision_token_secret == "development-only-change-me" or len(self.decision_token_secret) < 32:
            errors.append("DECISION_TOKEN_SECRET debe ser unico y tener al menos 32 caracteres")
        if self.mail_provider != "graph":
            errors.append("MAIL_PROVIDER debe ser graph")
        if not all([self.graph_tenant_id, self.graph_client_id, self.graph_client_secret, self.graph_from_email]):
            errors.append("Microsoft Graph debe estar completamente configurado")
        if self.encrypt.lower() not in {"yes", "true", "mandatory"}:
            errors.append("ENCRYPT debe estar activo para SQL Server")
        if self.trust_certificate.lower() in {"yes", "true"}:
            errors.append("TRUST_CERTIFICATE debe estar desactivado con certificado valido")

        if errors:
            detail = "; ".join(errors)
            raise RuntimeError(f"Configuracion insegura para produccion: {detail}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
