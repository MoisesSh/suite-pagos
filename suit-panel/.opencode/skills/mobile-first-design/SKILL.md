---
name: mobile-first-design
description: Diseño mobile-first para un dashboard administrativo. Breakpoints, touch targets, colapso de sidebar, tablas responsive y rendimiento en mobile sobre Next.js + Tailwind v4 + shadcn.
---

# Skill de Diseño Mobile-First

## Breakpoints

| Name    | Width      | Uso en el dashboard                       |
| ------- | ---------- | ----------------------------------------- |
| Mobile  | 320-480px  | Sidebar colapsado, single column          |
| Tablet  | 481-768px  | Sidebar colapsado, grid 2-col             |
| Desktop | 769-1024px | Sidebar abierto por default, grid 2-3 col |
| Large   | 1025px+    | Sidebar fijo, layouts completos           |

Regla: todo layout multi-columna colapsa a single-col en `< 768px` (`md:`).

```css
/* Base (mobile first) */
.grid-cols-1

/* Tablet y desktop */
.md\:grid-cols-2
.lg\:grid-cols-3
```

## Touch Targets (mínimo 48x48px)

| Componente          | Altura actual | Mobile         | Fix                                                            |
| ------------------- | ------------- | -------------- | -------------------------------------------------------------- |
| Button `size="sm"`  | `h-8` (32px)  | ❌ Muy chico   | Usar `size="default"` (`h-9`) o `size="lg"` (`h-10`) en mobile |
| Button `size="xs"`  | `h-6` (24px)  | ❌ Inaccesible | **Baneado en mobile.** Solo para badges/pills no interactivos  |
| `SidebarMenuButton` | `p-2` (~32px) | ❌ Justo       | Sidebar colapsa en mobile — no aplica                          |
| Inputs              | `h-9` (36px)  | ⚠️ Cercano     | Aceptable. Agregar `text-base` en mobile para evitar zoom      |
| Filter pills        | `h-7` (28px)  | ❌ Muy chico   | Usar `h-8` mínimo en mobile                                    |

## Sidebar Mobile

El shadcn `SidebarProvider` con `useIsMobile()` colapsa automáticamente en viewport `< 768px`.

- El `SidebarTrigger` (hamburguesa) debe ser visible y `min-h-[48px] min-w-[48px]`
- El sidebar overlay cubre toda la pantalla en mobile
- **No mostrar `ThemeToggle` en sidebar footer mobile** (se oculta con el colapso)

## Tablas Responsive

Todas las tablas deben tener scroll horizontal en mobile:

```tsx
<div className="overflow-x-auto -mx-4 px-4">
  <table className="min-w-[600px]">...</table>
</div>
```

Archivos que necesitan esto: `data-table.tsx`, cualquier tabla futura.

## Grids Responsive

| Layout desktop          | Layout mobile                               | Archivos                          |
| ----------------------- | ------------------------------------------- | --------------------------------- |
| `grid-cols-3`           | `grid-cols-1 md:grid-cols-2 lg:grid-cols-3` | dashboard steps, KPI cards        |
| `grid-cols-4`           | `grid-cols-2 lg:grid-cols-4`                | KPI cards, métricas               |
| `grid-cols-[1fr_300px]` | `grid-cols-1 lg:grid-cols-[1fr_300px]`      | dashboard layout, vitrina sidebar |

## Performance en Mobile

| Regla              | Detalle                                                                                                |
| ------------------ | ------------------------------------------------------------------------------------------------------ |
| HeroCanvas (bg)    | Desactivar en mobile: check `window.innerWidth < 768` o usar `useIsMobile()`                           |
| LoadingCanvas      | Ya funciona con `prefers-reduced-motion`                                                               |
| Animaciones Motion | `useReducedMotion()` obligatorio en todos los componentes                                              |
| JS bundle          | Lazy-load con `dynamic(() => import(...), { ssr: false })` para canvas, gráficos y componentes pesados |
| Imágenes           | Usar `next/image` con `sizes` y `priority` en hero                                                     |

## Texto Legible sin Zoom

Regla: mínimo `text-sm` (14px / 0.875rem) para cualquier texto legible en mobile.

| Tamaño actual    | Problema           | Fix                                                      |
| ---------------- | ------------------ | -------------------------------------------------------- |
| `text-[10px]`    | Ilegible en mobile | Mínimo `text-xs` (12px). Usar solo en badges no críticos |
| `text-[11px]`    | Ilegible en mobile | Subir a `text-xs` en mobile                              |
| `text-xs` (12px) | Aceptable          | OK para labels, metadatos, badges                        |

## Pre-Flight Checklist Mobile

- [ ] SidebarTrigger visible con touch target ≥ 48px?
- [ ] Tablas tienen `overflow-x-auto` en mobile?
- [ ] Grids colapsan con `grid-cols-1 md:grid-cols-2 lg:grid-cols-3`?
- [ ] Botones interactivos tienen `h-9` mínimo en mobile? (no `size="xs"` ni `size="sm"`)
- [ ] Texto mínimo `text-xs` (12px) en mobile?
- [ ] Canvas/animaciones pesadas se desactivan o lazy-load en mobile?
- [ ] `prefers-reduced-motion` respetado en todas las animaciones?
- [ ] Form inputs tienen `text-base` (16px) en mobile para evitar zoom automático?
- [ ] Layouts de sidebar/grid no usan `h-screen` (usar `min-h-dvh`)?
