---
name: arquitecto-scream-feature-onion
description: Arquitecto SCREAM + Feature-Based + Onion para proyectos con módulos y features. Crea estructuras de carpetas, valida dependencias y sugiere mejoras de modularización.
---

# Arquitecto SCREAM-Feature-Onion

Skill para trabajar con la arquitectura del proyecto basada en Scream + Feature-Based + Onion.

**Los componentes bajo `components/` (y las referencias a `shared/ui/components/` en los diagramas de este documento) son shadcn/ui**: código copiado al repo vía `npx shadcn@latest add <nombre>`, no una dependencia de `node_modules`. No los reescribas a mano — si falta alguno, instálalo con el CLI de shadcn; para dejar el set completo disponible, `npx shadcn@latest add --all`.

---

## Arquitectura del proyecto

### Patrón 1: Módulo simple

```
modules/[modulo]/
├── application/
│   ├── dtos/
│   │   └── [nombre]-dto.ts
│   └── use-cases/
│       ├── list-[nombres].ts
│       ├── create-[nombre].ts
│       ├── update-[nombre].ts
│       └── (otros según necesidad)
├── domain/
│   ├── entities/
│   │   ├── [nombre]-entity.ts
│   │   └── (VOs opcionales en entities o value-objects/)
│   └── ports/
│       └── repo-[nombre].ts
├── infrastructure/
│   ├── actions/
│   │   └── [nombres]-actions.ts
│   ├── http/
│   │   └── [nombres]-api.ts
│   ├── mappers/
│   │   └── mapper-[nombre].ts
│   └── repositories/
│       └── repo-[nombre]-api.ts
└── ui/
    ├── schema/
    │   └── schema-[nombre].ts
    ├── [nombre]-form.tsx
    ├── [nombre]-edit-form.tsx
    └── [nombres]-page.tsx
```

**Ejemplos:** `apoyo/`, `comedor/`, `tickets/`, `usuarios/`, `panel/`, `auth/`

### Patrón 2: Sub-módulo

```
modules/[modulo]/
└── [submodulo]/
    ├── application/
    ├── domain/
    ├── infrastructure/
    └── ui/
```

**Ejemplo:** `transporte/{vehiculos, choferes, rutas, origenes, viajes}/`

Cada sub-módulo replica la misma estructura interna del módulo simple.

### Capas y dependencias (Onion)

La flecha significa "depende de" → **siempre apunta hacia adentro**:

```
ui → infrastructure → application → domain
```

- **domain/** — Sin dependencias externas. Solo tipos/interfaces y factories.
- **application/** — Depende solo de `domain/` (ports, entities).
- **infrastructure/** — Implementa los ports de `domain/`. Depende de `domain/` y `application/`.
- **ui/** — Capa más externa. Depende de `application/` (DTOs, use-cases) y componentes de `shared/`.

### Shared

- `modules/[modulo]/shared/` (opcional) — Código compartido entre features del mismo módulo.
- `shared/` (raíz del proyecto) — Código compartido entre módulos diferentes.

```
shared/
├── commons/
│   └── api.ts                    → API.url (env)
├── hooks/
│   ├── index.ts
│   └── use-mobile.ts
├── index.ts                      → Re-export de todo
├── infrastructure/
│   ├── actions/
│   │   ├── direcciones-actions.ts  → Server actions organizacionales
│   │   └── empleados-actions.ts    → validateCedulaAction
│   └── http/
│       ├── blob-utils.ts           → createDownloadUrl, revokeDownloadUrl
│       ├── direcciones-api.ts      → API calls direcciones
│       ├── errors.ts               → SessionExpiredError
│       ├── fetcher-api.ts          → apiClient (core HTTP)
│       └── query-params.ts         → queryParams()
├── types/
│   ├── api-respose.ts
│   ├── index.ts
│   ├── layout-props.ts
│   └── types-apis.ts
└── ui/
    ├── components/                 → 60+ componentes shadcn/ui
    ├── layout/
    │   ├── breadcrumb.tsx
    │   ├── header-layout.tsx
    │   ├── index.ts
    │   ├── page-layout.tsx
    │   └── session-wrapper.tsx
    └── index.ts
```

**Regla:** si 2+ módulos usan el mismo tipo/schema/componente, migrar a `shared/` raíz.

---

## Mapa de ordenamiento de archivos

### Orden de creación por capa (Onion)

De adentro hacia afuera. Cada archivo solo depende de los que están antes.

| #   | Capa                           | Archivo                  | Depende de                                                     |
| --- | ------------------------------ | ------------------------ | -------------------------------------------------------------- |
| 1   | `domain/value-objects/`        | `[nombre]-vo.ts`         | — (tipos base)                                                 |
| 2   | `domain/entities/`             | `[nombre]-entity.ts`     | VOs (#1)                                                       |
| 3   | `domain/ports/`                | `repo-[nombre].ts`       | entities (#2)                                                  |
| 4   | `application/dtos/`            | `[nombre]-dto.ts`        | entities (#2)                                                  |
| 5   | `application/use-cases/`       | `list-[nombres].ts`      | ports (#3), dtos (#4)                                          |
| 6   | `application/use-cases/`       | `create-[nombre].ts`     | ports (#3), dtos (#4)                                          |
| 7   | `application/use-cases/`       | `update-[nombre].ts`     | ports (#3), dtos (#4)                                          |
| 8   | `infrastructure/mappers/`      | `mapper-[nombre].ts`     | entities (#2)                                                  |
| 9   | `infrastructure/http/`         | `[nombres]-api.ts`       | mappers (#8), `apiClient` (shared)                             |
| 10  | `infrastructure/repositories/` | `repo-[nombre]-api.ts`   | ports (#3), http (#9)                                          |
| 11  | `infrastructure/actions/`      | `[nombres]-actions.ts`   | repos (#10), use-cases (#5-7), `handleSessionExpired` (shared) |
| 12  | `ui/schema/`                   | `schema-[nombre].ts`     | — (solo zod)                                                   |
| 13  | `ui/`                          | `[nombre]-form.tsx`      | schema (#12), actions (#11)                                    |
| 14  | `ui/`                          | `[nombre]-edit-form.tsx` | schema (#12), actions (#11)                                    |
| 15  | `ui/`                          | `[nombres]-page.tsx`     | actions (#11), form (#13)                                      |
| 16  | `app/`                         | `(app)/[ruta]/page.tsx`  | page (#15)                                                     |

### Mapa visual del flujo de datos

**Escritura (crear/actualizar):**

```
form submit
  ↓
[Nombre]Form.tsx                         "use client"
  → startTransition(async () => {
      const r = await create[Nombre]Action(data)
    })
    ↓
[nombres]-actions.ts                     "use server"
  → await create[Nombre](repo, data)
    ↓
create-[nombre].ts                       use case
  → return repo.create(data)
    ↓
repo-[nombre]-api.ts                     repository impl
  → return post[Nombre](dto)
    ↓
[nombres]-api.ts                         http functions
  → return apiClient.post("path/", dto)
    ↓
fetcher-api.ts                           shared apiClient
  → fetch(API.url + path, { headers: { Authorization: Bearer <dj_access> }, body })
    ↓
Backend Django REST
```

**Lectura (listar):**

```
page mount
  ↓
[Nombres]Page.tsx                        "use client"
  → useSWR("key", fetch[Nombres]Action)
    ↓
[nombres]-actions.ts                     "use server"
  → return await list[Nombres](repo)
    ↓
list-[nombres].ts                        use case
  → const entities = await repo.getAll()
  → return entities.map(e => ({ id: e.id, ... }))
    ↓
repo-[nombre]-api.ts                     repository impl
  → return get[Nombres]()
    ↓
[nombres]-api.ts                         http functions
  → const data = await apiClient.get("path/")
  → return data.map(mapper[Nombre])
    ↓
fetcher-api.ts                           shared apiClient
  → fetch(API.url + path, { headers: { Authorization: Bearer <dj_access> } })
    ↓
Backend Django REST
```

### Estructura completa del proyecto

```
raíz/
├── auth.config.ts                       NextAuthConfig (provider Credentials)
├── auth.ts                              NextAuth() (JWT, callbacks)
├── proxy.ts                             Middleware (protección de rutas)
├── next.config.ts                       Configuración Next.js (images, serverActions)
├── components.json                      Configuración shadcn/ui
├── tsconfig.json                        Alias @/* -> raíz (no existen @modules/* ni @shared/*)
├── .env                                 Variables de entorno (desarrollo)
├── .env.example                         Template de variables
│
├── types/                               Tipos compartidos
│   ├── next-auth.d.ts                   Augment Session/User/JWT
│   ├── api-respose.ts                   ApiResponse<T>
│   ├── layout-props.ts                  LayoutPropsInterface
│   └── types-apis.ts                    ResponseDjango<T>
│
├── lib/
│   └── utils.ts                         cn() utility
│
├── shared/                              Código compartido entre módulos
│   ├── index.ts                         Barrel export
│   ├── commons/
│   │   └── api.ts                       API.url = process.env.DJANGO_API_SERVER
│   ├── hooks/
│   │   ├── index.ts
│   │   └── use-mobile.ts
│   ├── types/
│   │   ├── index.ts
│   │   ├── api-respose.ts
│   │   ├── layout-props.ts
│   │   └── types-apis.ts
│   ├── infrastructure/
│   │   ├── http/
│   │   │   ├── errors.ts                SessionExpiredError, handleSessionExpired
│   │   │   ├── query-params.ts          queryParams()
│   │   │   ├── fetcher-api.ts           apiClient (core HTTP)
│   │   │   ├── blob-utils.ts            createDownloadUrl, revokeDownloadUrl
│   │   │   └── direcciones-api.ts       getDependencias, etc.
│   │   └── actions/
│   │       ├── direcciones-actions.ts   fetchDependenciasAction, etc.
│   │       └── empleados-actions.ts     validateCedulaAction
│   └── ui/
│       ├── index.ts                     Barrel export
│       ├── components/                  60+ componentes shadcn/ui
│       │   ├── index.ts                 Barrel de todos los componentes
│       │   ├── field.tsx                Field, FieldLabel, FieldError, FieldDescription, etc.
│       │   ├── input.tsx                Input base
│       │   ├── select.tsx               Select base
│       │   ├── textarea.tsx             Textarea base
│       │   ├── button.tsx               Button base
│       │   ├── card.tsx                 Card, CardHeader, CardContent, etc.
│       │   ├── label.tsx                Label base
│       │   ├── popover.tsx              Popover, PopoverTrigger, PopoverContent
│       │   ├── calendar.tsx             Calendar (react-day-picker)
│       │   ├── dialog.tsx               Dialog, AlertDialog
│       │   ├── alert-dialog.tsx         AlertDialog full
│       │   ├── separator.tsx            Separator
│       │   ├── skeleton.tsx             Skeleton loading
│       │   ├── badge.tsx                Badge
│       │   ├── input-form.tsx           InputForm wrapper
│       │   ├── select-form.tsx          SelectForm wrapper
│       │   ├── date-form.tsx            DateForm wrapper
│       │   ├── file-form.tsx            FileForm wrapper
│       │   ├── textarea-form.tsx        TextareaForm wrapper
│       │   ├── combobox.tsx             Combobox (search + select)
│       │   ├── direccion-admin-selects.tsx  4 selects en cascada
│       │   ├── cedula-search.tsx        Búsqueda por cédula
│       │   ├── reporte-boton.tsx        Botón "Reporte"
│       │   ├── reporte-filtros-dialog.tsx Dialog de filtros para PDF
│       │   ├── app-sidebar.tsx          Sidebar de navegación
│       │   ├── user-avatar.tsx          Avatar del usuario
│       │   ├── logout-button.tsx        Botón de cerrar sesión
│       │   ├── empty.tsx                Estado vacío
│       │   ├── spinner.tsx              Spinner loading
│       │   ├── toast-provider.tsx       Sonner toast provider
│       │   └── ... (resto de shadcn/ui)
│       └── layout/
│           ├── index.ts                 Barrel export
│           ├── page-layout.tsx          PageLayout (title, subTitle, children)
│           ├── header-layout.tsx        HeaderLayout (left, title, right)
│           ├── breadcrumb.tsx           Breadcrumb automático por ruta
│           └── session-wrapper.tsx      SessionProvider wrapper
│
├── modules/                             Módulos del dominio
│   ├── auth/                            Autenticación
│   │   ├── infrastructure/actions/
│   │   │   └── auth-actions.ts          loginAction, logoutAction, changePasswordAction
│   │   └── ui/
│   │       ├── schema/
│   │       │   └── schema-login.ts      signInSchema
│   │       └── login-form.tsx           LoginForm
│   │
│   ├── apoyo/                           Personal de apoyo
│   │   ├── application/dtos/apoyo-dto.ts
│   │   ├── application/use-cases/
│   │   │   ├── list-apoyo.ts
│   │   │   ├── create-apoyo.ts
│   │   │   └── update-apoyo.ts
│   │   ├── domain/entities/apoyo-entity.ts
│   │   ├── domain/entities/origen-apoyo-entity.ts
│   │   ├── domain/ports/repo-apoyo.ts
│   │   ├── infrastructure/actions/apoyo-actions.ts
│   │   ├── infrastructure/http/apoyo-api.ts
│   │   ├── infrastructure/mappers/mapper-apoyo.ts
│   │   ├── infrastructure/repositories/repo-apoyo-api.ts
│   │   └── ui/
│   │       ├── schema/schema-apoyo.ts
│   │       └── apoyo-page.tsx
│   │
│   ├── comedor/                         Comedor
│   │   ├── application/dtos/comedor-dto.ts
│   │   ├── application/use-cases/
│   │   │   ├── create-menu.ts
│   │   │   ├── list-menus.ts
│   │   │   ├── update-menu.ts
│   │   │   ├── list-asistencia.ts
│   │   │   ├── registrar-asistencia.ts
│   │   │   └── obtener-metricas.ts
│   │   ├── domain/entities/menu-entity.ts
│   │   ├── domain/entities/asistencia-entity.ts
│   │   ├── domain/ports/repo-menu.ts
│   │   ├── domain/ports/repo-asistencia.ts
│   │   ├── infrastructure/actions/comedor-actions.ts
│   │   ├── infrastructure/http/comedor-api.ts
│   │   ├── infrastructure/mappers/mapper-menu.ts
│   │   ├── infrastructure/repositories/repo-comedor-api.ts
│   │   └── ui/
│   │       ├── schema/schema-menu.ts
│   │       ├── schema/schema-asistencia.ts
│   │       ├── comedor-page.tsx
│   │       ├── menu-edit-form.tsx
│   │       └── asistencia-page.tsx
│   │
│   ├── tickets/                       Tickets
│   │   ├── application/dtos/ticket-dto.ts
│   │   ├── application/use-cases/
│   │   │   ├── list-tickets.ts
│   │   │   ├── create-ticket.ts
│   │   │   └── asignar-ticket.ts
│   │   ├── domain/entities/ticket-entity.ts
│   │   ├── domain/entities/asignacion-entity.ts
│   │   ├── domain/ports/repo-ticket.ts
│   │   ├── infrastructure/actions/tickets-actions.ts
│   │   ├── infrastructure/actions/asignar-actions.ts
│   │   ├── infrastructure/http/tickets-api.ts
│   │   ├── infrastructure/mappers/mapper-ticket.ts
│   │   ├── infrastructure/repositories/repo-tickets-api.ts
│   │   └── ui/
│   │       ├── schema/schema-ticket.ts
│   │       ├── schema/schema-asignar.ts
│   │       ├── tickets-page.tsx
│   │       ├── ticket-form.tsx
│   │       ├── ticket-detalle-page.tsx
│   │       └── asignar-form.tsx
│   │
│   ├── usuarios/                        Usuarios
│   │   ├── application/dtos/usuario-dto.ts
│   │   ├── application/use-cases/
│   │   │   ├── list-usuarios.ts
│   │   │   ├── create-usuario.ts
│   │   │   ├── update-usuario.ts
│   │   │   └── list-permisos.ts
│   │   ├── domain/entities/usuario-entity.ts
│   │   ├── domain/ports/repo-usuario.ts
│   │   ├── infrastructure/actions/usuarios-actions.ts
│   │   ├── infrastructure/actions/permisos-actions.ts
│   │   ├── infrastructure/http/usuarios-api.ts
│   │   ├── infrastructure/mappers/mapper-usuario.ts
│   │   ├── infrastructure/repositories/repo-usuarios-api.ts
│   │   └── ui/
│   │       ├── schema/schema-usuario.ts
│   │       ├── schema/schema-usuario-edit.ts
│   │       ├── usuarios-page.tsx
│   │       ├── usuario-form.tsx
│   │       ├── usuario-edit-form.tsx
│   │       └── permisos-page.tsx
│   │
│   ├── panel/                          Panel
│   │   ├── application/dtos/panel-dto.ts
│   │   ├── application/use-cases/chart-panel.ts
│   │   ├── domain/entities/service-entity.ts
│   │   ├── domain/ports/repo-panel.ts
│   │   ├── domain/value-objects/services.ts
│   │   ├── infrastructure/http/api-client.ts
│   │   ├── infrastructure/mappers/mapper-services.ts
│   │   ├── infrastructure/repositories/repo-panel-api.ts
│   │   └── ui/panel-page.tsx
│   │
│   └── transporte/                      Transporte (sub-módulos)
│       ├── choferes/
│       │   ├── application/dtos/chofer-dto.ts
│       │   ├── application/use-cases/list-choferes.ts
│       │   ├── domain/entities/chofer-entity.ts
│       │   ├── domain/ports/repo-chofer.ts
│       │   ├── infrastructure/actions/choferes-actions.ts
│       │   ├── infrastructure/http/choferes-api.ts
│       │   ├── infrastructure/mappers/mapper-chofer.ts
│       │   ├── infrastructure/repositories/repo-chofer-api.ts
│       │   └── ui/
│       │       ├── schema/schema-chofer.ts
│       │       ├── choferes-page.tsx
│       │       └── chofer-edit-form.tsx
│       ├── vehiculos/
│       │   ├── application/dtos/vehiculo-dto.ts
│       │   ├── application/use-cases/list-vehiculos.ts
│       │   ├── application/use-cases/create-vehiculo.ts
│       │   ├── application/use-cases/update-vehiculo.ts
│       │   ├── domain/entities/vehiculo-entity.ts
│       │   ├── domain/ports/repo-vehiculo.ts
│       │   ├── infrastructure/actions/vehiculos-actions.ts
│       │   ├── infrastructure/http/vehiculos-api.ts
│       │   ├── infrastructure/mappers/mapper-vehiculo.ts
│       │   ├── infrastructure/repositories/repo-vehiculo-api.ts
│       │   └── ui/
│       │       ├── schema/schema-vehiculo.ts
│       │       ├── vehiculos-page.tsx
│       │       ├── vehiculo-form.tsx
│       │       └── vehiculo-edit-form.tsx
│       ├── rutas/
│       │   ├── ...
│       ├── origenes/
│       │   ├── ...
│       └── viajes/
│           ├── ...
│
├── app/                                 Next.js App Router
│   ├── layout.tsx                        RootLayout (Inter + Outfit, globals.css, ToastProvider)
│   ├── globals.css                       Estilos globales + tailwind
│   ├── favicon.ico
│   │
│   ├── (auth)/                           Rutas públicas (sin sidebar)
│   │   ├── layout.tsx                    AuthLayout (fondo bg.png, centrado)
│   │   ├── login/page.tsx               → LoginForm
│   │   └── signout/page.tsx             Cierra sesión
│   │
│   ├── (app)/                            Rutas protegidas (con sidebar)
│   │   ├── layout.tsx                    AppLayout (auth → SessionWrapper → SidebarProvider)
│   │   ├── loading.tsx                   Loading animado
│   │   ├── error.tsx                     Error boundary (403 → dialog)
│   │   ├── page.tsx                      Panel → PanelPage
│   │   ├── apoyo/page.tsx               → ApoyoPage
│   │   ├── apoyo/[id]/editar/page.tsx   → ApoyoEditForm
│   │   ├── comedor/page.tsx             → ComedorPage
│   │   ├── comedor/asistencia/page.tsx  → AsistenciaPage
│   │   ├── comedor/[id]/editar/page.tsx → MenuEditForm
│   │   ├── tickets/page.tsx           → TicketsPage
│   │   ├── tickets/crear/page.tsx     → TicketForm
│   │   ├── tickets/asignar/page.tsx   → AsignarForm
│   │   ├── tickets/[id]/page.tsx      → TicketDetallePage
│   │   ├── vehiculos/page.tsx           → VehiculosPage
│   │   ├── vehiculos/[id]/editar/page.tsx → VehiculoEditForm
│   │   ├── choferes/page.tsx            → ChoferesPage
│   │   ├── choferes/[id]/editar/page.tsx → ChoferEditForm
│   │   ├── rutas/page.tsx               → RutasPage
│   │   ├── rutas/[id]/editar/page.tsx   → RutaEditForm
│   │   ├── origenes/page.tsx            → OrigenesPage
│   │   ├── origenes/[id]/editar/page.tsx → OrigenEditForm
│   │   ├── viajes/page.tsx              Redirige a /viajes/panel
│   │   ├── viajes/panel/page.tsx        Panel de control
│   │   ├── viajes/asignaciones/page.tsx Asignaciones
│   │   ├── viajes/historial/page.tsx    Historial
│   │   ├── empleados/page.tsx           → UsuariosPage
│   │   ├── empleados/crear/page.tsx     → UsuarioForm
│   │   ├── empleados/[id]/editar/page.tsx → UsuarioEditForm
│   │   ├── permisos/page.tsx            → PermisosPage
│   │   └── admin/page.tsx               → AdminPage
│   │
│   └── api/
│       ├── auth/[...nextauth]/route.ts  NextAuth API handlers
│               └── reportes/pdf/route.ts        Proxy PDF (fetch directo a Django)
```

---

## Configuración del proyecto

Config real (no de plantilla) que rige esta arquitectura. Si alguno de estos archivos cambia, esta sección queda desactualizada — verifica contra el archivo real antes de confiar en el contenido de aquí.

### `tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx",
    "incremental": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "forceConsistentCasingInFileNames": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": [
    "next-env.d.ts",
    "**/*.ts",
    "**/*.tsx",
    ".next/types/**/*.ts",
    ".next/dev/types/**/*.ts",
    "**/*.mts"
  ],
  "exclude": ["node_modules"]
}
```

- **Único alias real: `@/*` → raíz del repo.** No existen `@modules/*` ni `@shared/*` — un import de un módulo se escribe `@/modules/[modulo]/...` y uno de shared, `@/shared/...` o `@/components/...` (ambos resuelven vía `@/*`).
- `strict: true` + `noUnusedLocals`/`noUnusedParameters`/`noImplicitReturns`/`noFallthroughCasesInSwitch`: no relajar estas flags para "hacer pasar" un archivo — corrige el código, no el compilerOptions.
- `pnpm typecheck` corre `tsc --noEmit` con esta config; es parte del gate de `Dockerfile.frontend`.

### `eslint.config.mjs` — arquitectura Onion enforced por `eslint-plugin-boundaries`

Las reglas R1-R3 de la tabla de abajo no son solo convención documentada: están **codificadas** en `eslint.config.mjs` y `eslint` falla si se violan. Los 4 tipos de capa reales (`boundaries/elements`) son `domain`, `application`, `validation` (`ui/schema/**`, los zod schemas — su propio tipo porque las Server Actions los importan para validar en el servidor), `infrastructure-actions`, `infrastructure-http`, `infrastructure-repo` y `ui`:

```js
"boundaries/elements": [
  { type: "domain", pattern: "modules/*/domain/**" },
  { type: "application", pattern: "modules/*/application/**" },
  { type: "validation", pattern: "modules/*/ui/schema/**" },
  { type: "infrastructure-actions", pattern: "modules/*/infrastructure/actions/**" },
  { type: "infrastructure-http", pattern: "modules/*/infrastructure/http/**" },
  { type: "infrastructure-repo", pattern: "modules/*/infrastructure/repositories/**" },
  { type: "ui", pattern: "modules/*/ui/**" },
]
```

Política real (`default: "disallow"`, todo lo no listado explícitamente queda prohibido):

| Desde                    | Puede importar de                                                                     |
| ------------------------ | ------------------------------------------------------------------------------------- |
| `application`            | `domain`                                                                              |
| `infrastructure-http`    | `domain`, `application`                                                               |
| `infrastructure-repo`    | `domain`, `application`, `infrastructure-http`                                        |
| `infrastructure-actions` | `domain`, `application`, `infrastructure-http`, `infrastructure-repo`, `validation`   |
| `ui`                     | `domain`, `application`, `infrastructure-actions`, `ui` (otros módulos), `validation` |
| `domain`                 | nada externo (sin política `allow` → cae en el `disallow` por defecto)                |

Además, `shared/**` tiene su propio boundary (`sharedIsolation`): solo puede depender de `shared/**`, nunca de `modules/**` — si `shared/` importara de un módulo concreto dejaría de ser compartido.

Reglas de estilo/calidad que también exige `eslint.config.mjs` (bloque `codeStyle`, aplican a `**/*.{ts,tsx}`):

- `import/order`: grupos `builtin, external, internal, parent, sibling, index, object, type`, con línea en blanco entre grupos y alfabetizado (case-insensitive).
- `@typescript-eslint/consistent-type-imports`: preferir `import type` para tipos.
- `eslint-config-prettier` va **al final** del array de `defineConfig([...])` — apaga las reglas de estilo de ESLint que chocarían con Prettier. Si se agrega un bloque nuevo de reglas, debe ir antes de `prettierConfig`, nunca después. Detalle completo del formato en la skill `formato-prettier`.

### `components.json` — config de shadcn/ui

```json
{
  "style": "base-nova",
  "rsc": true,
  "tsx": true,
  "tailwind": { "css": "app/globals.css", "baseColor": "neutral", "cssVariables": true },
  "iconLibrary": "lucide",
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  }
}
```

Confirma lo de la skill `patrones-implementacion-frontend`: los componentes en `components/ui/` son shadcn/ui instalado vía `npx shadcn@latest add <nombre>`, con iconos de `lucide-react` y estilos en `app/globals.css`.

### Scripts (`package.json`)

| Script                               | Comando                                     | Uso                                               |
| ------------------------------------ | ------------------------------------------- | ------------------------------------------------- |
| `pnpm dev`                           | `next dev`                                  | Servidor de desarrollo                            |
| `pnpm build` / `start`               | `next build` / `next start`                 | Build y arranque de producción                    |
| `pnpm lint`                          | `eslint`                                    | Arquitectura (`boundaries/*`) + calidad de código |
| `pnpm typecheck`                     | `tsc --noEmit`                              | Chequeo de tipos, sin emitir                      |
| `pnpm format` / `format:check`       | `prettier --write .` / `--check .`          | Formato (ver skill `formato-prettier`)            |
| `pnpm test:unit`                     | `vitest run --project=unit`                 | Unit tests (ver skill `testing-unit-vitest`)      |
| `pnpm test:e2e`                      | `playwright test`                           | E2E (ver skill `testing-e2e-playwright`)          |
| `pnpm storybook` / `build-storybook` | `storybook dev -p 6006` / `storybook build` | Ver skill `storybook-chromatic`                   |

Todos estos (menos `dev`/`storybook`) corren como gate en `Dockerfile.frontend` (stage `tester`) — si alguno falla, el build no llega a producción.

---

## Naming conventions

| Elemento        | Archivo (kebab-case)     | Exports                                                                                                         |
| --------------- | ------------------------ | --------------------------------------------------------------------------------------------------------------- |
| Entity          | `[nombre]-entity.ts`     | `interface [Nombre]Entity`, `function create[Nombre]Entity()`                                                   |
| Value Object    | `[nombre]-vo.ts`         | `type [Nombre]VO`, `function crear[Nombre]VO()`                                                                 |
| Repository port | `repo-[nombre].ts`       | `interface Repo[Nombre]`                                                                                        |
| DTO             | `[nombre]-dto.ts`        | `interface [Nombre]ItemDTO`, `Create[Nombre]DTO`, `Update[Nombre]DTO`                                           |
| Use case        | `[accion]-[nombre].ts`   | `function [accion][Nombre]()`                                                                                   |
| API client      | `[nombres]-api.ts`       | `function get[Nombres]()`, `post[Nombre]()`, `patch[Nombre]()`, `delete[Nombre]()`                              |
| Mapper          | `mapper-[nombre].ts`     | `function mapper[Nombre]()`                                                                                     |
| Repository impl | `repo-[nombre]-api.ts`   | `const repo[Nombre]Api: Repo[Nombre]`                                                                           |
| Server action   | `[nombres]-actions.ts`   | `function fetch[Nombres]Action()`, `create[Nombre]Action()`, `update[Nombre]Action()`, `delete[Nombre]Action()` |
| Zod schema      | `schema-[nombre].ts`     | `const [nombre]FormSchema`, `type [Nombre]FormType`                                                             |
| Form component  | `[nombre]-form.tsx`      | `export default function [Nombre]Form()`                                                                        |
| Edit form       | `[nombre]-edit-form.tsx` | `export default function [Nombre]EditForm()`                                                                    |
| Page component  | `[nombres]-page.tsx`     | `export default function [Nombres]Page()`                                                                       |

> **Nota sobre variaciones:** Las convenciones pueden variar entre módulos. Algunos usan nombres como `Repo[Nombre]` vs `IRepo[Nombre]`, o funciones factory vs funciones sueltas. El estándar documentado aquí es la recomendación. Al trabajar en un módulo existente, **seguir el patrón que ya usa ese módulo**.

### TypeScript

- **Sin `any`** — Usar `unknown` con type guard si es necesario.
- **Tipos explícitos** en parámetros y retornos.
- **`readonly`** en propiedades de entidades.
- **Sin clases** — Solo tipos (`type`/`interface`) + funciones puras + object literals para repositorios.
- **Interfaces para ports** del dominio. Object literals para implementaciones concretas.

### Zod

- Schemas en `ui/schema/schema-[nombre].ts`.
- Usar con `react-hook-form` + `@hookform/resolvers/zod`.
- El schema define el tipo del formulario via `z.infer<>`.
- Los schemas NO se comparten con server actions (cada capa valida por separado).

### Alias de importación

```
@/shared/ui/components/        → Componentes UI compartidos
@/shared/infrastructure/http/  → apiClient, queryParams, errors
@/shared/infrastructure/actions/ → Server actions compartidas
@/shared/                      → Todo el barrel de shared
@/modules/                     → Acceso a módulos
@/lib/utils                    → Utilidades (cn)
@/auth                         → NextAuth instance
```

---

## Auth

### Estructura del módulo auth

```
modules/auth/
├── infrastructure/actions/
│   └── auth-actions.ts   → loginAction, logoutAction, changePasswordAction
└── ui/
    ├── schema/
    │   └── schema-login.ts   → signInSchema (z.object)
    └── login-form.tsx         → LoginForm component
```

### Archivos raíz

```
auth.config.ts   → NextAuthConfig con provider Credentials
auth.ts          → NextAuth() con JWT strategy, callbacks jwt/session
types/next-auth.d.ts → Augment Session/User/JWT
proxy.ts         → Middleware: redirecciona a /login si no auth
```

### Flujo de login

```
LoginForm (cliente)
  → loginAction(cedula, password)      Server Action "use server"
    → signIn("credentials", {...})     next-auth
      → authorize() en auth.config.ts
        → fetch(DJANGO_API_SERVER + "users/auth/")
        → Si ok: guarda dj_access + dj_refresh en cookies (httpOnly)
        → Retorna user con id, name, cedula, permisos, djAccess, djRefresh
      → jwt callback: token ← user
      → session callback: session.user ← token
  → toast.success + router.push("/")
```

### Cookies

| Cookie                    | Propósito            | httpOnly | maxAge  |
| ------------------------- | -------------------- | -------- | ------- |
| `dj_access`               | Token JWT Django     | sí       | 15 min  |
| `dj_refresh`              | Refresh token Django | sí       | 8 horas |
| `next-auth.session-token` | Sesión next-auth     | sí       | 8 horas |

### Layout de rutas

```
app/
├── layout.tsx                        → RootLayout (fonts, ToastProvider)
├── (auth)/
│   ├── layout.tsx                    → AuthLayout (fondo, centrado)
│   ├── login/page.tsx               → LoginForm
│   └── signout/page.tsx             → Cierra sesión
└── (app)/
    ├── layout.tsx                    → AppLayout (auth() session check,
    │                                    SessionWrapper, Sidebar, Header,
    │                                    Breadcrumb)
    ├── loading.tsx                   → Loading spinner animado
    ├── error.tsx                     → Error boundary (403 → diálogo)
    └── [ruta]/page.tsx              → Páginas del módulo
```

---

## Distribución UI (app/ → modules/\*/ui/)

Las páginas en `app/` son **thin wrappers**. La lógica de UI y negocio está en `modules/*/ui/`.

### Patrón A: Thin wrapper (mayoría de casos)

```tsx
// app/(app)/vehiculos/page.tsx
import VehiculosPage from "@/modules/transporte/vehiculos/ui/vehiculos-page";
export default function Page() {
  return <VehiculosPage />;
}
```

### Patrón B: Server component con datos

```tsx
// app/(app)/tickets/page.tsx
import { listTickets } from "@/modules/tickets/application/use-cases/list-tickets";
import { repoTicketsApi } from "@/modules/tickets/infrastructure/repositories/repo-tickets-api";

export default async function Page() {
  const tickets = await listTickets(repoTicketsApi);
  return <TicketsPage tickets={tickets} />;
}
```

### Patrón C: Edit page con fetch + layout

```tsx
// app/(app)/apoyo/[id]/editar/page.tsx
import PageLayout from "@/shared/ui/layout/page-layout";
import ApoyoEditForm from "@/modules/apoyo/ui/apoyo-edit-form";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await obtenerData(repo, Number(id));
  if (!data)
    return (
      <PageLayout title="Error">
        <p>No encontrado</p>
      </PageLayout>
    );
  return (
    <PageLayout title="Editar">
      <ApoyoEditForm data={data} />
    </PageLayout>
  );
}
```

### Layouts compartidos

| Archivo                 | Rol                                                                                            |
| ----------------------- | ---------------------------------------------------------------------------------------------- |
| `app/layout.tsx`        | `Inter` + `Outfit` fonts, `globals.css`, `<ToastProvider />`                                   |
| `app/(app)/layout.tsx`  | `auth()` → `SessionWrapper` → `SidebarProvider` → `AppSidebar` + `HeaderLayout` + `Breadcrumb` |
| `app/(app)/loading.tsx` | Animación de carga con cuadrados rotando                                                       |
| `app/(app)/error.tsx`   | Error boundary: 403 → "Acceso Denegado" dialog, otros → mensaje genérico                       |
| `app/(auth)/layout.tsx` | Fondo fullscreen con `bg.png`, centrado vertical/horizontal                                    |

---

## Fetching

### Shared: apiClient

```typescript
// shared/infrastructure/http/fetcher-api.ts
export const apiClient = {
  get<T>(path): Promise<T>
  post<T>(path, body?): Promise<T>
  patch<T>(path, body?): Promise<T>
  put<T>(path, body?): Promise<T>
  delete<T>(path): Promise<T>
  postForm<T>(path, formData): Promise<T>       // multipart
  patchForm<T>(path, formData): Promise<T>      // multipart
  getBlob(path): Promise<Blob>                  // binario
};
```

Características internas:

- Lee `dj_access` de cookies (httpOnly) y lo inyecta como `Authorization: Bearer`
- En 401: intenta refresh con `dj_refresh`, si falla lanza `SessionExpiredError`
- En 403: lanza `new Error("No Tienes Permiso Para Ejecutar Esta Acción")`
- Si body es `FormData` → elimina `Content-Type` (lo setea el browser)
- `cache: "no-store"` en todas las requests

### Errores

```typescript
// shared/infrastructure/http/errors.ts
export class SessionExpiredError extends Error {
  name = "SessionExpiredError";
}
export function handleSessionExpired(error: unknown): void {
  if (error instanceof SessionExpiredError) redirect("/signout");
}
```

Toda server action debe capturar `SessionExpiredError`:

```typescript
export async function fetchXAction(): Promise<XDTO[]> {
  try {
    return await listX(repoX);
  } catch (error) {
    handleSessionExpired(error);
    throw error;
  }
}

export async function createXAction(values: XFormType) {
  try {
    await createX(repoX, values);
    return { success: "Creado exitosamente" };
  } catch (error) {
    handleSessionExpired(error);
    return { error: error instanceof Error ? error.message : "Error al crear" };
  }
}
```

### Server Actions + SWR (consumo en UI)

```typescript
// En página componente "use client":
const { data: items, isLoading, mutate } = useSWR("key-unica", fetchXAction);

// Después de crear/actualizar/eliminar:
mutate(); // refresca la lista automáticamente
```

### Patrón HTTP por módulo

Cada módulo define en `infrastructure/http/` funciones que envuelven `apiClient`:

```typescript
// modules/[modulo]/infrastructure/http/[nombres]-api.ts
import { apiClient } from "@/shared/infrastructure/http/fetcher-api";
import { Entity } from "../../domain/entities/[nombre]-entity";
import { mapper } from "../mappers/mapper-[nombre]";

export async function getEntities(): Promise<Entity[]> {
  const data = await apiClient.get<Entity[]>("api-path/");
  return data.map(mapper);
}
export async function postEntity(dto: object): Promise<Entity> {
  const data = await apiClient.post<Entity>("api-path/", dto);
  return mapper(data);
}
export async function patchEntity(id: number, dto: object): Promise<Entity> {
  const data = await apiClient.patch<Entity>(`api-path/${id}/`, dto);
  return mapper(data);
}
export async function deleteEntity(id: number): Promise<void> {
  await apiClient.delete(`api-path/${id}/`);
}
```

### Excepciones — no usan apiClient

| Ubicación                                  | Alternativa                           | Motivo                                                                 |
| ------------------------------------------ | ------------------------------------- | ---------------------------------------------------------------------- |
| `auth.config.ts`                           | `fetch()` directo + `cookies().set()` | Necesita setear `dj_access`/`dj_refresh` antes de que exista apiClient |
| `auth-actions.ts` → `changePasswordAction` | `fetch()` directo                     | Llama endpoint distinto de Django                                      |
| `app/api/reportes/pdf/route.ts`            | `fetch()` directo con cookie          | Proxy que streamnea PDF binario descargable                            |

---

## Query params / Search

### Utility

```typescript
// shared/infrastructure/http/query-params.ts
export function queryParams(
  params: Record<string, string | number | boolean | undefined | null>,
): string {
  // Filtra null/undefined/"" → "?clave=valor&clave2=valor2"
}
```

### Patrón: Búsqueda por cédula

```
CedulaSearch (componente cliente)
  → validateCedulaAction(cedula)     server action
    → queryParams({ cedula })         construye ?cedula=123
      → apiClient.get("employees/?" + qs)  filtra en backend
```

```typescript
// shared/ui/components/cedula-search.tsx  ("use client")
const handleValidate = () => {
  startTransition(async () => {
    const r = await validateCedulaAction(cedula);
    if (r.found) onFound({ id: r.id, nombres: r.nombres, ... });
  });
};

// shared/infrastructure/actions/empleados-actions.ts  ("use server")
export async function validateCedulaAction(cedula: string) {
  if (!cedula || cedula.length < 6) return { found: false };
  try {
    const qs = queryParams({ cedula });
    const data = await apiClient.get<EmployeeResponse>(`employees/${qs}`);
    return { found: true, nombres, apellidos, cedulaIdentidad, id };
  } catch {
    return { found: false };
  }
}
```

### Patrón: Filtro opcional

```typescript
// modules/comedor/infrastructure/http/comedor-api.ts
export async function getMenus(onlyActive?: boolean) {
  const qs = queryParams(onlyActive != null ? { only_active: onlyActive } : {});
  const data = await apiClient.get<MenuEntity[]>(`comedor/menus/${qs}`);
  return data.map(mapperMenu);
}
```

### Patrón: Filtros múltiples para reportes

```typescript
const params = { ticket, cedula, fecha_inicio, fecha_fin, niveles, oficina, ... };
const qs = queryParams(params);
const res = await fetch(`/api/reportes/pdf/${qs}`);
const blob = await res.blob();
const url = createDownloadUrl(blob);  // descarga del PDF
```

### Reglas del patrón

1. `queryParams()` se llama desde Server Action o Server Component, nunca directo desde el cliente (excepto proxy de reportes que va a `app/api/`)
2. Los componentes cliente reciben datos ya filtrados
3. `queryParams` omite automáticamente `null`, `undefined`, `""`
4. `CedulaSearch` es el componente compartido para búsqueda de empleados, acepta callback `onFound`

---

## Server Components vs Client Components

### Reglas

| Si necesitas...                                                                     | Marca                            |
| ----------------------------------------------------------------------------------- | -------------------------------- |
| Hooks (`useState`, `useEffect`, `useTransition`, `useForm`, `useSWR`, `useSession`) | `"use client"`                   |
| Eventos (`onClick`, `onChange`, `onSubmit`)                                         | `"use client"`                   |
| Solo renderizar props + JSX                                                         | **Sin** `"use client"`           |
| `async` + `await` para fetch de datos                                               | **Sin** `"use client"`           |
| `auth()` de next-auth                                                               | **Sin** `"use client"`           |
| Componentes shadcn/ui interactivos                                                  | Ya tienen `"use client"` interno |

### Patrón del proyecto

```typescript
// ✅ Server Component — app/(app)/tickets/page.tsx
// No lleva "use client", es thin wrapper o async data fetcher
export default async function Page() {
  const tickets = await listTickets(repoTicketsApi);
  return <TicketsPage tickets={tickets} />;
}

// ✅ Client Component — modules/tickets/ui/tickets-page.tsx
// Lleva "use client" porque usa hooks o eventos
"use client";
export default function TicketsPage({ tickets }: { tickets: TicketItemDTO[] }) {
  // usa useState, useTransition, etc.
}

// ✅ Excepción: páginas con useSWR
"use client";
export default function VehiculosPage() {
  const { data } = useSWR("vehiculos", fetchVehiculosAction);
  // ...
}

// ✅ Excepción: páginas con form submit
"use client";
export default function LoginForm() {
  const form = useForm<loginType>(...);
  // ...
}
```

### Árbol de decisión

```
¿El componente usa hooks, eventos, estado local o interactividad?
├── Sí → "use client"
└── No → ¿Necesita ser asíncrono (async/await)?
    ├── Sí → Server Component (sin "use client")
    └── No → Server Component (sin "use client")
```

**Nota:** Las páginas en `modules/*/ui/` suelen ser `"use client"`. Las páginas en `app/` suelen ser Server Components. Los componentes de `shared/ui/components/` ya manejan su propia directiva internamente.

## .env

### Variables

| Variable                     | Server-only | Dónde se usa                                                                                                                                       |
| ---------------------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DJANGO_API_SERVER`          | ✅          | `shared/commons/api.ts` → base URL de todos los `apiClient` calls. También directo en `auth.config.ts`, `auth-actions.ts`, `reportes/pdf/route.ts` |
| `NEXTAUTH_URL`               | ✅          | next-auth para callbacks                                                                                                                           |
| `AUTH_SECRET`                | ✅          | next-auth para firmar JWT                                                                                                                          |
| `DJANGO_API_URL`             | ✅          | Legacy, no se usa                                                                                                                                  |
| `NEXT_PUBLIC_DJANGO_API_URL` | ❌          | Legacy, no se usa en ningún cliente                                                                                                                |

### Reglas

1. **No se necesita `NEXT_PUBLIC_`** — El `apiClient` corre solo en Server Actions y Server Components. Nunca se expone la URL al cliente.
2. **`DJANGO_API_SERVER` es la única URL que importa** — Definida en `shared/commons/api.ts`, el resto de módulos ni tocan `process.env` directo.
3. **Excepciones** — `auth.config.ts`, `auth-actions.ts` y `reportes/pdf/route.ts` leen `process.env.DJANGO_API_SERVER` directo porque operan fuera del `apiClient`.
4. **Docker** — `next.dockerfile` NO copia `.env`. Las variables se pasan en tiempo de ejecución.
5. **`.env` está en git** — Contiene defaults de desarrollo. `.env.example` es el template. Para producción se sobreescribe con env vars del deployment.

---

## Plantillas de archivos base

### Entity — `domain/entities/[nombre]-entity.ts`

```typescript
export interface [Nombre]Entity {
  readonly id: number;
  [campo]: string;
}

export function create[Nombre]Entity(entity: [Nombre]Entity): [Nombre]Entity {
  if (!entity.[campo]) throw new Error("[Nombre]: [campo] requerido");
  return entity;
}
```

### Value Object — `domain/value-objects/[nombre]-vo.ts`

```typescript
export type [Nombre]VO = {
  readonly value: string;
};

export function crear[Nombre]VO(valor: string): [Nombre]VO {
  if (!valor || valor.trim().length === 0) {
    throw new Error("[Nombre]VO inválido: valor requerido");
  }
  return { value: valor.trim() };
}
```

### Repository port — `domain/ports/repo-[nombre].ts`

```typescript
import type { [Nombre]Entity } from "../entities/[nombre]-entity";

export interface Repo[Nombre] {
  getAll(): Promise<[Nombre]Entity[]>;
  getById(id: number): Promise<[Nombre]Entity>;
  create(params: object): Promise<[Nombre]Entity>;
  update(id: number, params: object): Promise<[Nombre]Entity>;
  remove(id: number): Promise<void>;
}
```

### DTO — `application/dtos/[nombre]-dto.ts`

```typescript
export interface [Nombre]ItemDTO {
  id: number;
  [campo]: string;
}

export interface Create[Nombre]DTO {
  [campo]: string;
}

export interface Update[Nombre]DTO {
  [campo]?: string;
}
```

### Use case — `application/use-cases/[accion]-[nombre].ts`

```typescript
import type { Repo[Nombre] } from "../../domain/ports/repo-[nombre]";
import type { [Nombre]ItemDTO } from "../dtos/[nombre]-dto";

export async function list[Nombres](repo: Repo[Nombre]): Promise<[Nombre]ItemDTO[]> {
  const entities = await repo.getAll();
  return entities.map((e) => ({
    id: e.id,
    [campo]: e.[campo],
  }));
}

export async function create[Nombre](repo: Repo[Nombre], dto: Create[Nombre]DTO): Promise<[Nombre]ItemDTO> {
  const entity = await repo.create(dto);
  return { id: entity.id, [campo]: entity.[campo] };
}
```

### Mapper — `infrastructure/mappers/mapper-[nombre].ts`

```typescript
import { create[Nombre]Entity, [Nombre]Entity } from "../../domain/entities/[nombre]-entity";

export function mapper[Nombre](values: [Nombre]Entity): [Nombre]Entity {
  return create[Nombre]Entity({
    id: values.id,
    [campo]: values.[campo] ?? "",
  });
}
```

### HTTP API — `infrastructure/http/[nombres]-api.ts`

```typescript
import { apiClient } from "@/shared/infrastructure/http/fetcher-api";
import { [Nombre]Entity } from "../../domain/entities/[nombre]-entity";
import { mapper[Nombre] } from "../mappers/mapper-[nombre]";

export async function get[Nombres](): Promise<[Nombre]Entity[]> {
  const data = await apiClient.get<[Nombre]Entity[]>("api-path/");
  return data.map(mapper[Nombre]);
}

export async function post[Nombre](dto: object): Promise<[Nombre]Entity> {
  const data = await apiClient.post<[Nombre]Entity>("api-path/", dto);
  return mapper[Nombre](data);
}

export async function patch[Nombre](id: number, dto: object): Promise<[Nombre]Entity> {
  const data = await apiClient.patch<[Nombre]Entity>(`api-path/${id}/`, dto);
  return mapper[Nombre](data);
}

export async function delete[Nombre](id: number): Promise<void> {
  await apiClient.delete(`api-path/${id}/`);
}
```

### Repository impl — `infrastructure/repositories/repo-[nombre]-api.ts`

```typescript
import type { Repo[Nombre] } from "../../domain/ports/repo-[nombre]";
import { get[Nombres], post[Nombre], patch[Nombre], delete[Nombre] } from "../http/[nombres]-api";

export const repo[Nombre]Api: Repo[Nombre] = {
  getAll: get[Nombres],
  getById: async (id) => { const items = await get[Nombres](); return items.find(i => i.id === id)!; },
  create: post[Nombre],
  update: patch[Nombre],
  remove: delete[Nombre],
};
```

### Server Action — `infrastructure/actions/[nombres]-actions.ts`

```typescript
"use server";

import { repo[Nombre]Api } from "../repositories/repo-[nombre]-api";
import { list[Nombres] } from "../../application/use-cases/list-[nombres]";
import { create[Nombre] } from "../../application/use-cases/create-[nombre]";
import type { [Nombre]ItemDTO } from "../../application/dtos/[nombre]-dto";
import { handleSessionExpired } from "@/shared/infrastructure/http/errors";

export async function fetch[Nombres]Action(): Promise<[Nombre]ItemDTO[]> {
  try {
    return await list[Nombres](repo[Nombre]Api);
  } catch (error) {
    handleSessionExpired(error);
    throw error;
  }
}

export async function create[Nombre]Action(values: {
  [campo]: string;
}) {
  try {
    await create[Nombre](repo[Nombre]Api, values);
    return { success: "[Nombre] creado exitosamente" };
  } catch (error) {
    handleSessionExpired(error);
    return { error: error instanceof Error ? error.message : "Error al crear [nombre]" };
  }
}

export async function delete[Nombre]Action(id: number) {
  try {
    await repo[Nombre]Api.remove(id);
    return { success: "[Nombre] eliminado" };
  } catch (error) {
    handleSessionExpired(error);
    return { error: error instanceof Error ? error.message : "Error al eliminar" };
  }
}
```

### Zod Schema — `ui/schema/schema-[nombre].ts`

```typescript
import { z } from "zod";

export const [nombre]FormSchema = z.object({
  [campo]: z.string().min(1, "El campo es requerido"),
});

export type [Nombre]FormType = z.infer<typeof [nombre]FormSchema>;
```

### Form component — `ui/[nombre]-form.tsx`

```typescript
"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTransition } from "react";
import { toast } from "sonner";
import InputForm from "@/shared/ui/components/input-form";
import SelectForm from "@/shared/ui/components/select-form";
import { Button } from "@/shared/ui/components/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/components/card";
import { Plus, Spinner } from "@phosphor-icons/react";
import { [Nombre]FormType, [nombre]FormSchema } from "./schema/schema-[nombre]";
import { create[Nombre]Action } from "../infrastructure/actions/[nombres]-actions";

interface [Nombre]FormProps {
  onSuccess?: () => void;
}

export default function [Nombre]Form({ onSuccess }: [Nombre]FormProps) {
  const [isPending, startTransition] = useTransition();
  const form = useForm<[Nombre]FormType>({
    resolver: zodResolver([nombre]FormSchema),
    defaultValues: { [campo]: "" },
  });

  const onSubmit = (data: [Nombre]FormType) => {
    startTransition(async () => {
      const r = await create[Nombre]Action(data);
      if (r.error) { toast.error(r.error); return; }
      toast.success(r.success);
      form.reset();
      onSuccess?.();
    });
  };

  return (
    <Card>
      <CardHeader><CardTitle>Nuevo [Nombre]</CardTitle></CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <InputForm form={form} name="[campo]" title="[Campo]" type="text" />
          <Button type="submit" disabled={isPending}>
            {isPending ? <Spinner /> : <Plus />}
            {isPending ? "Creando..." : "Crear [Nombre]"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
```

### Page component — `ui/[nombres]-page.tsx`

```typescript
"use client";

import useSWR from "swr";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import PageLayout from "@/shared/ui/layout/page-layout";
import { Button } from "@/shared/ui/components/button";
import { Card, CardContent } from "@/shared/ui/components/card";
import { Spinner, Pencil, Trash } from "@phosphor-icons/react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/shared/ui/components/alert-dialog";
import { fetch[Nombres]Action, delete[Nombre]Action } from "../infrastructure/actions/[nombres]-actions";
import [Nombre]Form from "./[nombre]-form";

export default function [Nombres]Page() {
  const { data: items, isLoading, mutate } = useSWR("[nombres]", fetch[Nombres]Action);
  const [isPending, startTransition] = useTransition();
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null);

  const handleDeleteConfirm = () => {
    if (!deleteTarget) return;
    startTransition(async () => {
      const r = await delete[Nombre]Action(deleteTarget);
      if (r.error) { toast.error(r.error); setDeleteTarget(null); return; }
      toast.success(r.success);
      setDeleteTarget(null);
      mutate();
    });
  };

  return (
    <PageLayout title="[Nombres]" subTitle="Gestión de [nombres]">
      <[Nombre]Form onSuccess={() => mutate()} />

      {isLoading ? (
        <div className="flex justify-center py-6"><Spinner className="size-6 animate-spin" /></div>
      ) : !items?.length ? (
        <p className="text-center text-muted-foreground py-6">No hay [nombres] registrados.</p>
      ) : (
        <div className="grid gap-3 mt-6">
          {(items ?? []).map((item) => (
            <Card key={item.id}>
              <CardContent className="flex items-center justify-between">
                <span className="text-foreground font-medium">{item.[campo]}</span>
                <button onClick={() => setDeleteTarget(item.id)} className="cursor-pointer p-2 text-muted-foreground hover:text-destructive">
                  <Trash className="size-4" />
                </button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <AlertDialog open={deleteTarget !== null} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar?</AlertDialogTitle>
            <AlertDialogDescription>Esta acción no se puede deshacer.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteConfirm} disabled={isPending} variant="destructive">Eliminar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageLayout>
  );
}
```

---

## Reglas de validación Onion

| Regla   | Violación                                                                               | Mensaje                                                                                                                                     |
| ------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **R1**  | `domain/` importa de `application/`, `infrastructure/`, `ui/` o externo                 | ❌ **R1**: Domain no puede importar de capas externas. Solo puede importar de otros archivos dentro de `domain/`.                           |
| **R2**  | `application/` importa de `infrastructure/` o `ui/`                                     | ❌ **R2**: Application no puede importar de infrastructure ni ui. Solo puede importar de `domain/`.                                         |
| **R3**  | `ui/` importa de `infrastructure/`                                                      | ❌ **R3**: UI no puede importar de infrastructure. Los datos deben llegar por props (DTOs) o Server Actions.                                |
| **R4**  | Un caso de uso instancia un repositorio con `new` o importa una implementación concreta | ❌ **R4**: Los casos de uso deben recibir el repositorio por parámetro (inyección de dependencias), no instanciarlo directamente.           |
| **R5**  | Un componente UI recibe una entidad del dominio en lugar de un DTO                      | ❌ **R5**: UI debe recibir DTOs, no entidades de dominio. Las entidades contienen lógica de dominio que no debe exponerse.                  |
| **R6**  | Imports relativos con más de 2 `../`                                                    | ⚠️ **R6**: Considera usar alias de importación (`@/modules/...`) en lugar de rutas relativas largas.                                        |
| **R7**  | Una Server Action no captura `SessionExpiredError` ni llama `handleSessionExpired()`    | ❌ **R7**: Toda Server Action debe capturar errores y llamar `handleSessionExpired(error)` para redireccionar al login si la sesión expiró. |
| **R8**  | Un componente UI con llamada asíncrona no usa `useTransition`                           | ❌ **R8**: Toda operación asíncrona en UI (submit, delete) debe usar `useTransition` + `startTransition` para manejar loading state.        |
| **R9**  | Archivo de feature no sigue kebab-case                                                  | ❌ **R9**: Los archivos deben usar kebab-case (`vehiculo-entity.ts`, `schema-vehiculo.ts`), no PascalCase ni camelCase.                     |
| **R10** | `app/` page contiene lógica de UI o de negocio en lugar de delegar al módulo            | ⚠️ **R10**: Las páginas en `app/` deben ser thin wrappers. La lógica de UI y negocio debe estar en `modules/*/ui/`.                         |

---

## Comandos

### 1. Crear una feature

```
@skill crea la feature de [nombre] en el módulo [modulo]
```

**Flujo:**

1. Verificar si `modules/[modulo]/` existe. Si no, preguntar si crearlo.
2. Preguntar: _"¿Es un sub-módulo o módulo independiente?"_
3. Crear estructura completa de carpetas según el patrón elegido.
4. Generar archivos base desde las plantillas (entity, port, DTO, use-cases, API, mapper, repo, actions, schema, form, page).
5. Preguntar: _"¿Quieres agregar campos adicionales a la entidad?"_
6. Preguntar: _"¿Usa SelectForm (necesita options de otro módulo) o FileForm (subida de archivos)?"_
7. Preguntar: _"¿Necesita búsqueda por cédula (CedulaSearch)?"_

### 2. Validar una feature

```
@skill valida [feature] en [modulo]
```

Lee todos los archivos de la feature y aplica las reglas de validación Onion (R1-R10). Reporta violaciones con mensajes y sugerencias.

### 3. Sugerir mejoras

```
@skill sugiere mejoras en [modulo]
```

Escanea todas las features del módulo, detecta VOs, tipos, componentes o schemas duplicados. Si encuentra duplicación entre 2+ features, sugiere migrar a `modules/[modulo]/shared/` o `shared/` raíz.

---

## Instrucciones adicionales

1. **Siempre confirmar** antes de sobrescribir archivos existentes.
2. Si el usuario no especifica el módulo, preguntar: _"¿En qué módulo deseas crear la feature? (ej: transporte, apoyo, comedor, tickets, usuarios)"_
3. Al crear una feature, preguntar por campos adicionales después de generar la estructura base.
4. Si durante la validación se detecta que un VO/tipo se repite en 2+ features del mismo módulo, sugerir migrar a `modules/[modulo]/shared/`.
5. Si se repite en 2+ módulos diferentes, sugerir migrar a `shared/` raíz.
6. Revisar que las Server Actions sigan el patrón try/catch con `handleSessionExpired()`.
7. Revisar que los forms usen `useTransition` para loading states.
8. Verificar que los archivos sigan kebab-case.
