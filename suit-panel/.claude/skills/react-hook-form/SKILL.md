---
name: react-hook-form
description: React Hook Form (RHF) genérico — useForm, register vs Controller/useController, validación con Zod (zodResolver, refine/superRefine, z.input vs z.output), useFieldArray, watch/getValues/useWatch/setValue, formState (Proxy y suscripción), performance (evitar re-renders), integración con componentes controlados estilo shadcn/ui, manejo de errores (root, setError/clearErrors) y antipatrones comunes. Skill genérica, aplicable a cualquier proyecto React/Next.js con RHF + Zod.
---

# React Hook Form

Skill de referencia genérica sobre React Hook Form (RHF) v7 + `@hookform/resolvers/zod`. No asume ningún proyecto concreto — los ejemplos usan componentes de UI genéricos o el patrón de shadcn/ui como referencia (por ser la librería de facto en el ecosistema Next.js + Tailwind actual), pero aplican a cualquier librería de componentes controlados (Radix, MUI, react-select, date pickers).

Para los patrones de implementación concretos de un proyecto que ya use RHF+Zod con sus propios componentes de formulario, ver la skill de patrones de implementación de ese proyecto — esta skill cubre el **por qué** y el **cuándo** de la API de RHF en sí.

---

## 1. `useForm` — opciones principales

```tsx
const form = useForm<FormValues>({
  resolver: zodResolver(schema),
  defaultValues: { nombre: "", email: "" },
  mode: "onBlur",
});
```

| Opción             | Qué hace                                                                                                                                                                                                                           |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `resolver`         | Integra un validador externo (Zod, Yup, Joi...). Recibe `values` + `context` + `options`, retorna `{ values, errors }`. **Mutuamente excluyente con `validate` de `register`** — si ambos están presentes, solo corre el resolver. |
| `defaultValues`    | Valores iniciales, síncronos o una función que retorna una Promise. Se cachean al montar; para cambiarlos después usa `reset()`.                                                                                                   |
| `values`           | Distinto de `defaultValues`: **actualiza reactivamente** el formulario cuando cambia el estado externo. Ideal para datos que llegan async de una API (ver §10.2).                                                                  |
| `mode`             | Estrategia de validación **antes** del primer submit: `"onSubmit"` (default), `"onBlur"`, `"onChange"`, `"onTouched"`, `"all"`.                                                                                                    |
| `reValidateMode`   | Estrategia de revalidación **después** del submit (default `"onChange"`).                                                                                                                                                          |
| `criteriaMode`     | `"firstError"` (default, un error por campo) vs `"all"` (todos los errores de un campo).                                                                                                                                           |
| `shouldFocusError` | Default `true` — enfoca el primer campo con error tras una validación fallida.                                                                                                                                                     |
| `shouldUnregister` | Si `true`, al desmontar un campo se borra su valor del form state (más parecido a un `<form>` nativo). Default `false`: RHF retiene valores de campos desmontados, útil en wizards/steps.                                          |
| `delayError`       | Retrasa en ms la aparición de un error (se remueve al instante si se corrige) — evita parpadeo mientras el usuario sigue tipeando.                                                                                                 |

Retorna: `register`, `unregister`, `handleSubmit`, `watch`, `formState`, `setValue`, `getValues`, `getFieldState`, `reset`, `resetField`, `trigger`, `setError`, `clearErrors`, `control`, `setFocus`.

---

## 2. `register` vs `Controller`/`useController`

### `register` — inputs HTML nativos, no controlados

```tsx
<input {...register("email", { required: true })} />
```

`register` conecta un `ref` directo al DOM (**no controlado**): no dispara re-render de React en cada tecla, solo cuando corresponde validar/mostrar error. Es la opción de mejor performance. Retorna `{ name, onChange, onBlur, ref }`.

Soporta reglas de validación nativas y una función `validate` (o record de funciones), que puede ser **async**:

```tsx
<input
  {...register("username", {
    validate: {
      checkAvailability: async (value) => {
        const isAvailable = await checkUsername(value);
        return isAvailable || "Ese usuario ya existe";
      },
    },
  })}
/>
```

### `Controller`/`useController` — componentes controlados

Obligatorio cuando el componente no expone un `ref` nativo compatible con `register` — el caso de casi todos los componentes **controlados** de librerías de UI (Radix, shadcn/ui, MUI, react-select, date pickers).

```tsx
<Controller
  control={control}
  name="fechaNacimiento"
  render={({ field }) => (
    <DatePicker onChange={field.onChange} onBlur={field.onBlur} selected={field.value} />
  )}
/>
```

**Regla general:** input HTML nativo → `register`. Componente controlado de terceros → `Controller`. No los mezcles sobre el mismo campo.

---

## 3. Validación con Zod (`@hookform/resolvers/zod`)

### Uso básico

```tsx
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

const schema = z.object({
  nombre: z.string().min(1, "Requerido"),
  edad: z.coerce.number().int().positive(),
});

type FormValues = z.infer<typeof schema>;

const form = useForm<FormValues>({ resolver: zodResolver(schema) });
```

### Validación cruzada entre campos: `refine`/`superRefine`

```tsx
const schema = z
  .object({
    password: z.string().min(8),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Las contraseñas no coinciden",
    path: ["confirmPassword"], // asocia el error a un campo concreto
  });
```

`superRefine` permite múltiples `ctx.addIssue()` en una sola pasada — útil para validar varios campos relacionados a la vez (ej. rango de fechas `inicio <= fin`).

### `z.input` vs `z.output` al tipar `useForm`

Clave cuando el schema **transforma** datos (`.coerce`, `.transform()`, `.default()`): el formulario edita la forma de **entrada** (`z.input`), pero `onSubmit` recibe la forma de **salida** ya transformada (`z.output`/`z.infer`). Tipar `useForm` con `z.infer` cuando el input real de un campo es distinto (ej. `z.coerce.number()` sobre un `<input type="number">`, cuyo valor crudo es `string`) es un error de tipado real, no cosmético.

```tsx
const schema = z.object({ monto: z.coerce.number().positive() });

// useForm soporta un tercer genérico (TTransformedValues) para separar input de output
const form = useForm<z.input<typeof schema>, unknown, z.output<typeof schema>>({
  resolver: zodResolver(schema),
  defaultValues: { monto: "" }, // string, como espera el <input>
});

function onSubmit(data: z.output<typeof schema>) {
  data.monto; // ya es `number`, transformado por el resolver
}
```

### Validación async

Zod soporta refinamientos async (`.refine`/`.superRefine` con función `async`) y el resolver de RHF espera la promesa correctamente — útil para comprobar disponibilidad de un username contra el backend dentro del propio schema. Para casos puntuales fuera de Zod, usa `validate` async directamente en `register` (§2).

---

## 4. `useFieldArray` — arrays dinámicos de campos

API: `fields`, `append`, `prepend`, `insert`, `swap`, `move`, `update`, `replace`, `remove`.

**Regla crítica:** usa `field.id` como `key` de React, nunca el índice — el índice cambia al reordenar/insertar/eliminar y React reasigna mal el estado interno de los inputs no controlados a las filas.

```tsx
// ❌ NO
fields.map((field, index) => <input key={index} {...register(`items.${index}.value`)} />);
// ✅ SÍ
fields.map((field, index) => <input key={field.id} {...register(`items.${index}.value`)} />);
```

| Método                           | Comportamiento                                                                                                        |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `append(data)` / `prepend(data)` | Agregan al final/inicio y enfocan el nuevo campo. `data` no puede ser un objeto vacío `{}`.                           |
| `insert(index, data)`            | Inserta en una posición concreta.                                                                                     |
| `swap(a, b)`                     | Intercambia dos posiciones.                                                                                           |
| `move(from, to)`                 | Reordena.                                                                                                             |
| `update(index, data)`            | Reemplaza una entrada — **desmonta y remonta** el campo (a diferencia de `setValue` sobre un índice, que no remonta). |
| `replace(data[])`                | Reemplaza todo el array.                                                                                              |
| `remove(index \| index[])`       | Elimina una, varias, o todas si no se pasa índice.                                                                    |

No combines `useFieldArray` con `shouldUnregister: true`; los datos deben ser siempre un array de objetos, nunca un array plano.

### Ejemplo completo — lista dinámica de teléfonos

```tsx
const schema = z.object({
  telefonos: z.array(z.object({ numero: z.string().min(7, "Mínimo 7 dígitos") })).min(1),
});
type FormValues = z.infer<typeof schema>;

function TelefonosForm() {
  const { control, register, handleSubmit } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { telefonos: [{ numero: "" }] },
  });
  const { fields, append, remove } = useFieldArray({ control, name: "telefonos" });

  return (
    <form onSubmit={handleSubmit((data) => console.log(data))}>
      {fields.map((field, index) => (
        <div key={field.id}>
          <input {...register(`telefonos.${index}.numero`)} />
          <button type="button" onClick={() => remove(index)}>
            Quitar
          </button>
        </div>
      ))}
      <button type="button" onClick={() => append({ numero: "" })}>
        Agregar teléfono
      </button>
      <button type="submit">Guardar</button>
    </form>
  );
}
```

---

## 5. `watch` vs `getValues` vs `useWatch`, y `setValue`

- **`watch()`** (método de `useForm`): se suscribe y **re-renderiza el componente raíz completo** en cada cambio del valor observado. Simple, pero caro en formularios grandes.
- **`useWatch({ control, name })`**: mira el mismo store que `watch`, pero **aísla la suscripción/re-render al nivel del Hook** — si se usa dentro de un subcomponente hijo, solo ese hijo se re-renderiza. Es la opción recomendada para "el campo B depende del valor del campo A" cuando A y B viven en componentes separados.
- **`getValues("campo")`** (o sin argumento, para todos los valores): lee el valor actual **sin suscribirse ni re-renderizar** — ideal dentro de handlers/callbacks (ej. leer un valor en un `onClick`, o justo antes de un submit parcial) donde no hace falta reactividad, solo el snapshot actual.

**Regla práctica:** mostrar un valor reactivamente en el JSX → `useWatch` (aislado) o `watch` (si el componente ya se re-renderiza igual por otros motivos); leer un valor dentro de una función/callback → `getValues`.

```tsx
setValue("nombre", "Ana", { shouldValidate: true, shouldDirty: true });
```

`setValue(name, value, options)` — `shouldValidate` revalida el campo tras el set; `shouldDirty` marca `dirtyFields`/`isDirty` comparando contra `defaultValues`; `shouldTouch` marca el campo como tocado.

---

## 6. `formState`: es un Proxy — la trampa de la suscripción

Propiedades: `errors`, `isDirty`, `dirtyFields`, `touchedFields`, `isSubmitted`, `isSubmitSuccessful`, `isSubmitting`, `isValid`, `isValidating`, `submitCount`.

**`formState` es un Proxy**: RHF salta la lógica de actualización para las propiedades a las que el componente no está suscrito. Eso significa que **leer una propiedad es lo que activa la suscripción** — si el componente no lee/desestructura `isValid` en el cuerpo de su función de render, RHF nunca dispara un re-render cuando `isValid` cambia, y el valor mostrado en pantalla queda desactualizado aunque internamente sí haya cambiado.

```tsx
// ❌ Acceso indirecto, fuera del render tracking normal — puede no re-renderizar como se espera
const state = form.formState;
console.log(state.isValid);

// ✅ Desestructurar directamente en el render del componente que debe reaccionar
const { isValid, isDirty, errors } = form.formState;
```

Para aislar esta suscripción a un subcomponente (sin que el padre entero dependa de `formState`), usa `useFormState({ control })` dentro de ese subcomponente — mismo patrón que `useWatch` para valores.

---

## 7. Performance: evitar re-renders innecesarios

- RHF es **"uncontrolled-first"**: por defecto usa refs en vez de `useState` por campo, así que escribir en un input no re-renderiza React en cada tecla.
- `mode: "onBlur"` (o el default `"onSubmit"`) genera muchos menos re-renders que `"onChange"`, a costa de feedback de validación más tardío. `"onChange"` solo se justifica cuando el feedback instantáneo es crítico (ej. medidor de fuerza de contraseña).
- Evita `watch()` sin argumentos (observa **todo** el formulario) dentro de un componente grande — prefiere `useWatch({ name: "campoEspecifico" })` en un subcomponente aislado.
- Campos controlados que re-renderizan mucho (ej. un color picker con updates continuos): aíslalos en su propio componente memoizado (`React.memo`) que reciba `control` y use `Controller`/`useController` internamente, para que el resto del formulario no vuelva a renderizar cuando ese campo cambia.
- **`FormProvider` + `useFormContext`**: para formularios grandes divididos en subcomponentes, evita pasar `register`/`control`/`formState` como props en cada nivel.

```tsx
const methods = useForm<FormValues>();

<FormProvider {...methods}>
  <form onSubmit={methods.handleSubmit(onSubmit)}>
    <SeccionDatosPersonales />
    <SeccionDireccion />
  </form>
</FormProvider>;

function SeccionDireccion() {
  const { register } = useFormContext<FormValues>();
  return <input {...register("direccion.calle")} />;
}
```

- **`defaultValues` como referencia estable**: pasar un objeto literal nuevo en cada render como `defaultValues` puede causar reinicializaciones inesperadas — decláralo como constante fuera del render, memoízalo, o (si viene de una API) usa `values` en vez de `defaultValues` (§10.2).

---

## 8. Integración con componentes controlados estilo shadcn/ui

shadcn/ui (y librerías similares construidas sobre Radix) usan primitivos de presentación (`Field`/`FieldLabel`/`FieldDescription`/`FieldError`, o en versiones más antiguas `FormField`/`FormItem`/`FormControl`/`FormMessage` — ambos patrones son estructuralmente equivalentes) junto con `Controller` de RHF. El patrón genérico:

```tsx
const form = useForm<z.infer<typeof schema>>({
  resolver: zodResolver(schema),
  defaultValues: { titulo: "", descripcion: "" },
});

<Controller
  name="titulo"
  control={form.control}
  render={({ field, fieldState }) => (
    <Field data-invalid={fieldState.invalid}>
      <FieldLabel htmlFor={field.name}>Título</FieldLabel>
      <Input {...field} id={field.name} aria-invalid={fieldState.invalid} />
      {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
    </Field>
  )}
/>;
```

Puntos clave para armar un wrapper `FormField` genérico y reutilizable:

- `field.value`, `field.onChange`, `field.onBlur` se pasan directamente a las props controladas del componente de UI.
- `field.ref` se pasa cuando el componente controlado expone un elemento focuseable real (ej. un `Input`); componentes puramente compuestos (ej. un `Select` de Radix) a veces no necesitan `ref` — depende del componente.
- `fieldState.invalid`/`fieldState.error` controlan el estado visual de error (`data-invalid`, `aria-invalid`) y el mensaje mostrado — no leas `formState.errors[name]` manualmente cuando ya tienes `fieldState` dentro del propio `Controller`.
- Un wrapper genérico evita repetir el boilerplate de `Controller` + presentación en cada campo; se parametriza con `name`, `control`, `label` y el componente controlado a renderizar.

---

## 9. Manejo de errores

- Error por campo: `errors.nombreCampo?.message`, disponible automáticamente cuando el resolver/reglas fallan.
- **`errors.root`**: namespace especial para errores que NO pertenecen a un campo concreto — típicamente un error del servidor tras el submit.

```tsx
const onSubmit = async (data: FormValues) => {
  const res = await fetch("/api/submit", { method: "POST", body: JSON.stringify(data) });
  if (!res.ok) {
    setError("root.serverError", { type: String(res.status), message: "Error del servidor" });
    return;
  }
};
// render:
{
  errors.root?.serverError && <p>{errors.root.serverError.message}</p>;
}
```

- **`setError(name, { type, message }, options?)`**: setea un error manual/async en cualquier campo (ej. tras validar contra el backend después del submit: "el email ya existe"). `options.shouldFocus` enfoca el campo.
- **`clearErrors(name?)`**: limpia errores manuales — sin argumento limpia todos.
- Un error seteado manualmente en un campo **se limpia automáticamente** si ese campo vuelve a pasar sus validaciones registradas en la próxima validación; los errores en `root` **no persisten entre submits** — hay que volver a setearlos o limpiarlos explícitamente.
- No uses como nombre de campo: `type`, `root`, `ref`, `types`, `message` — son palabras reservadas del API de errores.

---

## 10. Errores comunes / antipatrones

1. **`defaultValues` con referencia inestable**: un objeto literal `{}` nuevo en cada render (en vez de una constante fuera del componente o un valor memoizado) puede causar reinicializaciones inesperadas del form.
2. **Usar `defaultValues` para datos que llegan async** (ej. cargar un registro para editar desde una API): si `useForm` ya se montó con `defaultValues: {}` y los datos llegan después, el formulario **no se actualiza solo**. La solución correcta es usar la prop **`values`** (reactiva, §1) en vez de `defaultValues`, o resetear explícitamente con `reset(data)` cuando llegan los datos.
3. **Loop infinito con `reset()` dentro de un `useEffect`**: poner el objeto `formState` completo (o el `form` entero) en el array de dependencias de un `useEffect` que además llama `reset()` puede reiniciar el ciclo indefinidamente — depende solo de los valores primitivos concretos que necesites (ej. `formState.isSubmitSuccessful`), no del objeto completo.
4. **No leer/desestructurar `formState` donde se necesita reactividad** (§6) — la causa más citada de "mi `isValid`/`isDirty` no se actualiza en el UI".
5. **`useState` en paralelo a RHF para el mismo campo** — duplica la fuente de verdad; el valor real del campo debe vivir solo en RHF (accedido con `watch`/`useWatch`/`getValues`), nunca espejado en un `useState` adicional resincronizado a mano.
6. **`register` sobre un componente sin `ref` nativo compatible** (ej. un `Select` de shadcn/Radix) — el valor nunca se conecta correctamente al form. La solución es `Controller`/`useController` (§2).
7. **Pasar `value` controlado además de `register`**: RHF trabaja con inputs no controlados; mezclar `value` gestionado por un `useState` propio además de `register` rompe el modelo uncontrolled-first.
8. **Olvidar envolver el handler con `handleSubmit`**: `<form onSubmit={onSubmit}>` en vez de `<form onSubmit={handleSubmit(onSubmit)}>` — sin `handleSubmit`, RHF nunca corre la validación/resolver antes de invocar el callback.

---

## 11. Pre-flight checks

Antes de dar por terminado un formulario nuevo o modificado:

- [ ] **Cada campo controlado** de una librería de UI (Radix/shadcn, MUI, react-select, date pickers) usa `Controller`/`useController`, nunca `register` directo.
- [ ] **El schema de Zod** es la única fuente de verdad de validación — sin reglas de validación duplicadas a mano en el componente.
- [ ] **`useForm` está tipado con `z.input`** (no `z.infer`/`z.output`) si el schema usa `.coerce`, `.transform()` o `.default()`.
- [ ] **`useFieldArray`** usa `field.id` como `key`, nunca el índice.
- [ ] **Ningún `watch()` sin argumentos** en un componente grande — se usa `useWatch({ name })` aislado en un subcomponente cuando corresponde.
- [ ] **`formState`** se desestructura directamente en el render del componente que necesita reaccionar a `isValid`/`isDirty`/`errors`, no se accede indirectamente.
- [ ] **`defaultValues`** es una referencia estable (constante o memoizada); si los datos vienen de una carga async, se usa `values` o `reset(data)`, no `defaultValues`.
- [ ] **No hay `useState` duplicando** el valor de un campo que ya vive en RHF.
- [ ] **`handleSubmit`** envuelve el callback de submit — nunca se pasa el callback directo a `onSubmit`.
- [ ] **Errores del servidor tras el submit** usan `setError("root.serverError", ...)` o `setError(campo, ...)`, no un `useState` paralelo para mostrar el mensaje.
