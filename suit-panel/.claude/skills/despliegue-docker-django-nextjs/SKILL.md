---
name: despliegue-docker-django-nextjs
description: Dockerfiles multi-stage y docker-compose para proyectos Next.js + Django + Celery + Redis. Stages optimizados con pnpm, testing, build y producción.
---

# Skill de Despliegue Docker

Crea la infraestructura completa de contenedores para un proyecto Next.js + Django: frontend Next.js, backend Django, Celery worker y Redis.

---

## Estructura generada

```
deploy/
├── Dockerfile.frontend
├── Dockerfile.backend
├── Dockerfile.celery-worker
├── docker-compose.yml
├── docker-compose.override.yml
├── .dockerignore.frontend
├── .dockerignore.backend
└── scripts/
    └── entrypoint.backend.sh
```

---

## 1. Dockerfile.frontend

Multi-stage con 5 etapas: `base` → `deps` → `tester` → `builder` → `runner`.

```dockerfile
# ────────────────────────────────────────
# STAGE 1: base
# Imagen base con Node y pnpm
# ────────────────────────────────────────
FROM node:26-alpine AS base

RUN npm install -g pnpm@10.3.0
WORKDIR /app

# ────────────────────────────────────────
# STAGE 2: deps
# Solo instala dependencias (caché máximo)
# ────────────────────────────────────────
FROM base AS deps

COPY package.json pnpm-lock.yaml ./
RUN pnpm i --no-frozen-lockfile

# ────────────────────────────────────────
# STAGE 3: tester
# Linter, typecheck y tests E2E
# ────────────────────────────────────────
FROM deps AS tester

COPY . .
RUN pnpm lint
RUN pnpm typecheck
# RUN pnpm test:e2e       # descomentar cuando existan tests

# ────────────────────────────────────────
# STAGE 4: builder
# Compila la app Next.js
# ────────────────────────────────────────
FROM base AS builder

COPY --from=deps /app/node_modules ./node_modules

COPY package.json pnpm-lock.yaml tsconfig.json next.config.ts \
     postcss.config.mjs eslint.config.mjs components.json \
     auth.config.ts auth.ts proxy.ts ./

COPY app/ app/
COPY lib/ lib/
COPY modules/ modules/
COPY shared/ shared/
COPY types/ types/
COPY public/ public/

RUN pnpm build

# ────────────────────────────────────────
# STAGE 5: runner
# Imagen final de producción
# ────────────────────────────────────────
FROM base AS runner

ENV PORT=3000
ENV NODE_ENV=production
WORKDIR /app

COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000 || exit 1

CMD ["pnpm", "start"]
```

### Build targets

| Flag      | Comando                           | Uso                                            |
| --------- | --------------------------------- | ---------------------------------------------- |
| `tester`  | `docker build --target tester .`  | CI/CD — ejecuta tests, no produce imagen final |
| `builder` | `docker build --target builder .` | Debug — verifica que el build compila          |
| `runner`  | `docker build --target runner .`  | Producción — imagen final optimizada           |

---

## 2. Dockerfile.backend

Multi-stage: `base` → `deps` → `tester` → `runner`.

```dockerfile
# ────────────────────────────────────────
# STAGE 1: base
# ────────────────────────────────────────
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# ────────────────────────────────────────
# STAGE 2: deps
# ────────────────────────────────────────
FROM base AS deps

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ────────────────────────────────────────
# STAGE 3: tester
# ────────────────────────────────────────
FROM deps AS tester

COPY . .
RUN python manage.py check --deploy
RUN python manage.py test --noinput

# ────────────────────────────────────────
# STAGE 4: runner
# ────────────────────────────────────────
FROM deps AS runner

COPY . .
RUN python manage.py collectstatic --noinput

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python manage.py health_check || exit 1

CMD ["gunicorn", "app.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
```

---

## 3. Dockerfile.celery-worker

```dockerfile
# ────────────────────────────────────────
# STAGE 1: base
# ────────────────────────────────────────
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# ────────────────────────────────────────
# STAGE 2: deps
# ────────────────────────────────────────
FROM base AS deps

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ────────────────────────────────────────
# STAGE 3: runner
# ────────────────────────────────────────
FROM deps AS runner

COPY . .

CMD ["celery", "-A", "app", "worker", "--loglevel=info", "--concurrency=4"]
```

---

## 4. docker-compose.yml

```yaml
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    volumes:
      - postgres_data:/var/lib/postgresql/data
    env_file: .env
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 10s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: deploy/Dockerfile.backend
      target: runner
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - static_volume:/app/staticfiles

  celery-worker:
    build:
      context: .
      dockerfile: deploy/Dockerfile.celery-worker
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    env_file: .env

  frontend:
    build:
      context: ./frontend
      dockerfile: ../deploy/Dockerfile.frontend
      target: runner
    restart: unless-stopped
    depends_on:
      - backend
    env_file: .env
    ports:
      - "3000:3000"

volumes:
  postgres_data:
  redis_data:
  static_volume:
```

---

## 5. docker-compose.override.yml (desarrollo)

```yaml
services:
  backend:
    build:
      target: deps
    volumes:
      - .:/app
    command: python manage.py runserver 0.0.0.0:8000

  celery-worker:
    build:
      target: deps
    volumes:
      - .:/app

  frontend:
    build:
      target: deps
    volumes:
      - ./frontend:/app
      - /app/node_modules
    command: pnpm dev
    environment:
      - NODE_ENV=development

volumes:
  postgres_data:
  redis_data:
  static_volume:
```

Para desarrollo:

```bash
docker compose up -d
```

Para producción:

```bash
docker compose -f docker-compose.yml up -d
```

---

## 6. .dockerignore

### .dockerignore.frontend

```
.git
.gitignore
.next
node_modules
.env
.env.*
*.md
__pycache__
*.pyc
.eslintcache
.next
```

### .dockerignore.backend

```
.git
.gitignore
__pycache__
*.pyc
db.sqlite3
.env
.env.*
*.md
staticfiles
media
```

---

## 7. entrypoint.backend.sh

```bash
#!/bin/sh
set -e

echo "→ Ejecutando migrations..."
python manage.py migrate --noinput

echo "→ Colectando static files..."
python manage.py collectstatic --noinput --clear

echo "→ Iniciando servidor..."
exec "$@"
```

Usar en Dockerfile.backend reemplazando el CMD:

```dockerfile
COPY deploy/scripts/entrypoint.backend.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "app.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
```

---

## 8. Comandos útiles

```bash
# Build solo para testing (CI)
docker build --target tester -t app-frontend:test ./frontend

# Build producción
docker build --target runner -t app-frontend:latest ./frontend

# Build backend
docker build -f deploy/Dockerfile.backend --target runner -t app-backend:latest .

# Levantar todo
docker compose up -d

# Logs
docker compose logs -f backend frontend

# Ejecutar tests en CI sin montar volúmenes
docker build --target tester -t app-frontend:ci ./frontend
docker build -f deploy/Dockerfile.backend --target tester -t app-backend:ci .
```

---

## 9. Pre-flight checks

- [ ] `docker build --target tester` corre lint + typecheck + tests sin errores?
- [ ] `docker build --target runner` produce imagen final < 300MB (frontend)?
- [ ] `docker build -f Dockerfile.backend --target runner` produce imagen final < 500MB (backend)?
- [ ] `docker compose up -d` levanta los 5 servicios sin errores?
- [ ] Healthcheck de PostgreSQL responde (`pg_isready`)?
- [ ] Healthcheck de Redis responde (`redis-cli ping`)?
- [ ] Frontend responde en `http://localhost:3000`?
- [ ] Backend responde en `http://localhost:8000/api/schema/`?
- [ ] Static files servidos correctamente?
- [ ] Celery worker conecta a Redis y backend?
- [ ] `.dockerignore` excluye node_modules, **pycache**, .env, .git?
- [ ] `docker compose down -v` limpia volúmenes sin dejar residuales?
