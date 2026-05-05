import html

import httpx

from app.config import get_settings
from app.security.decision_tokens import create_decision_token


APP_META = {
    "WhatsApp": {"short": "WA", "color": "#1c9b75"},
    "YouTube": {"short": "YT", "color": "#b42318"},
    "LinkedIn": {"short": "IN", "color": "#2563eb"},
}


def get_logo_url() -> str:
    return f"{get_settings().public_app_url.rstrip('/')}/logo-avantika.png"


def build_email_header(title: str) -> str:
    return f"""
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
      <tr>
        <td style="vertical-align:middle;padding:0 16px 0 0;">
          <div style="font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#bce7db;">Autorizaciones Web</div>
          <h1 style="margin:8px 0 0;font-size:24px;line-height:1.25;color:#ffffff;">{html.escape(title)}</h1>
        </td>
        <td width="150" align="right" style="vertical-align:middle;">
          <img src="{html.escape(get_logo_url())}" alt="Avantika" width="130" style="display:block;width:130px;max-width:130px;height:auto;background:#ffffff;border-radius:14px;padding:8px;border:0;" />
        </td>
      </tr>
    </table>
    """


def get_applications(request: dict) -> str:
    return ", ".join(request["applications"])


def unique_recipients(values: list[str | None]) -> list[str]:
    recipients = []
    seen = set()
    for value in values:
        if not value:
            continue
        normalized = value.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        recipients.append(value)
    return recipients


def unique_recipients_except(values: list[str | None], excluded: list[str]) -> list[str]:
    excluded_set = {value.lower() for value in excluded}
    return [value for value in unique_recipients(values) if value.lower() not in excluded_set]


def get_approved_applications(request: dict) -> list[str]:
    return request.get("approvedApplications") or request["applications"]


def get_approved_applications_text(request: dict) -> str:
    return ", ".join(get_approved_applications(request))


def get_status_tone(status: str) -> dict:
    if status == "Rechazado por Gerencia":
        return {"label": "Solicitud rechazada", "color": "#b42318", "soft": "#fdecec"}
    if status == "Aprobado parcial por Gerencia":
        return {"label": "Solicitud aprobada parcialmente", "color": "#d97706", "soft": "#fff7ed"}
    if status == "Aplicación habilitada por el Coordinador TIC":
        return {"label": "Habilitación completada", "color": "#173b57", "soft": "#edf5ff"}
    return {"label": "Solicitud aprobada", "color": "#1c9b75", "soft": "#e8f7f1"}


def build_app_badges(request: dict, applications: list[str] | None = None) -> str:
    badges = []
    for application in applications or request["applications"]:
        meta = APP_META.get(application, {"short": application[:2].upper(), "color": "#173b57"})
        badges.append(
            f"""
            <span style="display:inline-block;margin:0 8px 8px 0;padding:8px 12px;border-radius:999px;background:#f8fafc;border:1px solid #e5ebf1;color:#243347;font-weight:800;font-size:13px;">
              <span style="display:inline-block;width:24px;height:24px;line-height:24px;text-align:center;border-radius:8px;background:{meta["color"]};color:#fff;font-size:10px;margin-right:7px;">{meta["short"]}</span>
              {html.escape(application)}
            </span>
            """
        )
    return "".join(badges)


def get_application_section_title(request: dict) -> str:
    if request["status"] == "Aprobado parcial por Gerencia":
        return "Aplicaciones aprobadas"
    if request["status"] == "Aprobado por Gerencia":
        return "Aplicaciones aprobadas - TOTAL"
    if request["status"] == "Aplicación habilitada por el Coordinador TIC":
        return "Aplicaciones habilitadas"
    return "Aplicaciones solicitadas"


def build_status_html(request: dict, message: str) -> str:
    tone = get_status_tone(request["status"])
    return f"""
    <!doctype html>
    <html lang="es">
      <body style="margin:0;background:#f6f8fb;font-family:Arial,Helvetica,sans-serif;color:#26313d;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f8fb;padding:28px 12px;">
          <tr>
            <td align="center">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:680px;background:#ffffff;border:1px solid #e4ebf2;border-radius:22px;overflow:hidden;">
                <tr>
                  <td style="padding:24px 28px;background:#173b57;color:#ffffff;">
                    {build_email_header(request["requestNumber"])}
                  </td>
                </tr>
                <tr>
                  <td style="padding:26px 28px;">
                    <div style="display:inline-block;background:{tone["soft"]};color:{tone["color"]};border-radius:999px;padding:9px 14px;font-size:13px;font-weight:800;margin-bottom:16px;">
                      {tone["label"]}
                    </div>
                    <p style="margin:0 0 20px;color:#5d6878;line-height:1.55;">{html.escape(message)}</p>

                    <div style="background:#f8fafc;border:1px solid #e5ebf1;border-radius:16px;padding:16px;margin-bottom:18px;">
                      <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                        <tr>
                          <td style="padding:8px 0;color:#738092;font-size:12px;font-weight:800;">Estado</td>
                          <td style="padding:8px 0;text-align:right;color:#243347;font-weight:800;">{html.escape(request["status"])}</td>
                        </tr>
                        <tr>
                          <td style="padding:8px 0;border-top:1px solid #e5ebf1;color:#738092;font-size:12px;font-weight:800;">Colaborador</td>
                          <td style="padding:8px 0;border-top:1px solid #e5ebf1;text-align:right;color:#243347;font-weight:700;">{html.escape(request["collaboratorName"])}</td>
                        </tr>
                        <tr>
                          <td style="padding:8px 0;border-top:1px solid #e5ebf1;color:#738092;font-size:12px;font-weight:800;">Macroproceso</td>
                          <td style="padding:8px 0;border-top:1px solid #e5ebf1;text-align:right;color:#243347;font-weight:700;">{html.escape(request["area"])}</td>
                        </tr>
                      </table>
                    </div>

                    <div style="margin-top:4px;">
                      <div style="margin:0 0 10px;color:#738092;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.06em;">{get_application_section_title(request)}</div>
                      {build_app_badges(request, get_approved_applications(request))}
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """


async def get_graph_access_token() -> str:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"https://login.microsoftonline.com/{settings.graph_tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": settings.graph_client_id,
                "client_secret": settings.graph_client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    data = response.json()
    if response.status_code >= 400:
        raise RuntimeError(data.get("error_description") or "No fue posible autenticar Microsoft Graph")
    return data["access_token"]


async def send_graph_mail(message: dict) -> None:
    settings = get_settings()
    required = [
        settings.graph_tenant_id,
        settings.graph_client_id,
        settings.graph_client_secret,
        settings.graph_from_email,
    ]
    if any(not value for value in required):
        raise RuntimeError("Microsoft Graph mail is missing required environment variables")

    access_token = await get_graph_access_token()
    content = message.get("html") or message.get("text", "")
    content_type = "HTML" if message.get("html") else "Text"

    payload = {
        "message": {
            "subject": message["subject"],
            "body": {"contentType": content_type, "content": content},
            "toRecipients": [
                {"emailAddress": {"address": address}} for address in message.get("to", [])
            ],
            "ccRecipients": [
                {"emailAddress": {"address": address}} for address in message.get("cc", [])
            ],
        },
        "saveToSentItems": True,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"https://graph.microsoft.com/v1.0/users/{settings.graph_from_email}/sendMail",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if response.status_code >= 400:
        raise RuntimeError(f"Microsoft Graph sendMail failed: {response.text}")


async def send_mail(message: dict) -> None:
    settings = get_settings()
    if settings.mail_provider == "console":
        print("\n--- Simulated email ---")
        print("To:", message.get("to", []))
        print("CC:", message.get("cc", []))
        print("Subject:", message["subject"])
        print(message.get("text") or message.get("html"))
        print("--- End simulated email ---\n")
        return

    if settings.mail_provider == "graph":
        await send_graph_mail(message)
        return

    raise RuntimeError("MAIL_PROVIDER must be console or graph")


def create_decision_url(request: dict, action: str, applications: list[str] | None = None) -> str:
    settings = get_settings()
    token = create_decision_token(
        request_id=request["id"],
        action=action,
        approver_email=request["managerEmail"],
        applications=applications,
    )
    return f"{settings.public_app_url}/api/decisions/{token}/confirm"


def build_approval_html(request: dict) -> str:
    approve_url = create_decision_url(request, "approve", request["applications"])
    reject_url = create_decision_url(request, "reject")
    rows = []

    for application in request["applications"]:
        meta = APP_META.get(application, {"short": application[:2].upper(), "color": "#173b57"})
        single_url = create_decision_url(request, "approve", [application])
        rows.append(
            f"""
            <tr>
              <td style="padding:10px 0;border-top:1px solid #e5ebf1;">
                <span style="display:inline-block;width:34px;height:34px;line-height:34px;text-align:center;border-radius:10px;background:{meta["color"]};color:#fff;font-weight:800;font-size:12px;margin-right:10px;">{meta["short"]}</span>
                <strong style="color:#243347;">{html.escape(application)}</strong>
              </td>
              <td style="padding:10px 0;border-top:1px solid #e5ebf1;text-align:right;">
                <a href="{single_url}" style="display:inline-block;background:#173b57;color:#fff;text-decoration:none;border-radius:12px;padding:10px 14px;font-weight:800;font-size:13px;">Aprobar {html.escape(application)}</a>
              </td>
            </tr>
            """
        )

    return f"""
    <!doctype html>
    <html lang="es">
      <body style="margin:0;background:#f6f8fb;font-family:Arial,Helvetica,sans-serif;color:#26313d;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f8fb;padding:28px 12px;">
          <tr>
            <td align="center">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:720px;background:#ffffff;border:1px solid #e4ebf2;border-radius:22px;overflow:hidden;">
                <tr>
                  <td style="padding:26px 28px;background:#173b57;color:#ffffff;">
                    {build_email_header(f"Solicitud {request['requestNumber']}")}
                  </td>
                </tr>
                <tr>
                  <td style="padding:26px 28px;">
                    <p style="margin:0 0 18px;color:#5d6878;line-height:1.55;">{html.escape(request["requesterName"])} solicita habilitación web para {html.escape(request["collaboratorName"])}.</p>
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin:0 0 20px;">
                      <tr>
                        <td style="padding:10px 0;color:#738092;font-size:12px;font-weight:800;">Jefe inmediato</td>
                        <td style="padding:10px 0;text-align:right;color:#243347;font-weight:700;">{html.escape(request["requesterName"])}</td>
                      </tr>
                      <tr>
                        <td style="padding:10px 0;border-top:1px solid #e5ebf1;color:#738092;font-size:12px;font-weight:800;">Colaborador</td>
                        <td style="padding:10px 0;border-top:1px solid #e5ebf1;text-align:right;color:#243347;font-weight:700;">{html.escape(request["collaboratorName"])}</td>
                      </tr>
                      <tr>
                        <td style="padding:10px 0;border-top:1px solid #e5ebf1;color:#738092;font-size:12px;font-weight:800;">Macroproceso</td>
                        <td style="padding:10px 0;border-top:1px solid #e5ebf1;text-align:right;color:#243347;font-weight:700;">{html.escape(request["area"])}</td>
                      </tr>
                    </table>
                    <div style="background:#f8fafc;border:1px solid #e5ebf1;border-radius:16px;padding:16px;margin-bottom:14px;">
                      <strong style="display:block;color:#243347;margin-bottom:6px;">Motivo</strong>
                      <p style="margin:0;color:#5d6878;line-height:1.5;">{html.escape(request["reason"])}</p>
                    </div>
                    <div style="background:#f8fafc;border:1px solid #e5ebf1;border-radius:16px;padding:16px;margin-bottom:22px;">
                      <strong style="display:block;color:#243347;margin-bottom:6px;">Aporte al proceso o resultado esperado</strong>
                      <p style="margin:0;color:#5d6878;line-height:1.5;">{html.escape(request["businessValue"])}</p>
                    </div>
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin-bottom:24px;">
                      {"".join(rows)}
                    </table>
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                      <tr>
                        <td style="padding:0 6px 10px 0;">
                          <a href="{approve_url}" style="display:block;text-align:center;background:#1c9b75;color:#fff;text-decoration:none;border-radius:14px;padding:14px 18px;font-weight:800;">Aprobar todo</a>
                        </td>
                        <td style="padding:0 0 10px 6px;">
                          <a href="{reject_url}" style="display:block;text-align:center;background:#b42318;color:#fff;text-decoration:none;border-radius:14px;padding:14px 18px;font-weight:800;">Rechazar todo</a>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """


async def send_approval_request_mail(request: dict) -> None:
    await send_mail(
        {
            "to": [request["managerEmail"]],
            "cc": [value for value in [request["collaboratorEmail"], request.get("copyEmail")] if value],
            "subject": f"Solicitud {request['requestNumber']} - Habilitación web",
            "html": build_approval_html(request),
            "text": "\n".join(
                [
                    f"Solicitud: {request['requestNumber']}",
                    f"Jefe inmediato: {request['requesterName']}",
                    f"Colaborador: {request['collaboratorName']}",
                    f"Macroproceso: {request['area']}",
                    f"Aplicaciones: {get_applications(request)}",
                    f"Motivo: {request['reason']}",
                    f"Aporte al proceso o resultado esperado: {request['businessValue']}",
                ]
            ),
        }
    )
    print(f"[mail] Solicitud {request['requestNumber']} enviada a {request['managerEmail']}")


async def send_decision_notification_mail(request: dict) -> None:
    if request["status"] == "Aprobado parcial por Gerencia":
        message = f"Tu solicitud fue aprobada parcialmente. Aplicaciones aprobadas: {get_approved_applications_text(request)}."
    elif request["status"] == "Aprobado por Gerencia":
        message = f"Tu solicitud fue aprobada en su totalidad. Aplicaciones aprobadas: {get_approved_applications_text(request)}."
    elif request["status"] == "Rechazado por Gerencia":
        message = "Tu solicitud fue revisada y no fue aprobada."
    else:
        message = "Tu solicitud fue revisada y cambió de estado."
    to_recipients = unique_recipients([request["collaboratorEmail"]])
    await send_mail(
        {
            "to": to_recipients,
            "cc": unique_recipients_except(
                [request.get("requesterEmail"), request.get("copyEmail")],
                to_recipients,
            ),
            "subject": f"Solicitud {request['requestNumber']} - {request['status']}",
            "html": build_status_html(request, message),
            "text": "\n".join(
                [
                    f"Tu solicitud {request['requestNumber']} cambió de estado.",
                    f"Estado actual: {request['status']}",
                    f"{get_application_section_title(request)}: {get_approved_applications_text(request)}",
                ]
            ),
        }
    )
    print(f"[mail] Notificación enviada para {request['requestNumber']} a {request['collaboratorEmail']}")


async def send_tic_activation_mail(request: dict) -> None:
    recipients = unique_recipients([request.get("copyEmail")])
    if not recipients:
        return

    await send_mail(
        {
            "to": recipients,
            "cc": unique_recipients_except([request["collaboratorEmail"]], recipients),
            "subject": f"Solicitud {request['requestNumber']} aprobada - Activación TIC",
            "html": build_status_html(
                request,
                "La solicitud fue aprobada y queda lista para realizar o confirmar la habilitación TIC.",
            ),
            "text": "\n".join(
                [
                    f"La solicitud {request['requestNumber']} fue aprobada por Gerencia.",
                    f"{get_application_section_title(request)}: {get_approved_applications_text(request)}",
                    f"Jefe inmediato: {request['requesterName']}",
                    f"Colaborador: {request['collaboratorName']}",
                ]
            ),
        }
    )
