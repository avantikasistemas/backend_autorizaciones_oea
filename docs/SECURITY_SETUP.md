# Configuracion de seguridad: Cloudflare Access + Microsoft Entra ID

Esta aplicacion no debe implementar login local. El login corporativo debe vivir en
Cloudflare Access usando Microsoft Entra ID como proveedor de identidad. El backend
valida el JWT emitido por Cloudflare y asigna permisos por grupos/correos.

## 1. Grupos en Microsoft Entra ID

Crear grupos de tipo **Seguridad**. No usar grupos de Microsoft 365 para este caso.
Los grupos de Microsoft 365 sirven mejor para colaboracion, correo, Teams y recursos
compartidos; para control de acceso a aplicaciones, los grupos de seguridad son la
opcion correcta.

Grupos recomendados:

- `AutorizacionesWeb-Usuarios`
- `AutorizacionesWeb-Aprobadores`
- `AutorizacionesWeb-Administradores`

Configuracion recomendada:

- Tipo de grupo: `Seguridad`
- Tipo de pertenencia: `Asignada`
- Miembros: asignar usuarios directamente
- Evitar grupos anidados para este flujo, especialmente si se usa sincronizacion SCIM

Rol esperado:

- `AutorizacionesWeb-Usuarios`: usuarios que pueden enviar solicitudes
- `AutorizacionesWeb-Aprobadores`: gerencia o aprobadores
- `AutorizacionesWeb-Administradores`: acceso completo

## 2. Cloudflare Zero Trust

### 2.1 Identity provider

En Cloudflare Zero Trust:

1. Ir a `Settings > Authentication`.
2. Agregar Microsoft Entra ID / Azure AD como proveedor.
3. Activar `Grupos de asistencia` en el proveedor Azure AD. Este es el switch
   que permite que Zero Trust recopile informacion de grupos desde Entra ID.
4. Probar inicio de sesion con un usuario corporativo.

En la pantalla del proveedor Azure AD, la opcion relevante para grupos es:

- `Grupos de asistencia`: activado

Esto requiere permisos en la aplicacion de Entra ID para leer grupos, normalmente
`Group.Read.All`, y consentimiento de administrador.

Opcional, pero recomendado si quieres mejor administracion a escala:

- `Habilitar SCIM`: activado

SCIM sincroniza usuarios y grupos desde Entra ID hacia Cloudflare. Es util para
que Cloudflare conozca grupos y membresias de forma mas consistente y para
facilitar baja/revocacion cuando se administran identidades en Entra.

La opcion `Sincronizacion de politicas de Azure AD` no es necesaria para este
flujo basico de Autorizaciones Web.

### 2.1.1 Si Cloudflare no deja seleccionar `Azure Groups`

Si al crear una politica aparece un error como:

`Failed to retrieve SCIM groups due to an unexpected error`

significa que Cloudflare esta intentando leer grupos sincronizados por SCIM, pero
SCIM no esta activo, no termino de sincronizar, o los grupos no estan dentro del
alcance de aprovisionamiento en Entra ID.

Para corregirlo:

1. En Cloudflare Zero Trust, abrir el proveedor `Azure AD`.
2. Activar `Habilitar SCIM`.
3. Copiar el endpoint SCIM y el token/secreto que muestre Cloudflare.
4. En Microsoft Entra ID, no usar la aplicacion empresarial existente del login
   de Cloudflare. SCIM requiere una aplicacion empresarial separada.
5. Ir a `Enterprise applications` > `New application` > `Create your own application`.
6. Crear una app llamada, por ejemplo, `Cloudflare Access SCIM`.
7. Elegir `Integrate any other application you don't find in the gallery (Non-gallery)`.
8. En esa nueva aplicacion, ir a `Provisioning` / `Aprovisionamiento`.
9. Configurar modo `Automatic`.
10. Pegar el endpoint SCIM y el token de Cloudflare.
11. Probar conexion.
12. En `Users and groups`, asignar los grupos:
   - `AutorizacionesWeb-Usuarios`
   - `AutorizacionesWeb-Aprobadores`
   - `AutorizacionesWeb-Administradores`
13. Iniciar aprovisionamiento y esperar a que termine la sincronizacion.
14. Volver a Cloudflare y crear la politica con selector `Azure Groups`.

Si en la aplicacion empresarial existente aparece el mensaje:

`Hoy no se admite el aprovisionamiento automatico integrado...`

eso es esperado para esa app. No es la app correcta para SCIM. Crea la aplicacion
separada `Cloudflare Access SCIM` tipo `Non-gallery`.

Importante: en Microsoft Entra ID, la sincronizacion de grupos solo ocurre para
los grupos incluidos en el alcance de aprovisionamiento. Si los usuarios aparecen
pero los grupos no, primero revisar el aprovisionamiento en Entra antes de
solucionar la politica en Cloudflare.

Alternativa temporal si SCIM aun no esta listo:

- En la politica de Cloudflare Access, usar `Emails ending in: @tuempresa.com`
  para permitir entrada general.
- En el backend, usar `ADMIN_EMAILS` y `APPROVER_EMAILS` para
  asignar permisos por correo mientras se completa SCIM.
- Si Cloudflare permite escribir manualmente el valor del selector `Azure Groups`,
  se puede pegar el `Object ID` del grupo de Entra ID en lugar de seleccionarlo
  desde el desplegable. Esto permite usar grupos sin esperar a que aparezcan por
  nombre, pero SCIM sigue siendo la mejor opcion para administracion a escala.

Esta alternativa es aceptable para una primera prueba, pero para produccion es
mejor usar grupos sincronizados.

### 2.1.2 Si Entra no permite asignar grupos a la app SCIM

Si Entra muestra:

`Los grupos no estan disponibles para la asignacion debido a su nivel de plan de Active Directory`

entonces el tenant no tiene habilitada la asignacion de grupos a aplicaciones
empresariales. Esta caracteristica requiere Microsoft Entra ID Premium P1 o P2
en el tenant. En ese caso, la pantalla solo permitira asignar usuarios
individuales.

Opciones:

1. Comprar o activar Microsoft Entra ID Premium P1/P2, o un plan que lo incluya
   como Microsoft 365 Business Premium, si aplica a la organizacion.
2. Mientras tanto, asignar usuarios individuales a la aplicacion SCIM.
3. Usar Cloudflare Access con `Emails ending in: @tuempresa.com` para permitir
   entrada corporativa.
4. Controlar roles en SQL Server con la tabla `dbo.RolesUsuarios`.

Esta alternativa sigue siendo segura si Cloudflare Access, Microsoft Entra ID y
MFA estan activos. La diferencia es administrativa: deberas mantener los roles
por correo en el backend hasta tener P1/P2 o grupos disponibles.

Proceso recomendado sin P1/P2:

1. En Cloudflare Access, politica `Allow` por dominio corporativo:
   `Emails ending in: @avantika.com.co`.
2. No depender de grupos de Entra para roles internos.
3. Ejecutar `Backend/database/01_crear_tablas.sql` en SQL Server.
4. Mantener los roles en la tabla `dbo.RolesUsuarios`.
5. Dejar al menos un administrador de respaldo tambien en `ADMIN_EMAILS` para
   evitar bloqueo accidental si la tabla queda vacia o hay un error operativo.

El frontend no decide permisos. El usuario entra por Cloudflare, el backend valida
su identidad y consulta SQL Server para saber si ve vista de administrador,
aprueba, rechaza o activa solicitudes.

Roles operativos actuales:

```sql
INSERT INTO dbo.RolesUsuarios (Correo, Rol)
VALUES
  ('tic@avantika.com.co', 'admin'),
  ('sistemas@avantika.com.co', 'admin'),
  ('auxiliartic@avantika.com.co', 'admin'),
  ('gerencia@avantika.com.co', 'approver'),
  ('tic@avantika.com.co', 'approver');
```

Los administradores pueden hacer todo en la aplicacion. El aprobador puede aprobar
o rechazar solicitudes. Los usuarios que puedan crear solicitudes deben tener rol
`requester` en `dbo.RolesUsuarios` o estar incluidos en `REQUESTER_EMAILS`.
Un usuario corporativo autenticado por Cloudflare Access pero sin rol solo podra
entrar a la aplicacion, pero no crear, aprobar ni administrar solicitudes.

### 2.2 Access Application

Crear una aplicacion tipo `Self-hosted`:

- Nombre: `Autorizaciones Web`
- Dominio: `autorizaciones.tuempresa.com`
- Session duration recomendada: 8 a 12 horas para usuarios normales; menor si la app es critica

Politica recomendada:

- Action: `Allow`
- Include:
  - Emails ending in: `@avantika.com.co`
- Require:
  - Identity provider: Microsoft Entra ID

Sin Entra P1/P2, los roles internos no salen de grupos de Entra. Cloudflare valida
que el usuario sea corporativo y el backend consulta SQL Server para decidir si es
administrador, aprobador o solicitante autorizado.

### 2.3 AUD Tag

En la aplicacion de Cloudflare Access:

1. Abrir `Access > Applications`.
2. Entrar a `Autorizaciones Web`.
3. Copiar `Application Audience (AUD) Tag`.
4. Ponerlo en el backend.

## 3. Variables del backend

En `Backend/.env`:

```env
NODE_ENV=production
PORT=3000
PUBLIC_APP_URL=https://autorizaciones.avantika.com.co
FRONTEND_ORIGIN=https://autorizaciones.avantika.com.co

CF_ACCESS_TEAM_DOMAIN=https://tu-equipo.cloudflareaccess.com
CF_ACCESS_AUDIENCE=aud-tag-de-la-aplicacion
ALLOW_DEV_AUTH=false

DRIVER=ODBC Driver 18 for SQL Server
DB_HOST=servidor_sql
DB_PORT=1433
DB_NAME=AutorizacionesWeb
DB_USER=autorizaciones_app
DB_PASS=
ENCRYPT=yes
TRUST_CERTIFICATE=no

DECISION_TOKEN_SECRET=usar-un-secreto-largo-aleatorio
DECISION_TOKEN_TTL_MINUTES=1440

MAIL_PROVIDER=graph
GRAPH_TENANT_ID=
GRAPH_CLIENT_ID=
GRAPH_CLIENT_SECRET=
GRAPH_FROM_EMAIL=
```

Notas:

- `ALLOW_DEV_AUTH=false` es obligatorio en produccion.
- `PUBLIC_APP_URL` y `FRONTEND_ORIGIN` deben ser HTTPS y apuntar al subdominio
  publico protegido por Cloudflare Access.
- `DECISION_TOKEN_SECRET` debe ser unico, largo y privado.
- `ENCRYPT=yes` y `TRUST_CERTIFICATE=no` requieren un certificado valido en SQL
  Server. Si el servidor SQL no tiene certificado valido, corregir el certificado
  antes de produccion en lugar de confiar certificados sin validar.
- Los correos en `ADMIN_EMAILS` y `APPROVER_EMAILS` son respaldo.
  La administracion principal de roles queda en `dbo.RolesUsuarios`.

Scripts SQL disponibles:

- `Backend/database/01_crear_tablas.sql`
- `Backend/database/02_insertar_roles_iniciales.sql`

La API valida estos parametros al iniciar cuando `NODE_ENV=production`. Si alguno
queda en modo desarrollo, el backend no arranca.

## 4. Sesiones y cache de login

Cloudflare Access guarda la sesion en cookies `CF_Authorization`.

Hay dos niveles:

- Sesion global en el dominio de Cloudflare Access.
- Sesion de aplicacion en el dominio protegido.

Mientras la cookie sea valida, el usuario no tendra que iniciar sesion de nuevo.
El backend aun valida el JWT en cada request usando el header
`CF-Access-Jwt-Assertion`.

Recomendacion:

- Aplicacion normal interna: 8 a 12 horas.
- Aplicacion sensible: 1 a 4 horas.
- Exigir MFA desde Microsoft Entra ID.
- Revocar usuarios quitandolos del grupo o deshabilitando la cuenta en Entra.

## 5. Botones de aprobacion y rechazo por correo

Los enlaces del correo deben pasar por Cloudflare Access tambien. Si el aprobador
no tiene sesion activa, Cloudflare le pedira login.

El backend valida:

1. Que el JWT de Cloudflare sea valido.
2. Que el usuario autenticado sea el aprobador esperado o administrador.
3. Que el token firmado del enlace sea valido y no haya vencido.
4. Que la solicitud no tenga ya una decision registrada.

Esto evita que una persona externa o un reenvio de correo pueda aprobar sin estar
autenticado y autorizado.
