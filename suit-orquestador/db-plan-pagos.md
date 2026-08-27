# Plan de modelado de datos — Suite Centralizada de Pagos

> Autor: `expert_database`. Primera pasada de planificación, integra el roadmap
> (`conatel-suite-pagos-roadmap.html`, secciones 03 y 04), el brief de research
> (`research-brief-pagos.md`, secciones 1-3), los hallazgos de documentación
> real de proveedor — **BDV (Banco de Venezuela), API C2P Cuentas Múltiples y
> API Conciliación**, `research-brief-pagos.md` sección 4 —, la investigación
> `research-seguridad-iframe.md` (CSP `frame-ancestors`, validación
> Origin/Referer, `postMessage`), `research-manejo-dinero-bd.md` (tipos y
> precisión de columnas monetarias, redondeo) y 3 decisiones de negocio
> confirmadas por el usuario (ver nota abajo). **No es un esquema
> final** — sirve de insumo para
> que `suit-backend` lo traduzca a modelos Django reales, aplicando las reglas
> de `supervision-modelos-bd` (UUIDv7 + `BaseModel`, catálogos vs `TextChoices`,
> matriz de `on_delete`, `related_name` explícito, índices, migraciones seguras)
> y el patrón de aislamiento de `integracion-bd-recaudacion` para cualquier
> dependencia externa (bóveda de tokenización, bancos).
>
> **Decisiones de negocio incorporadas en esta revisión:**
> 1. Filosofía explícita de multi-proveedor sin choque (sección 1).
> 2. Requisito de seguridad: registro de apps/dominios autorizados por proveedor, propio del Orquestador (sección 2.0).
> 3. Alcance reducido: tarjeta/tokenización queda fuera de alcance por ahora, único medio de pago real es BDV Pago Móvil C2P (sección 2.2, `TokenReferencia`).

---

## 1. Principio rector: database-per-service, sin FKs cruzadas

Dos bases PostgreSQL completamente independientes, sin JOIN posible entre
ellas ni transacción compartida:

- **Orquestador** — camino síncrono (autorizar/capturar/revertir). Consistencia
  fuerte, baja latencia.
- **Conciliación** — camino asíncrono, alimentado solo por eventos del bus
  RabbitMQ (`pago.*`). Cargas por lotes/reprocesos aisladas del cobro en vivo.

Toda referencia entre servicios es **lógica** (un UUID que viaja en el evento),
nunca una `ForeignKey` de Django. Esto incluye también la referencia hacia el
Developer Portal (dueño de `AppConsumidora`/API keys, gestión de uso —
distinto del registro de autorización de seguridad del Orquestador, ver 2.0)
y hacia la bóveda de tokenización externa: ambos son sistemas ajenos a estas
dos bases, igual que RECAUDACION lo es para `operador` — se
consultan/referencian, nunca se integran vía FK real.

### Principio explícito: multi-proveedor sin choque

**Decisión de negocio confirmada:** el sistema debe poder incorporar
múltiples proveedores de pago (BDV hoy, otros bancos/adquirentes/pasarelas
después) **sin que la llegada de uno nuevo choque con los ya existentes**.
Esto se formaliza como regla de diseño obligatoria para todo el agregado de
pago, no solo como intención:

- **Ningún campo de `IntencionPago`, `Autorizacion`, `Captura`, `Anulacion`
  o `Reembolso` puede ser específico de un proveedor.** Todo lo que varía
  por proveedor (tipos de operación, códigos de respuesta, formato de
  identificadores) vive en catálogos con FK a `ProveedorPago`
  (`TipoOperacionProveedor`, `CodigoRespuestaProveedor` — ya diseñados en
  2.1) o en el `payload_crudo`/`JSONField` de auditoría — nunca como un
  campo booleano/enum nuevo tipo `es_pago_movil_bdv` o una tabla
  `AutorizacionBDV` paralela a `Autorizacion`.
- Los campos genéricos ya definidos en 2.2 (`referencia_corta`,
  `identificador_interbancario`, `tipo_operacion`, `codigo_respuesta`,
  `payload_crudo`) son intencionalmente neutros de proveedor — un adaptador
  nuevo (T4: multi-adquirente, pasarela internacional) debe poder llenarlos
  sin requerir una migración de esquema, solo nuevas filas de catálogo y un
  adaptador nuevo en `infra/`.
- Corolario para el `PaymentProviderPort` del roadmap: si un proveedor
  nuevo necesita un dato que el agregado genérico no cubre, la primera
  pregunta de diseño es "¿esto es realmente parte del dominio de pago, o es
  detalle de protocolo del proveedor que pertenece a `payload_crudo`?" —
  antes de agregar una columna nueva al agregado compartido.

---

## 2. Orquestador — entidades

### 2.0 Registro de aplicaciones y dominios autorizados (requisito de seguridad)

**`CERRADO / DEFINITIVO`** — decisión de negocio confirmada dos veces por
el usuario, ya no es un punto abierto ni opcional: el Orquestador debe
mantener **su propio registro** de qué aplicaciones consumidoras
(identificadas por dominio/DNS) están autorizadas a usar el servicio, y con
qué `ProveedorPago` específico. Si el dominio que origina la petición no
está registrado, o el `ProveedorPago`/medio de pago solicitado no está
autorizado para esa app, **la petición se rechaza antes de crear ninguna
`IntencionPago`**. Esto es un control de seguridad propio del Orquestador —
no delega esta responsabilidad al Developer Portal (que sigue existiendo
para API keys y métricas de uso, un concern distinto y complementario, no
sustituto).

**Mecanismo técnico confirmado por `research-seguridad-iframe.md`** (el
formulario de cobro se sirve embebido por `<iframe>` en las apps
consumidoras — Conatel en Línea, Homologación, futuras apps): el registro
de dominios de esta sección no es solo un dato de auditoría, es el insumo
directo de dos controles de seguridad en cadena, ambos resueltos contra la
misma tabla `DominioPermitido`:

1. **`Content-Security-Policy: frame-ancestors` calculado dinámicamente por
   request** — la vista que sirve el formulario resuelve la app/dominio de
   origen contra `DominioPermitido`/`AplicacionRegistrada` y construye el
   header con el/los dominio(s) exactos autorizados para esa app, nunca un
   valor estático global ni wildcard. Es un control de navegador.
2. **Validación backend de `Origin`/`Referer` como defensa en
   profundidad** — porque `frame-ancestors` es un control que el navegador
   debe respetar pero el servidor no puede asumir cumplido (un cliente no
   estándar puede ignorarlo): el backend valida `Origin` (preferido) o
   `Referer` (fallback) contra la misma whitelist en la carga inicial del
   iframe, independientemente de si el navegador ya aplicó `frame-ancestors`.

Esto no agrega modelos nuevos — `DominioPermitido.dominio` (más
`DominioPermitido.activo`) ya es exactamente el dato que ambos controles
necesitan consultar por request; confirma que el diseño de esta sección
está correcto tal como está, no que falte una tabla adicional.

**Nota de supervisión (discrepancia a resolver, no a decidir unilateralmente):**
`research-seguridad-iframe.md` (punto 6 de su resumen) sugiere modelar
`dominios_autorizados` como tabla propia del **Developer Portal**, no del
Orquestador — razonando que cada app gestiona su dominio de embebido igual
que su API key. Esto choca en apariencia con la decisión de negocio ya
confirmada (el registro vive en el Orquestador, como control de seguridad
independiente). No se resuelve la discrepancia unilateralmente aquí: la
lectura más consistente con ambas fuentes es que el Developer Portal puede
ofrecer la **UI de autogestión** de dominios (donde el dueño de la app la
edita), pero el Orquestador mantiene su **propia copia de lectura rápida**
(`DominioPermitido`) como control de seguridad en el camino síncrono
crítico — no delega la decisión de rechazo a una consulta cross-servicio en
cada request de cobro. Si `suit-backend`/negocio prefieren que el Portal
sea la única fuente de verdad y el Orquestador la replique vía evento o
sincronización periódica (en vez de ser dueño primario), es un ajuste de
implementación, no de las tablas ya definidas en esta sección.

**`AplicacionRegistrada`** (`BaseModel`)
- `nombre` — nombre legible de la app consumidora (ej. "Conatel en Línea", "Homologación").
- `app_origen_id` — `UUIDField`, `unique=True`, referencia lógica al id de `AppConsumidora` del Developer Portal (sin FK real, cruza de servicio — mismo principio de la sección 1). Permite correlacionar el registro de seguridad del Orquestador con la gestión de API keys del portal sin acoplar las bases.
- `activa` — `BooleanField`, `db_index=True` (filtro constante en cada request de autorización).

**`DominioPermitido`**
- FK `aplicacion` → `AplicacionRegistrada`, `CASCADE`, `related_name='dominios'` (el dominio no tiene sentido sin la app que lo declara).
- `dominio` — `CharField`, **`unique=True` a nivel global** (un dominio no puede pertenecer a dos apps a la vez — es la clave de lookup en cada request entrante), `db_index=True`.
- `activo` — permite desactivar un dominio puntual sin desactivar toda la app (ej. mientras se rota un subdominio).

**`AplicacionProveedorPermitido`** — modelo intermedio explícito para la M2M `AplicacionRegistrada` ↔ `ProveedorPago` (con metadatos y ciclo de vida propio, no un M2M simple, según la matriz de decisión de relaciones):
- FK `aplicacion` → `AplicacionRegistrada`, `CASCADE`, `related_name='proveedores_autorizados'`.
- FK `proveedor` → `ProveedorPago`, `PROTECT`, `related_name='aplicaciones_autorizadas'`.
- `activo` — autorización puede revocarse sin borrar el historial de qué estuvo autorizado.
- `autorizado_en` (timestamp).
- `unique_together = ['aplicacion', 'proveedor']` — una sola fila de autorización por combinación.

**Flujo de rechazo (a nivel de servicio de aplicación, no solo de modelo):** resolver dominio de origen → `DominioPermitido` (activo) → `AplicacionRegistrada` (activa) → verificar `AplicacionProveedorPermitido` (activo) para el `ProveedorPago` solicitado → si cualquier paso falla, rechazar antes de tocar `IntencionPago`. El modelo soporta esta cadena de lookups con índices en cada punto de filtro.

`IntencionPago.app_origen_id` (2.2) pasa a ser una FK real a `AplicacionRegistrada` (`PROTECT` — no se borra el registro de una app con historial de pagos), en vez de un UUID suelto sin FK: a diferencia de `AppConsumidora` del portal (sistema externo), `AplicacionRegistrada` sí vive en esta misma base, por lo que la FK real aplica aquí.

### 2.1 Catálogos (FK con `on_delete=PROTECT`)

| Modelo | Propósito | Notas |
|---|---|---|
| `MedioPago` | tarjeta, Pago Móvil/C2P, transferencia, débito automático, pasarela internacional | Extensible sin deploy → catálogo, no `TextChoices`. |
| `ProveedorPago` | banco/adquirente/pasarela concreta detrás de un `MedioPago` | Soporta multi-adquirente/failover (T4) sin migración. Primera fila real confirmada: **BDV** (ver 2.5). |
| `ProveedorTokenizacion` | bóveda(s) PCI-DSS L1 certificadas | **FUERA DE ALCANCE por ahora** (decisión de negocio, ver `TokenReferencia` en 2.2) — se documenta la forma para cuando se retome, no se implementa en esta fase. |
| `Banco` | código SUDEBAN/BCV de 4 dígitos (ej. `"0102"` = BDV), nombre, activo | Confirmado por BDV (`customerBankCode`/`bancoOrigen` en ambos endpoints). `PROTECT` desde toda entidad que referencie un banco. El proveedor mantiene su propio catálogo dinámico (errores `1091`/`1092` = banco destino inactivo/no afiliado) que puede no coincidir con el nuestro — el catálogo local no se asume sincronizado automáticamente con el del banco. |
| `TipoOperacionProveedor` | valores como `"CELE"` del campo `operationType` del C2P | Catálogo por `ProveedorPago` (`PROTECT` a `ProveedorPago`), no string libre — cada proveedor puede tener su propio set. |
| `CodigoRespuestaProveedor` | tabla de referencia de los códigos de error/éxito de cada proveedor (`1000`, `1002`, ... `1094` para BDV C2P) | FK `PROTECT` a `ProveedorPago`, campos `codigo`, `descripcion`, `categoria` (`TextChoices`: `exito`, `duplicado_idempotente`, `error_negocio`, `error_tecnico`). Nunca hardcodear el mapeo en código — los códigos `1026`/`1094` de BDV se clasifican `duplicado_idempotente` y alimentan la lógica de `IdempotencyKey` (ver 2.3), no se muestran como fallo genérico. |

### 2.2 Agregado de pago

**`IntencionPago`** (`BaseModel`: UUIDv7 + timestamps)
- `monto` — **`DecimalField(max_digits=19, decimal_places=2)`** → `DECIMAL(19,2)` en Postgres. Es un monto **final** (lo cobrado/mostrado al usuario, en el formato que ya entrega BDV: `"amount": "1000.6"`), no un valor de cálculo intermedio — 2 decimales coincide con ISO 4217 para VES y USD (`research-manejo-dinero-bd.md` §2). **Nunca `FloatField` ni el tipo `MONEY` nativo de Postgres** (descartados sin ambigüedad por la misma investigación §1: `MONEY` depende del *locale* de la instancia, riesgo real en un proyecto con dos monedas).
- `moneda` — `TextChoices` (conjunto cerrado y estable de códigos ISO soportados).
- `medio_pago` → FK `MedioPago`, `PROTECT`.
- `aplicacion` → FK `AplicacionRegistrada` (ver 2.0), `PROTECT`, `related_name='intenciones_pago'`. **Actualizado**: ya no es un `UUIDField` suelto — al vivir `AplicacionRegistrada` en esta misma base (requisito de seguridad, 2.0), la referencia es una FK real, distinta del caso `AppConsumidora`/bóveda de tokenización (sistemas externos, sección 1).
- `idempotency_key` → OneToOne o FK a `IdempotencyKey` (ver 2.4).
- `estado_actual` — `TextChoices` cerrado (`pendiente`, `autorizado`, `capturado`, `anulado`, `fallido`, `reembolsado`, `expirado`). **Desnormalización justificada**: es un espejo de la última fila de `TransicionEstadoPago`, mantenido 100% automático por el servicio de transición (nunca editable a mano), documentado en el modelo — permite filtrar/listar sin recalcular el historial en cada consulta. `db_index=True` (filtro constante en dashboards/reintentos).
- `routing_flag` — `TextChoices` (`legacy`, `canario`) o booleano; persiste el bucket del canario 5–10% del strangler fig para poder auditar paridad legacy vs. nuevo por transacción (recomendación explícita del brief).

**`TransicionEstadoPago`** — tabla de auditoría *append-only*, fuente de verdad real del estado:
- FK `pago` → `IntencionPago`, `CASCADE`, `related_name='transiciones'`.
- `estado_anterior`, `estado_nuevo` — mismo `TextChoices` cerrado que `estado_actual`.
- `created_at` (sin `updated_at`: nunca se edita una fila ya escrita).
- **Punto abierto de implementación** (no de negocio): el brief recomienda que las transiciones inválidas sean estructuralmente imposibles a nivel DB (constraint/trigger de Postgres), no solo evitadas en la capa de aplicación — `suit-backend` debe evaluar si esto va como `CheckConstraint`/trigger explícito o queda solo validado en el servicio de dominio.

**Tipos de operación como entidades separadas** (no un único campo de estado ambiguo, por indicación explícita del brief):

| Modelo | `related_name` en `IntencionPago` | Nota |
|---|---|---|
| `Autorizacion` | `autorizaciones` | Reserva de fondos. Puede haber varias si hay reintento/failover multi-adquirente. |
| `Captura` | `capturas` | Transferencia real, post-autorización. |
| `Anulacion` (void) | `anulaciones` | Cancelación pre-settlement. |
| `Reembolso` (refund) | `reembolsos` | Reversión post-settlement. |

Todas: FK a `IntencionPago` (`CASCADE` — hijas dependientes del ciclo de vida del pago), FK a `ProveedorPago` (`PROTECT`), `referencia_proveedor` (id externo devuelto por el proveedor), `created_at`. Campo monetario propio (`monto`) — mismo tipo y misma razón que `IntencionPago.monto`: **`DecimalField(max_digits=19, decimal_places=2)`** → `DECIMAL(19,2)`, nunca `FloatField`/`MONEY`. Es el monto final de esa operación puntual (autorizado/capturado/anulado/reembolsado), no un cálculo intermedio.

**Campos confirmados por BDV que `Autorizacion`/`Captura`/`Anulacion` deben soportar de forma genérica (no hardcodeados a un banco)** — ver detalle en 2.5:
- `referencia_corta` — código corto (~8-12 dígitos) devuelto por el proveedor en la captura; es la clave de correlación usada por Conciliación. Campo distinto de `referencia_proveedor` porque un proveedor puede devolver más de un identificador (ver siguiente punto).
- `identificador_interbancario` — identificador largo (BDV: `endToEndId`, 62 caracteres) usado específicamente para anular la operación; no todos los proveedores lo tendrán, pero el campo debe existir separado de `referencia_corta` porque **no son intercambiables**: la anulación de BDV se hace por este campo, la conciliación por el corto.
- `tipo_operacion` → FK `TipoOperacionProveedor`, `PROTECT`.
- `codigo_respuesta` → FK `CodigoRespuestaProveedor`, `PROTECT` (nunca `CharField` libre — permite distinguir `duplicado_idempotente` de un error real sin parsear texto en cada consulta).
- `payload_crudo` — `JSONField`, la respuesta completa del proveedor tal como llegó. Justificado por el hallazgo de que BDV cambia el texto de sus mensajes entre versiones de su API (v6 ajustó la redacción de "pago ya conciliado") — sin el crudo, un cambio de wording del proveedor rompe cualquier reproceso retroactivo.

**`TokenReferencia` — FUERA DE ALCANCE por ahora (decisión de negocio explícita, no punto abierto)**
- **Alcance reducido confirmado por el usuario**: por ahora no se trabaja con tarjeta ni tokenización — el único medio de pago real es BDV Pago Móvil C2P (2.5), que no tokeniza nada (autentica con cédula + teléfono + OTP). `TokenReferencia`/`ProveedorTokenizacion` quedan **diferidos**, no implementados en esta fase.
- Se conserva el diseño documentado (FK/OneToOne a `IntencionPago`, `token` opaco, FK `ProveedorTokenizacion` `PROTECT`, regla dura de nunca almacenar PAN/CVV ni siquiera cifrado) como referencia para cuando el alcance se amplíe a tarjeta/pasarela internacional — no se borra del plan, se marca explícitamente diferido para que `suit-backend` no lo priorice ni migre estas tablas todavía.
- Cuando se retome: debe ser opcional (`null=True`) en `IntencionPago`, presente solo cuando `medio_pago` sea un adaptador basado en tarjeta — el resto del agregado (`Autorizacion`/`Captura`/etc.) no cambia, por el principio de multi-proveedor sin choque de la sección 1.

### 2.3 Outbox pattern (crítico, ruta crítica T2)

**`EventoOutbox`**
- FK `pago` → `IntencionPago`, `CASCADE`.
- `event_type` (`TextChoices` o `CharField` corto versionado por convención `pago.*`).
- `payload` — `JSONField`.
- `schema_version` — `PositiveSmallIntegerField`, explícito desde el primer contrato (gobernanza: dueño único de `pago.confirmado`, evita romper Conciliación en silencio).
- `estado` — `TextChoices` (`pendiente`, `enviado`, `fallido`), `db_index=True` (el relay filtra por `pendiente` constantemente).
- `created_at`, `sent_at` (nullable).

**Debe escribirse en la misma transacción de Postgres que el cambio de estado del pago** — es la garantía de atomicidad del patrón, no algo que el broker resuelva. Un proceso relay separado (poller o CDC) lee, publica a RabbitMQ y marca `enviado`. Entrega *at-least-once*: Conciliación deduplica por `event_id`, no asume exactly-once.

**`IdempotencyKey`**
- `key` — UUID generado por el cliente, `unique=True` (constraint a nivel DB, no solo aplicación, para prevenir inserciones duplicadas bajo concurrencia).
- `request_hash` — hash canónico del payload (monto, moneda, cuenta).
- `response_snapshot` — `JSONField`.
- `estado`, `expires_at`.
- Si llega una key repetida con `request_hash` distinto → rechazar, nunca reusar la respuesta cacheada.

### 2.4 Riesgo cambiario (T4) — FUERA DE ALCANCE por ahora

**`TasaCambioAplicada` — FUERA DE ALCANCE por ahora (decisión de negocio explícita, no punto abierto), misma condición que `TokenReferencia`/`ProveedorTokenizacion` (2.2).**
**Aclaración del usuario:** el proyecto **no va a hacer conversiones de moneda** — esto ya estaba implícito en el alcance reducido a BDV Pago Móvil C2P (2.5, sin tarjeta ni pasarela internacional), pero ahora es una decisión explícita, no una inferencia. `TasaCambioAplicada` se documenta solo como **referencia futura**, sin implementar en esta fase:

- FK/OneToOne a `IntencionPago`.
- `tasa` — si se retoma: `DecimalField(max_digits=18, decimal_places=6)` → `DECIMAL(18,6)`, **no 2 decimales** — es un valor de cálculo intermedio (multiplica al monto final), no un monto de presentación; 2 decimales introduciría un sesgo sistemático en cada conversión al truncar precisión de la tasa antes de aplicarla (`research-manejo-dinero-bd.md` §2). El monto final ya convertido seguiría guardándose en `DECIMAL(19,2)` como el resto del sistema — nunca un monto intermedio sin redondear como si fuera el oficial.
- `fuente`, `rate_timestamp` — sin cambios respecto al diseño original si se retoma.

Aislado en su propio adaptador/tabla (si se implementa) para no arrastrar el riesgo cambiario al resto de medios de pago, como pedía el roadmap — pero no forma parte del alcance actual.

**Nota de dominio sobre redondeo — solo aplicable si se retoma la conversión de moneda:** con conversiones fuera de alcance, **la advertencia previa de validar `ROUND_HALF_EVEN` contra normativa BCV no aplica hoy** — no hay ninguna operación de conversión en el sistema actual que requiera esa decisión. Se deja documentada para cuando (si) el alcance se amplíe:
- Estándar técnico por defecto sería `ROUND_HALF_EVEN` ("banker's rounding"), pero **a validar contra normativa BCV de conversión de divisas antes de fijarlo**, si en el futuro se reintroduce el riesgo cambiario — hay precedente regulatorio (la conversión del euro exige "round half up") de que la autoridad monetaria puede dictar una convención distinta a la técnica general.
- Si se retoma, la función de redondeo debe estar centralizada en el dominio compartido y con la misma especificación exacta replicada en Orquestador y Conciliación (no comparten código por database-per-service).

### 2.5 Adaptador confirmado: BDV Pago Móvil C2P (primer proveedor real)

Los dos PDFs leídos por research (`Doc - API C2P Cuentas Múltiples.pdf`,
`Doc- API Conciliación Dummy.pdf`) son documentación de **ambiente QA** del
Banco de Venezuela — confirman que el primer adaptador real detrás de
`PaymentProviderPort` es **BDV Pago Móvil C2P**, no un proveedor genérico.
Implicaciones directas para el modelo:

- **Autenticación por `X-API-Key` estática** (una para C2P, otra distinta
  para Conciliación) — no hay token de sesión que rotar en el modelo de
  datos; la rotación de la key es un secreto de infraestructura, fuera de
  este esquema.
- **Flujo de 3 pasos**: generación de OTP → proceso de cobro → anulación
  opcional. La generación de OTP **no produce ninguna referencia
  transaccional** — no justifica una entidad propia; alcanza con un
  timestamp (`otp_solicitado_at`) en `Autorizacion` para trazabilidad, sin
  crear una tabla `SolicitudOtp` separada (evita una entidad sin datos
  propios que modelar).
- **`coinType` confirma el catálogo de monedas**: el único valor visto en
  el dummy es `"VES"`, pero el contrato reserva campos para divisa
  extranjera (`cuentaDivisa`, `saldoCuentaDivisa`) — ver resolución del
  punto abierto 3 en la sección 5.
- **`customerBankCode`/`bancoOrigen` confirma el catálogo `Banco`** de 4
  dígitos, reutilizado igual en Orquestador (adaptador C2P) y en
  Conciliación (consulta `getMovement/v2`) — cada servicio mantiene su
  propia copia local del catálogo (sin FK cruzada entre DBs), poblada
  manualmente o por un comando de sincronización, nunca por FK directa a
  la tabla del otro servicio.

---

## 3. Conciliación — entidades

### 3.1 Catálogos

| Modelo | Propósito |
|---|---|
| `CuentaContable` | plan de cuentas del ledger, `PROTECT` desde las líneas |
| `Banco` | mismo catálogo conceptual que en Orquestador (código SUDEBAN/BCV de 4 dígitos), copia local propia de este servicio — sin FK cruzada entre DBs |

### 3.2 Ingesta de eventos

**`EventoPagoRecibido`**
- `event_id` — `unique=True` (dedup del *at-least-once* del outbox del Orquestador).
- `payload`, `schema_version` (espejo de lo publicado).
- `procesado_at` (nullable hasta que el consumer Celery lo procese).

### 3.2b Conciliación real con BDV: consulta síncrona, no feed batch

**Hallazgo que cambia el diseño respecto al bosquejo inicial:** el roadmap
describía Conciliación en abstracto como consumidora de un "estado de
cuenta" bancario. La API real de BDV (`POST /getMovement/v2`) es un
**servicio de consulta síncrona request/response por transacción**, no un
feed batch ni un webhook — Conciliación debe *hacer polling activo* de esta
API por cada pago pendiente, disparado por el consumo de `pago.confirmado`
desde RabbitMQ. Esto reemplaza/complementa `MovimientoBancario` (que se
mantiene como modelo genérico por si un banco futuro sí entrega extractos
batch) con dos entidades nuevas:

**`ConsultaConciliacionProveedor`** — un registro por cada intento de
consulta a `getMovement/v2` (puede haber más de uno por el mismo pago, por
el debounce de 30s del banco):
- FK `evento` → `EventoPagoRecibido`, `CASCADE`.
- FK `banco` → `Banco`, `PROTECT`.
- `referencia_corta` — clave de correlación con el `referencia` que el
  Orquestador recibió en la captura (ver 2.2) — es el campo primario de
  matching, **no** `cedula_pagador` (ver siguiente punto).
- `telefono_pagador` — clave de correlación secundaria, confiable incluso
  cuando `cedula_pagador` no lo es.
- `cedula_pagador` — dato informativo, **condicionalmente confiable**.
- `cedula_confiable` — `BooleanField`, derivado automáticamente de si la
  operación es BDV↔BDV o interbancaria (vía Suiche 7B). **Regla de negocio
  confirmada por el proveedor**: en operaciones interbancarias el banco
  sustituye la cédula real del pagador por `"V" + RIF del comercio
  receptor` — `cedula_pagador` **no** es una clave natural confiable de
  identidad del cliente en ese caso. `req_ced` (el flag que activa
  validación estricta de cédula en la consulta) debe ir `true` solo en
  operaciones BDV↔BDV; el dominio de Conciliación encapsula esta regla
  condicional, no queda como decisión manual del operador.
- `importe_esperado` — **`DecimalField(max_digits=19, decimal_places=2)`** → `DECIMAL(19,2)`, misma convención que `IntencionPago.monto` (el proveedor lo envía como string, ej. `"120.00"`; casteo directo a `Decimal` al persistir, nunca a `float`, y comparación exacta contra el monto de la captura — `research-manejo-dinero-bd.md` §5 documenta la comparación exacta de `Decimal` como confiable y preferible sobre comparación con tolerancia, justo el caso de uso de matching de esta tabla).
- `fecha_pago`.
- `codigo_respuesta_raw`, `mensaje_respuesta_raw` — texto crudo tal como
  llega, **necesario** porque BDV no distingue error de autenticación de
  "pago no encontrado" por código (ambos casos devuelven `1010`, solo el
  texto de `message` difiere) y porque el wording del mensaje ya cambió
  entre versiones de la API del proveedor (v6 ajustó el mensaje de "pago ya
  conciliado") — un parser basado en texto exacto sin el crudo guardado no
  puede reprocesar retroactivamente si el proveedor vuelve a cambiar el texto.
- `resultado_interpretado` — `TextChoices` (`conciliado`, `no_encontrado`,
  `monto_no_coincide`, `ya_conciliado`, `error_credenciales`,
  `pendiente_revision`) — la interpretación normalizada que sí puede usar
  el resto del sistema sin volver a parsear texto.
- `payload_crudo` — `JSONField`, respuesta completa del proveedor (tabla de
  staging/log crudo, separada del resultado interpretado, tal como pide el
  brief).
- `created_at`.

**`MovimientoBancario`** se mantiene como modelo **genérico** (no
específico de BDV) para el caso de un proveedor futuro que sí entregue
extracto batch — no se descarta, pero para el primer adaptador (BDV) el
camino real de datos es `ConsultaConciliacionProveedor`, no este modelo.

### 3.3 Ledger de doble entrada (T3, pero modelado desde ya)

Patrón validado en la industria (Stripe, Monzo, Nubank), citado en el brief:

**`TransaccionLedger`** — agrupador que ata las líneas balanceadas de una operación.
- `referencia_evento` — FK a `EventoPagoRecibido` (o UUID lógico si se prefiere desacoplar).
- `created_at`.

**`LineaLedger`**
- FK `transaccion` → `TransaccionLedger`, `CASCADE`, `related_name='lineas'`.
- FK `cuenta` → `CuentaContable`, `PROTECT`.
- `tipo` — `TextChoices` (`debito`, `credito`).
- `monto` — **`DecimalField(max_digits=19, decimal_places=2)`** → `DECIMAL(19,2)`, siempre positivo (el signo lo da `tipo`, no el monto). Misma convención que el resto del sistema — nunca mezclar con enteros de centavos en esta ni ninguna otra tabla.

**Punto abierto de implementación:** el brief insiste en que la suma de débitos y créditos de cada `TransaccionLedger` debe forzarse a nivel de motor (constraint/trigger de Postgres), no solo en la capa de aplicación, "para que un bug en un módulo no corrompa el ledger compartido". `suit-backend` debe decidir el mecanismo exacto (trigger `PL/pgSQL` vs. validación transaccional en el servicio + reconciliación periódica de auditoría).

### 3.4 Matching e importación bancaria

**`MovimientoBancario`**
- FK `banco` → `Banco`, `PROTECT`.
- `fecha`, `referencia_banco`.
- `monto` — **`DecimalField(max_digits=19, decimal_places=2)`** → `DECIMAL(19,2)`, misma convención que el resto del sistema.
- `estado_conciliacion` — `TextChoices` (`pendiente`, `conciliado`, `discrepante`), `db_index=True`.
- Candidata a partición por fecha si el volumen crece (no antes de tener señal real de tamaño, por la regla de la skill de supervisión).

**`Discrepancia`**
- FK nullable a `MovimientoBancario`, a `ConsultaConciliacionProveedor` y a `EventoPagoRecibido` (una discrepancia puede originarse en cualquiera de los lados del matching — incluyendo un `resultado_interpretado` en `monto_no_coincide`/`error_credenciales`/`pendiente_revision`, que siempre debe generar una `Discrepancia`, nunca fallar en silencio).
- `tipo`, `severidad`.
- `estado_resolucion` — `TextChoices`.
- `resuelto_por` — FK a usuario, `SET_NULL`, `null=True, blank=True` (auditoría de quién resolvió).
- Alerta obligatoria ante cualquier diferencia > 0, según el riesgo "doble contabilidad" del roadmap — la tabla es el soporte de datos de esa alerta, no la alerta en sí.

**`ReporteERP`**
- Trazabilidad de lo exportado al ERP contable: `fecha`, `referencia_externa`, `payload`/resumen.

### 3.5 `AsientoLedger` de solo-inserción — nota de auditoría

`TransaccionLedger`/`LineaLedger` y `MovimientoBancario` son tablas de
solo-inserción por diseño (nunca se editan retroactivamente, solo se
reversan con un asiento nuevo). Aplicar la misma vigilancia de `n_dead_tup`/
partición de la skill de supervisión cuando el volumen lo justifique — no
antes.

---

## 4. Reglas transversales aplicadas (checklist ya resuelto)

- Toda entidad propia hereda de `BaseModel` (UUIDv7 + timestamps), salvo
  catálogos importados de un sistema externo (no aplica aquí — no hay
  catálogos importados en pagos, a diferencia de RECAUDACION).
- Cero `CharField` de texto libre para conceptos cerrados o de catálogo:
  `MedioPago`, `ProveedorPago`, `Banco`, `CuentaContable`,
  `TipoOperacionProveedor`, `CodigoRespuestaProveedor` son catálogos;
  `estado_actual`, `tipo` (débito/crédito), `estado_conciliacion`,
  `resultado_interpretado` son `TextChoices` porque gobiernan lógica de
  código y son conjuntos cerrados. Excepción deliberada: `codigo_respuesta_raw`/
  `mensaje_respuesta_raw` en `ConsultaConciliacionProveedor` sí son texto
  libre — es staging crudo intencional, documentado en 3.2b, no un campo
  relacional disfrazado de texto.
- Ninguna FK de catálogo sin `on_delete=PROTECT`. Ninguna FK hija sin
  `on_delete=CASCADE` explícito y limitado a hijas dependientes del ciclo de
  vida del padre (`Autorizacion`, `Captura`, `Anulacion`, `Reembolso`,
  `TransicionEstadoPago`, `EventoOutbox`, `LineaLedger`).
- `related_name` explícito en cada relación, plural para colecciones.
- Índices en todo campo de estado usado para filtrar/pollear (`EventoOutbox.estado`,
  `MovimientoBancario.estado_conciliacion`, `IntencionPago.estado_actual`).
- Constraints de unicidad: `IdempotencyKey.key`, `EventoPagoRecibido.event_id`.
- **Convención monetaria única en todo el sistema** (`research-manejo-dinero-bd.md`):
  `DecimalField`/`DECIMAL` siempre, nunca `FloatField` ni el tipo `MONEY`
  nativo de Postgres. Montos finales (lo cobrado/mostrado/persistido como
  oficial) en `DECIMAL(19,2)` en todas las tablas del alcance actual. La
  escala mayor (`DECIMAL(18,6)`) y la nota de redondeo entre tasa y monto
  final solo aplican a `TasaCambioAplicada`, que está **fuera de alcance
  por ahora** (2.4) — el proyecto no hace conversiones de moneda en su
  alcance actual, así que hoy no hay ningún cálculo intermedio de tasa que
  redondear. Nunca mezclar con enteros de centavos en ninguna tabla.
- Ningún campo capaz de almacenar PAN/CVV en ningún modelo propio — solo
  `TokenReferencia.token` como referencia opaca.
- Ninguna FK cruzada entre las DBs de Orquestador y Conciliación — solo IDs
  lógicos que viajan en el payload del evento.

---

## 5. Puntos abiertos

Estado tras incorporar los hallazgos de BDV (sección 4 del brief) y las 3
decisiones de negocio de esta revisión. Se marcan `RESUELTO`,
`FUERA DE ALCANCE`, `PARCIAL` o `ABIERTO`.

1. **`FUERA DE ALCANCE (decisión de negocio)` — Proveedor real de
   tokenización.** Ya no es un punto abierto a resolver con research: el
   usuario confirmó que tarjeta/tokenización no se trabajan por ahora — el
   único medio de pago real es BDV Pago Móvil C2P. `TokenReferencia`/
   `ProveedorTokenizacion` quedan diferidos y documentados (2.2), sin
   urgencia de decisión. Se retoma si el alcance se amplía a tarjeta o
   pasarela internacional.
2. **`ABIERTO` — Mecanismo del relay outbox → RabbitMQ** (poller propio vs.
   CDC). No hay información de infraestructura interna en los PDFs de BDV;
   decisión de `suit-backend`/infra, no de un proveedor externo.
3. **`PARCIAL` — Catálogo de monedas.** BDV confirma `VES` como única
   moneda con tráfico real hoy (`coinType: "VES"` en el dummy), con campos
   reservados (`cuentaDivisa`, `saldoCuentaDivisa`) que anticipan soporte de
   divisa extranjera sin confirmarla activa. **Recomendación para
   `suit-backend`:** poblar el catálogo `Moneda`/`TextChoices` con `VES`
   (activo) + `USD` (reservado/inactivo) desde ya, sin esperar a T4 — el
   campo `activo` en el catálogo decide cuándo se habilita, sin migración
   nueva. Sigue abierto si el proyecto necesita una tercera moneda o un
   valor de activación distinto a T4.
4. **`CERRADO / DEFINITIVO` — Registro de apps/dominios autorizados.**
   Confirmado dos veces por el usuario, no es un punto abierto ni opcional:
   el Orquestador mantiene su propio registro de seguridad
   (`AplicacionRegistrada` + `DominioPermitido` +
   `AplicacionProveedorPermitido`, sección 2.0), independiente del
   Developer Portal. El mecanismo técnico está confirmado por
   `research-seguridad-iframe.md`: CSP `frame-ancestors` dinámico +
   validación `Origin`/`Referer` en backend, ambos resueltos contra
   `DominioPermitido`. Única nota abierta (de implementación, no de
   modelo): a quién pertenece la fuente de verdad editable del dominio —
   Portal como UI de autogestión + Orquestador como copia de lectura
   rápida, o Orquestador como única fuente — ver nota de supervisión en 2.0.
5. **`ABIERTO` — Mecanismo de balance-cero del ledger.** No afectado por
   BDV ni por las decisiones de esta revisión (BDV no participa del ledger
   de doble entrada, que es interno a Conciliación). Decisión de
   implementación en `suit-backend`.
6. **`ABIERTO` — Ventana de expiración de `IdempotencyKey.expires_at`.**
   BDV aporta un dato relacionado pero distinto: un **debounce de 30
   segundos** del lado del banco para la consulta de conciliación
   (`getMovement/v2` devuelve "ya fue conciliado" si se reconsulta la misma
   referencia dentro de 30s) — es una ventana de *deduplicación de consulta*
   en Conciliación, no la ventana de *expiración de idempotencia* del
   Orquestador citada en el brief (24-48h). No confundir ambas al
   implementar: son dos mecanismos distintos en dos servicios distintos.
   El valor de `expires_at` del Orquestador sigue sin definir.
7. **`ABIERTO` — Registro de esquemas de eventos versionado.** Gobernanza
   interna (dueño único de `pago.confirmado`), no depende de BDV.
8. **`PARCIAL` — Multi-adquirente/failover (T4).** BDV confirma que el
   **primer adaptador real es de un solo proveedor** (BDV), lo cual
   despriorizar la urgencia de resolver la semántica de failover para
   T1–T2 — el diseño de `Autorizacion` con múltiples filas por
   `IntencionPago` ya lo soporta estructuralmente sin cambios (reforzado
   ahora por el principio explícito de multi-proveedor sin choque, sección
   1). La pregunta original (¿nueva `Autorizacion` sobre la misma intención
   vs. nueva `IntencionPago` enlazada?) sigue sin decisión de negocio, pero
   deja de ser bloqueante hasta que se sume un segundo proveedor (T4).

### Decisiones de diseño ya cerradas por los hallazgos de BDV (no eran puntos de la lista original, pero quedaban implícitos en el bosquejo)

- `referencia_corta` y `identificador_interbancario`/`endToEndId` son campos
  **separados**, no un solo `referencia_proveedor` — confirmado por el
  propio contrato de BDV (2.2).
- `cedula_pagador` **no** es clave de correlación confiable por sí sola en
  Conciliación — se usa `telefono_pagador` + `referencia_corta`, con
  `cedula_confiable` como flag derivado (3.2b).
- Se necesita una tabla de staging/log crudo (`payload_crudo` +
  `codigo_respuesta_raw`/`mensaje_respuesta_raw`) separada del resultado
  interpretado en Conciliación, porque el proveedor no distingue tipos de
  error por código HTTP/código de negocio de forma confiable, y su wording
  cambia entre versiones (3.2b).
- Los códigos `1026`/`1094` de BDV se mapean a `CodigoRespuestaProveedor.categoria
  = 'duplicado_idempotente'`, no a error genérico — integra la idempotencia
  nativa del proveedor con `IdempotencyKey` en vez de duplicar lógica.

### Decisiones de negocio cerradas en esta revisión

- **Multi-proveedor sin choque** es ahora un principio explícito de diseño
  (sección 1), no solo una intención implícita en los catálogos por
  proveedor.
- **Registro de seguridad de apps/dominios** (`AplicacionRegistrada`,
  `DominioPermitido`, `AplicacionProveedorPermitido`) vive en el
  Orquestador, resuelve el punto 4 original, y cambia `IntencionPago.app_origen_id`
  de `UUIDField` suelto a FK real `PROTECT` (sección 2.0 y 2.2).
- **Tarjeta/tokenización quedan fuera de alcance por ahora** — `TokenReferencia`/
  `ProveedorTokenizacion` se documentan pero no se implementan; el único
  medio de pago real a modelar en esta fase es BDV Pago Móvil C2P.

---

## 6. Próximos pasos sugeridos

- `suit-backend` traduce este bosquejo a modelos Django reales dentro de
  `apps/<feature>/domain/` (o equivalente), aplicando la arquitectura
  Onion+Screaming ya definida en el roadmap (`autorizacion/`, `conciliacion/`,
  `tokenizacion/` como slices). El adaptador `autorizacion/infra/` para BDV
  ya tiene contrato de campos concreto (2.5, 2.2, 3.2b) — puede implementarse
  sin esperar más research.
- Antes de escribir migraciones, resolver al menos el punto abierto 6
  (expiración de idempotency keys del Orquestador — no confundir con el
  debounce de 30s de BDV) — afecta un tipo de campo concreto y no tiene
  ningún hallazgo de research que lo resuelva.
- El mecanismo de trigger de balance-cero (punto 5) y el de transición de
  estado válida (sección 2.2) deberían resolverse juntos, ya que ambos son
  la misma clase de decisión: ¿constraint/trigger a nivel Postgres, o
  disciplina exclusiva de la capa de servicio?
- Con tarjeta/tokenización fuera de alcance, el primer entregable realista
  de `suit-backend` es el agregado de pago (2.0-2.3) + adaptador BDV (2.5)
  completo, sin esperar por `TokenReferencia`/`ProveedorTokenizacion` —
  esas dos tablas se retoman solo si el alcance se amplía a tarjeta o
  pasarela internacional (T4).
- El flujo de rechazo por dominio/proveedor no autorizado (2.0) debe
  implementarse como parte del camino crítico de `autorizacion/`, antes de
  crear cualquier `IntencionPago` — es un control de seguridad, no una
  validación opcional.
