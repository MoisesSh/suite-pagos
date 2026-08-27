# Bloque de próximo paso — Paso 1

**Contexto leído:** `db-plan-pagos.md` (plan de datos de `expert_database`, maduro), `research-brief-pagos.md`, `research-stack-mensajeria.md`, `research-seguridad-iframe.md`. Todos apuntan al mismo primer entregable: el agregado de pago del **Orquestador** con el adaptador BDV C2P, antes que Conciliación (que depende del bus de eventos y es un servicio/DB aparte).

## Qué se haría primero

Módulo Django `apps/autorizacion` (slice del Orquestador, camino síncrono) — **solo modelos + migraciones + admin, sin endpoints todavía**. Razón: el plan marca como control de seguridad bloqueante que el registro de apps/dominios (2.0) exista y sea consultable antes de crear cualquier `IntencionPago`; construir eso primero y validarlo con tests de modelo/servicio antes de exponer HTTP evita levantar endpoints sobre un esquema que aún puede ajustarse.

## Alcance exacto (modelos concretos)

De `db-plan-pagos.md`, secciones 2.0–2.3 (excluyendo explícitamente lo diferido):

- **2.0 Registro de seguridad**: `AplicacionRegistrada`, `DominioPermitido`, `AplicacionProveedorPermitido`.
- **2.1 Catálogos**: `MedioPago`, `ProveedorPago`, `Banco`, `TipoOperacionProveedor`, `CodigoRespuestaProveedor`. (`ProveedorTokenizacion` — **fuera de alcance**, no se crea.)
- **2.2 Agregado de pago**: `IntencionPago`, `TransicionEstadoPago`, `Autorizacion`, `Captura`, `Anulacion`, `Reembolso`. (`TokenReferencia` — **fuera de alcance**, no se crea.)
- **2.3 Outbox/idempotencia**: `EventoOutbox`, `IdempotencyKey`.
- Catálogo `Moneda` poblado con `VES` (activo) + `USD` (reservado/inactivo) según recomendación de la sección 5 del plan.

No se toca `apps/conciliacion` ni su DB en este primer paso.

## Endpoints mínimos

Ninguno en esta primera entrega. El primer endpoint candidato para un segundo paso sería el de validación dominio→app→proveedor (2.0), consumido internamente antes de crear una `IntencionPago` — se propondría en un bloque siguiente, una vez migrados y probados los modelos.

## Qué necesito confirmar antes de ejecutar

1. **Alcance de este repo**: ¿`db-backend` aloja *solo* el Orquestador (una DB), o también Conciliación vía router multi-DB en el mismo proyecto Django? El plan dice "dos bases completamente independientes, sin FK cruzada" pero no aclara si es un proyecto Django o dos. Asumo **solo Orquestador** salvo que corrijas.
2. **Nombre de la app**: propongo `apps/autorizacion` (coincide con el slice del roadmap citado en el brief). Confirmar o indicar otro nombre.
3. **Punto abierto 6 del plan** (`IdempotencyKey.expires_at`): sin valor definido. Propongo default 48h (rango sugerido por el brief) salvo que prefieras dejarlo sin default y definirlo explícito en el service. Necesito tu decisión antes de escribir el modelo.
4. **Mecanismo de transiciones válidas / balance del ledger** (puntos abiertos 5 y el de `TransicionEstadoPago`): el plan deja abierto si se fuerza con `CheckConstraint`/trigger Postgres o solo disciplina de servicio. Para este primer paso (solo Orquestador, sin ledger) solo aplica a `TransicionEstadoPago` — ¿constraint a nivel DB o solo servicio de dominio por ahora?
5. Confirmar que uso `supervision-modelos-bd` (UUIDv7 + `BaseModel`, `PROTECT` en catálogos, `related_name` explícito) tal como indica el plan, sin desviaciones.

Quedo a la espera de tu orden explícita de ejecución (y de las respuestas a 1–4) antes de tocar código.
