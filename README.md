# Backend - Autorizaciones Web

API en Python con FastAPI para registrar solicitudes, gestionar aprobación/rechazo,
activar por TIC y enviar notificaciones por Microsoft Graph.

## Ejecutar local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 3000 --reload
```

## Seguridad

- Autenticación mediante Cloudflare Access JWT (`CF-Access-Jwt-Assertion`).
- Modo local con `ALLOW_DEV_AUTH=true`.
- Roles desde `dbo.RolesUsuarios` y respaldos por variables `ADMIN_EMAILS` /
  `APPROVER_EMAILS`.
- CORS restringido al origen del frontend.
- Enlaces de decisión cifrados con AES-256-GCM y vencimiento.
- En producción se deshabilitan `/docs`, `/redoc` y `/openapi.json`.
- En producción el backend no inicia si quedan valores inseguros como localhost,
  `ALLOW_DEV_AUTH=true`, token débil o SQL sin cifrado.

## Despliegue producción

1. Configurar `Backend/.env` con `NODE_ENV=production`.
2. Usar `PUBLIC_APP_URL` y `FRONTEND_ORIGIN` con el subdominio HTTPS real.
3. Dejar el backend escuchando solo en red interna o localhost del servidor.
4. Publicar el acceso externo únicamente mediante Cloudflare Tunnel + Access.
5. Exigir MFA en Microsoft Entra ID para los usuarios que entran por Access.
6. Usar una cuenta SQL con permisos mínimos sobre la base de esta aplicación.
7. Ejecutar el backend sin `--reload`.

## Base de Datos

Los scripts SQL estan en [database](database):

- [01_crear_tablas.sql](database/01_crear_tablas.sql): crea las tablas requeridas.
- [02_insertar_roles_iniciales.sql](database/02_insertar_roles_iniciales.sql): inserta roles base.

La aplicación no crea ni recrea tablas automaticamente.
