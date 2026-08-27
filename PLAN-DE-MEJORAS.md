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

### Bloque #3 — Adaptador real BDV Pago Móvil C2P ✅ COMPLETADO

**Propuesto por:** `suit-backend` · **Estado:** ejecutado y verificado (20/20 tests, Postgres real)

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

**Verificación:** 20/20 tests pasando contra Postgres real, `manage.py check` limpio.
Bug propio encontrado y corregido: la llamada HTTP y la transición a `fallido` no
pueden vivir en el mismo `transaction.atomic()` que el camino de éxito (Postgres
revierte la transición de fallo al re-lanzar la excepción) — quedaron separados.
Migración `0004_seed_catalogos_bdv_c2p.py` puebla `MedioPago`, `ProveedorPago`,
`Banco`, `TipoOperacionProveedor` y los 19 `CodigoRespuestaProveedor` reales.

---

### Bloque #4 — Endpoint público de cobro 🔄 EN EJECUCIÓN

**Propuesto por:** `suit-backend` · **Estado:** autorizado, en curso

**Alcance:** exponer el flujo `FlujoCobroC2PService` como endpoint público,
respetando el requisito de seguridad ya establecido (validación de dominio/iframe,
`research-seguridad-iframe.md`) antes de aceptar cualquier petición externa.

---

## `suit-conciliacion`

### Bloque #1 — Apps base de Conciliación ✅ COMPLETADO

**Propuesto por:** `suit-conciliacion` · **Estado:** ejecutado y verificado end-to-end (25/25 tests + prueba real contra RabbitMQ)

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

**Verificación:** 25/25 tests pasando. Pipeline end-to-end probado contra
infraestructura real (`suit-pagos-rabbitmq-1`): mensaje publicado al exchange
`pago` (topic, routing key `pago.confirmado`) → bootstep `EventoPagoConsumerStep`
→ tarea Celery `consumir_evento_pago` → `IngestaService` → `EventoPagoRecibido`
persistido en Postgres. Bug real encontrado y corregido: Celery 5.6 es
incompatible con RabbitMQ 4.x en el pidbox (`transient_nonexcl_queues`
deprecado, error 541) — fix permanente con `CELERY_WORKER_ENABLE_REMOTE_CONTROL
= False`. Puerto AMQP (5672) del contenedor RabbitMQ publicado en
`deploy/docker-compose.yml` para poder probar contra el broker real desde el host.

**Nota para `suit-orquestador`:** si en algún momento corre un worker Celery
propio contra el mismo RabbitMQ, aplicar el mismo fix de `transient_nonexcl_queues`.

---

### Bloque #2 — Adaptador HTTP real a BDV `getMovement/v2` 🔄 EN EJECUCIÓN

**Propuesto por:** `suit-conciliacion` · **Estado:** autorizado, en curso

**Alcance:** cliente HTTP real hacia la API de conciliación de BDV (`X-API-Key`
propia de Conciliación, manejo del debounce de 30s del banco), conectando la
lógica de interpretación ya lista en `domain/bdv.py`/`MatchingService`.

---

## `suit-frontend`

### Bloque #1 — Login + Discrepancias + Eventos ✅ COMPLETADO Y VERIFICADO E2E

**Propuesto por:** `suit-frontend` · **Estado:** verificado contra backend real (commits `a800935`, `f96364e`)

**Alcance:** contra `CONTRATO-API-ACTUAL.md` (endpoints reales de `suit-conciliacion`):
- Auth: NextAuth con relay manual de la cookie `refresh_token` HttpOnly
  (`authorize()` reenvía el `Set-Cookie` del backend), access token en el JWT de
  sesión (nunca expuesto al cliente), refresh automático en el callback `jwt`.
- Módulo `modules/conciliacion/discrepancias/` (Onion completo: domain/application/
  infrastructure/ui) — listado con filtro por `estado_resolucion`/`severidad`
  (SWR + react-hook-form/zod) y acción de resolver (Dialog + server action).
- Módulo `modules/conciliacion/eventos/` — listado de solo lectura con búsqueda.
- `transacciones-ledger` (detail) queda para un bloque #2.
- Dependencias nuevas: `next-auth`, `swr`, `react-hook-form`, `@hookform/resolvers`,
  `zod`, `sonner`, `next-themes`, shadcn (button, card, field, input, select,
  textarea, dialog, alert-dialog, badge, skeleton, separator).

**Verificación end-to-end contra `suit-conciliacion` real** (no mockeada) —
encontró y corrigió 4 desvíos reales del contrato documentado, que un mock
nunca hubiera revelado:
1. Paginación DRF no documentada: `discrepancias/` y `eventos/` devuelven
   `{count, next, previous, results}`, no un array plano.
2. `logout` requiere `Authorization: Bearer` + `refresh` en el body, la cookie
   sola no alcanza.
3. El `refresh` rota el token en cada llamada (viene también en el body) —
   hay que persistir el nuevo valor, no parsear `Set-Cookie` a mano.
4. Nombre de estado real es `abierta`, no `pendiente` (`Discrepancia.EstadoResolucion`).

Flujo de resolver discrepancia probado con datos reales sembrados en la DB de
`suit-conciliacion`: abierta → resuelta, con `resuelto_por`/`resuelto_at`
mapeados correctamente. `CONTRATO-API-ACTUAL.md` actualizado con los 4 hallazgos.

---

## `suit-portal`

### Bloque #1 — Estructura base + docs + formulario mockeado 🔄 EN EJECUCIÓN

**Propuesto por:** `suit-portal` · **Estado:** autorizado, en curso

**Alcance:** desbloqueado pese al gap #1 de `CONTRATO-API-ACTUAL.md` (CRUD de
registro de apps/dominios no existe todavía en el backend):
1. Layout base, nav, landing del portal.
2. Visor de documentación — iframe a `/api/docs/` de `suit-conciliacion` (único
   backend con Swagger hoy), con nota visible de que `suit-orquestador` aún no
   expone docs — el gap se muestra al usuario, no se oculta.
3. Formulario de registro de aplicación/dominio/proveedor (`modules/registro-aplicaciones/`,
   Onion completo), **submit mockeado con `// TODO` explícito** apuntando al gap
   #1 de `CONTRATO-API-ACTUAL.md` — se conecta al endpoint real cuando exista.
4. Tests: unit (schema de validación), E2E (formulario + mensaje mockeado, sin
   aserciones contra persistencia real), a11y.
- Dependencias nuevas: `zod`, `react-hook-form`, `@hookform/resolvers`, `sonner`,
  shadcn (button, input, label, select, card, field).

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
