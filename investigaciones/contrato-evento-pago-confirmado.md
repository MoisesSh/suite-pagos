# Contrato de evento — `pago.confirmado`

> Publicado por: **Orquestador de Pagos** (`suit-orquestador`, `apps/autorizacion`), vía
> `EventoOutbox` (outbox pattern, `db-plan-pagos.md` sección 2.3) — nunca directo a
> RabbitMQ desde la transacción de negocio.
> Consumido por: **Conciliación** (`suit-conciliacion`, `apps/conciliacion`), vía
> `EventoPagoRecibido` + `IngestaService.registrar_evento()` (dedup por `event_id`).
> Estado: **CERRADO — v1**, aprobado 2026-08-27. Cambios futuros requieren un
> `schema_version` nuevo, nunca modificar los campos de la v1 en el lugar (gobernanza:
> dueño único de `pago.confirmado` es el Orquestador — `research-brief-pagos.md`).

## Envolvente (columnas de `EventoOutbox`, no van dentro de `payload`)

| Campo | Origen | Nota |
|---|---|---|
| `event_id` | `EventoOutbox.id` (UUIDv7) | Conciliación lo usa como `EventoPagoRecibido.event_id` para deduplicar — entrega *at-least-once*, nunca *exactly-once*. |
| `event_type` | `"pago.confirmado"` | Constante. |
| `schema_version` | `1` | Ver política de versionado arriba. |
| `aggregate_id` | `EventoOutbox.pago_id` (FK) | El `pago_id` también viaja duplicado dentro de `payload` para no obligar a Conciliación a leer la FK del outbox. |

Se publica en la **misma transacción** que la creación de `Captura` (dentro de
`FlujoCobroC2PService.ejecutar_cobro`), en el instante exacto en que `IntencionPago`
pasa a `capturado` — nunca antes, nunca para otro estado.

## `payload` (JSON)

```json
{
  "pago_id": "0198f2b1-...-uuid",
  "aplicacion_id": "0198f1a0-...-uuid",
  "proveedor_codigo": "BDV",
  "medio_pago_codigo": "C2P",
  "monto": "1000.60",
  "moneda_codigo": "VES",
  "cedula_pagador": "V12345678",
  "telefono_pagador": "04125692243",
  "banco_pagador_codigo": "0102",
  "telefono_comercio": "04140282647",
  "referencia_corta": "090037579602",
  "identificador_interbancario": "0102010298400079090940416589264220251114162931090620472770",
  "codigo_respuesta_proveedor": "1000",
  "fecha_pago": "2025-11-14",
  "capturado_at": "2026-08-27T18:42:10.123456+00:00",
  "estado": "capturado",
  "routing_flag": "legacy",
  "payload_crudo_captura": { "...respuesta cruda completa de process/v2..." }
}
```

## Descripción de campos

| Campo | Tipo | Descripción |
|---|---|---|
| `pago_id` | string (UUID) | `IntencionPago.id`. Clave de correlación primaria del lado del Orquestador. |
| `aplicacion_id` | string (UUID) | `AplicacionRegistrada.id` — app consumidora dueña del pago. |
| `proveedor_codigo` | string | Código de `ProveedorPago` (hoy solo `"BDV"`). |
| `medio_pago_codigo` | string | Código de `MedioPago` (hoy solo `"C2P"`). |
| `monto` | string decimal | **Nunca float** — mismo criterio que el resto del sistema (`research-manejo-dinero-bd.md`). |
| `moneda_codigo` | string | Código de `Moneda` (`"VES"` hoy, `"USD"` reservado). |
| `cedula_pagador` | string | Formato `"V" + número`. En operaciones interbancarias puede no ser la identidad real del pagador (ver `identificador_interbancario`/nota de Conciliación) — Conciliación ya encapsula esa regla en `domain/bdv.py`. |
| `telefono_pagador` | string | Formato local venezolano (`04XXXXXXXXX`). Clave de correlación secundaria, confiable incluso cuando `cedula_pagador` no lo es. |
| `banco_pagador_codigo` | string | Código SUDEBAN/BCV de 4 dígitos del banco del pagador (`customerBankCode` del C2P) — es el `bancoOrigen` que Conciliación necesita para su propio `POST /getMovement/v2`, y el valor que determina BDV↔BDV vs. interbancario (`domain/bdv.py::es_operacion_intrabanco_bdv`). |
| `telefono_comercio` | string | `telefonoDestino` que exige `getMovement/v2`. Viaja en el evento en vez de vivir duplicado como config en dos servicios. |
| `referencia_corta` | string | Clave de matching primaria contra `getMovement/v2` (`referencia` de BDV, ~8-12 dígitos). |
| `identificador_interbancario` | string | `endToEndId` (62 caracteres) — trazabilidad/anulación, **no** intercambiable con `referencia_corta`. |
| `codigo_respuesta_proveedor` | string | Código de éxito de BDV para esta captura (siempre `"1000"` en este evento, ya que solo se publica en captura exitosa). |
| `fecha_pago` | string (`AAAA-MM-DD`) | Fecha que reporta el banco (`data.date` de `process/v2`) — se manda tal cual a `getMovement/v2` como `fechaPago`. |
| `capturado_at` | string (ISO 8601, con tz) | Timestamp real del Orquestador (`Captura.created_at`) — distinto de `fecha_pago`, que es la fecha que reporta el banco. |
| `estado` | string | `IntencionPago.EstadoPago` en el momento de publicar — siempre `"capturado"` para este evento. |
| `routing_flag` | string | `"legacy"` / `"canario"` — bucket del strangler fig, para auditar paridad si hace falta (T4). |
| `payload_crudo_captura` | object | Respuesta cruda completa de `process/v2`, igual que `Captura.payload_crudo` — permite reprocesar si BDV cambia el wording de algo (ya pasó una vez según el brief). |

## Uso esperado del lado de Conciliación

Mapeo directo a la firma ya escrita en `apps/conciliacion/application/services/matching.py`:

```python
MatchingService.procesar_respuesta_bdv(
    evento=evento_pago_recibido,
    banco=Banco.objects.get(codigo=payload['banco_pagador_codigo']),
    referencia_corta=payload['referencia_corta'],
    telefono_pagador=payload['telefono_pagador'],
    cedula_pagador=payload['cedula_pagador'],
    importe_esperado=Decimal(payload['monto']),
    fecha_pago=payload['fecha_pago'],
    respuesta_cruda=respuesta_de_getMovement_v2,  # la respuesta de Conciliación consultando al banco, no payload_crudo_captura
)
```

`payload['telefono_comercio']` y `payload['banco_pagador_codigo']` son los datos que
Conciliación necesita para armar su propia consulta `POST /getMovement/v2` antes de
poder llamar a `MatchingService`.
