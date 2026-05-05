from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from app.mail.mailer import (
    send_approval_request_mail,
    send_decision_notification_mail,
    send_tic_activation_mail,
)
from app.schemas.requests import CreateRequestPayload, RolesPayload
from app.security.auth import get_current_user, require_roles
from app.security.decision_tokens import verify_decision_token
from app.storage.requests import (
    create_request,
    list_requests,
    list_requests_by_email,
    require_request,
    update_request,
)
from app.storage.roles import email_has_any_role, has_any_role, read_role_assignments, write_role_assignments


router = APIRouter(prefix="/api")


def get_display_name(user: dict) -> str:
    name = (user.get("name") or "").strip()
    if name and name != "Development User":
        return name

    email = (user.get("email") or "").strip()
    local_part = email.split("@", 1)[0]
    return local_part.replace(".", " ").replace("_", " ").replace("-", " ").title() or "Usuario"


def get_approved_applications(request: dict, selected_applications: list[str] | None) -> list[str]:
    requested_applications = request.get("requestedApplications") or request["applications"]
    if not selected_applications:
        return requested_applications

    approved = [app for app in selected_applications if app in requested_applications]
    if not approved:
        raise HTTPException(
            status_code=400,
            detail="La decisión no contiene aplicaciones válidas para esta solicitud",
        )
    return list(dict.fromkeys(approved))


def get_decision_result_label(request: dict) -> str:
    if request["status"] == "Aprobado parcial por Gerencia":
        return "Aprobado Parcial"
    if request["status"] == "Aprobado por Gerencia":
        return "Aprobado TOTAL"
    if request["status"] == "Rechazado por Gerencia":
        return "Rechazado"
    return request["status"]


def decision_result_html(label: str) -> str:
    return f"""<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{label}</title>
    <style>
      body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; font-family: system-ui, sans-serif; background: #ffffff; color: #243347; }}
      h1 {{ margin: 0; font-size: clamp(32px, 6vw, 54px); line-height: 1.1; text-align: center; }}
    </style>
  </head>
  <body>
    <h1>{label}</h1>
  </body>
</html>"""


def apply_manager_decision(
    *,
    request_id: str,
    action: str,
    responsible: str,
    applications: list[str] | None = None,
) -> dict:
    now = datetime.now(timezone.utc)

    def updater(current: dict) -> dict:
        if current.get("rejectedAt") or current.get("activatedAt"):
            raise HTTPException(status_code=409, detail="La solicitud ya tiene una decisión registrada")
        if action == "reject" and current.get("approvedApplications"):
            raise HTTPException(status_code=409, detail="La solicitud ya tiene aprobaciones registradas")
        if action == "approve" and current["status"] == "Aprobado por Gerencia":
            raise HTTPException(status_code=409, detail="La solicitud ya fue aprobada totalmente")

        approved = action == "approve"
        requested_apps = current.get("requestedApplications") or current["applications"]
        current_approved_apps = current.get("approvedApplications") or []
        selected_approved_apps = get_approved_applications(current, applications) if approved else []
        approved_apps = list(dict.fromkeys([*current_approved_apps, *selected_approved_apps]))
        rejected_apps = [app for app in requested_apps if app not in approved_apps] if approved else requested_apps
        partial = approved and len(approved_apps) < len(requested_apps)
        application_summary = ", ".join(approved_apps if approved else requested_apps)

        if approved:
            status = "Aprobado parcial por Gerencia" if partial else "Aprobado por Gerencia"
            manager_approval = "PARCIAL" if partial else "SI"
            action_text = (
                f"Solicitud aprobada parcialmente. Aprobadas acumuladas: {', '.join(approved_apps)}. "
                f"Pendientes: {', '.join(rejected_apps)}"
                if partial
                else f"Solicitud aprobada totalmente. Aprobadas: {', '.join(approved_apps)}"
            )
        else:
            status = "Rechazado por Gerencia"
            manager_approval = "NO"
            action_text = "Solicitud rechazada por Gerencia"

        return {
            **current,
            "applications": requested_apps,
            "requestedApplications": requested_apps,
            "approvedApplications": approved_apps,
            "application": application_summary,
            "status": status,
            "managerApproval": manager_approval,
            "approvedAt": (current.get("approvedAt") or now) if approved else None,
            "rejectedAt": None if approved else now,
            "auditTrail": [
                *current["auditTrail"],
                {"date": now, "action": action_text, "responsible": responsible},
            ],
        }

    return update_request(request_id, updater)


def ensure_decision_actor(decision: dict, user: dict) -> None:
    expected = (decision.get("approverEmail") or "").lower()
    current = (user.get("email") or "").lower()
    if not expected:
        raise HTTPException(status_code=400, detail="El enlace no tiene aprobador asociado")
    if not has_any_role(user, ["approver", "admin"]):
        raise HTTPException(status_code=403, detail="No autorizado")
    if expected != current and not has_any_role(user, ["admin"]):
        raise HTTPException(status_code=403, detail="No autorizado")


def ensure_requester_actor(payload: CreateRequestPayload, user: dict) -> None:
    if not has_any_role(user, ["requester", "admin"]):
        raise HTTPException(status_code=403, detail="No autorizado para crear solicitudes")


def ensure_approver_target(email: str) -> None:
    if not email_has_any_role(email, ["approver", "admin"]):
        raise HTTPException(status_code=400, detail="El aprobador seleccionado no está autorizado")


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"user": user}


@router.get("/roles")
async def get_roles(_: dict = Depends(require_roles(["admin"]))):
    return {"roles": read_role_assignments()}


@router.put("/roles")
async def put_roles(payload: RolesPayload, _: dict = Depends(require_roles(["admin"]))):
    return {"roles": write_role_assignments(payload.model_dump())}


@router.get("/requests")
async def get_requests(_: dict = Depends(require_roles(["admin", "approver"]))):
    return {"requests": list_requests()}


@router.get("/requests/mine")
async def get_my_requests(user: dict = Depends(get_current_user)):
    return {"requests": list_requests_by_email(user["email"])}


@router.post("/requests", status_code=201)
async def post_request(payload: CreateRequestPayload, user: dict = Depends(get_current_user)):
    ensure_requester_actor(payload, user)
    ensure_approver_target(str(payload.managerEmail))
    payload_data = payload.model_dump()
    payload_data["requesterName"] = get_display_name(user)
    payload_data["requesterEmail"] = user["email"]
    request = create_request(payload_data, user)
    await send_approval_request_mail(request)
    return {"request": request}


@router.post("/requests/{request_id}/approve")
async def approve_request(
    request_id: str,
    payload: dict | None = None,
    user: dict = Depends(require_roles(["admin", "approver"])),
):
    request = apply_manager_decision(
        request_id=request_id,
        action="approve",
        responsible=user["email"],
        applications=(payload or {}).get("applications"),
    )
    await send_decision_notification_mail(request)
    await send_tic_activation_mail(request)
    return {"request": request}


@router.post("/requests/{request_id}/reject")
async def reject_request(request_id: str, user: dict = Depends(require_roles(["admin", "approver"]))):
    request = apply_manager_decision(
        request_id=request_id,
        action="reject",
        responsible=user["email"],
    )
    await send_decision_notification_mail(request)
    return {"request": request}


@router.post("/requests/{request_id}/activate")
async def activate_request(request_id: str, user: dict = Depends(require_roles(["admin"]))):
    now = datetime.now(timezone.utc)

    def updater(current: dict) -> dict:
        if not current.get("approvedAt"):
            raise HTTPException(status_code=409, detail="La solicitud debe estar aprobada antes de activar")
        if current.get("activatedAt"):
            raise HTTPException(status_code=409, detail="La solicitud ya fue activada")
        return {
            **current,
            "status": "Aplicación habilitada por el Coordinador TIC",
            "activatedAt": now,
            "auditTrail": [
                *current["auditTrail"],
                {
                    "date": now,
                    "action": "Aplicación habilitada en Firewall y Antivirus",
                    "responsible": user["email"],
                },
            ],
        }

    request = update_request(request_id, updater)
    await send_decision_notification_mail(request)
    return {"request": request}


@router.get("/decisions/{token}/confirm", response_class=HTMLResponse)
async def decision_link(token: str, user: dict = Depends(get_current_user)):
    decision = verify_decision_token(token)
    ensure_decision_actor(decision, user)
    try:
        request = apply_manager_decision(
            request_id=decision["requestId"],
            action=decision["action"],
            responsible=decision.get("approverEmail") or "Aprobador por correo",
            applications=decision.get("applications"),
        )
        await send_decision_notification_mail(request)
        if decision["action"] == "approve":
            await send_tic_activation_mail(request)
    except HTTPException as error:
        if error.status_code != 409:
            raise
        request = require_request(decision["requestId"])

    return HTMLResponse(decision_result_html(get_decision_result_label(request)))


@router.post("/decisions/{token}/confirm", response_class=HTMLResponse)
async def decision_link_post(token: str, user: dict = Depends(get_current_user)):
    return await decision_link(token, user)
