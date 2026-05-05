from app.config import get_settings
from app.storage.database import get_connection


def normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def read_role_assignments() -> dict[str, list[str]]:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT Correo, Rol FROM dbo.RolesUsuarios")
        rows = cursor.fetchall()

    roles = {"admins": [], "approvers": [], "requesters": []}
    for correo, rol in rows:
        if rol == "admin":
            roles["admins"].append(correo)
        if rol == "approver":
            roles["approvers"].append(correo)
        if rol == "requester":
            roles["requesters"].append(correo)
    return roles


def get_user_roles(user: dict) -> list[str]:
    settings = get_settings()
    email = normalize(user.get("email"))
    assignments = read_role_assignments()
    roles = []

    admin_emails = [normalize(item) for item in settings.admin_email_list + assignments["admins"]]
    approver_emails = [normalize(item) for item in settings.approver_email_list + assignments["approvers"]]
    requester_emails = [normalize(item) for item in settings.requester_email_list + assignments["requesters"]]

    if email in admin_emails:
        roles.extend(["admin", "approver", "requester"])

    if email in approver_emails:
        roles.append("approver")

    if email in requester_emails:
        roles.append("requester")

    return sorted(set(roles))


def has_any_role(user: dict, roles: list[str]) -> bool:
    return any(role in user.get("roles", []) for role in roles)


def email_has_any_role(email: str, roles: list[str]) -> bool:
    return has_any_role({"email": email, "roles": get_user_roles({"email": email})}, roles)


def write_role_assignments(roles: dict[str, list[str]]) -> dict[str, list[str]]:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM dbo.RolesUsuarios")
        for email in roles.get("admins", []):
            cursor.execute(
                "INSERT INTO dbo.RolesUsuarios (Correo, Rol) VALUES (?, 'admin')",
                email.strip().lower(),
            )
        for email in roles.get("approvers", []):
            cursor.execute(
                "INSERT INTO dbo.RolesUsuarios (Correo, Rol) VALUES (?, 'approver')",
                email.strip().lower(),
            )
        for email in roles.get("requesters", []):
            cursor.execute(
                "INSERT INTO dbo.RolesUsuarios (Correo, Rol) VALUES (?, 'requester')",
                email.strip().lower(),
            )
        connection.commit()

    return read_role_assignments()
