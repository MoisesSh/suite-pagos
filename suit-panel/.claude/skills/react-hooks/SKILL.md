---
name: react-hooks
description: Hooks de React (useState, useEffect, useLayoutEffect, useMemo, useCallback, useRef, useContext, useReducer, useTransition, useDeferredValue, useId, useSyncExternalStore, use()) — reglas de los Hooks, custom hooks, cuándo NO usar useEffect, errores comunes (dependencias, closures obsoletas, Strict Mode) y patrones recomendados con React 19+. Skill genérica, aplicable a cualquier proyecto React/Next.js.
---

# React Hooks

Skill de referencia genérica sobre Hooks de React (React 19+). No asume ningún proyecto ni framework de UI concretos — aplica a cualquier componente de función en React o Next.js (App Router o Pages Router).

El principio rector de toda esta skill: **un Hook con estado (`useState`, `useEffect`, `useReducer`) es la excepción, no el default.** Antes de reachear por uno, pregunta si el valor puede calcularse durante el render o resolverse directamente en un event handler (ver §4). El código sin Hooks innecesarios es más simple, más rápido y tiene menos bugs.

---

## 1. Reglas de los Hooks (Rules of Hooks)

### Regla 1: Solo llamar Hooks en el nivel superior

Nunca dentro de condicionales, loops, funciones anidadas, `try/catch`, ni después de un `return` condicional. React depende del **orden** de las llamadas a Hooks entre renders para asociar cada llamada con su estado interno — si el orden cambia entre renders, el estado se desincroniza silenciosamente.

```tsx
// ❌ Dentro de un condicional
function Bad({ cond }: { cond: boolean }) {
  if (cond) {
    const theme = useContext(ThemeContext);
  }
}

// ❌ Después de un return condicional
function Bad({ cond }: { cond: boolean }) {
  if (cond) return null;
  const theme = useContext(ThemeContext);
}

// ❌ Dentro de un event handler o de otro Hook
function Bad() {
  const style = useMemo(() => {
    const theme = useContext(ThemeContext); // un Hook no puede llamar a otro Hook así
    return { color: theme };
  }, []);
}
```

### Regla 2: Solo llamar Hooks desde funciones de React

Solo desde componentes de función o desde otros custom Hooks — nunca desde una función JS regular ni desde un componente de clase.

```tsx
// ❌ Función JS regular
function getStatus() {
  const [status] = useOnlineStatus();
  return status;
}

// ✅ Componente de función
function StatusBadge() {
  const [status] = useOnlineStatus();
  return <span>{status}</span>;
}
```

### Herramienta de validación

`eslint-plugin-react-hooks` detecta automáticamente violaciones de ambas reglas en tiempo de desarrollo. Su regla `exhaustive-deps` valida además el array de dependencias de `useEffect`/`useMemo`/`useCallback` (ver §5.1). **Nunca deshabilites `exhaustive-deps` con un comentario para silenciar un warning** — el warning casi siempre señala un bug real (closure obsoleta), no un falso positivo. Si el linter parece equivocarse, la solución es reestructurar el código (§5), no silenciarlo.

---

## 2. Hooks built-in: qué resuelven, cuándo usarlos, cuándo no

### `useState` — estado local

```tsx
const [count, setCount] = useState(0);
setCount((c) => c + 1); // función actualizadora: no depende del valor "cerrado" del render actual
```

**No usar cuando** el valor puede **derivarse** de props/otro estado durante el render — eso duplica una fuente de verdad que puede desincronizarse (ver §4.1).

### `useEffect` — sincronizar con un sistema externo

Sirve para sincronizar un componente con algo que vive **fuera de React**: red, DOM, suscripciones de terceros, temporizadores, APIs del navegador sin equivalente declarativo. No es para transformar datos ni para reaccionar a eventos del usuario (ver §4).

```tsx
useEffect(() => {
  const controller = new AbortController();
  fetch(url, { signal: controller.signal })
    .then((r) => r.json())
    .then(setData)
    .catch((err) => {
      if (err.name !== "AbortError") throw err;
    });
  return () => controller.abort(); // cleanup
}, [url]);
```

### `useLayoutEffect` — igual que `useEffect`, pero antes del paint

Se ejecuta sincrónicamente **antes de que el navegador pinte** la pantalla. Úsalo solo cuando necesitas medir el DOM (layout, tamaño, posición) y mutar el DOM/estado antes de que el usuario vea un parpadeo visual (FOUC). Bloquea el pintado, así que usarlo de más degrada el rendimiento percibido.

**Regla práctica:** empieza siempre con `useEffect`; migra a `useLayoutEffect` solo si aparece un flash visual causado por una medición de layout.

### `useMemo` — cachear un cálculo

```tsx
const visibleItems = useMemo(() => filterAndSort(items, filter), [items, filter]);
```

Cachea el **resultado** de un cálculo, recalculando solo si cambian sus dependencias. Para cálculos baratos (aritmética simple, formateo corto), el costo de comparar dependencias puede superar al del propio cálculo — no memoices por costumbre. Con el React Compiler activo (§6.3), buena parte de estos usos manuales dejan de hacer falta.

### `useCallback` — cachear la identidad de una función

```tsx
const handleClick = useCallback(() => doSomething(id), [id]);
```

Cachea la **identidad** de una función entre renders, para no romper la memoización de un hijo (`React.memo`) ni disparar de más un efecto que la tenga como dependencia. El caso de uso más sólido en 2026 (con Compiler) sigue siendo cuando la identidad de la función es parte de un **contrato con un sistema externo**: un event listener nativo, o una librería de terceros que compara por referencia.

### `useRef` — valor mutable fuera del ciclo de render

```tsx
const inputRef = useRef<HTMLInputElement>(null);
const intervalRef = useRef<number | null>(null);
```

Guarda un valor mutable (`ref.current`) que persiste entre renders **sin disparar re-render** al cambiar. Dos usos: referencia a un nodo DOM, o "caja mutable" para cualquier valor que no debe formar parte del ciclo de render (id de un `setInterval`, valor anterior de una prop, flag de "ya inicializado"). **No lo uses** para valores que la UI debe reflejar — eso es `useState`.

### `useContext` — leer un Context

```tsx
const theme = useContext(ThemeContext);
```

Lee el valor del proveedor de Context más cercano por encima en el árbol, evitando prop drilling. Debe llamarse en el nivel superior del componente (no condicionalmente) — a diferencia de `use()` (§2.11).

### `useReducer` — estado con transiciones complejas

Alternativa a `useState` cuando el próximo estado depende de combinar varias piezas del estado anterior, o cuando hay múltiples transiciones de estado que se repiten en distintos handlers. Centraliza la lógica en una función reducer pura, testeable sin renderizar nada.

```tsx
type Action = { type: "increment" } | { type: "reset" };

function reducer(state: { count: number }, action: Action) {
  switch (action.type) {
    case "increment":
      return { count: state.count + 1 };
    case "reset":
      return { count: 0 };
  }
}

const [state, dispatch] = useReducer(reducer, { count: 0 });
```

### `useTransition` — actualizaciones no urgentes

```tsx
const [isPending, startTransition] = useTransition();

function selectTab(nextTab: string) {
  startTransition(() => setTab(nextTab));
}
```

Marca una actualización de estado como no bloqueante: React sigue respondiendo a la interacción del usuario mientras procesa un render pesado en segundo plano.

**Limitaciones:**

- No sirve para controlar directamente el valor de un `<input>` de texto — ese valor siempre debe actualizarse de forma síncrona/urgente.
- Un `setState` ejecutado **después de un `await`** dentro de `startTransition(async () => {...})` deja de contarse como transición; hay que volver a envolverlo: `startTransition(() => setPage(...))` tras el `await`.
- Puede ser interrumpida por una interacción más urgente del usuario.

### `useDeferredValue` — diferir un valor

```tsx
const [query, setQuery] = useState("");
const deferredQuery = useDeferredValue(query, ""); // 2º argumento = initialValue (React 19)

// El input siempre responde de inmediato:
<input value={query} onChange={(e) => setQuery(e.target.value)} />
// Esta parte cara de la UI se actualiza "atrasada":
<SearchResults query={deferredQuery} />
```

Diferencia con `useTransition`: `useDeferredValue` difiere un **valor** que llega por props/estado ya existente (útil cuando no controlas el código que dispara la actualización); `useTransition` envuelve explícitamente la **función** que actualiza el estado.

### `useId` — id único estable

Genera un id único por instancia de componente, consistente entre servidor y cliente (evita mismatches de hidratación). Uso típico: asociar `<label htmlFor>` con un `<input id>` generado dinámicamente, o ids de atributos ARIA. No lo uses para `key`s de listas ni para ids que deban ser deterministas entre distintos componentes.

### `useSyncExternalStore` — suscribirse a un store externo sin tearing

```tsx
function useOnlineStatus(): boolean {
  const subscribe = (callback: () => void) => {
    window.addEventListener("online", callback);
    window.addEventListener("offline", callback);
    return () => {
      window.removeEventListener("online", callback);
      window.removeEventListener("offline", callback);
    };
  };
  return useSyncExternalStore(
    subscribe,
    () => navigator.onLine,
    () => true,
  );
}
```

Es el reemplazo recomendado del patrón "suscribirse a un evento del navegador con `useEffect` + `useState`" (§4.9): evita "tearing" (que distintas partes de la UI muestren snapshots inconsistentes del store durante una actualización concurrente).

### `use()` (React 19) — leer una Promise o un Context durante el render

No es técnicamente un "Hook" en el sentido estricto de las reglas del §1: **puede llamarse condicionalmente**.

```tsx
// Lee Context — a diferencia de useContext, sí puede ir dentro de un if
function HorizontalRule({ show }: { show: boolean }) {
  if (show) {
    const theme = use(ThemeContext);
    return <hr className={theme} />;
  }
  return null;
}

// Lee una Promise — el componente se suspende mientras está pendiente
function Albums({ albumsPromise }: { albumsPromise: Promise<Album[]> }) {
  const albums = use(albumsPromise);
  return (
    <ul>
      {albums.map((a) => (
        <li key={a.id}>{a.title}</li>
      ))}
    </ul>
  );
}
// <Suspense fallback={<Loading />}>
//   <ErrorBoundary fallback={<Err />}><Albums albumsPromise={cachedPromise} /></ErrorBoundary>
// </Suspense>
```

**Reglas críticas de `use()` con promesas:**

1. La promesa debe estar **cacheada** (misma instancia entre renders). Crear la promesa inline en cada render (`use(fetch(url))`) produce un loop de Suspense o el error "A component was suspended by an uncached promise". Patrón correcto: un `Map` de caché por URL/key, o una librería de data-fetching que ya cachea (React Query, SWR, `fetch` de un Server Component).
2. No envuelvas `use()` en `try/catch` — usa un `<ErrorBoundary>` para manejar el rechazo.
3. No leas manualmente `promise.status`/`promise.value` como atajo; siempre pasa la promesa a `use()`.
4. Debe llamarse dentro de un componente o Hook, nunca a nivel de módulo.

---

## 3. Custom Hooks

### Convención de nombres

Debe empezar con `use` + mayúscula (`useOnlineStatus`, `useFormInput`), igual que los Hooks nativos. Esto habilita dos cosas: que el linter de Hooks verifique las reglas del §1 sobre él, y que cualquier lector sepa, solo por el nombre, que la función puede contener estado/efectos de React y debe seguir las reglas de Hooks.

Si una función no usa ningún Hook por dentro, **no debe** llevar el prefijo `use` — es una función utilitaria regular (`getSortedItems(items)`, no `useSortedItems(items)`).

### Cuándo extraer un custom Hook

Cuando la misma lógica con estado (típicamente `useState` + `useEffect` juntos) se repite, textualmente o casi, en dos o más componentes.

```tsx
// Antes: duplicado en dos componentes distintos
const [isOnline, setIsOnline] = useState(true);
useEffect(() => {
  function handleOnline() {
    setIsOnline(true);
  }
  function handleOffline() {
    setIsOnline(false);
  }
  window.addEventListener("online", handleOnline);
  window.addEventListener("offline", handleOffline);
  return () => {
    window.removeEventListener("online", handleOnline);
    window.removeEventListener("offline", handleOffline);
  };
}, []);

// Después: extraído a useOnlineStatus.ts
export function useOnlineStatus(): boolean {
  const [isOnline, setIsOnline] = useState(true);
  useEffect(() => {
    function handleOnline() {
      setIsOnline(true);
    }
    function handleOffline() {
      setIsOnline(false);
    }
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);
  return isOnline;
}
// Uso: const isOnline = useOnlineStatus();
```

**Punto crítico:** los custom Hooks comparten **lógica** con estado, no el **estado en sí** — cada llamada crea su propia instancia de estado independiente (igual que llamar `useState` dos veces con nombres distintos).

**Anti-patrón:** Hooks "de ciclo de vida" genéricos sin propósito de dominio claro (`useMount(fn)`, `useUpdate(fn)`). Prefiere Hooks enfocados en un caso de uso concreto (`useChatRoom`, `useDebouncedSearch`) en vez de envoltorios genéricos alrededor de `useEffect`.

### Custom Hooks de referencia

```tsx
// useDebounce — retrasa la propagación de un valor N ms
function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}

// useLocalStorage — sincroniza un estado con localStorage
function useLocalStorage<T>(key: string, initialValue: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = window.localStorage.getItem(key);
      return raw ? (JSON.parse(raw) as T) : initialValue;
    } catch {
      return initialValue;
    }
  });
  useEffect(() => {
    window.localStorage.setItem(key, JSON.stringify(value));
  }, [key, value]);
  return [value, setValue] as const;
}

// useMediaQuery — se suscribe a un matchMedia con useSyncExternalStore (sin tearing)
function useMediaQuery(query: string): boolean {
  const subscribe = (callback: () => void) => {
    const mql = window.matchMedia(query);
    mql.addEventListener("change", callback);
    return () => mql.removeEventListener("change", callback);
  };
  const getSnapshot = () => window.matchMedia(query).matches;
  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}

// useOnClickOutside — detecta clicks fuera de un elemento referenciado
function useOnClickOutside<T extends HTMLElement>(
  ref: React.RefObject<T | null>,
  handler: () => void,
) {
  const onClickOutside = useEffectEvent(handler); // ver §6.5
  useEffect(() => {
    function listener(event: MouseEvent) {
      if (!ref.current || ref.current.contains(event.target as Node)) return;
      onClickOutside();
    }
    document.addEventListener("mousedown", listener);
    return () => document.removeEventListener("mousedown", listener);
  }, [ref]);
}

// usePrevious — guarda el valor de la render anterior sin disparar render
function usePrevious<T>(value: T): T | undefined {
  const ref = useRef<T>(undefined);
  useEffect(() => {
    ref.current = value;
  });
  return ref.current;
}
```

---

## 4. Cuándo NO usar `useEffect`

Principio general (react.dev, "You Might Not Need an Effect"): un Effect es un escape hatch para sincronizar con un **sistema externo**. Si no hay ningún sistema externo involucrado, probablemente no hace falta un Effect.

### 4.1 Transformar/derivar datos para el render → calcular durante el render

```tsx
// ❌
const [fullName, setFullName] = useState("");
useEffect(() => setFullName(firstName + " " + lastName), [firstName, lastName]);

// ✅ Se recalcula en cada render, sin Effect
const fullName = firstName + " " + lastName;
```

Si el cálculo es costoso, usa `useMemo` en vez de `useState` + `useEffect` — sigue siendo "durante el render", solo que cacheado.

### 4.2 Resetear todo el estado de un componente al cambiar una prop clave → usar `key`

```tsx
// En vez de un Effect que detecta el cambio de userId y resetea manualmente cada state:
<Profile userId={userId} key={userId} />
// Al cambiar el key, React destruye y remonta el componente, reseteando su estado automáticamente.
```

### 4.3 Ajustar (no resetear todo) el estado cuando cambia una prop → ajustar durante el render

```tsx
// ❌ Effect que detecta el cambio de `items` y limpia `selection`
useEffect(() => {
  if (items !== prevItems) setSelection(null);
}, [items]);

// ✅ Guardar solo el id y derivar la selección durante el render
const [selectedId, setSelectedId] = useState<string | null>(null);
const selection = items.find((item) => item.id === selectedId) ?? null;
```

### 4.4 Compartir lógica entre varios event handlers → extraer una función

```tsx
// ❌ Effect que reacciona a un cambio de estado
useEffect(() => {
  if (product.isInCart) showNotification(`Agregado ${product.name}`);
}, [product]);

// ✅ Función común llamada directamente desde cada handler
function buyProduct() {
  addToCart(product);
  showNotification(`Agregado ${product.name}`);
}
function handleBuyClick() {
  buyProduct();
}
function handleCheckoutClick() {
  buyProduct();
  navigateTo("/checkout");
}
```

### 4.5 Enviar un POST o analítica al enviar un formulario → en el event handler

```tsx
// ✅ Analítica de "vista" sí puede ir en un Effect (sucede porque el componente se mostró)
useEffect(() => {
  post("/analytics/event", { eventName: "visit_form" });
}, []);

// ✅ El submit (una acción del usuario) va en el handler, no en un Effect que "observe" un flag
function handleSubmit(e: React.FormEvent) {
  e.preventDefault();
  post("/api/register", { firstName, lastName });
}
```

### 4.6 Encadenar cálculos (un Effect dispara un setState que dispara otro Effect) → resolver todo en el handler

```tsx
// ❌ Cadena de Effects — cada paso es un render extra, y es frágil ante nuevos requisitos
useEffect(() => {
  if (card?.gold) setGoldCardCount((c) => c + 1);
}, [card]);
useEffect(() => {
  if (goldCardCount > 3) setRound((r) => r + 1);
}, [goldCardCount]);

// ✅ Todo resuelto en el mismo handler que originó el cambio
function handlePlaceCard(nextCard: Card) {
  setCard(nextCard);
  if (nextCard.gold) {
    if (goldCardCount < 3) setGoldCardCount(goldCardCount + 1);
    else {
      setGoldCardCount(0);
      setRound(round + 1);
    }
  }
}
```

### 4.7 Inicializar la aplicación una sola vez → guard fuera del componente

```tsx
let didInit = false;
function App() {
  useEffect(() => {
    if (!didInit) {
      didInit = true;
      loadDataFromLocalStorage();
      checkAuthToken();
    }
  }, []);
}
```

Necesario porque en desarrollo, con `<StrictMode>`, los Effects de montaje corren **dos veces** (§5.5) — sin el guard, la inicialización correría dos veces.

### 4.8 Notificar a un componente padre de un cambio → en el mismo evento que originó el cambio

```tsx
// ❌ Effect "tardío" que reacciona al cambio de isOn
useEffect(() => {
  onChange(isOn);
}, [isOn, onChange]);

// ✅ Llamar directamente en el handler que produce el cambio
function updateToggle(nextIsOn: boolean) {
  setIsOn(nextIsOn);
  onChange(nextIsOn);
}
```

### 4.9 Suscribirse a un store externo → `useSyncExternalStore`

Ver el ejemplo `useOnlineStatus` en §2.10. Es el reemplazo correcto del patrón "Effect que agrega un listener y actualiza state" — evita tearing en renderizado concurrente.

### Cuándo SÍ hace falta `useEffect`

Fetching de datos (si no usas una librería/framework con caché propia), sincronizar con una API del navegador sin equivalente declarativo, integrar una librería no-React (widgets de mapas, editores de texto de terceros), o cualquier suscripción/conexión genuina a un sistema externo:

```tsx
useEffect(() => {
  let ignore = false;
  fetchResults(query, page).then((json) => {
    if (!ignore) setResults(json);
  });
  return () => {
    ignore = true;
  }; // evita condición de carrera / setState tras unmount
}, [query, page]);
```

---

## 5. Errores comunes con `useEffect`

### 5.1 Silenciar el linter de dependencias

Deshabilitar `react-hooks/exhaustive-deps` no arregla el warning: le miente a React sobre qué valores usa el Effect, y esos valores quedan **congelados** con el valor que tenían cuando el Effect se creó.

```tsx
// ❌ Bug: el contador siempre suma el `increment` inicial, nunca el actual
function onTick() {
  setCount(count + increment);
}
useEffect(() => {
  const id = setInterval(onTick, 1000);
  return () => clearInterval(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, []);
```

La solución correcta nunca es silenciar el linter: es cambiar el código para que la dependencia deje de hacer falta (§5.2–5.4) o agregarla de verdad.

### 5.2 Dependencias de objetos/funciones recreadas en cada render

Dos objetos/funciones con el mismo contenido creados en renders distintos son referencias **distintas** — si uno es dependencia de un Effect, el Effect se re-ejecuta en cada render aunque "nada haya cambiado" en la práctica.

```tsx
// ❌ `options` es un objeto nuevo en cada render → el chat se reconecta en cada tecla escrita
function ChatRoom({ roomId }: { roomId: string }) {
  const [message, setMessage] = useState("");
  const options = { serverUrl: "https://localhost:1234", roomId };
  useEffect(() => {
    const connection = createConnection(options);
    connection.connect();
    return () => connection.disconnect();
  }, [options]); // ❌
}
```

Tres soluciones, según el caso:

```tsx
// (a) Objeto/función 100% estático → moverlo fuera del componente
const options = { serverUrl: "https://localhost:1234", roomId: "music" };
function ChatRoom() {
  useEffect(() => {
    /* usa options */
  }, []); // sin dependencias
}

// (b) Depende de props reactivas → construirlo DENTRO del Effect
function ChatRoom({ roomId }: { roomId: string }) {
  useEffect(() => {
    const connection = createConnection({ serverUrl, roomId }); // se crea aquí, no afuera
    connection.connect();
    return () => connection.disconnect();
  }, [roomId]); // solo depende del primitivo
}

// (c) Llega por props ya como objeto → extraer los primitivos ANTES del Effect
function ChatRoom({ options }: { options: { roomId: string; serverUrl: string } }) {
  const { roomId, serverUrl } = options;
  useEffect(() => {
    const connection = createConnection({ roomId, serverUrl });
    connection.connect();
    return () => connection.disconnect();
  }, [roomId, serverUrl]); // depende de primitivos, no del objeto
}
```

### 5.3 Dependencia circular sobre el propio state → función actualizadora

```tsx
// ❌ El Effect depende de `messages` solo para leer su valor anterior → se reconecta en cada mensaje
useEffect(() => {
  connection.on("message", (m) => setMessages([...messages, m]));
  return () => connection.disconnect();
}, [roomId, messages]);

// ✅ setState(prev => ...) no necesita leer `messages` desde el closure del Effect
useEffect(() => {
  connection.on("message", (m) => setMessages((msgs) => [...msgs, m]));
  return () => connection.disconnect();
}, [roomId]);
```

### 5.4 Closures obsoletas (stale closures) y `useEffectEvent`

Cuando un Effect lee un valor (prop/state) que **no debería** hacerlo reactivo — no quieres que el Effect se re-ejecute cuando ese valor cambia, pero sí quieres leer su valor más reciente — la solución correcta es `useEffectEvent` (estable desde React 19.2), no quitar la dependencia del array a mano.

```tsx
import { useEffectEvent, useEffect } from "react";

function ChatRoom({ roomId, muted }: { roomId: string; muted: boolean }) {
  const onConnected = useEffectEvent(() => {
    console.log("Connected to " + roomId);
    if (!muted) showNotification("Connected to " + roomId); // lee el `muted` más reciente
  });

  useEffect(() => {
    const connection = createConnection(roomId);
    connection.on("connected", () => onConnected());
    connection.connect();
    return () => connection.disconnect();
  }, [roomId]); // ✅ NO incluye `muted` — cambiarlo no reconecta el chat
}
```

**Reglas de `useEffectEvent`:**

- Solo se llama **desde dentro de un Effect** (o de otro Effect Event) — nunca durante el render ni desde un event handler normal.
- Nunca se pasa como prop a otro componente — para eso sigue existiendo `useCallback`.
- Nunca se agrega al array de dependencias del Effect.
- Su identidad de función cambia intencionalmente en cada render — no es un reemplazo de `useCallback`.
- No lo uses como atajo para "silenciar" una dependencia que en realidad sí debería disparar el Effect; solo aplica cuando el valor genuinamente no debe ser reactivo.

### 5.5 Effects que corren dos veces en desarrollo (Strict Mode)

En desarrollo, `<StrictMode>` monta, desmonta y vuelve a montar cada componente una vez extra, ejecutando el `setup` + `cleanup` de cada Effect dos veces. Es **intencional**: expone bugs de Effects que no limpian correctamente después de sí mismos. **No es un bug de React ni algo que "arreglar" con un guard `useRef` genérico** — es una señal de que el `cleanup` está incompleto. Un Effect bien escrito (agregar/quitar el mismo listener o conexión, de forma idempotente) tolera el doble montaje sin problema. Solo en el caso legítimo de "esto debe correr una única vez en toda la vida de la app" usa el guard a nivel de módulo del §4.7.

---

## 6. Patrones recomendados (React 19+)

### 6.1 Funciones de actualización de estado

`setX((prev) => nuevoValor)` en vez de `setX(x + 1)` cuando el nuevo valor depende del anterior. Evita bugs de batching (varias llamadas seguidas en el mismo handler que solo incrementan una vez) y elimina la necesidad de tener el valor actual como dependencia de un Effect/callback (ver §5.3).

### 6.2 `useReducer` para estado complejo

Preferible a varios `useState` independientes cuando el próximo estado combina más de un campo anterior, o hay más de 3-4 transiciones de estado que se repiten en varios handlers. Centraliza la lógica en una función pura, fácil de testear sin renderizar nada.

### 6.3 El React Compiler y el futuro de `useMemo`/`useCallback`

El React Compiler memoiza automáticamente en build-time los casos que puede analizar de forma segura, eliminando la necesidad de la mayoría de los `useMemo`/`useCallback` "preventivos" escritos por costumbre. Esto **no los vuelve obsoletos**: siguen haciendo falta cuando (a) la identidad de una función/valor es parte de un contrato con un sistema externo que el compilador no puede ver (dependencia de un Effect, prop de una librería de terceros que compara por referencia), o (b) profiling real muestra un cuello de botella que el compilador no optimizó. Recomendación práctica: escribe código legible primero, deja que el compilador optimice los casos seguros, mide, y memoiza manualmente solo donde los datos lo justifiquen.

### 6.4 `useRef` para valores mutables fuera del ciclo de render

IDs de timers, flags de "ya se ejecutó", el valor anterior de una prop (`usePrevious`), contadores internos que no deben causar re-render — todo esto es candidato a `useRef` en vez de `useState`.

### 6.5 `useTransition`/`useDeferredValue` para UI concurrente sin librerías externas

Reemplazan patrones manuales de "loading state" para actualizaciones costosas de UI (filtrados grandes, cambios de pestaña con contenido pesado, búsquedas) sin necesitar debounce/throttle de terceros — React prioriza automáticamente la interacción del usuario sobre el render diferido.

### 6.6 Cleanup correcto en `useEffect`

- Suscripciones (`addEventListener`, sockets, observers): el cleanup debe des-suscribir exactamente lo que el setup suscribió.
- Fetch: usa `AbortController` y aborta en el cleanup, o un flag `ignore` para descartar la respuesta si el componente ya cambió de props/se desmontó (evita condiciones de carrera).

```tsx
useEffect(() => {
  const controller = new AbortController();
  fetch(url, { signal: controller.signal })
    .then((r) => r.json())
    .then(setData)
    .catch((err) => {
      if (err.name !== "AbortError") throw err;
    });
  return () => controller.abort();
}, [url]);
```

---

## 7. Errores comunes generales (fuera de `useEffect`)

1. **Mutar el estado directamente** en vez de reemplazarlo por una copia nueva (`state.push(x)` en vez de `setState([...state, x])`). React compara por referencia para decidir si re-renderizar; mutar in-place no cambia la referencia y el render no se dispara, o se dispara con datos inconsistentes.
2. **`useState` para un valor derivable durante el render** (§4.1) — duplica una fuente de verdad que puede desincronizarse.
3. **Dependencias de objetos/funciones no memoizadas causando loops infinitos** — un Effect que depende de un objeto recreado en cada render y que además llama a un `setState` sin condición de guarda re-renderiza indefinidamente. Solución: aplicar los patrones del §5.2, o memoizar el objeto/función en el padre si genuinamente debe ser estable entre renders.
4. **`useEffect` para sincronizar dos piezas de estado local entre sí** (antipatrón: "cuando cambia A, actualizo B con un Effect") — casi siempre B puede derivarse de A durante el render (§4.1) en vez de vivir en su propio `useState` sincronizado por un Effect.

---

## 8. Pre-flight checks

Antes de dar por terminado cualquier componente o custom Hook nuevo:

- [ ] **Ningún Hook se llama condicionalmente**, dentro de loops, ni después de un `return` (§1).
- [ ] **Cada `useEffect` sincroniza con un sistema externo real** — si no hay red/DOM/suscripción/timer involucrados, revisar si aplica alguno de los casos del §4 para eliminarlo.
- [ ] **El array de dependencias está completo** (`exhaustive-deps` sin deshabilitar) — ninguna dependencia fue quitada a mano para silenciar el linter.
- [ ] **Objetos/funciones que son dependencia de un Effect** están memoizados, movidos fuera del componente, o construidos dentro del propio Effect (§5.2).
- [ ] **Valores no reactivos leídos dentro de un Effect** (que no deben re-disparar la sincronización) usan `useEffectEvent`, no la eliminación manual de la dependencia (§5.4).
- [ ] **Todo Effect con suscripción/conexión tiene cleanup**, y ese cleanup deshace exactamente lo que el setup hizo (§5.5, §6.6).
- [ ] **Fetches dentro de `useEffect`** manejan cancelación (`AbortController` o flag `ignore`) para evitar condiciones de carrera.
- [ ] **Custom Hooks nuevos** llevan el prefijo `use` solo si usan Hooks por dentro, y resuelven un caso de uso concreto (no son wrappers genéricos de ciclo de vida).
- [ ] **`useMemo`/`useCallback` nuevos** están justificados por un contrato con un sistema externo o por profiling real, no agregados "por si acaso".
- [ ] **No hay estado duplicado**: ningún `useState` guarda un valor que ya puede derivarse de otro estado/prop durante el render.
