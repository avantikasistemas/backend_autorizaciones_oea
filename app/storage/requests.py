import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.storage.database import get_connection


def to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def parse_applications(value: str | None) -> list[str]:
    try:
        return json.loads(value or "[]")
    except json.JSONDecodeError:
        return []


def split_applications(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def get_value(row: Any, name: str, default: Any = None) -> Any:
    return getattr(row, name, default)


def map_request(row: Any, audit_trail: list[dict] | None = None) -> dict:
    requested_applications = parse_applications(row.Aplicaciones)
    requester_name = row.NombreSolicitante
    requester_email = row.CorreoSolicitante
    collaborator_name = get_value(row, "NombreColaborador", requester_name)
    collaborator_email = get_value(row, "CorreoColaborador", requester_email)
    approved_applications = (
        split_applications(row.AplicacionResumen)
        if row.Estado in (
            "Aprobado parcial por Gerencia",
            "Aprobado por Gerencia",
            "Aplicación habilitada por el Coordinador TIC",
        )
        else []
    )

    return {
        "id": str(row.Id),
        "requestNumber": row.NumeroSolicitud,
        "requesterName": requester_name,
        "requesterEmail": requester_email,
        "collaboratorName": collaborator_name,
        "collaboratorEmail": collaborator_email,
        "employeeName": collaborator_name,
        "employeeEmail": collaborator_email,
        "area": row.Area,
        "applications": requested_applications,
        "requestedApplications": requested_applications,
        "approvedApplications": approved_applications,
        "reason": row.Motivo,
        "businessValue": row.AporteProceso,
        "managerName": row.NombreGerente,
        "managerEmail": row.CorreoGerente,
        "copyEmail": row.CorreoCopia or "",
        "application": row.AplicacionResumen,
        "status": row.Estado,
        "createdAt": to_iso(row.FechaCreacion),
        "approvedAt": to_iso(row.FechaAprobacion),
        "rejectedAt": to_iso(row.FechaRechazo),
        "activatedAt": to_iso(row.FechaActivacion),
        "managerApproval": row.AprobacionGerencia,
        "ticResponsible": row.ResponsableTic,
        "auditTrail": audit_trail or [],
    }


def get_audit_trail(cursor, request_id: str) -> list[dict]:
    cursor.execute(
        """
        SELECT Fecha, Accion, Responsable
        FROM dbo.TrazabilidadSolicitudes
        WHERE SolicitudId = ?
        ORDER BY Fecha ASC, Id ASC
        """,
        request_id,
    )
    return [
        {"date": to_iso(row.Fecha), "action": row.Accion, "responsible": row.Responsable}
        for row in cursor.fetchall()
    ]


def hydrate_request(cursor, row: Any | None) -> dict | None:
    if row is None:
        return None
    return map_request(row, get_audit_trail(cursor, str(row.Id)))


def list_requests() -> list[dict]:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM dbo.Solicitudes ORDER BY FechaCreacion DESC")
        rows = cursor.fetchall()
        return [hydrate_request(cursor, row) for row in rows]


def list_requests_by_email(email: str) -> list[dict]:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT *
            FROM dbo.Solicitudes
            WHERE LOWER(CorreoSolicitante) = LOWER(?)
            ORDER BY FechaCreacion DESC
            """,
            email,
        )
        rows = cursor.fetchall()
        return [hydrate_request(cursor, row) for row in rows]


def find_request(request_id: str) -> dict | None:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM dbo.Solicitudes WHERE Id = ?", request_id)
        return hydrate_request(cursor, cursor.fetchone())


def require_request(request_id: str) -> dict:
    request = find_request(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return request


def get_next_request_number(cursor) -> str:
    cursor.execute(
        """
        SELECT MAX(TRY_CAST(SUBSTRING(NumeroSolicitud, 4, 20) AS INT)) AS HighestNumber
        FROM dbo.Solicitudes
        WHERE NumeroSolicitud LIKE 'AW-%'
        """
    )
    highest_number = cursor.fetchone().HighestNumber or 0
    return f"AW-{highest_number + 1:04d}"


def insert_audit_trail(cursor, request: dict, audit_items: list[dict]) -> None:
    for item in audit_items:
        cursor.execute(
            """
            INSERT INTO dbo.TrazabilidadSolicitudes (SolicitudId, Fecha, Accion, Responsable)
            VALUES (?, ?, ?, ?)
            """,
            request["id"],
            item["date"],
            item["action"],
            item["responsible"],
        )


def create_request(payload: dict, user: dict) -> dict:
    payload["collaboratorEmail"] = payload.get("collaboratorEmail") or payload["requesterEmail"]

    with get_connection() as connection:
        cursor = connection.cursor()
        now = datetime.now(timezone.utc)
        request = {
            "id": str(uuid.uuid4()),
            "requestNumber": get_next_request_number(cursor),
            **payload,
            "application": ", ".join(payload["applications"]),
            "status": "Pendiente aprobación Gerencia",
            "createdAt": now,
            "approvedAt": None,
            "rejectedAt": None,
            "activatedAt": None,
            "managerApproval": None,
            "ticResponsible": "Coordinador TIC",
            "auditTrail": [
                {
                    "date": now,
                    "action": "Solicitud creada por el usuario",
                    "responsible": user["email"],
                }
            ],
        }
        cursor.execute(
            """
            INSERT INTO dbo.Solicitudes (
              Id, NumeroSolicitud, NombreSolicitante, CorreoSolicitante, NombreColaborador, CorreoColaborador,
              Area, Aplicaciones, Motivo, AporteProceso, NombreGerente, CorreoGerente, CorreoCopia, AplicacionResumen, Estado,
              FechaCreacion, ResponsableTic
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            request["id"],
            request["requestNumber"],
            request["requesterName"],
            request["requesterEmail"],
            request["collaboratorName"],
            request["collaboratorEmail"],
            request["area"],
            json.dumps(request["applications"]),
            request["reason"],
            request["businessValue"],
            request["managerName"],
            request["managerEmail"],
            request.get("copyEmail") or None,
            request["application"],
            request["status"],
            request["createdAt"],
            request["ticResponsible"],
        )
        insert_audit_trail(cursor, request, request["auditTrail"])
        connection.commit()

    return {**request, "createdAt": to_iso(request["createdAt"])}


def update_request(request_id: str, updater) -> dict:
    current = require_request(request_id)
    updated = updater(current)
    new_audit_items = updated["auditTrail"][len(current["auditTrail"]) :]

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE dbo.Solicitudes
            SET Estado = ?,
                Aplicaciones = ?,
                AplicacionResumen = ?,
                FechaAprobacion = ?,
                FechaRechazo = ?,
                FechaActivacion = ?,
                AprobacionGerencia = ?
            WHERE Id = ?
            """,
            updated["status"],
            json.dumps(updated.get("requestedApplications") or updated["applications"]),
            updated.get("application") or ", ".join(updated["applications"]),
            updated.get("approvedAt"),
            updated.get("rejectedAt"),
            updated.get("activatedAt"),
            updated.get("managerApproval"),
            updated["id"],
        )
        insert_audit_trail(cursor, updated, new_audit_items)
        connection.commit()

    return updated
