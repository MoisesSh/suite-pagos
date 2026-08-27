---
name: animaciones-frontend
description: Motion + Animejs + GSAP + CSS animations para frontend. Árbol de decisión, patrones canónigos, reglas, forbidden patterns y pre-flight checks.
---

# Skill de Animaciones Frontend

## Árbol de decisión

| Escenario                                                 | Biblioteca                   | Razón                                               |
| --------------------------------------------------------- | ---------------------------- | --------------------------------------------------- |
| UI state change (toggle, hover, mount/unmount)            | Motion                       | Declarativo, se integra con React                   |
| Scroll-reveal, fade-in-up al entrar al viewport           | Motion `whileInView`         | 3 líneas, nativo, no necesita setup                 |
| Layout animation (reorder, shared element between routes) | Motion `layout` / `layoutId` | Automático, FLIP implícito                          |
| SVG line drawing / morphing                               | Animejs                      | Opera sobre atributos SVG (`strokeDashoffset`, `d`) |
| Text scramble / scatter / decode effect                   | Animejs                      | Imperativo, control frame a frame                   |
| Timeline coreografiado multi-paso                         | Animejs `anime.timeline()`   | Secuencias sin anidar `setTimeout`                  |
| Stagger en grids grandes (>20 items)                      | Animejs                      | Sin re-renders de React, opera sobre DOM directo    |
| Motion path (objeto sigue una trayectoria)                | Animejs                      | `translateX/Y` sobre el DOM, no necesita scroll     |
| Full-page scrolltelling, pinning de secciones             | GSAP + ScrollTrigger         | Scroll primitives maduras (pin, scrub, trigger)     |
| Horizontal scroll hijack                                  | GSAP + ScrollTrigger         | scrub + pin sobre track horizontal                  |
| Canvas 3D, particle systems, backgrounds                  | Three.js / WebGL             | Render fuera del DOM, GPU-accelerado                |
| Hover, focus, active, transition simples                  | CSS transitions              | Zero JS, zero bundle cost                           |

## Reglas generales

- **Una biblioteca por componente.** Si un componente ya usa `motion.div`, no agregues `anime()` o GSAP sobre el mismo elemento. Las bibliotecas compiten por el mismo RAF loop.
- **Reduced motion obligatorio.** Toda animación con `MOTION_INTENSITY > 3` debe degradarse a estático cuando `prefers-reduced-motion: reduce` está activo.
- **Solo `transform` y `opacity`** para animaciones performantes. Nunca animar `top`, `left`, `width`, `height` — causan layout recalculation.
- **Cleanup en todo `useEffect`.** Toda animación creada en un `useEffect` DEBE tener cleanup: `.pause()`, `.kill()`, `.revert()`, o `animation.pause()` en el return. Una fuga de RAF loop es un bug silencioso.

---

## Motion

### Reglas

- Importar desde `motion/react`: `import { motion } from "motion/react"`.
- Usar `useReducedMotion()` para degradar animaciones cuando el usuario prefiere movimiento reducido.
- Aislar en componentes hoja con `"use client"`. Server Components NO pueden usar Motion.
- `useState` NUNCA para valores continuos (mouse position, scroll progress, pointer physics). Usar `useMotionValue` + `useTransform`.
- Para scroll-reveal, preferir `whileInView` sobre `useEffect` + IntersectionObserver.

### Canonical: Scroll-reveal stagger

```tsx
"use client";
import { motion, useReducedMotion } from "motion/react";

export function RevealStagger({ items }: { items: string[] }) {
  const reduce = useReducedMotion();
  return (
    <ul className="grid gap-6">
      {items.map((item, i) => (
        <motion.li
          key={item}
          initial={reduce ? false : { opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{
            duration: 0.6,
            delay: i * 0.06,
            ease: [0.16, 1, 0.3, 1],
          }}
        >
          {item}
        </motion.li>
      ))}
    </ul>
  );
}
```

---

## Animejs

### Reglas

- Importar como `import anime from "animejs"` (default export). No destructurar.
- **Targets siempre son elementos del DOM**: usar `ref` o selectores CSS (`".clase"`, `"#id"`). NUNCA apuntar a componentes React directamente.
- **No usar Animejs para animaciones triviales.** Fade-in simple, hover scale, fade-up reveal → Motion o CSS. Animejs es para lo complejo.
- **No usar `anime.setTimeout`.** Para secuencias multi-paso, usar `anime.timeline()`.
- **No mezclar Animejs con Motion en el mismo componente.** Si el componente ya tiene un `motion.div`, no le agregues `anime()`.
- **No usar Animejs para scroll-driven.** No tiene scroll primitives nativas. Para scroll → GSAP + ScrollTrigger.
- **Cleanup obligatorio:** guardar el return de `anime()` y llamar `.pause()` en el cleanup del `useEffect`.

### Canonical: SVG Line Drawing

```tsx
"use client";
import { useEffect, useRef } from "react";
import anime from "animejs";
import { useReducedMotion } from "motion/react";

export function SvgLineDraw({ paths }: { paths: string[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();

  useEffect(() => {
    if (reduce || !ref.current) return;
    const pathEls = ref.current.querySelectorAll("path");
    const animations = Array.from(pathEls).map((el) => {
      const length = el.getTotalLength();
      el.style.strokeDasharray = String(length);
      el.style.strokeDashoffset = String(length);
      return anime({
        targets: el,
        strokeDashoffset: [length, 0],
        duration: 2000,
        delay: anime.stagger(200),
        easing: "easeInOutQuad",
        autoplay: true,
      });
    });
    return () => animations.forEach((a) => a.pause());
  }, [reduce]);

  return (
    <div ref={ref}>
      {paths.map((d, i) => (
        <path key={i} d={d} />
      ))}
    </div>
  );
}
```

### Canonical: Timeline coreografiado

```tsx
"use client";
import { useEffect, useRef } from "react";
import anime from "animejs";

export function ChoreographedTimeline() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const tl = anime.timeline({ easing: "easeOutExpo", autoplay: true });
    tl.add({ targets: ref.current?.querySelector(".step-1"), translateX: 250, duration: 1000 })
      .add({ targets: ref.current?.querySelector(".step-2"), translateY: 100, duration: 800 })
      .add({ targets: ref.current?.querySelector(".step-3"), scale: 1.5, duration: 600 });
    return () => tl.pause();
  }, []);

  return (
    <div ref={ref}>
      <div className="step-1">Paso 1</div>
      <div className="step-2">Paso 2</div>
      <div className="step-3">Paso 3</div>
    </div>
  );
}
```

### Canonical: Text Scramble

```tsx
"use client";
import { useEffect, useRef } from "react";
import anime from "animejs";

export function TextScramble({ text }: { text: string }) {
  const ref = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const chars = "abcdefghijklmnopqrstuvwxyz!@#$%^&*()";
    const original = text;
    let frame = 0;
    const animation = anime({
      targets: el,
      duration: 1500,
      update: () => {
        frame++;
        const progress = frame / 60;
        const visibleCount = Math.floor(progress * original.length);
        const result = original
          .split("")
          .map((char, i) =>
            i < visibleCount ? char : chars[Math.floor(Math.random() * chars.length)],
          )
          .join("");
        if (el) el.textContent = result;
      },
      complete: () => {
        if (el) el.textContent = original;
      },
    });
    return () => animation.pause();
  }, [text]);

  return <h2 ref={ref}>{text}</h2>;
}
```

---

## GSAP + ScrollTrigger

### Reglas

- Registrar plugin: `gsap.registerPlugin(ScrollTrigger)`.
- **Skeletons canónigos obligatorios:** todo sticky-stack o horizontal-pan debe seguir exactamente los patrones de `start: "top top"`, `pin: true`, `scrub: true/false` de las secciones 5.A y 5.B de `design-taste-frontend`.
- Aislar en `useEffect` con cleanup `() => ctx.revert()`.
- NO usar GSAP para micro-interactions UI. Motion es más liviano y declarativo para eso.
- NO usar `window.addEventListener("scroll", ...)` — para eso está ScrollTrigger.

### Regla de scroll

```tsx
// NO
window.addEventListener("scroll", handler);

// SÍ
gsap.to(el, { scrollTrigger: { trigger, start: "top top", end: "+=500", scrub: true } });
```

---

## Three.js / WebGL

### Reglas

- Solo para: canvas backgrounds, 3D scenes, particle systems, mesh gradients.
- NO usar Three.js para animaciones del DOM layer (botones, cards, texto).
- Lazy-load obligatorio: `dynamic(() => import("./Scene"), { ssr: false })`. Three.js no debe estar en el bundle crítico.
- Aislar en componente hoja con `"use client"`.

---

## Forbidden Patterns (todas las bibliotecas)

| Patrón                                       | Prohibido porque                                         | Alternativa                                                                                      |
| -------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `window.addEventListener("scroll", handler)` | Jank, no batching, corre en cada frame                   | Motion `useScroll()`, GSAP ScrollTrigger, IntersectionObserver, CSS `animation-timeline: view()` |
| `window.scrollY` en React state              | Re-renders en cada frame                                 | `useMotionValue` + `useTransform`                                                                |
| `requestAnimationFrame` tocando React state  | Re-renders en cada frame                                 | motion values, Animejs callbacks, GSAP `onUpdate`                                                |
| Animejs apuntando a un componente React      | No funciona, Animejs opera sobre el DOM real             | Usar `ref` en el elemento HTML subyacente                                                        |
| Motion + GSAP en el mismo componente         | Compiten por el mismo RAF loop, resultados impredecibles | Elegir UNA biblioteca por componente                                                             |
| Motion + Animejs en el mismo elemento        | Conflicto de `transform` y `opacity`                     | Elegir UNA biblioteca por elemento                                                               |
| Animejs para scroll-driven                   | No tiene scroll primitives nativas                       | GSAP + ScrollTrigger                                                                             |
| GSAP para hover/fade-in simples              | Overkill, bundle pesado                                  | CSS transition o Motion                                                                          |
| Animejs para fade-in-up de cards             | Overkill, Motion lo hace en 3 líneas con `whileInView`   | Motion                                                                                           |

---

## Install Commands

```bash
# Motion
pnpm add motion

# Animejs
pnpm add animejs

# GSAP + ScrollTrigger
pnpm add gsap

# Three.js
pnpm add three

# Types (incluidos en motion, animejs, gsap, three — no requieren @types/)
```

---

## Pre-Flight Animation Checks

- [ ] **Animation library justificada:** cada animación no-trivial tiene una biblioteca asignada con una razón (Motion para state-change, Animejs para SVG/timeline, GSAP para scroll)?
- [ ] **Cleanup obligatorio:** todo `useEffect` que crea animaciones llama `.pause()` / `.kill()` / `.revert()` en el return?
- [ ] **No biblioteca incorrecta:** no hay Animejs para fade-in simple, no hay Motion para SVG line drawing, no hay GSAP para hover effect?
- [ ] **No mixing:** ningún componente usa dos bibliotecas de animación diferentes sobre el mismo elemento?
- [ ] **Reduced motion:** toda animación con `MOTION_INTENSITY > 3` respeta `prefers-reduced-motion`?
- [ ] **Solo transform & opacity:** ninguna animación usa `top`, `left`, `width`, `height`?
- [ ] **Animejs targets son DOM:** ningún `anime()` apunta a un componente React directamente (siempre usa refs a elementos HTML)?
