# Modelo de datos — Suite Centralizada de Pagos (v1, primera pasada)

> Generado por el coordinador a partir de `suit-backend/db-plan-pagos.md`
> (autor: agente `expert_database`, worktree `db-backend`). Es un bosquejo de
> planificación, no un esquema final — quedan puntos abiertos marcados en el
> plan original (sección 5). Dos bases PostgreSQL independientes, **sin FKs
> cruzadas entre ellas** (`database-per-service`): toda relación entre
> Orquestador y Conciliación es un ID lógico que viaja en el evento RabbitMQ
> `pago.*`, nunca un JOIN.

## Diagrama — DB Orquestador (síncrono)

```mermaid
erDiagram
    MedioPago ||--o{ IntencionPago : "tipifica"
    ProveedorPago ||--o{ Autorizacion : "ejecuta"
    ProveedorPago ||--o{ Captura : "ejecuta"
    ProveedorPago ||--o{ Anulacion : "ejecuta"
    ProveedorPago ||--o{ Reembolso : "ejecuta"
    ProveedorPago ||--o{ TipoOperacionProveedor : "define"
    ProveedorPago ||--o{ CodigoRespuestaProveedor : "define"
    ProveedorTokenizacion ||--o{ TokenReferencia : "emite"
    Banco ||--o{ ProveedorPago : "opera_como"

    IntencionPago ||--o{ TransicionEstadoPago : "historial"
    IntencionPago ||--o{ Autorizacion : "autorizaciones"
    IntencionPago ||--o{ Captura : "capturas"
    IntencionPago ||--o{ Anulacion : "anulaciones"
    IntencionPago ||--o{ Reembolso : "reembolsos"
    IntencionPago ||--o| TokenReferencia : "opcional_si_tarjeta"
    IntencionPago ||--o| TasaCambioAplicada : "si_internacional"
    IntencionPago ||--o| IdempotencyKey : "protegido_por"
    IntencionPago ||--o{ EventoOutbox : "publica"

    TipoOperacionProveedor ||--o{ Autorizacion : "clasifica"
    CodigoRespuestaProveedor ||--o{ Autorizacion : "clasifica"

    IntencionPago {
        uuid id PK
        decimal monto
        text moneda "TextChoices: VES activo, USD reservado"
        uuid app_origen_id "FK logica, sin FK real (Developer Portal)"
        text estado_actual "espejo de TransicionEstadoPago"
        text routing_flag "legacy/canario, strangler fig"
    }
    TransicionEstadoPago {
        uuid id PK
        uuid pago_id FK
        text estado_anterior
        text estado_nuevo
        datetime created_at "append-only, sin updated_at"
    }
    Autorizacion {
        uuid id PK
        uuid pago_id FK
        uuid proveedor_id FK
        text referencia_corta "correlacion con Conciliacion"
        text identificador_interbancario "endToEndId, usado para anular"
        uuid tipo_operacion_id FK
        uuid codigo_respuesta_id FK
        jsonb payload_crudo
        datetime otp_solicitado_at
    }
    Captura {
        uuid id PK
        uuid pago_id FK
        uuid proveedor_id FK
        text referencia_corta
        text identificador_interbancario
    }
    Anulacion {
        uuid id PK
        uuid pago_id FK
        uuid proveedor_id FK
    }
    Reembolso {
        uuid id PK
        uuid pago_id FK
        uuid proveedor_id FK
    }
    TokenReferencia {
        uuid id PK
        uuid pago_id FK
        uuid proveedor_tokenizacion_id FK
        text token "opaco, nunca PAN/CVV"
    }
    EventoOutbox {
        uuid id PK
        uuid pago_id FK
        text event_type "pago.*"
        jsonb payload
        int schema_version
        text estado "pendiente/enviado/fallido"
        datetime sent_at
    }
    IdempotencyKey {
        uuid key PK "generado por el cliente"
        text request_hash
        jsonb response_snapshot
        datetime expires_at "ABIERTO: valor sin definir"
    }
    TasaCambioAplicada {
        uuid id PK
        uuid pago_id FK
        decimal tasa
        text fuente
        datetime rate_timestamp "congelada por transaccion"
    }
    MedioPago { uuid id PK text nombre }
    ProveedorPago { uuid id PK text nombre "primer proveedor real: BDV" }
    ProveedorTokenizacion { uuid id PK text nombre "ABIERTO: sin proveedor real aun" }
    Banco { text codigo PK "4 digitos SUDEBAN/BCV" text nombre }
    TipoOperacionProveedor { uuid id PK uuid proveedor_id FK text codigo }
    CodigoRespuestaProveedor { uuid id PK uuid proveedor_id FK text codigo text categoria }
```

## Diagrama — DB Conciliación (asíncrono, solo consume eventos)

```mermaid
erDiagram
    EventoPagoRecibido ||--o{ ConsultaConciliacionProveedor : "dispara_polling"
    EventoPagoRecibido ||--o{ Discrepancia : "puede_generar"
    EventoPagoRecibido ||--o{ TransaccionLedger : "referencia"
    Banco ||--o{ ConsultaConciliacionProveedor : "consultado_en"
    Banco ||--o{ MovimientoBancario : "origina"
    ConsultaConciliacionProveedor ||--o{ Discrepancia : "puede_generar"
    MovimientoBancario ||--o{ Discrepancia : "puede_generar"
    CuentaContable ||--o{ LineaLedger : "clasifica"
    TransaccionLedger ||--o{ LineaLedger : "lineas"

    EventoPagoRecibido {
        uuid id PK
        text event_id UK "dedup at-least-once del outbox"
        jsonb payload
        int schema_version
        datetime procesado_at "nullable hasta consumer Celery"
    }
    ConsultaConciliacionProveedor {
        uuid id PK
        uuid evento_id FK
        text banco_codigo FK
        text referencia_corta "clave primaria de matching"
        text telefono_pagador "clave secundaria confiable"
        text cedula_pagador "informativo, condicional"
        bool cedula_confiable "derivado: BDV-BDV vs interbancario"
        decimal importe_esperado
        text codigo_respuesta_raw "texto crudo, cambia entre versiones API"
        text mensaje_respuesta_raw
        text resultado_interpretado "conciliado/no_encontrado/monto_no_coincide/..."
        jsonb payload_crudo
    }
    MovimientoBancario {
        uuid id PK
        text banco_codigo FK
        date fecha
        decimal monto
        text estado_conciliacion "generico, para banco futuro con extracto batch"
    }
    Discrepancia {
        uuid id PK
        uuid movimiento_id FK "nullable"
        uuid consulta_id FK "nullable"
        uuid evento_id FK "nullable"
        text severidad
        text estado_resolucion
        uuid resuelto_por FK "SET_NULL"
    }
    TransaccionLedger {
        uuid id PK
        uuid referencia_evento FK
        datetime created_at
    }
    LineaLedger {
        uuid id PK
        uuid transaccion_id FK
        uuid cuenta_id FK
        text tipo "debito/credito"
        decimal monto "siempre positivo, signo lo da tipo"
    }
    CuentaContable { uuid id PK text nombre }
    Banco { text codigo PK "copia local, sin FK cruzada con Orquestador" }
    ReporteERP { uuid id PK date fecha text referencia_externa jsonb payload }
```

## Flujo entre servicios (sin FK, solo eventos)

```mermaid
flowchart LR
    subgraph Orquestador["DB Orquestador (Postgres)"]
        IP[IntencionPago] --> EO[EventoOutbox]
    end
    EO -- "misma transaccion Postgres" --> Relay["Relay/poller\n(ABIERTO: poller propio vs CDC)"]
    Relay -- "publica, at-least-once" --> MQ[["RabbitMQ\ntopic pago.*"]]
    MQ -- "consume, Celery worker" --> EPR[EventoPagoRecibido]
    subgraph Conciliacion["DB Conciliación (Postgres)"]
        EPR --> CCP["ConsultaConciliacionProveedor\n(polling activo a getMovement/v2)"]
        CCP --> DISC[Discrepancia]
        EPR --> LEDGER[TransaccionLedger + LineaLedger]
    end
```

## Puntos abiertos que afectan directamente este modelo

Ver detalle completo y razonamiento en `suit-backend/db-plan-pagos.md` §5.
Resumen de estado:

| # | Punto | Estado |
|---|---|---|
| 1 | Proveedor real de tokenización de tarjeta | `ABIERTO` |
| 2 | Mecanismo del relay outbox → RabbitMQ (poller vs CDC) | `ABIERTO` |
| 3 | Catálogo definitivo de monedas | `PARCIAL` — VES activo, USD reservado |
| 4 | Dónde vive `AppConsumidora`/API keys | `ABIERTO` |
| 5 | Mecanismo de balance-cero del ledger (trigger vs. servicio) | `ABIERTO` |
| 6 | Ventana de expiración de `IdempotencyKey.expires_at` | `ABIERTO` |
| 7 | Gobernanza del schema de eventos versionado | `ABIERTO` |
| 8 | Semántica de reintentos multi-adquirente | `PARCIAL` — despriorizado hasta T4 |

## Fuentes

- `conatel-suite-pagos-roadmap.html` (roadmap del proyecto)
- `research-brief-pagos.md` (mejores prácticas + hallazgos de 2 PDFs reales de BDV: API C2P Cuentas Múltiples, API Conciliación)
- `suit-backend/db-plan-pagos.md` (plan de modelado de `expert_database`)
