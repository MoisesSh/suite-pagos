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
| POST | `/api/auth/logout/` | requiere `Authorization: Bearer <access>` + `{"refresh": "..."}` en el body — la sola cookie no alcanza | invalida refresh (blacklist) |

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

**No existe todavía** ningún endpoint para: listar/crear `AplicacionRegistrada`,
`DominioPermitido` ni `AplicacionProveedorPermitido` (el registro de apps/dominios
del Developer Portal). Hoy solo se gestionan por Django admin. Es el bloqueador
real para que `suit-portal` tenga algo funcional más allá de UI estática — ver
nota abajo.

---

## Gaps conocidos (para no bloquear a los frontends, pero a tener en cuenta)

1. **CRUD de registro de apps/dominios** (`suit-portal` lo necesita para
   funcionar de verdad) — no implementado. Candidato a próximo bloque de
   `suit-backend` una vez cierre el flujo de cobro.
2. **Auth JWT de `suit-orquestador`** — si el panel (`suit-frontend`) necesita
   ver datos del Orquestador (no solo Conciliación), ese backend no tiene login
   propio todavía. A definir si el panel solo lee de Conciliación por ahora.
3. **Swagger de `suit-orquestador`** — no configurado (sí en Conciliación).
