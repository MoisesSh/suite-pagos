---
name: tipos-typescript
description: Buenas prácticas de tipado en TypeScript para proyectos React/Next.js con Zod y react-hook-form — interface vs type, genéricos, utility types, discriminated unions para estado, type guards y narrowing, any vs unknown, tipos inferidos de Zod (z.infer/z.input) vs tipos declarados a mano, branded types, y errores comunes de tipado en formularios y rutas de Next.js.
---

# Tipos de TypeScript: Buenas Prácticas

Skill de referencia para escribir y auditar tipos en un frontend React/Next.js con Zod y react-hook-form. El objetivo no es "tipar por tipar": es que el tipo haga imposible representar un estado inválido, y que el compilador atrape en la revisión de código los errores que de otro modo aparecerían en producción.

---

## 1. `interface` vs `type`: cuándo usar cada uno

Ambos pueden describir la forma de un objeto y en la mayoría de los casos son intercambiables. La elección importa en los casos donde **no** son intercambiables:

### Usa `interface` cuando:

- Describes la forma de un objeto o el contrato de una clase (`implements`).
- Necesitas **declaration merging** — la misma interfaz declarada dos veces se fusiona automáticamente. Esto es exclusivo de `interface` y es lo que permite, por ejemplo, extender tipos de una librería externa (aumentar el módulo de una librería de terceros) sin tocar su código fuente.
- Vas a extender el tipo repetidamente (`interface B extends A`) — el compilador reporta errores de forma más clara en cadenas largas de herencia que con intersecciones (`&`).

```typescript
interface Cliente {
  id: string;
  nombre: string;
}

interface ClienteConHistorial extends Cliente {
  pedidos: Pedido[];
}
```

### Usa `type` cuando:

- Necesitas una **unión** (`type EstatusPedido = "pendiente" | "enviado" | "cancelado"`) — `interface` no puede expresar uniones.
- Necesitas alias de tuplas, funciones, tipos primitivos, tipos mapeados o tipos condicionales.
- Estás definiendo el tipo de un valor derivado (`z.infer<typeof schema>`, `ReturnType<typeof fn>`, un utility type combinado).

```typescript
type Coordenada = [lat: number, lng: number];
type Comparador<T> = (a: T, b: T) => number;
type ClaveDePedido = keyof Pedido;
```

### Regla práctica de consistencia

Si un objeto se define una sola vez y no necesita fusionarse ni extenderse en cadena, cualquiera de los dos funciona igual de bien — prioriza la consistencia del equipo/módulo sobre la preferencia personal. La única señal fuerte para decidir es: **¿esto es una unión, una tupla o un tipo derivado? → `type`. ¿Es la forma de un objeto que alguien más podría necesitar extender o fusionar? → `interface`.**

---

## 2. Genéricos: parámetros, constraints e inferencia

Un genérico existe para preservar la relación entre el tipo de entrada y el tipo de salida de una función o componente — si esa relación no existe, no hace falta un genérico.

```typescript
// Sin genérico: se pierde el tipo específico, todo se convierte en `unknown[]`
function agruparPor(items: unknown[], clave: (item: unknown) => string) {}

// Con genérico: el tipo de `items` se preserva en el valor de retorno
function agruparPor<T, K extends PropertyKey>(items: T[], clave: (item: T) => K): Record<K, T[]> {
  const resultado = {} as Record<K, T[]>;
  for (const item of items) {
    const k = clave(item);
    (resultado[k] ??= []).push(item);
  }
  return resultado;
}
```

### Constraints (`extends`)

Restringen qué tipos aceptan el genérico, permitiendo acceder a propiedades sin usar `any`:

```typescript
function ordenarPorFecha<T extends { creadoEn: Date }>(items: T[]): T[] {
  return [...items].sort((a, b) => a.creadoEn.getTime() - b.creadoEn.getTime());
}
```

### Genéricos en componentes React

Útiles para componentes de lista/tabla reutilizables que no deben acoplarse a una entidad concreta:

```tsx
function Lista<T>({ items, render }: { items: T[]; render: (item: T) => React.ReactNode }) {
  return (
    <ul>
      {items.map((item, i) => (
        <li key={i}>{render(item)}</li>
      ))}
    </ul>
  );
}

// Uso: TypeScript infiere T = Producto a partir de `productos`
<Lista items={productos} render={(p) => p.nombre} />;
```

### Trampa común de inferencia

Si TypeScript no puede inferir el genérico a partir de los argumentos (por ejemplo, porque el único uso del tipo está en el valor de retorno), termina infiriendo `unknown` o el tipo por defecto en vez de fallar — hay que pasar el tipo explícitamente:

```typescript
function crearEstadoVacio<T>(): T[] {
  return [];
}

const productos = crearEstadoVacio<Producto>(); // sin el <Producto> explícito, T queda como `unknown`
```

No abuses de los genéricos donde una unión simple o una sobrecarga de función explican mejor la intención — un genérico sin ninguna restricción (`<T,>`) que solo se usa una vez suele ser una señal de sobre-ingeniería.

---

## 3. Utility Types (`Pick`, `Omit`, `Partial`, `Record`, etc.)

Los utility types evitan redeclarar formas de objeto que ya existen en otro tipo.

| Utility                           | Uso típico                                                                                                  |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `Partial<T>`                      | DTO de actualización parcial (`PATCH`): todos los campos opcionales.                                        |
| `Required<T>`                     | Forzar que todos los campos opcionales de un tipo existan (ej. tras aplicar `defaultValues`).               |
| `Pick<T, K>`                      | Proyectar solo los campos que un componente o endpoint necesita.                                            |
| `Omit<T, K>`                      | Reusar una forma quitando campos que no aplican (ej. quitar `id`/`createdAt` en un formulario de creación). |
| `Record<K, V>`                    | Diccionarios con claves conocidas (`Record<EstatusPedido, string>` para mapear estatus → etiqueta).         |
| `Readonly<T>`                     | Marcar un valor como no mutable a nivel de tipo (props, config compartida).                                 |
| `ReturnType<T>` / `Parameters<T>` | Derivar tipos a partir de una función existente sin declararlos por separado.                               |
| `Awaited<T>`                      | Obtener el tipo resuelto de una `Promise` (útil con `params`/`searchParams` de Next.js — ver §9).           |
| `Extract<T, U>` / `Exclude<T, U>` | Filtrar los miembros de una unión que cumplen (o no) una condición.                                         |
| `NonNullable<T>`                  | Quitar `null`/`undefined` de un tipo, típicamente tras narrowing.                                           |

```typescript
type Pedido = {
  id: string;
  cliente: string;
  monto: number;
  estatus: "pendiente" | "enviado" | "cancelado";
  creadoEn: Date;
};

// Formulario de creación: sin id ni fecha, que los pone el backend
type CrearPedidoInput = Omit<Pedido, "id" | "creadoEn">;

// Actualización parcial
type ActualizarPedidoInput = Partial<Omit<Pedido, "id" | "creadoEn">>;

// Etiquetas de UI por estatus
const ETIQUETA_ESTATUS: Record<Pedido["estatus"], string> = {
  pendiente: "Pendiente",
  enviado: "Enviado",
  cancelado: "Cancelado",
};
```

### Trampa conocida: `Omit` sobre uniones discriminadas

`Omit<T, K>` no se distribuye sobre los miembros de una unión — si `T` es una unión discriminada, `Omit` puede colapsar el discriminante y romper el narrowing. Si necesitas quitar un campo de cada miembro de una unión, usa una versión distributiva:

```typescript
type DistributiveOmit<T, K extends keyof T> = T extends unknown ? Omit<T, K> : never;
```

---

## 4. Discriminated Unions para modelar estado

El error más común al modelar estado (carga de datos, resultados de una operación) es usar varios campos booleanos/opcionales independientes, lo que permite representar combinaciones imposibles:

```typescript
// ❌ Estado "imposible" representable: loading=true y data presente a la vez,
// o error y data presentes a la vez — el tipo no lo impide.
type EstadoPedidos = {
  loading: boolean;
  error?: string;
  data?: Pedido[];
};
```

La alternativa correcta es una unión discriminada por un campo literal común (a menudo `status` o `type`):

```typescript
type EstadoPedidos =
  | { status: "inactivo" }
  | { status: "cargando" }
  | { status: "listo"; data: Pedido[] }
  | { status: "error"; error: string };

function render(estado: EstadoPedidos) {
  switch (estado.status) {
    case "inactivo":
      return null;
    case "cargando":
      return "Cargando...";
    case "listo":
      return estado.data.length; // TS sabe que `data` existe aquí, sin `?.` ni `!`
    case "error":
      return estado.error;
  }
}
```

Cada rama del `switch`/`if` acota (narrows) automáticamente los demás campos del tipo — ya no hace falta comprobar `data !== undefined` por separado. Este mismo patrón aplica a resultados de validación (`{ success: true, data } | { success: false, error }`, como devuelve `schema.safeParse()` de Zod) y a acciones de un reducer.

### Exhaustividad garantizada por el compilador

Usa una función `assertNever` en la rama `default` para que agregar un nuevo miembro a la unión sin actualizar el `switch` sea un **error de compilación**, no un bug silencioso en producción:

```typescript
function assertNever(x: never): never {
  throw new Error(`Caso no manejado: ${JSON.stringify(x)}`);
}

function label(estado: EstadoPedidos): string {
  switch (estado.status) {
    case "inactivo":
      return "";
    case "cargando":
      return "Cargando...";
    case "listo":
      return `${estado.data.length} pedidos`;
    case "error":
      return estado.error;
    default:
      return assertNever(estado); // si se agrega un nuevo status, esta línea no compila
  }
}
```

---

## 5. Type Guards y Narrowing

### Narrowing nativo

`typeof`, `instanceof`, `in`, comparaciones con literales, y la propiedad discriminante de una unión (§4) acotan el tipo automáticamente dentro del bloque:

```typescript
function describir(valor: Cliente | Producto) {
  if ("razonSocial" in valor) {
    return valor.razonSocial; // TS sabe que es `Cliente` aquí
  }
  return valor.nombre; // aquí es `Producto`
}
```

### Type predicates personalizados

Cuando la condición de narrowing no es una simple comprobación de propiedad, declara una función con `x is T`:

```typescript
function esCliente(valor: Cliente | Producto): valor is Cliente {
  return "razonSocial" in valor && typeof valor.razonSocial === "string";
}

const clientes = lista.filter(esCliente); // el resultado es Cliente[], no (Cliente | Producto)[]
```

### Funciones `asserts`

Para validar y lanzar en un solo paso (útil al inicio de una función que asume una precondición):

```typescript
function assertEsCliente(valor: unknown): asserts valor is Cliente {
  if (typeof valor !== "object" || valor === null || !("razonSocial" in valor)) {
    throw new Error("Se esperaba un Cliente");
  }
}
```

### Trampa común: filtrar `null`/`undefined` sin narrowing

`array.filter(Boolean)` **no** cambia el tipo del array resultante en TypeScript (sigue siendo `(T | null | undefined)[]`) salvo que se use un predicate explícito:

```typescript
// ❌ El tipo de `limpios` sigue siendo (Pedido | null)[]
const limpios = pedidos.filter(Boolean);

// ✅ Predicate explícito: el tipo de `limpios` es Pedido[]
const limpios = pedidos.filter((p): p is Pedido => p != null);
```

---

## 6. Evitar `any`: `unknown` como alternativa correcta

`any` desactiva la verificación de tipos por completo y **contamina** todo lo que toca — una vez que un valor es `any`, cualquier cosa derivada de él también lo es, silenciosamente, sin ningún error del compilador.

`unknown` es el tipo correcto para "no sé qué es esto todavía": acepta cualquier valor, pero **obliga a acotar el tipo (narrowing) antes de usarlo**, por lo que el compilador sigue protegiendo el resto del código.

```typescript
// ❌ any: se puede llamar .toUpperCase() sobre un número sin que el compilador avise
async function obtenerDatos(): Promise<any> {
  const res = await fetch("/api/pedidos");
  return res.json();
}

// ✅ unknown: obliga a validar antes de usar
async function obtenerDatos(): Promise<unknown> {
  const res = await fetch("/api/pedidos");
  return res.json();
}

const datos = await obtenerDatos();
const pedidos = pedidoListSchema.parse(datos); // valida y estrecha el tipo con Zod
```

### Dónde aparece `unknown` legítimamente

- El resultado de `fetch().json()`, `JSON.parse()`, o cualquier dato externo antes de validarlo.
- El parámetro de una server action o de un manejador de webhook, antes de pasarlo por `schema.safeParse()`.
- La variable de un bloque `catch` (con `useUnknownInCatchVariables` habilitado, el default en TypeScript moderno) — nunca asumas que es una instancia de `Error` sin comprobarlo:
  ```typescript
  try {
    await enviarPedido();
  } catch (error: unknown) {
    const mensaje = error instanceof Error ? error.message : String(error);
  }
  ```

### Regla de auditoría

`any` explícito o implícito (`noImplicitAny` desactivado) en código nuevo es una señal para preguntar "¿por qué no se puede tipar esto?", no una solución aceptable. Si aparece un `as any` para silenciar un error, el objetivo es corregir el tipo real, no dejar el cast.

---

## 7. Tipos inferidos de Zod (`z.infer`) vs tipos declarados a mano

Cuando ya existe un schema de Zod para una forma de datos, **derivar el tipo del schema es preferible a declararlo por separado** — evita que el tipo y la validación en runtime diverjan silenciosamente cuando alguien edita uno y olvida el otro.

```typescript
const pedidoSchema = z.object({
  cliente: z.string().min(2),
  monto: z.coerce.number().positive(),
});

// ✅ Una sola fuente de verdad
type PedidoFormType = z.infer<typeof pedidoSchema>;

// ❌ Duplica la forma a mano — puede divergir del schema sin que nada avise
type PedidoFormType = {
  cliente: string;
  monto: number;
};
```

### `z.infer` (= `z.output`) vs `z.input`

`z.infer<typeof schema>` (alias de `z.output<typeof schema>`) da el tipo **después** de aplicar `.transform()`/`.coerce`/`.default()` — es decir, lo que devuelve `schema.parse()`. `z.input<typeof schema>` da el tipo **antes** de esas transformaciones — lo que el schema espera recibir. Cuando el schema no tiene transformaciones ambos son iguales, pero en cuanto aparece `.coerce.number()`, `.transform()` o `.default()`, **difieren**, y usar el que no corresponde es un error de tipado real, no cosmético (ver §9 para el caso concreto con `useForm`).

```typescript
const pedidoSchema = z.object({
  monto: z.coerce.number(), // acepta string en la entrada, entrega number en la salida
});

type PedidoInput = z.input<typeof pedidoSchema>; // { monto: string | number }
type PedidoOutput = z.infer<typeof pedidoSchema>; // { monto: number }
```

### Cuándo sí declarar el tipo a mano

Solo para formas que nunca cruzan un límite de validación (props internas de un componente puramente de presentación, tipos de retorno de un hook que no vienen de una API o de un formulario). Si el dato viene de un formulario, una respuesta de red o cualquier entrada externa, debería tener un schema de Zod, y el tipo debería derivarse de él.

---

## 8. Branded / Opaque Types

### El problema: obsesión primitiva

Dos identificadores de entidades distintas (`ClienteId`, `ProductoId`) suelen ser ambos `string` a nivel de tipo. Sin branding, nada impide pasar un `ProductoId` donde se espera un `ClienteId` — compilan igual porque estructuralmente son el mismo tipo.

```typescript
function buscarCliente(id: string) {}
function buscarProducto(id: string) {}

const productoId = "abc-123";
buscarCliente(productoId); // compila sin error, aunque sea semánticamente incorrecto
```

### Branding manual

Se agrega una propiedad fantasma que no existe en runtime, solo a nivel de tipo:

```typescript
type ClienteId = string & { readonly __brand: "ClienteId" };
type ProductoId = string & { readonly __brand: "ProductoId" };

function comoClienteId(valor: string): ClienteId {
  return valor as ClienteId; // el único lugar donde se hace el cast, tras validar el formato
}

function buscarCliente(id: ClienteId) {}

buscarCliente(comoClienteId(productoId)); // sigue compilando, pero ya requiere un cast explícito
buscarCliente(productoId); // ❌ ahora sí es un error de tipos
```

### Branding con Zod

Zod tiene soporte nativo para esto vía `.brand()`, que además valida el formato en runtime en el mismo lugar donde se crea el tipo:

```typescript
const clienteIdSchema = z.string().uuid().brand<"ClienteId">();
type ClienteId = z.infer<typeof clienteIdSchema>;

const clienteId = clienteIdSchema.parse(valorCrudo); // valida el UUID y devuelve un ClienteId
```

**Importante:** el brand es una técnica puramente del sistema de tipos — se borra por completo al compilar a JavaScript, no valida nada por sí solo. La validación real la sigue haciendo el schema (`.uuid()` en el ejemplo); el brand solo evita que, una vez validado, el valor se confunda con otro string sin marca.

### Cuándo usarlo, y cuándo no

Útil para IDs de entidades que no deberían ser intercambiables, unidades de medida representadas como `number` (metros vs. pies), o valores primitivos que ya pasaron una validación específica (un email validado vs. un string cualquiera). No lo apliques a todo por sistema — añade una capa de fricción (casts explícitos en los bordes) que solo vale la pena donde confundir dos valores del mismo tipo primitivo sería un bug real y difícil de detectar.

---

## 9. Errores comunes de tipado en React/Next.js + Zod + react-hook-form

### a) Tipar `useForm` con el tipo de salida cuando el schema transforma la entrada

Si el schema usa `.coerce`, `.transform()` o `.default()`, el tipo de los _valores del formulario_ (lo que espera `defaultValues` y lo que produce cada campo antes de validar) es `z.input<typeof schema>`, no `z.infer`/`z.output`. El valor ya validado (lo que se recibe en `onSubmit`) sí es el de salida.

```typescript
const pedidoSchema = z.object({
  monto: z.coerce.number().positive(), // el input del <input> es string, el output es number
});

// ❌ Con z.infer, el tipo de `monto` es `number`, pero react-hook-form
// pasa el valor crudo del input (string) antes de que el resolver lo valide.
const form = useForm<z.infer<typeof pedidoSchema>>({
  resolver: zodResolver(pedidoSchema),
});

// ✅ El formulario se tipa con la forma de ENTRADA; el resolver se encarga
// de entregar la forma de SALIDA ya validada dentro de onSubmit.
const form = useForm<z.input<typeof pedidoSchema>>({
  resolver: zodResolver(pedidoSchema),
  defaultValues: { monto: "" },
});

function onSubmit(data: z.output<typeof pedidoSchema>) {
  // aquí `data.monto` ya es `number`
}
```

Cuando el schema no transforma nada, `z.input` y `z.infer` coinciden y este matiz no aparece — el error solo se manifiesta al agregar `.coerce`/`.transform()` a un schema que antes no los tenía, sin revisar el tipo del formulario que lo usa.

### b) `params`/`searchParams` como objeto plano en vez de `Promise`

En el App Router de Next.js, `params` y `searchParams` de una página son **promesas**, no objetos síncronos — hay que `await`-earlos (o usar el hook `use()` en un Client Component) antes de leer sus propiedades. Tipar la prop como el objeto directo en vez de `Promise<...>` es un error de tipado que además esconde el `await` faltante:

```typescript
// ❌ Tipo incorrecto — además, sin `await`, `params.slug` sería una propiedad de una Promise
export default function Page({ params }: { params: { slug: string } }) {
  return <h1>{params.slug}</h1>;
}

// ✅
export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <h1>{slug}</h1>;
}
```

Cuando el proyecto genera los helpers de rutas de Next.js (`next dev`/`next build`), prefiere el helper global `PageProps<'/ruta/[slug]'>` en vez de tipar `params`/`searchParams` a mano — se mantiene sincronizado automáticamente con las rutas reales del proyecto:

```typescript
export default async function Page(props: PageProps<"/pedidos/[id]">) {
  const { id } = await props.params;
}
```

### c) Declarar el tipo del formulario por separado del schema

Si `useForm<T>()` recibe un `T` escrito a mano y el `resolver` usa un schema distinto, ambos pueden divergir sin que el compilador lo note hasta que los campos no calcen en runtime. Deriva siempre el genérico del propio schema (§7), nunca lo dupliques.

### d) `any` en manejadores de eventos

```typescript
// ❌
function onChange(e: any) {
  setValor(e.target.value);
}

// ✅
function onChange(e: React.ChangeEvent<HTMLInputElement>) {
  setValor(e.target.value);
}
```

### e) `React.FC<Props>` por costumbre

`React.FC` añade una prop `children` implícita (no siempre deseada) y complica los componentes genéricos. Prefiere una función tipada directamente:

```typescript
// ✅ preferido
function TarjetaProducto({ producto }: { producto: Producto }) {
  /* ... */
}
```

### f) Validar en el cliente y confiar ciegamente en el servidor

Tipar el parámetro de una server action como `FormData`/`unknown` y pasarlo por `schema.safeParse()` es correcto; tiparlo como `Record<string, any>` o como el tipo de dominio directamente (`Pedido`) sin volver a validar es un atajo que anula la razón de tener el schema en el servidor. Ver la skill `validacion-input-protegido` para el patrón completo de validación en server actions.

### g) Estado "aún no cargado" representado con `any` o con un tipo demasiado amplio

```typescript
// ❌
const [pedido, setPedido] = useState<any>(null);

// ✅ unión explícita: "todavía no hay pedido" es un estado válido y tipado
const [pedido, setPedido] = useState<Pedido | null>(null);
```

### h) Uniones discriminadas sin exhaustividad forzada

Un `switch` sobre una unión de estado (§4) sin una rama `default` que llame a `assertNever` permite agregar un nuevo caso a la unión sin que ningún `switch` existente avise que le falta manejarlo — el error se descubre en producción, no en la revisión de código.

### i) `as` para forzar un tipo en vez de validar

```typescript
// ❌ Si el shape real no calza, esto falla en runtime más adelante, no aquí
const pedido = datosCrudos as Pedido;

// ✅ Falla temprano y con un mensaje claro si el shape no calza
const pedido = pedidoSchema.parse(datosCrudos);
```

### j) El mismo concepto de dominio duplicado en dos campos del schema

Un schema tiene un campo de texto libre (ej. `tipo: z.string()`) cuyos valores válidos coinciden, en la práctica, con los códigos de un catálogo que ese mismo schema **ya modela** a través de otro campo — típicamente un array pensado originalmente para otro propósito (ej. `tecnologias: z.array(z.string())`). El resultado son dos representaciones tipadas por separado del mismo dato, sin ninguna relación entre sí a nivel de tipos ni de validación: nada impide que `tipo` diverja de lo que contiene `tecnologias`, y el formulario/UI acaba leyendo una u otra según quién la haya escrito.

```typescript
// ❌ `tipo` y `categorias` modelan el mismo concepto por separado
const productoSchema = z.object({
  tipo: z.string(), // texto libre: "elec", "Electrónica", "ELECTRONICA"...
  categorias: z.array(z.enum(CATEGORIAS)), // catálogo real, ya tipado y cerrado
});

// ✅ Un solo campo tipado como fuente de verdad; si se necesita un "tipo principal"
// se deriva del catálogo, no se declara como un segundo campo independiente.
const productoSchema = z.object({
  categorias: z.array(z.enum(CATEGORIAS)).min(1),
});
type ProductoFormType = z.infer<typeof productoSchema>;
const tipoPrincipal = (p: ProductoFormType) => p.categorias[0];
```

**Regla de supervisión:** antes de agregar (o de dejar como está) un campo `z.string()` de texto libre, revisa si el schema ya tiene un campo `z.enum()`/`z.array()` contra un catálogo cuyos valores cubran ese mismo concepto. Si es así, unifica en ese campo — el de texto libre se elimina o se deriva del otro con una función, nunca coexiste como una segunda fuente de verdad independiente. La misma regla del backend (ver skill `supervision-modelos-bd`, §3) aplica aquí: dos representaciones tipadas del mismo dato pueden desincronizarse exactamente igual que dos columnas de base de datos.

---

## 10. Checklist de Auditoría de Tipos

Antes de aprobar un cambio que introduce o modifica tipos:

- [ ] **`any`:** ¿Hay algún `any` explícito o implícito que debería ser `unknown` + narrowing, o un tipo concreto?
- [ ] **Zod como fuente de verdad:** ¿Existe un schema de Zod para esta forma de datos? Si sí, ¿el tipo se deriva con `z.infer`/`z.input`/`z.output` en vez de declararse a mano por separado?
- [ ] **Concepto duplicado:** ¿un campo de texto libre nuevo cubre un concepto que el schema ya modela con un `z.enum()`/catálogo en otro campo? Si sí, unificar en uno solo.
- [ ] **`z.input` vs `z.infer`:** si el schema usa `.coerce`, `.transform()` o `.default()`, ¿el genérico de `useForm` usa `z.input`, no `z.infer`?
- [ ] **Estado modelado con unión discriminada:** ¿un estado de carga/resultado usa un campo discriminante (`status`/`type`) en vez de varios booleanos/opcionales independientes que permiten combinaciones inválidas?
- [ ] **Exhaustividad:** ¿los `switch` sobre uniones discriminadas tienen una rama `default` con `assertNever`?
- [ ] **Narrowing real, no solo casts:** ¿el código usa type predicates / `in` / discriminante en vez de `as` para acotar un tipo?
- [ ] **IDs no intercambiables:** si dos entidades distintas tienen IDs del mismo tipo primitivo y podrían confundirse por error, ¿se evaluó usar branded types?
- [ ] **`interface` vs `type`:** ¿se usó `type` para uniones/tuplas/tipos derivados e `interface` solo donde aporta (herencia, declaration merging)?
- [ ] **Next.js App Router:** ¿`params`/`searchParams` están tipados (o inferidos vía el helper de rutas) como `Promise`, con su `await` correspondiente?
- [ ] **Eventos de React:** ¿los manejadores usan los tipos de evento de React (`React.ChangeEvent<...>`, `React.FormEvent<...>`) en vez de `any`?
