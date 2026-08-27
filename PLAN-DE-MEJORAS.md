# Plan de Mejoras — Suite Centralizada de Pagos

> Registro consolidado de todos los "bloques de próximo paso" que arman los agentes
> de código (`suit-orquestador`, `suit-conciliacion`, `suit-frontend`, `suit-portal`)
> antes de recibir la orden de ejecución del coordinador. Se agrega un bloque nuevo
> cada vez que un agente propone el siguiente incremento de trabajo.

Última actualización: 2026-08-27 12:30

---

## `suit-orquestador`

### Bloque #1 — Modelos base del Orquestador ✅ COMPLETADO

**Propuesto por:** `suit-backend` · **Estado:** ejecutado y verificado contra Postgres real

**Alcance:** Módulo Django `apps/autorizacion` — solo modelos + migraciones + admin,
sin endpoints. Secciones 2.0–2.3 de `db-plan-pagos.md`:
- 2.0 Registro de seguridad: `AplicacionRegistrada`, `DominioPermitido`, `AplicacionProveedorPermitido`
- 2.1 Catálogos: `Moneda`, `MedioPago`, `ProveedorPago`, `Banco`, `TipoOperacionProveedor`, `CodigoRespuestaProveedor`
- 2.2 Agregado de pago: `IntencionPago`, `TransicionEstadoPago`, `Autorizacion`, `Captura`, `Anulacion`, `Reembolso`
- 2.3 Outbox/idempotencia: `EventoOutbox`, `IdempotencyKey` (expires_at = 48h)
- Fuera de alcance (no creados): `TokenReferencia`, `ProveedorTokenizacion`

**Decisiones tomadas antes de ejecutar:**
- Proyecto Django aloja solo el Orquestador (Conciliación es proyecto separado)
- `IdempotencyKey.expires_at` = 48 horas
- Transiciones de `IntencionPago` forzadas con trigger PL/pgSQL en Postgres, no solo disciplina de servicio
- `Moneda` como modelo de catálogo real (no `TextChoices`), decisión del agente para permitir activar/desactivar monedas sin deploy — confirmada por el coordinador

**Verificación:** `manage.py check` y `makemigrations --check` sin errores. Migrado contra
Postgres real (base `orquestador_pagos`). Trigger de transiciones probado funcionalmente
(acepta transición válida, rechaza salto inválido, rechaza estado desincronizado). Seed de
monedas confirmado en base real (VES activo, USD inactivo).

---

### Bloque #2 — Endpoint de validación de acceso ✅ COMPLETADO

**Propuesto por:** `suit-backend` · **Estado:** ejecutado, testeado y commiteado (`f62e3f3`)

**Alcance:** Control de seguridad bloqueante (sección 2.0) — rechaza la petición antes
de crear cualquier `IntencionPago` si el dominio/app/proveedor no está registrado.
- `application/services.py`: `ValidacionAccesoService.validar(dominio, proveedor_codigo)`
  — cadena `DominioPermitido(activo)` → `AplicacionRegistrada(activa)` →
  `AplicacionProveedorPermitido(activo)`. Excepción única `AccesoNoAutorizadoError(motivo)`
  con motivos distinguibles: `dominio_no_registrado`, `dominio_inactivo`,
  `aplicacion_inactiva`, `proveedor_no_encontrado`, `proveedor_no_autorizado`.
- Endpoint `POST /api/autorizacion/validar-acceso/` — `{"dominio", "proveedor"}` →
  200 `{"autorizado": true, ...}` o 403 `{"autorizado": false, "motivo": "..."}`.
  `AllowAny` (se consulta antes de cualquier autenticación de usuario).

**Verificación:** 10 tests (servicio + vista, éxito y cada motivo de rechazo), corridos
contra Postgres real incluyendo la migración del trigger. Todos pasan.

---

### Bloque #3 — Adaptador real BDV Pago Móvil C2P 🔄 EN EJECUCIÓN

**Propuesto por:** `suit-backend` · **Estado:** autorizado, en curso

**Alcance:** `infrastructure/adapters/bdv_c2p.py` — cliente HTTP del flujo de 3 pasos
(OTP, cobro, anulación) contra la API real de BDV documentada en los PDFs de
proveedor, autenticación `X-API-Key`. Flujo mínimo `IntencionPago → Autorizacion →
Captura` usando el adaptador (sin exponer aún endpoint público de cobro ni iframe).

**Decisiones tomadas antes de ejecutar:**
- `Autorizacion` y `Captura` se crean en la misma transacción a partir de una sola
  respuesta BDV (C2P es cargo instantáneo, sin reserva separada del lado del banco)
- Categorización de los 19 códigos de error de BDV en `CodigoRespuestaProveedor.categoria`
  aprobada según propuesta del agente (1000→éxito, 1026/1094→duplicado_idempotente,
  1002/1041/1050/1091→error_técnico, resto→error_negocio)
- `requests` agregado a `requirements.txt`
- API key dummy de QA en `.env` local (no commiteado), comentada explícitamente
  como solo-QA, rotar antes de producción
- Tests: mock de `requests.post` en el adaptador, mock del adaptador completo en
  los tests del servicio de flujo de cobro — nunca contra el host real de BDV

---

## `suit-conciliacion`

### Bloque #1 — Apps base de Conciliación 🔄 EN EJECUCIÓN

**Propuesto por:** `suit-conciliacion` · **Estado:** autorizado, en curso

**Alcance:**
1. **`apps/shared`** — `BaseModel` abstracto (UUID v7 + timestamps)
2. **`apps/users`** — staff local de Conciliación (auth JWT, patrón simplejwt +
   cookie HttpOnly de la skill), `Usuario(AbstractUser, BaseModel)`
3. **`apps/conciliacion`** — agregado completo de la sección 3 del plan de datos:
   - Catálogos: `CuentaContable`, `Banco`
   - Ingesta: `EventoPagoRecibido` (dedup por `event_id`)
   - Matching BDV: `ConsultaConciliacionProveedor`, `MovimientoBancario` (genérico)
   - Ledger de doble entrada: `TransaccionLedger`, `LineaLedger`
   - `Discrepancia` (3 FK nullable, `resuelto_por` → `apps.users.Usuario`)
   - `ReporteERP`
   - Servicios: `ingesta.py`, `matching.py`, `ledger.py`
   - Infra: `tasks.py` (worker Celery consumiendo `pago.*` de RabbitMQ, polling a BDV)
   - Endpoints mínimos: listado/detalle de discrepancias, resolución, eventos, ledger

**Decisiones tomadas antes de ejecutar:**
- Auth de staff: usuario propio local en Conciliación (no identidad de otro servicio) —
  `Discrepancia.resuelto_por` es FK real con `SET_NULL`
- Balance-cero del ledger: constraint/trigger a nivel Postgres (consistente con el
  patrón ya aplicado en el Orquestador)
- Relay RabbitMQ→Celery: worker consumiendo directo de la cola (patrón estándar,
  no poller — el poller es específico del lado Orquestador/outbox)

**Gaps de modelado resueltos por `expert_database_conciliacion` antes de este bloque:**
`related_name` faltantes, `on_delete`/tipo de relación de `TransaccionLedger.referencia_evento`,
`on_delete` de las 3 FK nullable de `Discrepancia`, tipado de `Discrepancia.tipo`/`.severidad`
como `TextChoices`, `ReporteERP.payload` como `JSONField`, índices en `referencia_corta` y
`procesado_at`.

---

## `suit-frontend`

Sin bloques todavía — panel administrativo interno, scaffold verificado (build
exitoso), en espera del contrato de API de `suit-orquestador`/`suit-conciliacion`
para proponer el primer bloque de integración.

---

## `suit-portal`

Sin bloques todavía — Developer Portal, scaffold verificado, en espera del contrato
de API de registro de aplicaciones/dominios (sección 2.0 de `db-plan-pagos.md`,
ya implementado en `suit-orquestador`) para proponer el primer bloque de integración.

---

## Infraestructura de despliegue

### `deploy/` — Docker + docker-compose ✅ COMPLETADO (coordinador)

Carpeta creada directamente por el coordinador (infraestructura transversal, no
propia de un solo servicio), siguiendo el patrón de la skill
`despliegue-docker-django-nextjs` (ya copiada a los 4 proyectos), adaptado a las
decisiones reales del proyecto:

- `Dockerfile.backend` (genérico, `SERVICE_DIR` selecciona `suit-orquestador` o
  `suit-conciliacion`), `Dockerfile.celery-worker` (solo Conciliación),
  `Dockerfile.frontend` (genérico, `suit-frontend`/`suit-portal`, usa `npm` no `pnpm`)
- `docker-compose.yml`: 2 Postgres separados (`postgres-orquestador`,
  `postgres-conciliacion` — nunca un solo Postgres con schemas), 1 RabbitMQ
  (sin Redis), 4 servicios de aplicación + 1 worker Celery
- `docker-compose.override.yml` para desarrollo (hot reload, código montado)
- `README.md` con variables de entorno, comandos de uso y pre-flight checks

**Pendiente de verificación real** (no se corrió `docker build`/`docker compose up`
todavía — los backends siguen en desarrollo activo): una vez `suit-orquestador` y
`suit-conciliacion` completen sus bloques en curso, correr el checklist de
`deploy/README.md` para validar que el stack completo levanta sin errores.

---

## Cómo se usa este archivo

Cada vez que un agente arma un bloque nuevo, el coordinador lo agrega aquí con:
propuesto por, alcance exacto, decisiones tomadas antes de ejecutar, y estado
(`propuesto` → `autorizado` → `en ejecución` → `completado`/`verificado`). No se
edita retroactivamente el contenido de un bloque ya completado, salvo para
corregir un error — el historial de decisiones queda como registro.
