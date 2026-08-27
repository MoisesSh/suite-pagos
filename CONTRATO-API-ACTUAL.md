# Contrato de API — estado real (no planificado)

> Extraído directamente del código ya implementado y testeado (no del plan de
> datos). Se actualiza cada vez que un backend cierra un bloque con endpoints
> nuevos. Fuente de verdad para `suit-frontend` y `suit-portal`.

Última actualización: 2026-08-27 15:30

## `suit-conciliacion` (puerto 8002 en compose, `localhost:8000` en dev directo)

### Auth (JWT + cookie HttpOnly del refresh) — `apps/users`

| Método | Ruta | Body | Respuesta |
|---|---|---|---|
| POST | `/api/auth/login/` | `{"email", "password"}` | `{access, refresh, usuario: {...}}` + cookie `refresh_token` HttpOnly |
| POST | `/api/auth/refresh/` | (cookie) | nuevo access token **+ nuevo `refresh` en el body** — rota en cada llamada, persistir el nuevo valor (no parsear `Set-Cookie` a mano) |
| POST | `/api/auth/logout/` | requiere `Authorization: Bearer <access>`; el refresh se acepta por cookie **o** por `{"refresh": "..."}` en el body (prueba cookie primero, cae al body) — depende del cliente si puede reenviar cookies automáticamente | invalida refresh (blacklist) |

**Verificado contra servidor real** (2026-08-27): `POST /api/auth/login/` devuelve
`{"access": "...", "refresh": "...", "usuario": {"id", "email", "username", "is_staff", "is_superuser"}}`
— el campo es `usuario` (no `user`), y `refresh` viaja también en el body además
de la cookie `refresh_token` (HttpOnly, `Path=/api/auth/`, `SameSite=Strict`).

### Conciliación — `apps/conciliacion` (todo requiere `IsAuthenticated`)

| Método | Ruta | Query params / body | Respuesta |
|---|---|---|---|
| GET | `/api/conciliacion/discrepancias/` | `?estado_resolucion=&severidad=` | **paginado DRF**: `{count, next, previous, results: [DiscrepanciaSerializer]}` — no un array plano |
| PATCH | `/api/conciliacion/discrepancias/<uuid:pk>/resolver/` | `{"estado_resolucion": "resuelta"\|"descartada"\|"en_revision", "notas": ""}` | `DiscrepanciaSerializer` actualizado, o 404 |
| GET | `/api/conciliacion/eventos/` | `?search=` (por `event_id`/`event_type`) | **paginado DRF**: `{count, next, previous, results: [EventoPagoRecibidoSerializer]}` |
| GET | `/api/conciliacion/transacciones-ledger/<uuid:pk>/` | — | `TransaccionLedgerSerializer` con `lineas` anidadas |

**`DiscrepanciaSerializer`** (solo lectura, salvo vía `/resolver/`):
```json
{
  "id": "uuid", "movimiento": "uuid|null", "consulta": "uuid|null", "evento": "uuid|null",
  "tipo": "string", "severidad": "string", "estado_resolucion": "abierta|resuelta|descartada|en_revision",
  "resuelto_por": {"id": "uuid", "email": "...", "username": "...", "is_staff": bool, "is_superuser": bool} | null,
  "resuelto_at": "iso-datetime|null", "notas": "string", "created_at": "iso-datetime"
}
```

**`EventoPagoRecibidoSerializer`** (solo lectura):
```json
{"id": "uuid", "event_id": "string", "event_type": "string", "schema_version": int, "procesado_at": "iso-datetime|null", "created_at": "iso-datetime"}
```

**`TransaccionLedgerSerializer`** (solo lectura):
```json
{"id": "uuid", "referencia_evento": "uuid", "created_at": "iso-datetime",
 "lineas": [{"id": "uuid", "cuenta": "uuid", "tipo": "debito|credito", "monto": "19.99"}]}
```

**Documentación interactiva:** `drf-spectacular` ya configurado — Swagger UI en
`/api/docs/` cuando `DEBUG=True`, schema OpenAPI crudo en `/api/schema/`.

---

## `suit-orquestador` (puerto 8001 en compose)

**Sin auth JWT propia todavía** (los endpoints de autorización son `AllowAny`,
diseñados para ser llamados por apps consumidoras/servidores, no por un usuario
logueado en un panel). No expone Swagger todavía (drf-spectacular no está en
`requirements.txt` de este proyecto aún).

| Método | Ruta | Body | Respuesta |
|---|---|---|---|
| POST | `/api/autorizacion/validar-acceso/` | `{"dominio": "...", "proveedor": "BDV"}` | 200 `{"autorizado": true, "aplicacion": "..."}` o 403 `{"autorizado": false, "motivo": "dominio_no_registrado\|dominio_inactivo\|aplicacion_inactiva\|proveedor_no_encontrado\|proveedor_no_autorizado"}` |
| POST | `/api/autorizacion/cobro/otp/` | *(en desarrollo — Bloque #4)* | — |
| POST | `/api/autorizacion/cobro/` | *(en desarrollo — Bloque #4, requiere token de sesión de checkout emitido por `validar-acceso`)* | — |

### Admin — registro de apps/dominios (`api/admin_views.py`, `TokenAuthentication` + `IsAdminUser`)

Resuelve el gap #1 (ya no bloquea a `suit-portal`). El token se genera desde
Django admin (`/admin/authtoken/tokenproxy/`) por un superuser, y `suit-portal`
lo guarda server-side en su propio `.env` (nunca expuesto al navegador) —
`Authorization: Token <...>`.

| Método | Ruta | Body | Respuesta |
|---|---|---|---|
| POST | `/api/autorizacion/admin/aplicaciones/` | `{"nombre", "dominio", "proveedor"}` | 201 `{"id", "nombre", "dominio", "proveedor"}` — mismo shape que `CreateAplicacionParams`/`AplicacionRegistradaEntity` de `suit-portal` |
| GET | `/api/autorizacion/admin/aplicaciones/` | — | lista con `dominios`/`proveedores_autorizados` anidados |
| PATCH | `/api/autorizacion/admin/aplicaciones/<uuid:id>/` | `{"activa": true\|false}` | app activada/desactivada (kill switch, mismo campo que usa `ValidacionAccesoService`) |

**Fuera de alcance de este bloque** (a pedir explícitamente si se necesita):
editar/desactivar un `DominioPermitido`/`AplicacionProveedorPermitido`
individual, o agregar un segundo dominio/proveedor a una app ya creada.

---

## Gaps conocidos (para no bloquear a los frontends, pero a tener en cuenta)

1. ~~CRUD de registro de apps/dominios~~ — **RESUELTO** (ver sección Admin arriba).
   `suit-portal` puede reemplazar su mock por el endpoint real.
2. **Auth JWT de `suit-orquestador`** — si el panel (`suit-frontend`) necesita
   ver datos del Orquestador (no solo Conciliación), ese backend no tiene login
   propio de usuario final todavía (solo `TokenAuthentication` para admin/M2M).
   A definir si el panel solo lee de Conciliación por ahora.
3. **Swagger de `suit-orquestador`** — no configurado (sí en Conciliación).
