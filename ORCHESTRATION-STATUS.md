# Estado de Orquestación — Suite Centralizada de Pagos

> Mantenido por el coordinador (esta sesión). Se actualiza cada vez que un agente entrega
> un avance o cambia de estado. No es responsabilidad de los agentes actualizarlo.

Última actualización: 2026-08-27 08:25

## Objetivo activo

Diseñar el modelo de datos y luego la API/UI para la Suite Centralizada de Pagos
(payment gateway interno), según `conatel-suite-pagos-roadmap.html`: Orquestador
(síncrono) + Conciliación (asíncrono), database-per-service, sin FKs cruzadas.

## Jerarquía y dependencias

```
research (transversal) ──┐
                          ├──> expert_database ──> suit-backend ──> suit-frontend
                          │        (Top)             (Middle)          (Bottom)
```

## Tabla de agentes

| Agente | Sesión Claude | Worktree / carpeta | Estado | Último entregable |
|---|---|---|---|---|
| `research` | `research` | raíz `suit_pagos` | Investigando stack RabbitMQ/Celery/Redis (en curso) | `research-brief-pagos.md` (roadmap + mejores prácticas + hallazgos de 2 PDFs BDV) |
| `expert_database` | `expert_database` | `orca/workspaces/suit-backend/db-backend` | Plan v2 entregado, en espera de aprobación/decisiones | `db-plan-pagos.md` (v2: catálogos Banco/TipoOperacionProveedor/CodigoRespuestaProveedor confirmados con BDV, ConsultaConciliacionProveedor reemplaza el supuesto de feed batch) |
| `suit-backend` | `suit-backend` | `orca/workspaces/suit-backend/db-backend` (mismo worktree, terminal separado) | Skills cargadas, regla de "bloque de próximo paso" aceptada, en espera del esquema final | — (sin código de dominio aún) |
| `suit-frontend` | `suit-frontend` | `orca/workspaces/suit-frontend/ui-frontend` | Skills globales revisadas, regla de "bloque de próximo paso" aceptada, en espera del contrato de API | — (solo scaffold Next.js) |

## Documentos generados para el usuario

- `DB-MODELO.md` (raíz) — diagramas Mermaid (ER Orquestador, ER Conciliación, flujo de eventos) del modelo de `db-plan-pagos.md`.
- `ORCHESTRATION-STATUS.md` (este archivo) — estado vivo de los 4 agentes.

## Insumos ya generados

- `research-brief-pagos.md` — mejores prácticas (outbox, idempotencia, ledger doble entrada,
  tokenización PCI) + hallazgos reales de 2 PDFs de proveedores (C2P Cuentas Múltiples,
  Conciliación Dummy): dos IDs de correlación (referencia corta / end_to_end_id), catálogo
  de bancos, moneda VES con placeholder USD, códigos de error de idempotencia propios del
  proveedor (1026/1094), caso de `cedulaPagador` sustituida en operaciones interbancarias,
  conciliación por polling (no webhook), necesidad de tabla de staging cruda.
- `db-plan-pagos.md` — bosquejo de modelos Django para Orquestador y Conciliación,
  con reglas de `supervision-modelos-bd` aplicadas (UUIDv7, catálogos vs TextChoices,
  matriz on_delete, índices). 8 puntos abiertos de negocio/infra pendientes de decisión.

## Puntos abiertos pendientes de decisión del usuario

1. Proveedor real de tokenización (forma exacta de `TokenReferencia.token`)
2. Catálogo definitivo de monedas soportadas (¿solo VES/USD desde T1?)
3. Confirmar que `AppConsumidora`/API keys viven solo en el Developer Portal
4. Mecanismo de balance-cero del ledger (trigger Postgres vs. validación en servicio)
5. Ventana de expiración de `IdempotencyKey.expires_at` (industria: 24-48h)
6. Gobernanza del registro de esquemas de eventos versionados
7. Semántica de reintentos multi-adquirente (nueva `Autorizacion` vs. nueva `IntencionPago`)
8. Mecanismo del relay outbox → RabbitMQ (poller propio vs. CDC/Debezium)

## Regla de ejecución para `suit-backend` y `suit-frontend`

A partir de ahora, estos dos agentes **no ejecutan trabajo directamente**: antes de
desarrollar/resolver/mejorar/arreglar/optimizar algo, arman un **bloque de próximo paso**
(qué se va a hacer, alcance, archivos afectados) y esperan la orden de ejecución del
coordinador antes de tocar código.

## Decisiones de arquitectura confirmadas (2026-08-27)

- Multi-proveedor sin choque es principio de diseño obligatorio (ningún campo específico
  de proveedor en el agregado de pago; todo lo variable va en catálogos por proveedor).
- `suit-frontend` = panel administrativo interno, NO el formulario de cobro.
- El formulario de cobro se sirve embebido por iframe en las apps consumidoras
  (probablemente servido por `suit-backend`), con `frame-ancestors` dinámico por
  dominio registrado + validación Origin/Referer en backend + postMessage con
  validación de origen (ver `research-seguridad-iframe.md`).
- Registro de seguridad de apps/dominios vive en el Orquestador (`AplicacionRegistrada`,
  `DominioPermitido`, `AplicacionProveedorPermitido`) — si el dominio/app no está
  registrado para ese proveedor, se rechaza. Resuelve el punto abierto 4 del plan de datos.
- Fuera de alcance por ahora: tarjeta y tokenización (`TokenReferencia`,
  `ProveedorTokenizacion` documentados pero no implementados). Único medio de pago real:
  BDV Pago Móvil C2P (de los PDFs que analizó `research`).
- Stack de mensajería verificado: RabbitMQ 4.3.x + Celery ≥5.6.x; Redis no es obligatorio
  (ni broker ni result backend) — rol opcional acotado a locks/rate-limiting/cache si se
  necesita más adelante (`research-stack-mensajeria.md`).

## Bloque de próximo paso #1 — `suit-backend` (COMPLETADO Y VERIFICADO)

`apps/autorizacion` creada con modelos + migraciones + admin del Orquestador
(2.0 registro de apps/dominios, catálogos, agregado de pago, outbox/idempotencia).
Corriendo contra **Postgres real** (base `orquestador_pagos`, credenciales en
`.env`, cubierto por `.gitignore`). Trigger PL/pgSQL de transiciones de estado
verificado funcionalmente (acepta válidas, rechaza saltos inválidos y estados
desincronizados). Seed de monedas (VES activo, USD inactivo) confirmado.

**Siguiente paso en curso:** endpoint de validación dominio→app→proveedor
(control de seguridad bloqueante de la sección 2.0) — autorizado, en ejecución.

**Nota de infraestructura para recordar:** el runtime de Orca se reinició dos
veces durante esta sesión, matando terminales de agentes sin previo aviso
(el trabajo en archivos no se perdió, solo las sesiones). Si vuelve a pasar,
recrear terminales con `orca terminal create` en el mismo worktree y re-briefar
con los archivos ya guardados en disco — no se pierde progreso real.

## Próximos pasos del coordinador

1. Esperar a que `expert_database` termine de refinar `db-plan-pagos.md` con los hallazgos
   de la sección 4 del brief.
2. Decidir con el usuario los puntos abiertos (o delegarlos a `expert_database` con defaults).
3. Pasar el plan final a `suit-backend` para que arme su primer bloque de próximo paso
   (modelos Django reales) y esperar la orden de ejecución.
4. Una vez `suit-backend` entregue el contrato de API, pasarlo a `suit-frontend` para su
   primer bloque de próximo paso.
