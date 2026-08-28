# Estado de Orquestación — Suite Centralizada de Pagos

> Mantenido por el coordinador. Punto de partida para retomar la sesión sin
> perder contexto — leer esto primero en una sesión nueva, antes de tocar nada.

Última actualización: 2026-08-27 19:30

## Qué es este proyecto

Payment gateway interno para Conatel: desacopla medios de pago del core de
cada app (Conatel en Línea, Homologación, futuras). Dos servicios de datos
independientes (Orquestador síncrono, Conciliación asíncrona) comunicados
solo por eventos, un panel administrativo, y un Developer Portal. Primer y
único proveedor real: **BDV Pago Móvil C2P** (documentación real de proveedor
ya analizada, no un banco genérico). Ver `conatel-suite-pagos-roadmap.html`
(actualizado con todas las decisiones tomadas) para el contexto de negocio
completo.

## Estructura (monorepo, un único repo git en la raíz)

```
suit_pagos/                    ← repo git único (historial nuevo desde b904c3d)
├── suit-orquestador/          ← Django/DRF — Orquestador (síncrono)
├── suit-conciliacion/         ← Django/DRF — Conciliación (asíncrono)
├── suit-frontend/             ← Next.js — panel administrativo interno
├── suit-portal/               ← Next.js — Developer Portal
├── deploy/                    ← Dockerfiles + docker-compose.yml + .env (gitignored)
├── investigaciones/           ← ~14 research-*.md con evidencia técnica
└── *.md (documentos vivos, ver abajo), roadmap.html, 2 PDFs de BDV
```

Cada subproyecto es independiente en runtime (DB propia, deploy propio),
comparten solo el repo git — decisión explícita del usuario.

## Documentos vivos (leer en este orden para reconstruir contexto)

1. **Este archivo** — estado operativo, cómo retomar.
2. `PLAN-DE-MEJORAS.md` — registro completo de los 12 bloques ejecutados,
   con decisiones tomadas y verificaciones de cada uno. Es el changelog real.
3. `CONTRATO-API-ACTUAL.md` — endpoints reales que existen HOY (no lo
   planificado), con shapes verificados contra servidores reales.
4. `db-plan-pagos.md` (raíz, copia) — plan de datos completo de ambos servicios.
5. `ARQUITECTURA-HIBRIDA-RUST.md` — 2 componentes candidatos a extraer a Rust
   (motor de matching, balance del ledger) cuando el volumen lo justifique.
6. `investigaciones/*.md` — evidencia detrás de cada decisión de stack
   (RabbitMQ vs Redis, Rust vs Django, schemas vs bases separadas, manejo de
   dinero, outbox vs CDC, seguridad de iframe, arquitectura backend).

## Estado de infraestructura AHORA MISMO

**Stack Docker completo corriendo** (`docker compose -p suit-pagos -f deploy/docker-compose.yml`):

| Servicio | URL | Notas |
|---|---|---|
| `suit-orquestador` | http://localhost:8001 | Swagger en `/api/docs/` |
| `suit-conciliacion` | http://localhost:8002 | Swagger en `/api/docs/` |
| `suit-frontend` | http://localhost:3000 | Login real funcionando |
| `suit-portal` | http://localhost:3001 | Formulario de registro conectado real |
| RabbitMQ management | http://localhost:15672 | user/pass guest/guest |
| Flower | http://localhost:5555 | Monitoreo Celery |
| `postgres-orquestador`, `postgres-conciliacion` | internos | Bases separadas, ya migradas |

Usar **siempre `-p suit-pagos`** al correr `docker compose` sobre este
proyecto (evita colisión de nombre con otros proyectos en el mismo host —
ya pasó una vez, ver `PLAN-DE-MEJORAS.md` Bloque #11).

**Servidores de prueba locales (fuera de Docker, para el iframe):**
- `http://127.0.0.1:8010` — `manage.py runserver` de `suit-orquestador`
  corriendo directo (no Docker), sirve `/api/autorizacion/cobro/formulario/`.
- `http://localhost:5500` — servidor estático (`python -m http.server`) que
  sirve `test-iframe-bloque10.html` (scratchpad del agente `suit-backend`),
  necesario para que el origen sea `http://localhost:5500` y no `file://`
  (el CSP `frame-ancestors` rechaza `file://`, correctamente).
- Estos dos **no sobreviven un reinicio de máquina** — si hay que retomar la
  prueba visual del iframe, hay que levantarlos de nuevo (ver comandos abajo).

**Usuario real de staff (panel, `suit-conciliacion`):**
`hmachado@conatel.gob.ve` / `3054=HitM` — `is_staff=True`, `is_superuser=True`.
Vive en la base de Docker (`postgres-conciliacion`), no en ninguna base local.

**Tokens admin generados (para `suit-portal` → CRUD de `suit-orquestador`):**
Token real vive en `suit-portal/.env` (`ORQUESTADOR_ADMIN_TOKEN`) y corresponde
al usuario `portal_admin` en la base Docker de `suit-orquestador`.

## Tabla de agentes (8 activos ahora mismo, en Orca)

| Agente | Handle de terminal | Carpeta | Rol |
|---|---|---|---|
| `research` | `term_58452870-0b7b-4bc2-b292-0b20b1fadb9c` | raíz | Investigación transversal |
| `expert_database` | `term_1dd78f9c-d028-41c9-9bc6-0185f874fd85` | `suit-orquestador/` | Modelado de datos Orquestador |
| `suit-backend` | `term_5f77227b-4a22-406f-b04f-bee4f32177b6` | `suit-orquestador/` | Backend Django Orquestador |
| `expert_database_conciliacion` | `term_6e8d137c-26bf-4db1-abe0-bbd8894813d0` | `suit-conciliacion/` | Modelado de datos Conciliación |
| `suit-conciliacion` | `term_3324f6c0-b75c-4721-ad24-3d018077b762` | `suit-conciliacion/` | Backend Django Conciliación |
| `suit-frontend` | `term_2d26d5f0-4885-4db6-9edf-d180ebd56a73` | `suit-frontend/` | Panel admin Next.js |
| `suit-portal` | `term_77daed55-1eed-43ba-8346-5e84fc4594ea` | `suit-portal/` | Developer Portal Next.js |

**Nota:** hay 4 handles adicionales (`term_c2002c32...`, `term_643afdaf...`,
`term_e624cb9d...`, `term_cf0a073f...`) que son terminales huérfanos de
reinicios previos del runtime de Orca — no usarlos, no están briefeados con
el contexto actual. Si al retomar la sesión los handles de arriba ya no
responden (el runtime de Orca se reinició de nuevo, ya pasó varias veces),
recrear con `orca terminal create --worktree "id:<repoId>::<path>" --command
"claude -n <nombre>"` y re-briefar con los documentos vivos de arriba — el
trabajo real nunca se pierde porque vive en git/Postgres, no en la sesión.

## Reglas de trabajo vigentes (todos los agentes)

1. **Bloque de próximo paso obligatorio**: ningún agente ejecuta código sin
   presentar antes qué va a hacer, alcance, archivos afectados — y esperar
   la orden explícita del coordinador.
2. **Comunicación solo a través del coordinador**: ningún agente espera que
   el usuario escriba directo en su terminal ni se bloquea en un diálogo
   interactivo — las preguntas se escriben como texto plano y el agente
   queda en espera normal.
3. **YAGNI consistente**: no se suma infraestructura/dependencia/abstracción
   sin una necesidad real y medible (aplicado a Redis, Rust, CDC, librerías
   de dinero, roles de usuario — todos evaluados y diferidos hasta que haya
   evidencia real de necesidad).

## Qué se construyó (resumen — detalle completo en `PLAN-DE-MEJORAS.md`)

**`suit-orquestador`** — 13 bloques completados: modelos base, validación de
acceso (dominio→app→proveedor), adaptador BDV C2P real, endpoint público de
cobro (con token de checkout firmado — **fix de seguridad real**: el monto
está atado criptográficamente al token, nunca en un query param editable),
contrato del evento `pago.confirmado` + escritura de outbox, relay
outbox→RabbitMQ, Swagger, CRUD de registro de apps/dominios, **formulario de
cobro embebido por iframe** (con CSP `frame-ancestors` dinámico, selector de
banco poblado desde catálogo real — el hardcode a BDV se corrigió porque
rompía la interoperabilidad interbancaria que el propio servicio soporta).

**`suit-conciliacion`** — modelos completos (ledger de doble entrada,
matching, discrepancias), cliente HTTP real a BDV, worker Celery consumiendo
RabbitMQ real, permisos de staff (solo `is_staff` resuelve discrepancias).
Encontró y corrigió 2 bugs reales de producción (colisión de nombres de cola
Celery/RabbitMQ, migración de trigger nunca probada contra Postgres real).

**`suit-frontend`** — login + Discrepancias + Eventos, verificado end-to-end
contra el backend real (encontró y corrigió 4 desvíos reales del contrato:
paginación DRF, auth de logout, rotación de refresh token, nombre de estado).

**`suit-portal`** — landing, visor de Swagger, formulario de registro de
apps **ya conectado de verdad** (no mockeado) al CRUD del Orquestador.

**Verificación de integración real end-to-end**: cobro real contra BDV QA →
Orquestador → RabbitMQ real → Conciliación → matching → discrepancia. Todo
probado contra infraestructura real, nunca simulado — esto encontró **9 bugs
reales de producción** a lo largo de la sesión (ninguno visible en desarrollo
aislado, todos aparecieron al integrar de verdad).

## Decisiones de arquitectura clave (no reabrir sin evidencia nueva)

- Backend Django/DRF, híbrido con Rust diferido (2 componentes candidatos,
  puertos ya definidos, sin implementar).
- Bases PostgreSQL completamente separadas por servicio (no schemas).
- RabbitMQ + Celery, sin Redis como broker (rol futuro: cache/locks).
- Relay outbox: poller Celery, no CDC/Debezium (documentado como ruta de
  evolución futura si el volumen lo exige).
- Fuera de alcance: tarjeta, tokenización, conversión de divisas.
- Sin librería externa de manejo de dinero (`Decimal` nativo alcanza).
- Auth de staff vía Django admin, sin flujo de autoregistro (volumen bajo,
  interno) — mismo criterio para admin de apps del Orquestador.
- Sentry: evaluado, pospuesto (self-hosted es desproporcionado; se retoma
  con un DSN real, solo el SDK).

## Gaps conocidos, no bloqueantes

1. **Developer Portal sin login propio de usuario externo** — hoy es un
   server Next.js con un token admin fijo en `.env`, no hay auto-registro de
   desarrolladores externos con su propia cuenta. Evaluado explícitamente,
   sin decisión tomada todavía (usuario dijo "ya veremos" sobre otros temas
   similares — mismo criterio probablemente aplica acá).
2. **Sentry** — sin DSN real conectado.
3. **`suit-orquestador` sin auth JWT de usuario final** — solo
   `TokenAuthentication` para admin/M2M; decisión de que el panel
   (`suit-frontend`) solo lee de Conciliación por ahora, no del Orquestador.

## Comandos útiles para retomar

```bash
# Verificar que el stack Docker sigue vivo
docker compose -p suit-pagos -f deploy/docker-compose.yml ps

# Si se cayó, levantarlo de nuevo
docker compose -p suit-pagos -f deploy/docker-compose.yml up -d

# Re-levantar los servidores de prueba del iframe (si hace falta)
cd suit-orquestador && source .venv/Scripts/activate && python manage.py runserver 8010
cd <scratchpad-de-suit-backend> && python -m http.server 5500

# Generar un checkout_token fresco para probar el iframe (vencen a los 15 min)
# Pedirselo directamente al agente suit-backend, sabe el mecanismo exacto
# (CheckoutTokenService.generar) y dónde vive el archivo de prueba.
```
