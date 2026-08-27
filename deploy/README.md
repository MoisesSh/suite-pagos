# Deploy — Suite Centralizada de Pagos

Orquesta los 4 servicios del monorepo con Docker Compose. Build context = raíz
del repo (`..`), para que cada Dockerfile pueda acceder a su carpeta de
servicio vía `--build-arg SERVICE_DIR=<carpeta>`.

## Servicios

| Servicio | Tipo | Puerto | Base de datos propia |
|---|---|---|---|
| `postgres-orquestador` | Postgres 17 | interno | `orquestador_pagos` |
| `postgres-conciliacion` | Postgres 17 | interno | `conciliacion_pagos` |
| `rabbitmq` | RabbitMQ 4.3 (management) | 15672 (UI) | — |
| `flower` | Monitoreo de tareas Celery | 5555 (UI) | — |
| `suit-orquestador` | Django/DRF | 8001 | `postgres-orquestador` |
| `suit-conciliacion` | Django/DRF | 8002 | `postgres-conciliacion` |
| `suit-conciliacion-celery-worker` | Celery worker | — | (comparte DB de conciliación) |
| `suit-frontend` | Next.js (panel admin) | 3000 | — |
| `suit-portal` | Next.js (Developer Portal) | 3001 | — |

**Nota:** `suit-orquestador` no tiene worker Celery propio — su relay
outbox→RabbitMQ es un poller vía Celery beat corriendo dentro del proceso
backend mismo (ver `investigaciones/research-outbox-vs-cdc.md`). Solo
Conciliación necesita un worker separado, porque consume la cola `pago.*`.

**Redis no aparece en este compose a propósito.** No es broker (es RabbitMQ)
ni result backend de Celery (ver `investigaciones/research-rabbitmq-vs-redis.md`
y `investigaciones/research-stack-mensajeria.md`). Si en el futuro se necesita
para cache/locks/rate-limiting, se agrega entonces — no antes.

## Variables de entorno

Cada servicio Django lee su propio `.env` (`suit-orquestador/.env`,
`suit-conciliacion/.env` — ya usados por los agentes en desarrollo, nunca
commiteados). El compose además necesita, en un `.env` junto a este
`docker-compose.yml` (o exportadas en el shell):

```
ORQUESTADOR_DB_USER=postgres
ORQUESTADOR_DB_PASSWORD=<...>
ORQUESTADOR_DB_NAME=orquestador_pagos

CONCILIACION_DB_USER=postgres
CONCILIACION_DB_PASSWORD=<...>
CONCILIACION_DB_NAME=conciliacion_pagos

RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
```

Los frontends leen `suit-frontend/.env.local` y `suit-portal/.env.local`
respectivamente (convención estándar de Next.js).

## Uso

**Importante:** siempre usar `-p suit-pagos` (o el flag `--project-name`) al
correr `docker compose` en esta carpeta. Sin un nombre de proyecto explícito,
Compose usa el nombre del directorio padre (`deploy`) como project name —
si el host tiene otro proyecto con una carpeta `deploy/` (ej. otro repo
llamado igual), Compose puede confundir/detener los contenedores del otro
proyecto al no encontrarlos en este `docker-compose.yml`. Ya ocurrió una vez
en desarrollo — usar siempre `-p suit-pagos` evita el problema.

```bash
# Desarrollo (hot reload, monta el código como volumen)
docker compose -p suit-pagos -f deploy/docker-compose.yml -f deploy/docker-compose.override.yml up -d

# Producción (imágenes optimizadas, sin volúmenes de código)
docker compose -p suit-pagos -f deploy/docker-compose.yml up -d

# Build de un servicio específico (ejemplo: solo el Orquestador)
docker build -f deploy/Dockerfile.backend --build-arg SERVICE_DIR=suit-orquestador -t suit-orquestador:latest .

# Correr solo la suite de tests de un backend (target `tester`, no produce imagen final)
docker build -f deploy/Dockerfile.backend --build-arg SERVICE_DIR=suit-conciliacion --target tester .

# Logs
docker compose -p suit-pagos -f deploy/docker-compose.yml logs -f suit-orquestador suit-conciliacion

# Limpiar todo (incluye volúmenes de datos — perder las bases locales)
docker compose -p suit-pagos -f deploy/docker-compose.yml down -v
```

## Pre-flight checks

- [ ] `docker build --target tester` corre `manage.py check` + tests sin errores (ambos backends)
- [ ] `docker build --target tester` corre `npm run lint` sin errores (ambos frontends)
- [ ] `docker compose up -d` levanta los 8 servicios sin errores
- [ ] Healthcheck de ambos Postgres responde (`pg_isready`)
- [ ] Healthcheck de RabbitMQ responde (`rabbitmq-diagnostics ping`)
- [ ] `suit-orquestador` responde en `http://localhost:8001/api/autorizacion/validar-acceso/`
- [ ] `suit-conciliacion` responde y el worker Celery conecta a RabbitMQ + su Postgres propio
- [ ] `suit-frontend` responde en `http://localhost:3000`
- [ ] `suit-portal` responde en `http://localhost:3001`
- [ ] Ningún contenedor de `suit-orquestador` puede alcanzar `postgres-conciliacion` ni viceversa (verificar aislamiento de red si se usan redes Docker separadas)
