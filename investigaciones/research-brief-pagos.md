# Brief de contexto — Suite Centralizada de Pagos (para modelado de esquema de datos)

## 1. Contexto del proyecto (fuente: `conatel-suite-pagos-roadmap.html`)

Payment gateway interno para Conatel que desacopla medios de pago del core de las apps (piloto: Homologación → Conatel en Línea), vía **strangler fig**. Dos servicios independientes, cada uno con DB propia:

- **Orquestador de Pagos** (Django, Onion+Screaming+feature-sliced): camino síncrono — autorizar/capturar/revertir. Slices: `autorizacion/`, `conciliacion/`, `tokenizacion/`, cada uno con `domain/`, `application/`, `infra/`. Adaptadores de salida por proveedor (tarjeta, Pago Móvil/C2P, transferencia, débito automático, pasarela internacional) detrás de un puerto `PaymentProviderPort`.
- **Conciliación**: async, consume eventos de RabbitMQ (`pago.*`) vía Celery workers, DB propia, no bloquea el cobro. Objetivo: 5 días → 1h.
- **Bóveda de tokenización**: proveedor PCI-DSS L1 externo — el PAN nunca toca infra propia.
- **Developer Portal** (Next.js): API keys, métricas de uso.

Repo actual (`suit-backend`/`suit-frontend`) está en esqueleto — sin modelos de datos aún.

## 2. Implicaciones directas para el esquema de datos

### Database-per-service — separación estricta
- Orquestador: intenciones de pago, estado de transacción, **tokens de referencia** (nunca PAN). PostgreSQL, optimizado para baja latencia/consistencia fuerte.
- Conciliación: movimientos bancarios, matching, discrepancias, ledger contable. PostgreSQL en instancia separada — sus cargas por lotes/reprocesos no deben competir por I/O con el cobro en vivo.
- Ningún JOIN cross-servicio a nivel de DB. La única frontera es el bus de eventos.

### Outbox pattern (crítico para T2, "idempotencia + outbox" en ruta crítica)
- El Orquestador necesita una tabla `outbox_events` en la **misma DB y transacción** que el cambio de estado del pago (atomicidad garantizada por la DB, no por el broker). Campos típicos: `id`, `aggregate_id` (payment_id), `event_type`, `payload` (JSON versionado), `status` (pending/sent/failed), `created_at`, `sent_at`.
- Un proceso relay separado (poller o CDC tipo Debezium) publica a RabbitMQ y marca como enviado. Entrega es *at-least-once* — Conciliación debe deduplicar por `event_id`.
- Fuente: [microservices.io — Transactional outbox](https://microservices.io/patterns/data/transactional-outbox.html)

### Idempotencia (riesgo alto en el roadmap: "doble contabilidad")
- Tabla dedicada `idempotency_keys` (o namespace separado): `key` (UUID generado por el cliente), `request_hash` (payload canónico: monto, moneda, cuenta), `response_snapshot`, `status`, `expires_at` (ventana 24-48h es estándar de la industria). Constraint UNIQUE a nivel DB para prevenir inserciones duplicadas bajo concurrencia.
- Si el `request_hash` no coincide con una key repetida, rechazar — no reusar la respuesta cacheada.

### Máquina de estados de la transacción (debe reflejarse en el modelo, no solo en código)
- Estados típicos de la industria: `pending → authorized → captured/completed`, con ramas a `voided`, `failed`, `refunded`. Un pago `refunded` no puede transicionar a `voided`, etc.
- Recomendación: modelar transiciones válidas con constraint/trigger a nivel DB (o al menos una tabla `payment_status_transitions` de auditoría append-only) para que estados ilegales sean estructuralmente imposibles, no solo evitados por la capa de aplicación.
- Distinguir explícitamente `authorization` (reserva) vs `capture` (transferencia real) vs `void` (cancelación pre-settlement) vs `refund` (reversión post-settlement) como tipos de evento/registro separados, no como un único campo de estado ambiguo.

### Ledger de doble entrada en Conciliación (T3 del roadmap)
- Patrón validado en la industria (Stripe, Monzo, Nubank): cada transacción se registra como ≥2 líneas (débito/crédito) que deben sumar cero, forzado con constraints/triggers a nivel DB — no solo en la capa de aplicación, para que un bug en un módulo no corrompa el ledger compartido.
- Separar `accounts` (plan de cuentas), `ledger_entries` (líneas individuales) y `ledger_transactions` (agrupador que ata las líneas balanceadas), más una tabla de `discrepancies`/`matching_exceptions` para diffs >0 (mencionado como alerta obligatoria en riesgos).
- Fuentes: [freeCodeCamp — Bank Ledger PostgreSQL](https://www.freecodecamp.org/news/build-a-bank-ledger-in-go-with-postgresql-using-the-double-entry-accounting-principle/), [Matthew Wong — ERP General Ledger PostgreSQL](https://www.matthewswong.com/en/blog/erp-general-ledger-double-entry-design/)

### Tokenización / alcance PCI-DSS
- El Orquestador solo almacena una **referencia de token** (string opaco del proveedor de bóveda), nunca PAN, CVV ni datos de autenticación sensible. No debe existir ningún campo en el esquema propio capaz de contener PAN, ni siquiera cifrado — eso mantiene el alcance de auditoría fuera de esas tablas.
- Fuente: [SecurityMetrics — Tokenization PCI-DSS](https://www.securitymetrics.com/blog/what-tokenization-and-how-can-i-use-it-pci-dss-compliance)

### Contrato de eventos versionado (gobernanza: dueño único de `pago.confirmado`)
- El payload de cada evento (`payload` JSON en el outbox) necesita un campo de versión de esquema explícito desde el día 1. Recomendación: JSON Schema versionado en un registro compartido (aunque sea un repo/carpeta versionada, no necesariamente Confluent-style), con reglas de compatibilidad backward. Evita que Conciliación se rompa en silencio ante un cambio de esquema.

### Riesgo cambiario (T4, medio de pago internacional)
- Si se modela liquidación internacional, aislar en tablas propias del adaptador correspondiente: tasa BCV oficial congelada por transacción **con timestamp auditable** (campo `exchange_rate`, `rate_timestamp`, `rate_source`) — no un tipo de cambio mutable global.

## 3. Recomendaciones concretas para `expert_database`

1. Diseñar dos esquemas/DBs completamente independientes (Orquestador, Conciliación) sin FKs cruzadas — solo referencias lógicas por ID que viajan en los eventos.
2. Incluir desde el diseño inicial: `outbox_events`, `idempotency_keys`, tabla de transiciones de estado auditable, y separación estricta de `payment_intent`/`authorization`/`capture`/`refund` como entidades o tipos de evento distintos.
3. Ledger de Conciliación como doble entrada desde T2/T3 (no como añadido tardío) — constraints DB-level para balance cero.
4. Ningún campo destinado a PAN/CVV en ningún esquema propio; solo `token_reference` (FK lógica a la bóveda externa).
5. Versionar el schema de eventos (`schema_version` en el payload) desde el primer contrato `pago.*`.
6. Para el piloto Homologación con canario 5-10%, considerar un campo de `routing_flag`/`canary_bucket` en las tablas de transacción si el bandera-por-transacción necesita persistirse para auditoría de paridad legacy vs. nuevo.

---

## 4. Hallazgos de documentación real de proveedor (BDV — Banco de Venezuela)

Se leyeron completos los dos PDFs sin trackear en la raíz del repo: `Doc - API C2P Cuentas Múltiples .pdf` (4 páginas, v1, 10/12/2025) y `Doc- API Conciliación Dummy.pdf` (5 páginas, v6, 17/11/2025). Ambos son documentación **dummy de ambiente Calidad (QA)** del Banco de Venezuela (BDV), no de producción — los endpoints usan el host `bdvconciliacionqa.banvenez.com:444`. Esto confirma que **el primer adaptador de proveedor real a implementar es BDV Pago Móvil C2P**, con conciliación provista por el mismo banco (no un feed de estado de cuenta genérico como asumía el roadmap en abstracto).

### 4.1 API C2P Cuentas Múltiples (BDV) — cobro vía Pago Móvil C2P

Servicio para que un comercio cobre a una persona natural vía Pago Móvil C2P, con selección de cuenta de abono por número de teléfono afiliado. Flujo de **3 etapas** con 3 endpoints POST distintos — esto mapea directo a la máquina de estados ya prevista en el brief (autorización → captura → anulación), pero con nombres y payloads reales:

**Autenticación:** header `X-API-Key` (string estático por comercio/ambiente) + `Content-Type: application/json`. Es autenticación simple por API key, no OAuth — la validez y rotación de esa key es responsabilidad del comercio/orquestador, no hay token de sesión.

**1. Generación de OTP** — `POST /BankMobilePaymentC2P/MultipleAccounts/paymentkey/v2`
- Entrada: `{ "customerDocumentId": "V12345678" }`
- Salida: `{ "code": "1000", "message": "Proceso finalizado", "data": null, "status": 200 }`
- Nota: dispara el envío de la clave OTP al pagador; no genera aún ninguna referencia de transacción.

**2. Proceso de Cobro** — `POST /BankMobilePaymentC2P/MultipleAccounts/process/v2`
- Entrada:
  ```json
  {
    "customerDocumentId": "V12345678",
    "customerNumberInstrument": "04125692243",
    "amount": "1000.6",
    "customerBankCode": "0102",
    "concept": "Pago",
    "otp": "5551111",
    "coinType": "VES",
    "operationType": "CELE",
    "commerceNumberInstrument": "04140282647"
  }
  ```
- Salida (éxito):
  ```json
  {
    "code": "1000",
    "message": "Proceso finalizado",
    "data": {
      "date": "2025-11-14",
      "endToEndId": "0102010298400079090940416589264220251114162931090620472770",
      "cuenta": null,
      "saldoDisponible": null,
      "cuentaDivisa": null,
      "saldoCuentaDivisa": null,
      "referencia": "090037579602"
    },
    "status": 200
  }
  ```
- **`endToEndId`** es la referencia interbancaria larga (62 caracteres, formato numérico posicional: parece codificar código de banco + fecha + secuencia) — es el identificador que se debe guardar para poder anular la operación después.
- **`referencia`** es un código corto (12 dígitos) — es el que se usa para conciliación (ver 4.2, campo `referencia`).
- Campos `cuenta`, `saldoDisponible`, `cuentaDivisa`, `saldoCuentaDivisa` vienen `null` en este dummy pero están reservados en el contrato — sugiere que el proveedor soporta cuentas en divisa (USD) además de VES, relevante para el riesgo cambiario de T4.
- `coinType` confirma catálogo de monedas mínimo: al menos `"VES"` (y probablemente un código de divisa extranjera, dado el campo `cuentaDivisa`).
- `operationType: "CELE"` — sugiere un catálogo de tipos de operación (posiblemente distingue Pago Móvil directo vs. C2P vs. otros canales); el orquestador debería modelar esto como enum/catálogo, no como string libre.
- `customerBankCode` / `bancoOrigen` (ver 4.2) son códigos de banco de 4 dígitos (ej. `"0102"` = Banco de Venezuela) — confirma la necesidad de un **catálogo de bancos** (código SUDEBAN/BCV) como tabla de referencia, no un campo de texto libre.

**3. Proceso de Anulación** — `POST /BankMobilePaymentC2P/MultipleAccounts/annulment/v2`
- Entrada: `{ "endToEndId": "<el mismo recibido en el cobro>", "referenceOrigin": null }`
- Salida (éxito): mismo shape que el cobro pero con todos los campos de `data` en `null` excepto `date` — es decir, la anulación no devuelve una nueva referencia, solo confirma.
- Esto valida el punto ya anotado en la sección 2: `void` es un tipo de operación distinto de `capture`, referenciado por `endToEndId`, no por el `referencia` corto.

**Tabla de errores (catálogo a modelar como tabla de referencia, no hardcodear):**
`1000` Transacción realizada · `1002` Error envío conector · `1006` Rif no es Merchant · `1013` Monto inválido · `1014` Beneficiario no afiliado a PagomóvilBDV · `1015` No afiliado a ClavemóvilBDV · `1026` Referencia/Monto duplicado · `1034` Saldo insuficiente · `1041` Servicio inactivo · `1050` Timeout · `1055` Clave no existe · `1056` Teléfono no corresponde al titular · `1061` Monto supera límite diario · `1062` Cuenta con inconvenientes · `1065` Cantidad de transacciones superada · `1080` Documento de identidad inválido · `1091` Banco destino inactivo · `1092` Banco destino no afiliado · `1094` Operación duplicada.

Nótese que **`1026` (Referencia/Monto duplicado)** y **`1094` (Operación duplicada)** son señales nativas del proveedor de una lógica de idempotencia del lado del banco — el orquestador debería mapear estos códigos a su propia tabla `idempotency_keys` (sección 2) en vez de tratarlos como errores genéricos, porque indican un reintento exitosamente detectado, no una falla real de negocio.

### 4.2 API Conciliación (BDV) — verificación de pagos móviles recibidos

Servicio que permite validar/conciliar un pago móvil recibido contra los registros del banco, en tiempo real. Es el mecanismo de conciliación real que reemplazará (o alimentará) el "Servicio de Conciliación" descrito en el roadmap — importante: **es un servicio de consulta síncrono (request/response por transacción)**, no un feed batch ni un webhook de eventos. Esto tiene una implicación directa de diseño: el servicio de Conciliación de Conatel necesitará *poll* activamente esta API por cada pago pendiente de conciliar (probablemente disparado por el consumo del evento `pago.confirmado` desde RabbitMQ), no simplemente ingerir un extracto bancario.

**Autenticación:** header `X-API-Key` (distinta a la del C2P) + `Content-Type: application/json`.

**Endpoint:** `POST https://bdvconciliacionqa.banvenez.com:444/getMovement/v2`

**Request:**
```json
{
  "cedulaPagador": "V27037606",
  "telefonoPagador": "04127141363",
  "telefonoDestino": "04127141363",
  "referencia": "12345678",
  "fechaPago": "2023-02-12",
  "importe": "120.00",
  "bancoOrigen": "0102",
  "reqCed": false
}
```

| Campo | Tipo | Notas de modelado |
|---|---|---|
| `cedulaPagador` | String | Formato `"V" + número`. **Caso especial interbancario**: cuando el pago viene de Suiche 7B, el banco no provee la cédula real del pagador y la sustituye por `"V" + RIF del comercio receptor` — el campo NO es confiablemente la identidad del pagador en operaciones interbancarias; para esos casos identificar al cliente por `telefonoPagador`. **Esto es una regla de negocio que debe vivir en el dominio de Conciliación, no asumirse como dato limpio.** |
| `telefonoPagador` / `telefonoDestino` | String | Formato local venezolano (`04XXXXXXXXX`), sin código de país. |
| `referencia` | String | La referencia corta (coincide en formato con el `referencia` de 12 dígitos devuelto por el C2P) — es la clave de correlación entre el evento del Orquestador y la consulta a Conciliación. |
| `fechaPago` | String | Formato `AAAA-MM-DD` (fecha, sin hora). |
| `importe` | String | Decimal con punto, **como string, no número** — el orquestador debe normalizar/castear con cuidado de precisión (usar `Decimal`, nunca float, al persistir). |
| `bancoOrigen` | String | Código de banco (mismo catálogo que `customerBankCode` del C2P). |
| `reqCed` | Boolean | Activa validación estricta de cédula — **solo debe ser `true` en operaciones BDV↔BDV**; en operaciones interbancarias debe ir `false` (dado el problema de cédula sustituida arriba). Esto es una regla condicional según el `bancoOrigen`/`bancoDestino` que el dominio de Conciliación debe encapsular. |

**Respuesta exitosa:**
```json
{
  "code": 1000,
  "message": "Monto: 120.00 - estatus: Transacción realizada",
  "data": {
    "status": "1000",
    "amount": "120.00",
    "reason": "Transacción realizada",
    "referencia": "12345678"
  },
  "status": 200
}
```

**Escenarios de no-match / error (todos devuelven HTTP `status: 200`, el resultado real va en `code`/`data`):**
- Datos errados / no existe coincidencia → `code: 1010`, `message: "No se pudo validar el movimiento : Registro solicitado no existe"`, `data: null`.
- Monto/importe errado → `code: 1010`, `message` incluye el monto real devuelto por el banco junto al estatus (`"monto : 120.00 - estatus : Transacción realizada"`) — es decir, **en un mismatch de monto el banco sí devuelve el monto real dentro del string de `message`, pero no estructurado en `data`**; el parser de Conciliación tendría que extraerlo del mensaje si quiere comparar automáticamente contra el monto esperado (o tratarlo como discrepancia manual).
- Pago ya conciliado previamente → `code: 1010`, `message: "Pago Móvil procesado exitosamente en el BDV. El movimiento ya fue conciliado anteriormente."`, `data: null`. Ocurre si (a) ya se validó/concilió antes, o (b) se reconsulta el mismo pago dentro de los primeros 30 segundos tras la primera consulta (rate-limit/debounce del lado del banco).
- API Key errada → también `code: 1010`, `message: "Cliente no afiliado al producto"` — **el error de autenticación no se distingue por HTTP status (siempre 200) ni por un código distinto de negocio**; solo por el texto del mensaje. Esto es una limitación real del proveedor a tener en cuenta: el dominio de Conciliación no puede confiar en `code`/`status` para distinguir "falla de credenciales" de "pago no encontrado" — necesita parsear `message` o tratar ambos como "no conciliable, requiere revisión manual".

**Códigos de respuesta (solo dos, binario):** `1000` = Pago conciliado exitosamente · `1010` = Pago no conciliado / error / datos no válidos / ya conciliado (código único para 4 escenarios distintos, diferenciados solo por el texto de `message`).

### 4.3 Impacto en los puntos abiertos de `expert_database`

- **Formato real de "referencia" de conciliación:** confirmado como string numérico corto (~8-12 dígitos, ej. `"12345678"`, `"090037579602"`), generado por el banco, distinto del `endToEndId` (identificador largo interbancario de 62 caracteres usado solo para anulación). El esquema de Conciliación necesita **dos campos de correlación separados**: `referencia_corta` (para conciliar/matchear) y `end_to_end_id` (para trazabilidad/anulación), no uno solo.
- **Catálogo de medios/monedas:** el único `coinType` confirmado en el dummy es `"VES"`, con campos reservados (`cuentaDivisa`, `saldoCuentaDivisa`) que anticipan soporte de divisa extranjera — modelar `moneda` como catálogo desde ya (VES + placeholder USD), no como enum cerrado de un solo valor.
- **Catálogo de bancos:** códigos de 4 dígitos tipo `"0102"` (BDV) reutilizados en ambos servicios (`customerBankCode`, `bancoOrigen`) — crear tabla `bancos` (código, nombre, activo) en vez de validar el código inline; el error `1091`/`1092` (banco destino inactivo/no afiliado) confirma que el proveedor mantiene su propio catálogo dinámico que puede no coincidir con el nuestro.
- **Estructura real de "eventos"/operaciones:** el proveedor NO emite eventos async ni webhooks — todo es request/response síncrono. Esto significa que el evento `pago.confirmado` que el Orquestador publica a RabbitMQ (según el roadmap) es una **construcción propia** basada en la respuesta del `process/v2`, no algo que el banco entregue de forma nativa; y que el servicio de Conciliación de Conatel debe **orquestar sus propias consultas periódicas/reactivas** al `getMovement/v2` del banco (con manejo del debounce de 30s) en vez de solo escuchar pasivamente.
- **Idempotencia real del proveedor:** los códigos `1026` (Referencia/Monto duplicado) y `1094` (Operación duplicada) del C2P, más el comportamiento de debounce de 30s y el mensaje "ya fue conciliado anteriormente" de Conciliación, deben mapearse explícitamente en la tabla `idempotency_keys`/`matching_exceptions` del brief original — son señales de idempotencia del lado del proveedor, no errores de negocio a mostrar tal cual al usuario.
- **Ambigüedad de identidad del pagador:** el caso `cedulaPagador` sustituido por `"V" + RIF del comercio` en operaciones interbancarias es una regla de negocio no trivial que el esquema debe soportar — sugiere no usar `cedula_pagador` como clave natural/única para identificar al cliente en la tabla de matching; usar `telefono_pagador` + `referencia` como clave de correlación primaria, con `cedula_pagador` como dato informativo condicionalmente confiable (flag `cedula_confiable: bool` derivado de si la operación es BDV↔BDV o interbancaria).
- **Manejo de errores no estructurado:** dado que el proveedor devuelve HTTP 200 con toda la semántica de error embebida en `code`+`message` en texto libre (incluyendo no distinguir error de autenticación de "no encontrado"), Conciliación necesita una tabla de **staging/log crudo de respuestas del proveedor** (payload completo + timestamp) separada de la tabla de resultado interpretado, para poder re-parsear mensajes retroactivamente si cambia la redacción del proveedor (ya ocurrió: la v6 del control de versiones dice "Ajuste de mensaje para pagos conciliados anteriormente" — el texto del mensaje cambió entre versiones del proveedor, lo cual rompería un parser basado en texto exacto si no se versiona).
