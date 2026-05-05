from pydantic import BaseModel, EmailStr, Field, TypeAdapter, field_validator


ALLOWED_APPLICATIONS = {"WhatsApp", "YouTube", "LinkedIn"}
ALLOWED_MACROPROCESSES = {
    "ABASTECIMIENTO",
    "CAPITAL HUMANO",
    "DIRECCIONAMIENTO ESTRATÉGICO",
    "GESTIÓN DE COTIZACIONES",
    "GESTIÓN FINANCIERA",
    "INFRAESTRUCTURA",
    "LOGÍSTICA",
    "MERCADEO",
    "PRESTACIÓN DEL SERVICIO TÉCNICO",
    "SERVICIO AL CLIENTE",
    "SIG",
    "TIC",
    "VENTAS",
}
EMAIL_ADAPTER = TypeAdapter(EmailStr)


class CreateRequestPayload(BaseModel):
    requesterName: str | None = Field(default=None, max_length=120)
    requesterEmail: EmailStr | None = None
    collaboratorName: str = Field(min_length=3, max_length=120)
    collaboratorEmail: EmailStr | None = None
    area: str = Field(min_length=2, max_length=120)
    applications: list[str] = Field(min_length=1, max_length=3)
    reason: str = Field(min_length=15, max_length=1500)
    businessValue: str = Field(min_length=15, max_length=1500)
    managerName: str = Field(min_length=2, max_length=120)
    managerEmail: EmailStr
    copyEmail: str | None = ""

    @field_validator("applications")
    @classmethod
    def validate_applications(cls, values: list[str]) -> list[str]:
        unique_values = list(dict.fromkeys(values))
        invalid = [value for value in unique_values if value not in ALLOWED_APPLICATIONS]
        if invalid:
            raise ValueError("Aplicación no permitida")
        return unique_values

    @field_validator("area")
    @classmethod
    def validate_area(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in ALLOWED_MACROPROCESSES:
            raise ValueError("Macroproceso no permitido")
        return normalized

    @field_validator("copyEmail")
    @classmethod
    def validate_copy_email(cls, value: str | None) -> str:
        if not value:
            return ""
        return str(EMAIL_ADAPTER.validate_python(value.strip()))


class RolesPayload(BaseModel):
    admins: list[EmailStr] = []
    approvers: list[EmailStr] = []
    requesters: list[EmailStr] = []
