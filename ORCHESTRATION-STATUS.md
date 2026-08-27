# Estado de Orquestación — Suite Centralizada de Pagos

> Mantenido por el coordinador (esta sesión). Se actualiza cada vez que un agente entrega
> un avance o cambia de estado. No es responsabilidad de los agentes actualizarlo.

Última actualización: 2026-08-27 12:26

## Estructura del proyecto (monorepo, un único repo git en la raíz)

```
suit_pagos/                    ← repo git único (historial nuevo, commit inicial b904c3d)
├── suit-orquestador/          ← Django/DRF — servicio Orquestador (síncrono), antes "suit-backend"
├── suit-conciliacion/         ← Django/DRF — servicio Conciliación (asíncrono), nuevo
├── suit-frontend/             ← Next.js — panel administrativo interno
├── suit-portal/               ← Next.js — Developer Portal (nuevo, para desarrolladores externos)
├── investigaciones/           ← todos los research-*.md
└── *.md, roadmap.html, PDFs de proveedores
```

Cada subproyecto es independiente en tiempo de ejecución (DB propia, deploy propio),
pero comparten un único repositorio git — decisión explícita del usuario tras
detectar que 3 repos separados generaban fricción operativa innecesaria.

## Objetivo activo

Payment gateway interno para Conatel (Orquestador + Conciliación + Panel + Developer
Portal), según `conatel-suite-pagos-roadmap.html` (ya actualizado con todas las
decisiones de esta sesión).

## Tabla de agentes (7 activos)

| Agente | Sesión Claude | Carpeta | Estado |
|---|---|---|---|
| `research` | `research` | raíz | Transversal, briefeado tras reinicio de runtime, en espera |
| `expert_database` | `expert_database` | `suit-orquestador/` | Modelado Orquestador maduro (`db-plan-pagos.md`) |
| `suit-backend` | `suit-backend` | `suit-orquestador/` | Bloque #1 y #2 completados y verificados contra Postgres real |
| `expert_database_conciliacion` | `expert_database_conciliacion` | `suit-conciliacion/` | Resolvió 6 gaps de modelado en sección 3, 1 punto de negocio resuelto |
| `suit-conciliacion` | `suit-conciliacion` | `suit-conciliacion/` | Bloque de próximo paso #1 autorizado, en ejecución |
| `suit-frontend` | `suit-frontend` | `suit-frontend/` | Panel admin, build verificado, en espera de contrato de API |
| `suit-portal` | `suit-portal` | `suit-portal/` | Developer Portal, scaffold confirmado, en espera de contrato de API de registro de apps/dominios |

## Regla de ejecución vigente (todos los agentes de código)

Ningún agente ejecuta trabajo directamente: arman un **bloque de próximo paso**
(qué se hará, alcance, archivos afectados, qué falta confirmar) y esperan la
orden de ejecución explícita del coordinador antes de tocar código.

**Regla de comunicación (2026-08-27):** ningún agente espera que el usuario
escriba directamente en su terminal, ni se bloquea en un diálogo interactivo
esperando su respuesta — el usuario no mira las terminales de los agentes,
solo el coordinador. Toda pregunta o decisión bloqueante se escribe como texto
plano dirigido al coordinador, y el agente queda en espera normal (no en un
menú de selección). El coordinador la lleva al usuario y trae la respuesta.

## Decisiones de arquitectura confirmadas

- **Monorepo único** en la raíz, historial de git nuevo (no se preservó el de los
  3 repos previos, por decisión del usuario — el historial previo era mínimo).
- **Backend en Django/DRF**, arquitectura híbrida con Rust confirmada para dos
  componentes puntuales cuando el volumen lo justifique: motor de matching de
  Conciliación y validación de balance del ledger de doble entrada (ver
  `ARQUITECTURA-HIBRIDA-RUST.md`). Ambos quedan detrás de un puerto explícito
  desde el día 1, aunque implementados en Python.
- **Multi-proveedor sin choque** es principio de diseño obligatorio.
- **`suit-frontend`** = panel administrativo interno. **`suit-portal`** = Developer
  Portal externo (registro de apps, API keys, dominios, documentación). El
  formulario de cobro real se sirve embebido por iframe en las apps consumidoras
  (`frame-ancestors` dinámico + validación Origin/Referer en backend).
- **Registro de seguridad de apps/dominios** vive en `suit-orquestador` —
  `AplicacionRegistrada`, `DominioPermitido`, `AplicacionProveedorPermitido`.
  Ya implementado y verificado (`ValidacionAccesoService` + endpoint).
- **Bases de datos PostgreSQL completamente separadas** por servicio (no schemas
  compartidos) — `orquestador_pagos` ya creada y en uso; Conciliación tendrá su
  propia base cuando `suit-conciliacion` llegue a las migraciones.
- **RabbitMQ + Celery**, sin Redis como broker (rol futuro acotado a cache/locks).
- **Relay outbox → RabbitMQ**: poller Celery simple (no Debezium/CDC) del lado
  Orquestador. Del lado Conciliación: worker Celery consumiendo directo de la
  cola `pago.*` (patrón estándar, no poller — eso es específico del outbox).
- **Fuera de alcance por ahora**: tarjeta y tokenización. Único medio de pago
  real: BDV Pago Móvil C2P.
- **Manejo de dinero**: `Decimal`/`DECIMAL` nativo, sin librería externa
  (`django-money` evaluada y descartada por ahora — el sistema no hace
  conversión de divisas).
- **Balance-cero del ledger y transiciones de estado**: forzados con
  constraint/trigger a nivel Postgres, no solo disciplina de servicio
  (ya implementado y probado funcionalmente en `suit-orquestador`).
- **Auth de staff de Conciliación**: usuario propio local (`apps/users` dentro
  de `suit-conciliacion`), no identidad de otro servicio — `Discrepancia.resuelto_por`
  es FK real con `SET_NULL`.

## Avances de código verificados

**`suit-orquestador`** (Postgres real, base `orquestador_pagos`):
- `apps/autorizacion`: catálogos (Moneda, MedioPago, ProveedorPago, Banco,
  TipoOperacionProveedor, CodigoRespuestaProveedor), agregado de pago
  (IntencionPago, TransicionEstadoPago, Autorizacion/Captura/Anulacion/Reembolso),
  outbox/idempotencia (EventoOutbox, IdempotencyKey con expires_at=48h).
- Trigger PL/pgSQL de transiciones de estado, probado funcionalmente (acepta
  válidas, rechaza saltos inválidos y estados desincronizados).
- `ValidacionAccesoService` + endpoint `POST /api/autorizacion/validar-acceso/`
  (control de seguridad bloqueante dominio→app→proveedor), 10 tests pasando.
- Commit `f62e3f3` (historial previo, ya integrado al monorepo).

**`suit-conciliacion`**: bloque de próximo paso #1 autorizado y en ejecución
(apps/shared, apps/users con auth JWT local, apps/conciliacion con el agregado
completo de la sección 3 del plan — catálogos, ingesta, matching BDV, ledger
de doble entrada, discrepancias, endpoints mínimos).

**`suit-frontend`** y **`suit-portal`**: solo scaffold verificado (build exitoso),
sin código de dominio — ambos en espera del contrato de API del backend.

## Documentos de referencia

- `conatel-suite-pagos-roadmap.html` — actualizado con todas las decisiones.
- `DB-MODELO.md` — diagramas Mermaid del modelo de datos.
- `ARQUITECTURA-HIBRIDA-RUST.md` — componentes candidatos a extraer a Rust.
- `db-plan-pagos.md` (raíz, copia de referencia; el vivo está en `suit-orquestador/`
  y `suit-conciliacion/`) — plan de datos completo de ambos servicios.
- `investigaciones/*.md` — 10 investigaciones técnicas con evidencia (RabbitMQ vs
  Redis, Rust vs Django, schemas vs bases separadas, manejo de dinero, outbox vs
  CDC, seguridad de iframes, arquitectura backend, etc.)

## Puntos abiertos pendientes de decisión del usuario

1. Proveedor real de tokenización — diferido, fuera de alcance actual.
2. Catálogo definitivo de monedas más allá de VES/USD — no urgente.
3. Confirmar `AppConsumidora`/API keys — resuelto: viven en `suit-orquestador`
   (registro de seguridad), `suit-portal` es solo la interfaz de gestión.
4. Ventana de expiración de `IdempotencyKey.expires_at` — resuelto: 48h.
5. Gobernanza del registro de esquemas de eventos versionados — pendiente,
   no bloqueante para el MVP.
6. Semántica de reintentos multi-adquirente — despriorizado hasta T4.

## Notas operativas

- El runtime de Orca se reinició varias veces durante esta sesión, matando
  terminales de agentes sin previo aviso. El trabajo en archivos nunca se
  perdió (todo en disco/git), solo las sesiones — recrear terminales con
  `orca terminal create` y re-briefar con los archivos ya guardados.
- Los agentes pueden mandarse mensajes entre sí de forma nativa vía Orca
  (`@nombre-agente`) — ya se usó entre `expert_database_conciliacion` y
  `suit-conciliacion` para coordinar el esquema antes de escribir código.
