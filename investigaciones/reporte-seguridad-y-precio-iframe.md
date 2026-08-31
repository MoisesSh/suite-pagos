# Reporte consolidado — Auditoría de seguridad y patrón de precio en iframe

Suite Centralizada de Pagos (suit-orquestador, suit-conciliacion, suit-panel, suit-portal, deploy/).
Investigación de solo lectura, sin cambios de código. Fecha: 2026-08-29.

---

# TAREA 1 — Auditoría de seguridad

**Alcance:** suit-orquestador, suit-conciliacion, suit-panel, suit-portal, deploy/.

## CRÍTICA

### 1. `SECRET_KEY` de Django hardcodeada y commiteada — firma el `checkout_token` que autoriza cobros C2P
**`suit-orquestador/config/settings.py:28`**
```python
SECRET_KEY = 'django-insecure-5s!fewuq53zd@%*swfiyi7z9-iu##)yqrbkhvw$a(7zkx2ajnw'
```
No se lee de entorno (a diferencia de `suit-conciliacion`, que sí usa `env('SECRET_KEY', default=...)`). Está en git desde el commit inicial.

`checkout_token.py:30,44` firma/verifica con `django.core.signing.dumps/loads` **sin pasar `key=`**, por lo que usa `settings.SECRET_KEY` por defecto — la misma clave que firma sesiones/CSRF de Django. Cualquiera con acceso al repo (que ya expone la clave en texto plano) puede **forjar un `checkout_token` válido para cualquier `aplicacion_id`, `proveedor_codigo`, `monto` y `moneda`**, saltándose la validación de dominio→aplicación→proveedor de `ValidarAccesoView`, y controlar el monto real que se cobra vía BDV. Esto rompe la premisa de diseño del propio módulo (el OTP autentica al pagador, pero el monto/aplicación depende de la integridad del token).

**Fix:** mover `SECRET_KEY` a variable de entorno obligatoria (fail-fast si falta), rotarla ya (debe considerarse comprometida por estar en git), y usar una clave de firma independiente para `checkout_token` (parámetro `key=` propio, rotable sin invalidar sesiones).

### 2. `DEBUG = True` hardcodeado en suit-orquestador
**`suit-orquestador/config/settings.py:31`**, sin override por entorno desde el primer commit. Cualquier excepción no controlada en el flujo de cobro expone traceback completo (SQL, settings, rutas de archivo, variables de entorno). Además habilita `/api/schema/` y `/api/docs/` sin protección adicional.

**Fix:** `DEBUG = env.bool('DEBUG', default=False)` con default `False`.

### 3. Datos sensibles (cédula, teléfono, payload crudo de BDV) persistidos en texto plano, sin cifrado en reposo
- `suit-orquestador/apps/autorizacion/domain/models.py:265` (`OperacionPagoBase.payload_crudo`, heredado por `Autorizacion:272`, `Captura:291`, `Anulacion:307`, `Reembolso:323`) — `JSONField` con la respuesta cruda íntegra de BDV (confirmado en `bdv_c2p.py:72`, incluye `customerDocumentId`, `customerNumberInstrument`).
- `suit-orquestador/.../models.py:349` (`EventoOutbox.payload`) — incluye en claro `cedula_pagador`, `telefono_pagador`, `telefono_comercio` y `payload_crudo_captura` anidado (construido en `flujo_cobro_c2p.py:69-90`), publicado tal cual a RabbitMQ.
- `suit-conciliacion/apps/conciliacion/domain/models.py:82-93` (`cedula_pagador`, `telefono_pagador`, `payload_crudo`) y `:50` (`EventoPagoRecibido.payload`) — mismos datos en claro.

No hay `django-cryptography`, `django-fernet-fields`, `pgcrypto` ni ningún mecanismo de cifrado de campo en `requirements.txt` ni en el código. Cualquier acceso de lectura a la BD (dump, backup filtrado, o el propio Django admin) expone cédulas, teléfonos y respuestas completas del banco en claro.

**Agravante directo:** el Django admin no enmascara estos campos — `suit-conciliacion/apps/conciliacion/admin.py:35-39` incluso hace `telefono_pagador` buscable (`search_fields`), y `suit-orquestador/apps/autorizacion/admin.py:146-153` no excluye `payload_crudo` del detalle.

**Fix:** cifrado de campo a nivel de aplicación (Fernet con rotación de clave) para `payload_crudo`, `cedula_pagador`, `telefono_pagador` e `IdempotencyKey.response_snapshot`; `exclude`/`readonly_fields` truncados en los `ModelAdmin`.

## ALTA

### 4. Replay del `checkout_token` dentro de la ventana de 900s — no hay marca de "consumido"
`CheckoutTokenService.verificar()` (`checkout_token.py:42-46`) es el único punto de validación de firma+TTL, invocado consistentemente por `SolicitarOtpView`, `EjecutarCobroView` y `FormularioCobroView` — esto está bien centralizado. Pero **no existe ningún campo que marque el token como usado**. La deduplicación real es `IdempotencyKey`, cuyo `key` es un **UUID generado por el cliente**, no derivado del `checkout_token`. Por tanto, un `checkout_token` válido dentro de sus 15 minutos puede reutilizarse para iniciar múltiples `IntencionPago` distintos (cada llamada con `idempotency_key` nueva crea una nueva intención). El único freno práctico es el throttle `cobro_c2p` (30/hora por IP) y que cada intento requiere un OTP válido del banco.

**Fix:** derivar/atar un identificador de "uso único" al propio `checkout_token` (p. ej. un `jti` marcado en BD atómicamente al ejecutar el cobro), no depender solo del UUID que aporta el cliente.

### 5. Refresh token de JWT expuesto en el body JSON además de la cookie HttpOnly
`suit-conciliacion/apps/users/api/views.py:41-50,68-71` — el objetivo de `JWT_REFRESH_COOKIE` (HttpOnly) es evitar robo vía XSS, pero el mismo `refresh` se devuelve también en el body JSON en login y en cada rotación. Hoy lo consume el server de Next.js (no JS de navegador), pero anula la garantía de HttpOnly a nivel de contrato de API para cualquier consumidor futuro.

**Fix:** no incluir `refresh` en el body cuando ya se setea como cookie.

### 6. `CORS_ALLOW_ALL_ORIGINS` con fallback ligado a `DEBUG` (default inseguro) + `CORS_ALLOW_CREDENTIALS=True`
`suit-conciliacion/config/settings.py:20,24-27`: `DEBUG` tiene `default=True`, y si `DEBUG=True` y `CORS_ALLOWED_ORIGINS` está vacío, se activa `CORS_ALLOW_ALL_ORIGINS=True` junto con `CORS_ALLOW_CREDENTIALS=True`. Esto refleja `Access-Control-Allow-Origin` al origen solicitante, ampliando el vector de robo de `access_token` si existe XSS en cualquier dominio. Mitigado parcialmente porque la cookie de refresh usa `SameSite=Strict`, pero es un "fail open" doble (DEBUG default inseguro → CORS abierto default inseguro).

**Fix:** invertir default de `DEBUG` a `False`; exigir `CORS_ALLOWED_ORIGINS` no vacío de forma independiente de `DEBUG`.

### 7. RabbitMQ/Flower con credenciales por defecto `guest`/`guest` y puertos publicados al host
`deploy/docker-compose.yml:52-53,57-59,128-139` — fallback `${RABBITMQ_USER:-guest}`/`${RABBITMQ_PASSWORD:-guest}`, puertos `15672`/`5672`/`5555` publicados, `FLOWER_UNAUTHENTICATED_API: "true"`. Si el operador no define las variables en `.env`, el broker queda con credenciales conocidas y alcanzable desde fuera del host. No hay compose de producción separado que fuerce esto.

**Fix:** eliminar el fallback `:-guest` (obligar la variable), no publicar esos puertos fuera de la red interna en el compose usado para producción.

## MEDIA

### 8. `DEBUG` de suit-conciliacion con default `True`
`suit-conciliacion/config/settings.py:20` — es override-able por entorno (a diferencia del punto 2), pero el default inseguro es la causa raíz del punto 6.

### 9. Tokens DRF `authtoken` del admin CRUD sin expiración ni rotación
`suit-orquestador/apps/autorizacion/api/admin_views.py:25-26,64-65`, `settings.py:51-57` — `rest_framework.authtoken.Token` no expira nunca; revocación es manual desde `/admin/`. Severidad media porque los endpoints ya están correctamente protegidos con `IsAdminUser`+`TokenAuthentication`, y no se encontró camino de auto-escalación de privilegios en ningún servicio.

**Fix:** expiración por antigüedad o migrar a JWT de corta duración, como ya hace suit-conciliacion.

### 10. `deploy/rabbitmq.conf` — `deprecated_features.permit.transient_nonexcl_queues`/`global_qos`: evaluado, **no es vulnerabilidad**
Son banderas de compatibilidad AMQP 0-9-1 para Kombu/Celery/Flower; siguen requiriendo la misma conexión autenticada que cualquier otra operación del broker. No abren superficie nueva a clientes no autenticados. El riesgo real de este componente es el punto 7 (credenciales por defecto), no este `.conf`.

### 11. Inconsistencia SameSite entre cookie del backend (`Strict`) y la que realmente fija Next.js (`Lax`)
`suit-conciliacion/config/settings.py:191` vs `suit-panel/src/auth.config.ts:42`, `auth.ts:27` — el usuario final queda bajo `Lax` porque Next.js re-setea la cookie server-side; la política `Strict` del backend solo aplica a consumidores directos. No crítico, pero es una discrepancia de diseño no documentada que conviene alinear o al menos documentar explícitamente.

### 12. `BDV_C2P_BASE_URL` con default apuntando al ambiente QA real del banco
`suit-orquestador/config/settings.py:173-174` — si falta la env var, cae a `https://bdvconciliacionqa.banvenez.com:444` con `API_KEY=''`. Impacto bajo (rechazo por key vacía) pero inconsistente con el criterio más conservador (`default=None`) que sí aplica suit-conciliacion.

## BAJA / COSMÉTICA

- **`middleware.ts` ausente en suit-panel** — la protección de rutas depende solo del layout `(app)` (`auth()` + `redirect`), funciona hoy pero no es defensa en profundidad ante nuevas rutas fuera de ese layout group.
- **Frontend no oculta UI según `isStaff`/`isSuperuser`** — el backend ya rechaza con 403 correctamente; es solo UX (controles que fallarían en vez de estar ocultos).
- **`X-Frame-Options: SAMEORIGIN` como fallback legacy** en `FormularioCobroView` — deliberado, subordinado al CSP `frame-ancestors`, correcto.

## Verificado explícitamente — SIN hallazgo (no re-auditar)

- **CSP `frame-ancestors` dinámico** (`suit-orquestador/apps/autorizacion/api/formulario_views.py:19-58`): comparación de **igualdad exacta** contra whitelist en BD (`DominioPermitido`), no `endswith()`/regex con wildcard. Un origen tipo `evil-conatel.gob.ve` es rechazado (confirmado por test `test_origin_no_registrado_responde_403`). No hay bypass.
- **Logging de datos sensibles**: revisado exhaustivamente en ambos backends — ningún `logger.*`/`print()` expone cédula/teléfono/payload de BDV. El problema está en persistencia (punto 3), no en logs.
- **SQL injection / SSRF / deserialización insegura / mass assignment**: no se encontró `.raw()`/`.extra()` con interpolación insegura, `pickle.loads`, `yaml.load` inseguro, `eval`/`exec`, ni serializers con `fields='__all__'` peligroso. La URL de BDV se arma solo desde config de servidor, nunca desde input de request.
- **Escalación de privilegios / mass assignment de `is_staff`**: no existe endpoint de registro/perfil que acepte esos campos desde el cliente en ningún servicio.
- **`.env` con secretos reales**: no están commiteados en git (verificado con `git ls-files`); solo placeholders en `.env.example`.
- **CORS en suit-orquestador**: no existe (`corsheaders` ni siquiera instalado) — correcto, dado que ese servicio no usa cookies de sesión de navegador.

## Prioridad de remediación

1. Puntos 1 y 2 (secretos/DEBUG hardcodeados) son triviales de arreglar y deben resolverse antes que cualquier otra cosa, porque comprometen todo lo demás (firma de tokens, exposición de tracebacks).
2. Luego el punto 3 (cifrado de datos sensibles) y el punto 4 (replay de checkout_token), por impacto directo en cobros reales y cumplimiento normativo.
3. Después los puntos 5, 6 y 7 (ALTA).
4. Los puntos 8-12 (MEDIA) y los de BAJA/COSMÉTICA pueden agendarse sin urgencia.

---

# TAREA 2 — Patrón de inyección de monto real en el iframe

## Lo que confirma el código actual

**1. `ValidarAccesoRequestSerializer`** — `suit-orquestador/apps/autorizacion/api/serializers.py:4-12`
```python
dominio = serializers.CharField(max_length=255)
proveedor = serializers.CharField(max_length=30, ...)
monto = serializers.DecimalField(max_digits=19, decimal_places=2)
moneda = serializers.CharField(max_length=3)
concepto = serializers.CharField(max_length=100, required=False, default='Pago')
```
- `monto`: **sin `min_value`**. Acepta negativos y cero (DRF `DecimalField` no valida signo por defecto). Sin límite máximo por transacción.
- `moneda`: **`CharField` libre**, no `ChoiceField` ni validación contra el catálogo `Moneda` (existe el modelo `Moneda` en `apps/autorizacion/domain/models.py:34`, pero `validar-acceso` no lo consulta — solo se usa la FK `Moneda` más adelante en `IntencionPago`, ya dentro de `FlujoCobroC2PService.iniciar`).
- `concepto`: libre hasta 100 chars, sin sanitización visible en este archivo.

**2. Generación/firma del `checkout_token`** — `checkout_token.py:28-46`
- Usa `django.core.signing.dumps/loads` (firma HMAC con `SECRET_KEY`, no cifrado — el payload es legible, solo no falsificable) con `salt='autorizacion.checkout_token'`.
- Payload firmado: `aplicacion_id`, `proveedor_codigo`, `monto`, `moneda`, `concepto` (línea 30-38).
- TTL: `settings.CHECKOUT_TOKEN_MAX_AGE_SEGUNDOS` (`config/settings.py:187`, default **900s = 15 min**), verificado vía `max_age=` en `signing.loads` (línea 44).

**3. Mecanismo de un solo uso — NO EXISTE para el `checkout_token`.**
- `resolver_checkout_token` (`checkout_token_resolver.py:12-36`) solo valida firma + vigencia + que el proveedor coincida + re-valida app/proveedor. No marca el token como consumido en ningún lado, no hay tabla ni caché de tokens ya usados.
- Lo único idempotente en el flujo es `IdempotencyKey` (`application/services/idempotencia.py`), pero esa key es **generada por el cliente en `/cobro/`** (`EjecutarCobroRequestSerializer.idempotency_key`, `serializers.py:38`), no está atada al `checkout_token`. Consecuencia concreta: dentro de los 15 minutos de vigencia, el mismo `checkout_token` puede usarse para invocar `/cobro/otp/` y `/cobro/` repetidas veces con `idempotency_key` distintas cada vez — nada en el servidor lo impide (`views.py:101-181` no verifica "token ya consumido"). Coincide con el hallazgo de seguridad #4.

**4. `GUIA-INTEGRACION-IFRAME.md:117-122`** — confirma explícitamente que el webhook server-to-server **no existe hoy**, es "no existe todavía, evaluar si hace falta según el volumen real". La única confirmación es el `postMessage` al navegador (línea 96-115), y el propio documento admite el caso de falla: si el Origin/Referer no se pudo determinar, "simplemente no manda nada" y la app consumidora queda sin ninguna señal — solo sugiere "un mecanismo alternativo... o un webhook".

**5. Monto hardcodeado** — `suit-portal/src/modules/prueba-iframe/application/use-cases/generar-checkout-session.ts:9-17`, campo `monto: "1000.60"` dentro del objeto `CHECKOUT_DE_PRUEBA` (comentario en línea 6-8 aclara que es intencional, solo para la demo del Portal).

## Comparación con la industria (documentación oficial de gateways reales)

| Gateway | Monto/moneda server-to-server | Token opaco corta duración | Un solo uso además de TTL | Webhook server-to-server |
|---|---|---|---|---|
| **Stripe Checkout** | Sí, `checkout.sessions.create` se llama desde el servidor del comercio (nunca desde el navegador) | Sí, `expires_at` configurable 30 min–24h (default 24h); tras completarse el `status` pasa a `complete`/`expired` | Sí implícito: una sesión completada no puede reutilizarse (`status` cambia y ya no acepta pago); además Stripe recomienda `idempotency key` propia en cada operación de creación | **Sí, obligatorio en la práctica** — `checkout.session.completed` vía webhook es la fuente de verdad recomendada; Stripe advierte explícitamente que el navegador del cliente puede no volver a la landing page y por eso el fulfillment nunca debe depender solo de la redirección/postMessage del cliente |
| **Mercado Pago (Checkout Pro)** | Sí, la `Preference` se crea server-side con `notification_url` | El `init_point`/preference_id es de uso puntual para esa transacción | El estado del pago se resuelve consultando la API por `payment_id`, no reusable | **Sí** — Webhooks (reemplazo del IPN legado) con validación de firma `x-signature` (HMAC), retries hasta 4 días si no se responde 200/201 |
| **PayPal Orders API v2** | Sí, `POST /v2/checkout/orders` es exclusivamente server-side (documentado como "no llamar desde browser") | El `order_id` devuelto se usa para aprobar/capturar una única vez | La orden pasa por estados (`CREATED`→`APPROVED`→`COMPLETED`), no reutilizable tras capturar | **Sí** — Webhooks (`PAYMENT.CAPTURE.COMPLETED`, etc.) como confirmación autoritativa, independiente del retorno del navegador |
| **Culqi** | Sí, Órdenes de Pago se crean server-side | El token/orden se referencia una vez | Documentación indica reconciliación vía evento `order.status.changed` | **Sí** — Webhooks configurables por tipo de evento (cargos, órdenes, suscripciones, etc.) |
| **dLocal** | Sí, Smart Fields tokeniza en el navegador pero el pago (monto/moneda) se crea vía Payments API server-side | El token de tarjeta es de un solo uso para tokenizar, no para el monto | — | **Sí** — notificaciones server-to-server a `notification_url` con reintentos programados (hasta ~4 días) hasta recibir 2xx |

**Conclusión de la comparación:** en los cinco gateways, sin excepción, (a) el monto/moneda se fija siempre server-to-server, nunca editable desde el navegador — igual que el Orquestador; (b) el token/sesión que llega al navegador es opaco y de corta duración — igual que el Orquestador (15 min está incluso más ajustado que el default de Stripe de 24h); pero (c) **todos** tienen webhook/notificación server-to-server como mecanismo *primario* de confirmación (no opcional, no "a evaluar"), justamente porque el postMessage/redirect del navegador puede perderse; y (d) todos evitan reprocesar la misma sesión/orden una vez resuelta (estado que transiciona, no vuelve a `pending`).

## Respuestas concretas

### 1. ¿Es el patrón actual el estándar de la industria?

Sí, en su núcleo. El principio "el servidor del comercio declara el monto, el navegador solo recibe una referencia opaca de corta vida" es exactamente Stripe/Mercado Pago/PayPal/Culqi/dLocal. La implementación con `django.core.signing` (HMAC + TTL) es una variante razonable de lo que Stripe hace con sesiones de estado server-side y PayPal/MP con IDs de orden consultables. Donde el patrón actual se queda corto es en las dos piezas que la industria trata como no-negociables (ver punto 2).

### 2. Qué falta para producción real

- **Estado "usado una sola vez" del `checkout_token`: NO existe hoy** (confirmado arriba, `checkout_token_resolver.py` y `EjecutarCobroView` en `views.py:101-181` no marcan consumo). Recomendación concreta: agregar un registro (tabla o cache Redis con TTL=`CHECKOUT_TOKEN_MAX_AGE_SEGUNDOS`) que marque el token como consumido en el primer `EjecutarCobroView.post` que llegue a `COMPLETADO`, y rechace cualquier intento posterior con el mismo token — hoy solo el `IdempotencyKey` (client-generado) protege contra doble cobro, y un cliente que genera nuevas `idempotency_key` por cada intento puede reintentar cobros con el mismo `checkout_token` indefinidamente dentro de los 15 min.
- **Webhook server-to-server: confirmado como pendiente en la propia guía** (`GUIA-INTEGRACION-IFRAME.md:117-122`, literalmente "no existe todavía"). Todos los gateways investigados lo tratan como obligatorio, no opcional, precisamente para el caso que la guía admite como fallo: cuando Origin/Referer no se pudo determinar y el postMessage nunca llega. Sin este webhook, una app consumidora real no tiene forma confiable de saber que un pago se completó si el navegador del pagador se cierra o pierde conexión antes de recibir el postMessage — es una brecha de confiabilidad, no solo de conveniencia.

### 3. Qué le falta al endpoint `validar-acceso` / al flujo para integrarse en producción sin tocar el Orquestador

- **Validar `monto > 0`**: hoy `DecimalField` sin `min_value` acepta `0` y negativos (`serializers.py:10`). Agregar `min_value=Decimal('0.01')`.
- **Límite máximo por transacción**: no existe ningún techo hoy; agregar `max_value` (configurable por proveedor/aplicación) para evitar montos absurdos o de fraude.
- **Validar `moneda` contra el catálogo real**: hoy es `CharField` libre de 3 caracteres sin relación con el modelo `Moneda` existente (`domain/models.py:34`) ni con las monedas que el proveedor (`BDV`) realmente soporta (hoy solo VES en la práctica). Cambiar a `ChoiceField` derivado del catálogo, o validar contra `Moneda.objects.filter(activo=True)` en el serializer/servicio, para que un valor inválido falle en `validar-acceso` (400) en vez de fallar más adelante en `FlujoCobroC2PService.iniciar` con un error menos claro.
- **Documentar/exponer el límite conocido de BDV QA** (ya lo hace la guía en `GUIA-INTEGRACION-IFRAME.md:148-152`, pero solo como advertencia de ambiente QA — no aplica a producción real según el propio texto).

Con esas tres correcciones (monto>0 + límite máximo + moneda validada contra catálogo) más el estado de un solo uso del `checkout_token` y el webhook server-to-server, el endpoint quedaría alineado con el estándar que Stripe/Mercado Pago/PayPal/Culqi/dLocal exigen hoy para integraciones de producción.

## Fuentes consultadas

- [Create a Checkout Session | Stripe API Reference](https://docs.stripe.com/api/checkout/sessions/create)
- [The Checkout Sessions API | Stripe Documentation](https://docs.stripe.com/payments/checkout-sessions)
- [Fulfill orders | Stripe Documentation](https://docs.stripe.com/checkout/fulfillment)
- [Checkout Sessions | Stripe API Reference](https://docs.stripe.com/api/checkout/sessions)
- [Expire a Checkout Session | Stripe API Reference](https://docs.stripe.com/api/checkout/sessions/expire?lang=node)
- [Stripe currencies documentation](https://docs.stripe.com/currencies.md)
- [Integrate Checkout Pro and set up a predesigned experience](https://www.mercadopago.com.ar/developers/en/docs/checkout-pro/overview)
- [IPN | Mercado Pago](https://www.mercadopago.com.br/developers/en/docs/checkout-pro/additional-content/notifications/ipn)
- [How to use PayPal REST APIs | PayPal Developer](https://developer.paypal.com/api/rest/integration/orders-api)
- [Orders | PayPal Developer](https://developer.paypal.com/docs/api/orders/v2/)
- [Webhooks overview | PayPal Developer](https://developer.paypal.com/api/rest/webhooks)
- [Culqi Checkout multipago versión 4](https://docs.culqi.com/es/documentacion/checkout/v4/culqi-checkout/)
- [Webhooks | Culqi Documentación](https://docs.culqi.com/es/documentacion/pagos-online/webhooks/)
- [Receive notifications | dLocal](https://docs.dlocal.com/docs/receive-notifications)
- [Set up guide | dLocal Smart Fields](https://docs.dlocal.com/docs/set-up-smart-fields)
