# Plan de Mejoras — Suite Centralizada de Pagos

> Registro consolidado de todos los "bloques de próximo paso" que arman los agentes
> de código (`suit-orquestador`, `suit-conciliacion`, `suit-panel`, `suit-portal`)
> antes de recibir la orden de ejecución del coordinador. Se agrega un bloque nuevo
> cada vez que un agente propone el siguiente incremento de trabajo.

Última actualización: 2026-08-30

---

## Bloque #19 — Fix: registro/listado de aplicaciones no funcionaba en Docker (ECONNREFUSED) ✅ COMPLETADO (coordinador)

**Reportado por:** usuario (probando el panel real, "no registra las apps autorizadas").

**Bug:** `deploy/docker-compose.yml`, servicio `suit-panel` — el bloque `environment:` sobreescribía `CONCILIACION_API_URL` con el hostname interno de Docker (`http://suit-conciliacion:8000`) pero **no hacía lo mismo con `ORQUESTADOR_API_URL`**, así que ese valor se colaba desde `suit-panel/.env` (`http://localhost:8001`, correcto para desarrollo local fuera de Docker). Dentro de la red de compose, `localhost` es el propio contenedor de `suit-panel`, no el Orquestador — cualquier fetch server-side a `ORQUESTADOR_API_URL` fallaba con `ECONNREFUSED` (confirmado en `docker logs suit-pagos-suit-panel-1`). Afectaba tanto el listado como el alta/edición de `AplicacionRegistrada` (todo el módulo `aplicaciones/` de `suit-panel` depende de esta URL).

**Fix:** agregado `ORQUESTADOR_API_URL: http://suit-orquestador:8000` al `environment:` del servicio `suit-panel`, mismo patrón ya usado para `CONCILIACION_API_URL`. Recreado el contenedor (sin rebuild, solo variable de entorno) y verificado en vivo: `GET /api/autorizacion/admin/aplicaciones/` desde dentro del contenedor de `suit-panel` devuelve las 3 aplicaciones reales ya registradas.

**Lección:** cuando un servicio del compose necesita hablar con más de un backend interno, cada URL debe overridearse explícitamente — el `env_file` de desarrollo local nunca debe asumirse válido dentro de la red de Docker.

---

## Bloque #18 — Fix: 2 bugs reales de infraestructura encontrados al probar el Developer Portal ✅ COMPLETADO (coordinador)

**Reportado por:** usuario (probando el Developer Portal real, iframe de Swagger roto y botón de documentación muerto).

**Bug 1 — `NEXT_PUBLIC_*` de `suit-portal` horneadas con el valor por defecto equivocado.** Next.js inlinea las variables `NEXT_PUBLIC_*` en el bundle del cliente durante `npm run build`, no en runtime — pero `deploy/Dockerfile.frontend` copiaba el código y corría el build sin pasar esas variables como build arg, y el `.env` real está excluido a propósito del build context (`.dockerignore` raíz). Resultado: el bundle quedó con el default hardcodeado en el código (`http://localhost:8000/api/docs/`), no el real (`:8002`) — el iframe y el link de "Abrir en una pestaña nueva" apuntaban a un puerto sin nada escuchando. Fix: `NEXT_PUBLIC_CONCILIACION_DOCS_URL`/`NEXT_PUBLIC_ORQUESTADOR_PUBLIC_URL` agregadas como `ARG`+`ENV` en el Dockerfile antes del build, y como `build.args` en el servicio `suit-portal` de `docker-compose.yml`. Verificado: el bundle reconstruido ya tiene `localhost:8002` horneado.

**Bug 2 — Docker Compose interpola `$VAR` dentro de los valores de `env_file`, corrompiendo secretos generados con `$`.** Los `SECRET_KEY` recién rotados de `suit-orquestador` y `suit-conciliacion` (Bloques #15/#16) contenían el carácter `$` seguido de letras (ej. `...387ibp$fioe+tp6x4u...`) — Compose lo interpretó como una referencia a una variable de entorno inexistente y la reemplazó silenciosamente por string vacío, sin error visible más que un warning fácil de pasar por alto (`The "fioe" variable is not set`). El `SECRET_KEY` real corriendo en Docker no coincidía con el `.env` en disco. Fix: ambas claves regeneradas sin `$`. **Regla nueva para todos los agentes:** ningún secreto generado para un `.env` debe contener `$` — usar un alfabeto sin ese carácter.

**Contenedor huérfano de nuevo** (mismo patrón del Bloque #11): al recrear `suit-orquestador` tras el build de `suit-portal`, quedó momentáneamente con `CMD [python3]` en vez del entrypoint real — resuelto con rebuild `--no-cache` + recreate explícito, mismo fix que la vez anterior.

---

## Bloque #15 — Remediación de seguridad, prioridad CRÍTICA (suit-orquestador) 🔄 PROPUESTO

**Origen:** auditoría de seguridad del agente `research` (`investigaciones/reporte-seguridad-y-precio-iframe.md`), a pedido del usuario, en el contexto de que este proyecto es una pasarela de pagos real en producción para instituciones del estado.

**Alcance — asignado a `suit-backend`:**
1. **`SECRET_KEY` hardcodeada y commiteada** (`config/settings.py:28`) — la misma clave firma el `checkout_token`. Cualquiera con el repo puede forjar un token válido con cualquier monto. Fix: leer de env obligatoria (fail-fast si falta), rotar la clave ya (debe tratarse como comprometida), y usar una clave de firma **independiente** para `checkout_token` (parámetro `key=` propio en `django.core.signing`, no compartir con `SECRET_KEY` de sesiones/CSRF).
2. **`DEBUG=True` hardcodeado** (`config/settings.py:31`) — cambiar a `env.bool('DEBUG', default=False)`.
3. **`checkout_token` sin marca de "consumido"** — un token válido se puede reutilizar dentro de los 15 min para reintentar cobros indefinidamente (el `IdempotencyKey` no lo cubre porque el cliente genera un UUID nuevo cada vez). Fix: registrar el token como consumido atómicamente en el primer `EjecutarCobroView.post` que llegue a `COMPLETADO`, rechazar cualquier uso posterior del mismo token.
4. **Validación de `monto`/`moneda` en `ValidarAccesoRequestSerializer`**: agregar `min_value=Decimal('0.01')` y un `max_value` configurable (evitar monto negativo/cero y sin techo); validar `moneda` contra el catálogo real `Moneda.objects.filter(activo=True)` en vez de aceptar cualquier string de 3 caracteres.
5. **Cifrado de campos sensibles en reposo**: `payload_crudo` (en `Autorizacion`/`Captura`/`Anulacion`/`Reembolso`), `EventoOutbox.payload` (contiene `cedula_pagador`/`telefono_pagador` en claro). Evaluar Fernet con rotación de clave a nivel de campo. Además, en el admin: excluir/truncar estos campos del detalle (`admin.py:146-153` no los excluye hoy).
6. **`BDV_C2P_BASE_URL` con default apuntando al QA real del banco** (`settings.py:173-174`) — cambiar a `default=None` (mismo criterio que ya usa suit-conciliacion).

**No incluido en este bloque (a evaluar aparte):** webhook server-to-server (ver Bloque #17).

---

## Bloque #16 — Remediación de seguridad, prioridad CRÍTICA/ALTA (suit-conciliacion) 🔄 PROPUESTO

**Origen:** mismo reporte de auditoría.

**Alcance — asignado a `suit-conciliacion`:**
1. **`DEBUG` con default `True`** (`config/settings.py:20`) — cambiar default a `False`. Es la causa raíz de los puntos 2 y 3.
2. **`CORS_ALLOW_ALL_ORIGINS` fail-open** (`settings.py:20,24-27`) — hoy se activa automáticamente si `DEBUG=True` y `CORS_ALLOWED_ORIGINS` vacío, junto con `CORS_ALLOW_CREDENTIALS=True`. Exigir `CORS_ALLOWED_ORIGINS` no vacío de forma independiente del valor de `DEBUG`.
3. **Refresh token JWT expuesto también en el body JSON** (`apps/users/api/views.py:41-50,68-71`), además de la cookie HttpOnly — anula la protección HttpOnly a nivel de contrato. Fix: no incluir `refresh` en el body cuando ya se setea como cookie (confirmar primero con `suit-panel` que no rompe su flujo actual, que sí lo consume del body — ver nota de coordinación abajo).
4. **Cifrado de campos sensibles**: mismos campos que en suit-orquestador (`cedula_pagador`, `telefono_pagador`, `payload_crudo`), en `apps/conciliacion/domain/models.py:82-93,50`. Admin: `admin.py:35-39` no debería tener `telefono_pagador` en `search_fields`.
5. **Catálogo `Banco` vacío en Docker** (hallazgo de `suit-backend`, no del research) — poblar seed con al menos `0102`/BDV, ya venía pendiente de la sesión anterior.

**Nota de coordinación:** el punto 3 de este bloque (quitar `refresh` del body) puede romper a `suit-panel` si su `authorize()` de NextAuth lo lee del body en vez de la cookie — coordinar con `suit-panel` antes de mergear ese cambio puntual, no bloquear el resto del bloque por esto.

---

## Bloque #17 — Deploy: credenciales por defecto (pendiente) + Webhook server-to-server 🔄 ASIGNADO A `suit-backend`

**Origen:** mismo reporte de auditoría. **Decisión del usuario sobre el webhook:** no es opcional — depender solo del `postMessage` al navegador dejaba a la app consumidora sin confirmación si el navegador del pagador se cierra antes de recibirlo. Se construye ahora.

### Parte 1 — RabbitMQ/Flower con credenciales por defecto (sigue sin asignar)
Quitar el fallback `:-guest` en `deploy/docker-compose.yml` (obligar la variable en `.env`), evaluar no publicar esos puertos en un compose de "producción" separado del de desarrollo.

### Parte 2 — Webhook server-to-server, diseño cerrado

**Reutiliza el patrón outbox que ya existe** (mismo `EventoOutbox`/poller Celery beat del Bloque #6), no una tabla ni mecanismo nuevo desde cero — coherente con cómo ya se resolvió la entrega confiable hacia RabbitMQ.

1. **`AplicacionRegistrada`**: dos campos nuevos, ambos opcionales (una app puede seguir sin webhook si no lo necesita todavía) —
   - `webhook_url` (URLField, configurado por staff al registrar/editar la app — mismo CRUD admin del Bloque #7, que ahora pasa a `suit-panel` por decisión aparte del usuario).
   - `webhook_secret` (generado automáticamente al setear `webhook_url`, nunca editable a mano — es la clave HMAC, mismo rol que el "signing secret" de Stripe).
2. **`WebhookEntrega`** (modelo nuevo, 1:1 con cada `EventoOutbox` que tenga una `aplicacion` con `webhook_url` seteada): `evento` (FK), `intentos`, `estado` (`pendiente`/`entregado`/`agotado`), `ultimo_intento_at`, `ultima_respuesta_status`. Igual de campos a `EventoOutbox`, no un genérico reusable — evitar acoplar el mecanismo de RabbitMQ con el de HTTP.
3. **Poller Celery beat nuevo** (mismo patrón que `OutboxRelayService`, tick fijo, `SELECT ... FOR UPDATE SKIP LOCKED`): por cada `WebhookEntrega` pendiente, `POST` el payload del evento (mismo JSON que ya viaja a RabbitMQ) al `webhook_url`, con header `X-Suit-Signature: sha256=<hmac_sha256(webhook_secret, body)>` — la app consumidora valida la firma antes de confiar en el payload (igual que Stripe/PayPal/Mercado Pago).
4. **Reintentos con backoff fijo por tick** (mismo criterio ya usado para el relay RabbitMQ — no exponencial per-row), tope de intentos configurable (`WEBHOOK_MAX_INTENTOS`, default razonable ~10) antes de pasar a `agotado`. 2xx del consumidor = `entregado`; cualquier otra cosa (timeout, 4xx, 5xx, sin respuesta) = reintento.
5. **Timeout corto por request** (ej. 5s) — nunca bloquear el poller esperando a un consumidor lento.
6. Documentar en `GUIA-INTEGRACION-IFRAME.md` cómo validar la firma (ejemplo de código, mismo nivel de detalle que ya tiene el `postMessage`), y que el webhook es la fuente de verdad *primaria* — el `postMessage` queda como UX (redirigir/actualizar la pantalla más rápido), no como único mecanismo de confirmación.

**No urgente / agendar sin bloquear lo anterior:** tokens DRF admin sin expiración (mitigado por permisos), inconsistencia SameSite Strict/Lax entre backend y Next.js, falta `middleware.ts` en suit-panel como defensa en profundidad.

---

## Bloque #14 — Fix: crash-loop del worker Celery de Conciliación (gossip/mingle) ✅ COMPLETADO

**Encontrado por:** coordinador y `suit-backend`, en paralelo, mientras se corría un
cobro real end-to-end contra Docker a pedido del usuario · **Resuelto por:** coordinador

**Bug:** `suit-pagos-suit-conciliacion-celery-worker-1` llevaba **toda la sesión**
en crash-loop (`RestartFreqExceeded: 5 in 1s`) pese al fix
`CELERY_WORKER_ENABLE_REMOTE_CONTROL=False` ya aplicado en el Bloque #1 de
Conciliación — el contenedor mostraba "Up" en `docker ps` porque Docker no ve el
restart interno de billiard, solo el proceso padre. Traceback real:
`kombu/pidbox.py:309 _publish → kombu/common.py:maybe_declare` — no era la cola
de negocio (`conciliacion.eventos_pago.inbox`, correctamente `durable=True`),
sino que **gossip/mingle** (coordinación worker-a-worker, mecanismo distinto del
pidbox) también declaran colas transitorias exclusivas que RabbitMQ 4.x rechaza
con el mismo error 541 `transient_nonexcl_queues`.
`CELERY_WORKER_ENABLE_REMOTE_CONTROL=False` solo cubre el pidbox, no gossip/mingle.

**Fix:** `--without-gossip --without-mingle --without-heartbeat` agregado al
`CMD` de `deploy/Dockerfile.celery-worker`. Rebuild + recreate → worker arranca
limpio y estable (`celery@... ready.`, conectado a RabbitMQ, sin restarts).

**Consecuencia real detectada por `suit-backend`:** el cobro real que corrió
mientras el worker seguía en crash-loop (`pago_id 06a90fa3-dae4-7163-8000-03195a6f83c4`,
`event_id 06a90fa3-ed05-7d59-8000-21ece2e83043`) quedó con su `EventoOutbox`
marcado `enviado` (el publisher confirm del broker fue exitoso) pero
probablemente **nunca llegó a ninguna cola**, porque el worker nunca estuvo
arriba para declararla. Se le pidió a `suit-backend` reprocesar/republicar ese
evento puntual ahora que el worker está sano.

**Gap de diseño anotado, no corregido en este pase** (propuesto por
`suit-backend`): el publisher del relay no usa el flag `mandatory` de AMQP, así
que no hay forma de detectar un mensaje no enrutado — un `EventoOutbox` puede
quedar "enviado" sin que ningún consumidor lo haya recibido. Queda para una
decisión de diseño futura, no es parte de este fix puntual.

**Segundo quirk de BDV QA documentado** (encontrado por `suit-backend` en la
misma prueba): además del monto literal (`"1000.6"`, ver Bloque #8), el campo
`concept` también matchea literal contra el ejemplo del PDF (`"Pago"`) —
cualquier otro texto dispara el mismo código no documentado `1001`.

**Actualización del mismo bloque — causa raíz real y fix definitivo:** el
fix de arriba (`--without-gossip/--without-mingle`) resolvió el crash-loop
pero introdujo un problema nuevo: reportado por el usuario ("en flower no veo
nada, no me muestra nada"). Investigando se encontró que **Flower declara su
propia cola de eventos exclusiva/transitoria** (mecanismo `celeryev`,
independiente de gossip/mingle) y choca con el mismo error 541 — no hay flag
de arranque de Flower para evitarlo. Además, `CELERY_WORKER_ENABLE_REMOTE_CONTROL
= False` (el fix original del pidbox, Bloque #1 de Conciliación) apaga
también el `inspect` que Flower necesita para listar workers/stats, aunque el
worker esté sano.

**Fix definitivo, a nivel de broker en vez de parchear cada cliente:**
`deploy/rabbitmq.conf` (nuevo, montado en el contenedor `rabbitmq`) reactiva
las dos features deprecadas que de verdad estaban causando todo esto:
```
deprecated_features.permit.transient_nonexcl_queues = true
deprecated_features.permit.global_qos = true
```
Con esto, `CELERY_WORKER_ENABLE_REMOTE_CONTROL` vuelve a su default (`True`)
en ambos backends, y el `CMD` de `deploy/Dockerfile.celery-worker` vuelve a
ser simple (`celery worker -E`, sin ningún `--without-*`). Verificado en vivo:
worker con mingle activo (`mingle: all alone`, sin crashear), Flower
mostrando el worker real vía `GET /api/workers` (stats, pool, cola activa,
tarea registrada) tras reiniciarlo tras el arranque del worker.

**Lección:** los fixes puntuales de Bloques #1/#6 (desactivar remote control)
eran correctos para lo que tenían delante en ese momento, pero escondían la
causa raíz (una feature deprecada del broker) detrás de un parche por
cliente — cada nuevo consumidor de RabbitMQ (gossip/mingle, luego Flower)
volvía a pisar el mismo error 541 de una forma distinta. Corregirlo una vez
en la config del broker evita seguir jugando a las escondidas con este bug.

---

## Bloque #10 — Verificación de despliegue completo con Docker ✅ COMPLETADO — HITO FINAL

**Ejecutado por:** coordinador · **Estado:** los 8 servicios levantados y verificados

`docker compose -p suit-pagos -f deploy/docker-compose.yml up -d` — build de las
5 imágenes propias + `postgres-orquestador`, `postgres-conciliacion`, `rabbitmq`
(management), `flower` (monitoreo de Celery, agregado a pedido). Los 8 contenedores
saludables, smoke test HTTP contra cada uno:

| Servicio | URL | Resultado |
|---|---|---|
| `suit-orquestador` | `:8001/api/schema/` | 200 |
| `suit-conciliacion` | `:8002/api/docs/` | 200 |
| `suit-panel` | `:3000` | 302 → `/login` (esperado, ruta protegida) |
| `suit-portal` | `:3001` | 200 |
| RabbitMQ management | `:15672` | 200 |
| Flower | `:5555` | 200 |

**Bug real encontrado y corregido en el camino:** la migración
`0003_ledger_balance_trigger.py` de `suit-conciliacion` nunca se había probado
contra Postgres real (el smoke test local usó SQLite, donde el trigger es un
no-op) — al correr contra `postgres-conciliacion` en Docker, `RAISE EXCEPTION
'... % ...'` (placeholder propio de PL/pgSQL) chocaba con el parseo de
parámetros de psycopg3 en `schema_editor.execute()`. Fix correcto: `params=None`
explícito en las 4 llamadas SQL de la migración (no escapar `%%`, que también
falla en esta versión de psycopg). Test de regresión nuevo agregado
(`test_ledger_balance_trigger.py`, `TransactionTestCase` porque el trigger es
`DEFERRABLE INITIALLY DEFERRED`).

**Nota sobre `deploy/.env` y variables de compose:** `postgres-orquestador` y
`postgres-conciliacion` son bases Docker nuevas, distintas de las que usan los
backends en desarrollo local directo (venv + Postgres del host) — el nombre
de base del Orquestador en Docker es `orquestador_pagos` vía override explícito
en el `environment:` del servicio (evitar reintroducir el mismo desajuste).

**Sentry:** evaluado, decisión pospuesta — self-hosted requiere ~10 contenedores
adicionales (Postgres, Kafka, ClickHouse, workers propios), desproporcionado
para el estado actual del proyecto. Se retoma cuando haya un DSN real (SaaS o
self-hosted externo) para conectar solo el SDK, sin agregar infraestructura.

---

## Bloque #11 — Usuario real de staff + 3 bugs de conectividad Docker ✅ COMPLETADO

**Coordinado entre** coordinador y `suit-conciliacion` · **Estado:** login real
end-to-end y registro real de apps end-to-end, ambos verificados en Docker

**Usuario de staff real:** `hmachado@conatel.gob.ve` (is_staff=True,
is_superuser=True) — decisión de alta vía Django admin, sin flujo de
autoregistro (mismo criterio ya aplicado para el admin del Orquestador: staff
interno, identidad ya conocida por quien da de alta). Permisos ajustados:
`DiscrepanciaResolverView` ahora exige `IsAdminUser` además de
`IsAuthenticated` (solo staff resuelve, cualquier autenticado consulta).

**3 bugs reales de despliegue encontrados al probar el login/registro de
verdad en Docker** (ninguno visible en desarrollo local, todos específicos del
entorno containerizado):

1. **NextAuth `UntrustedHost`** — Auth.js v5 detrás de Docker/proxy rechaza el
   host por defecto. Fix: `AUTH_TRUST_HOST=true` en el entorno de `suit-panel`.
2. **`DisallowedHost` de Django** en ambos backends — `ALLOWED_HOSTS` no incluía
   los hostnames internos de Docker (`suit-orquestador`, `suit-conciliacion`).
   `suit-conciliacion` ya soportaba `ALLOWED_HOSTS` vía env; se agregó al
   compose. `suit-orquestador` lo tenía hardcodeado a `[]` sin soporte de env
   — gap de código real, corregido por `suit-backend` (default `[]` preservado
   para no cambiar el comportamiento local).
3. **Contenedor huérfano de `suit-conciliacion`** con `CMD [python3]` en vez del
   entrypoint real — causado por dos invocaciones de `docker compose` con el
   mismo nombre de proyecto (`suit-pagos`) pisándose entre sí (una desde la
   raíz con `-f` explícito, otra desde `deploy/` sin `-f`, que además
   auto-mezcló `docker-compose.override.yml`). Resuelto con rebuild `--no-cache`
   y recreate explícito. **Lección operativa:** un solo lado (coordinador)
   debe correr `docker compose` sobre este proyecto a la vez.

---

## Bloque #12 — Formulario de cobro embebido por iframe ✅ COMPLETADO

**Propuesto por:** `suit-backend` · **Estado:** ejecutado y verificado (77/77 tests, servidor real de prueba corriendo)

**Alcance:** `GET /api/autorizacion/cobro/formulario/?checkout_token=...` — vista
server-rendered (Django, sin SPA) que sirve el formulario real de cobro C2P
(cédula/teléfono → OTP → confirmar), embebible por iframe en apps consumidoras.

**Corrección de seguridad aplicada antes de construir la vista** (encontrada
al revisar el plan inicial, no en el research previo): el monto a cobrar
**no puede viajar en un query param editable por el navegador** — el OTP
autentica al pagador, no valida que el monto sea el que la app realmente
factura; un pagador técnico podría auto-reducirse su propia factura editando
la URL del iframe. Fix: `ValidarAccesoRequestSerializer` ahora exige
`monto`/`moneda`/`concepto` al iniciar el checkout, atados criptográficamente
dentro del `checkout_token` (mismo mecanismo de firma que `aplicacion_id`/
`proveedor_codigo`). `EjecutarCobroRequestSerializer` ya **no acepta** esos
campos — el cobro real siempre usa lo que dice el token verificado, nunca el
body del submit. Test de regresión específico:
`test_monto_del_body_se_ignora_se_usa_el_del_checkout_token`.

**Seguridad de iframe** (`research-seguridad-iframe.md` aplicado):
- `Content-Security-Policy: frame-ancestors <dominio>:*` armado por request
  contra los `DominioPermitido` activos de la app — nunca estático. Wildcard
  de puerto porque `DominioPermitido.dominio` no guarda puerto.
- Origin (preferido) o Referer (fallback) validados contra esa misma lista;
  si no matchea, `403` sin CSP permisiva. Si ninguno viene, se permite —
  `frame-ancestors` queda como control primario (defensa en profundidad, no
  única barrera).
- `X-Frame-Options: SAMEORIGIN` solo en esta vista (fallback legacy), resto
  del proyecto sigue en `DENY` por default de Django.
- `postMessage` con `targetOrigin` exacto (el Origin/Referer capturado) —
  nunca `'*'`; si no se pudo determinar el origen, no se manda ningún mensaje.

**Verificado en vivo** contra un servidor real (`localhost:8010`): CSP
correcta (`frame-ancestors localhost:*`), `postMessage` con `parentOrigin`
exacto, llamada de OTP real contra BDV QA (`{"resultado":"otp_enviado"}`).
Página de prueba standalone con el iframe embebido real, lista para abrir en
navegador (checkout_token vence a los 15 min).

**Verificación final, contra contenedores reales:**
- Login real de `hmachado` vía NextAuth → 302 a `/`, cookies de sesión y
  refresh seteadas correctamente.
- Registro real de una aplicación desde `suit-portal` → `suit-orquestador`
  (token admin generado en la base de datos real de Docker, no la de
  desarrollo local — son instancias Postgres distintas) → `201`, fila real
  creada (`AplicacionRegistrada` "Docker Smoke Test").

---

## Bloque #13 — Fix: Swagger de Conciliación bloqueado por iframe en el Portal ✅ COMPLETADO

**Reportado por:** usuario (probando el Developer Portal real) · **Resuelto por:** `suit-conciliacion`

**Bug:** la página "Documentación" de `suit-portal` embebe por iframe el Swagger
de `suit-conciliacion` (`/api/docs/`), pero `X-Frame-Options: DENY` (default
del middleware de clickjacking de Django) lo bloqueaba — mismo tipo de
protección que el propio proyecto usa a propósito en otros lados, pero acá
nadie la había exceptuado para esta vista.

**Fix:** `xframe_options_exempt` + `Content-Security-Policy: frame-ancestors
'self' {PORTAL_ORIGIN}` aplicado únicamente a `/api/schema/` y `/api/docs/`
(mismo patrón que el formulario de cobro del Orquestador) — resto del proyecto
sigue en `DENY` por default, sin excepción global. `PORTAL_ORIGIN` vía env
(`http://localhost:3001` en dev), agregado a `deploy/docker-compose.yml`.

**Verificado en 3 niveles:** unit test aislado de la función (headers
correctos), servidor de desarrollo local, y el stack Docker real donde se
reportó el bug (`curl -I http://localhost:8002/api/docs/` confirma el CSP
correcto, sin `X-Frame-Options`). 41/41 tests. Nota técnica: un test de
integración real contra `/api/docs/` vía `manage.py test` es inviable porque
esas rutas solo se registran `if settings.DEBUG`, y `manage.py test` fuerza
`DEBUG=False` — se optó por testear la función en aislamiento + verificación
manual real, en vez de un test frágil.

---

## `suit-orquestador`

### Bloque #1 — Modelos base del Orquestador ✅ COMPLETADO

**Propuesto por:** `suit-backend` · **Estado:** ejecutado y verificado contra Postgres real

**Alcance:** Módulo Django `apps/autorizacion` — solo modelos + migraciones + admin,
sin endpoints. Secciones 2.0–2.3 de `db-plan-pagos.md`:
- 2.0 Registro de seguridad: `AplicacionRegistrada`, `DominioPermitido`, `AplicacionProveedorPermitido`
- 2.1 Catálogos: `Moneda`, `MedioPago`, `ProveedorPago`, `Banco`, `TipoOperacionProveedor`, `CodigoRespuestaProveedor`
- 2.2 Agregado de pago: `IntencionPago`, `TransicionEstadoPago`, `Autorizacion`, `Captura`, `Anulacion`, `Reembolso`
- 2.3 Outbox/idempotencia: `EventoOutbox`, `IdempotencyKey` (expires_at = 48h)
- Fuera de alcance (no creados): `TokenReferencia`, `ProveedorTokenizacion`

**Decisiones tomadas antes de ejecutar:**
- Proyecto Django aloja solo el Orquestador (Conciliación es proyecto separado)
- `IdempotencyKey.expires_at` = 48 horas
- Transiciones de `IntencionPago` forzadas con trigger PL/pgSQL en Postgres, no solo disciplina de servicio
- `Moneda` como modelo de catálogo real (no `TextChoices`), decisión del agente para permitir activar/desactivar monedas sin deploy — confirmada por el coordinador

**Verificación:** `manage.py check` y `makemigrations --check` sin errores. Migrado contra
Postgres real (base `orquestador_pagos`). Trigger de transiciones probado funcionalmente
(acepta transición válida, rechaza salto inválido, rechaza estado desincronizado). Seed de
monedas confirmado en base real (VES activo, USD inactivo).

---

### Bloque #2 — Endpoint de validación de acceso ✅ COMPLETADO

**Propuesto por:** `suit-backend` · **Estado:** ejecutado, testeado y commiteado (`f62e3f3`)

**Alcance:** Control de seguridad bloqueante (sección 2.0) — rechaza la petición antes
de crear cualquier `IntencionPago` si el dominio/app/proveedor no está registrado.
- `application/services.py`: `ValidacionAccesoService.validar(dominio, proveedor_codigo)`
  — cadena `DominioPermitido(activo)` → `AplicacionRegistrada(activa)` →
  `AplicacionProveedorPermitido(activo)`. Excepción única `AccesoNoAutorizadoError(motivo)`
  con motivos distinguibles: `dominio_no_registrado`, `dominio_inactivo`,
  `aplicacion_inactiva`, `proveedor_no_encontrado`, `proveedor_no_autorizado`.
- Endpoint `POST /api/autorizacion/validar-acceso/` — `{"dominio", "proveedor"}` →
  200 `{"autorizado": true, ...}` o 403 `{"autorizado": false, "motivo": "..."}`.
  `AllowAny` (se consulta antes de cualquier autenticación de usuario).

**Verificación:** 10 tests (servicio + vista, éxito y cada motivo de rechazo), corridos
contra Postgres real incluyendo la migración del trigger. Todos pasan.

---

### Bloque #3 — Adaptador real BDV Pago Móvil C2P ✅ COMPLETADO

**Propuesto por:** `suit-backend` · **Estado:** ejecutado y verificado (20/20 tests, Postgres real)

**Alcance:** `infrastructure/adapters/bdv_c2p.py` — cliente HTTP del flujo de 3 pasos
(OTP, cobro, anulación) contra la API real de BDV documentada en los PDFs de
proveedor, autenticación `X-API-Key`. Flujo mínimo `IntencionPago → Autorizacion →
Captura` usando el adaptador (sin exponer aún endpoint público de cobro ni iframe).

**Decisiones tomadas antes de ejecutar:**
- `Autorizacion` y `Captura` se crean en la misma transacción a partir de una sola
  respuesta BDV (C2P es cargo instantáneo, sin reserva separada del lado del banco)
- Categorización de los 19 códigos de error de BDV en `CodigoRespuestaProveedor.categoria`
  aprobada según propuesta del agente (1000→éxito, 1026/1094→duplicado_idempotente,
  1002/1041/1050/1091→error_técnico, resto→error_negocio)
- `requests` agregado a `requirements.txt`
- API key dummy de QA en `.env` local (no commiteado), comentada explícitamente
  como solo-QA, rotar antes de producción
- Tests: mock de `requests.post` en el adaptador, mock del adaptador completo en
  los tests del servicio de flujo de cobro — nunca contra el host real de BDV

**Verificación:** 20/20 tests pasando contra Postgres real, `manage.py check` limpio.
Bug propio encontrado y corregido: la llamada HTTP y la transición a `fallido` no
pueden vivir en el mismo `transaction.atomic()` que el camino de éxito (Postgres
revierte la transición de fallo al re-lanzar la excepción) — quedaron separados.
Migración `0004_seed_catalogos_bdv_c2p.py` puebla `MedioPago`, `ProveedorPago`,
`Banco`, `TipoOperacionProveedor` y los 19 `CodigoRespuestaProveedor` reales.

---

### Bloque #4 — Endpoint público de cobro ✅ COMPLETADO

**Propuesto por:** `suit-backend` · **Estado:** ejecutado y verificado (43/43 tests)

**Alcance:** `FlujoCobroC2PService` expuesto como endpoint público, con **token
de sesión de checkout firmado** (`TimestampSigner`, corta duración, encapsula
`aplicacion_id` + `proveedor_codigo`) emitido por `ValidarAccesoView` y validado
por el endpoint de cobro — decisión tomada para cerrar el hueco de seguridad
del camino crítico ahora, en vez de dejarlo pendiente hasta el bloque del iframe
(ver `research-seguridad-iframe.md`). Incluye idempotencia real (`IdempotencyKey`
con dedup por `request_hash`, respuesta cacheada si coincide, 409 si difiere).

---

### Bloque #5 — Contrato del evento `pago.confirmado` + escritura de `EventoOutbox` ✅ COMPLETADO

**Propuesto por:** `suit-backend` · **Estado:** ejecutado y verificado (45/45 tests)

**Alcance:** contrato de 10 campos persistido en
`investigaciones/contrato-evento-pago-confirmado.md` (incluye `cedula_pagador`/
`telefono_pagador` que Conciliación necesita para el matching, `routing_flag`,
`payload_crudo_captura`). `FlujoCobroC2PService.ejecutar_cobro` escribe el
`EventoOutbox` dentro de la misma transacción atómica que `Captura` — un cobro
fallido no publica ningún evento. **Desbloqueó a `suit-conciliacion`.**

---

### Bloque #6 — Relay outbox → RabbitMQ ✅ COMPLETADO

**Propuesto por:** `suit-backend` · **Estado:** ejecutado y verificado en vivo (50/50 tests + RabbitMQ real)

**Alcance:** poller vía Celery beat (no CDC/Debezium, según
`research-outbox-vs-cdc.md`) — `SELECT ... FOR UPDATE SKIP LOCKED` en lotes de
100, publisher confirms de RabbitMQ antes de marcar `enviado`, backoff fijo por
tick (no exponencial per-row, decisión YAGNI consistente con el resto del
proyecto) con tope de reintentos antes de pasar a `fallido`. Incluye el mismo
fix `CELERY_WORKER_ENABLE_REMOTE_CONTROL=False` que encontró Conciliación.
Cierra el pipeline end-to-end Orquestador → RabbitMQ → Conciliación.

**Verificación en vivo:** `EventoOutbox` real → `OutboxRelayService.procesar_lote()`
→ exchange `pago` (aislado con routing key de prueba, sin tocar la cola real de
Conciliación) → confirmado recibido, fila marcada `enviado`. Confirmó
empíricamente que el fix `CELERY_WORKER_ENABLE_REMOTE_CONTROL=False` también
es necesario del lado Orquestador (lo disparó por accidente durante la prueba).
**Incidente resuelto:** quedó un mensaje de prueba de una verificación anterior
atascado en la cola real `conciliacion.eventos_pago` — el coordinador lo purgó
directamente vía `rabbitmqctl purge_queue` antes de que el worker de
Conciliación pudiera intentar procesarlo y fallar.

---

## `suit-conciliacion`

### Bloque #1 — Apps base de Conciliación ✅ COMPLETADO

**Propuesto por:** `suit-conciliacion` · **Estado:** ejecutado y verificado end-to-end (25/25 tests + prueba real contra RabbitMQ)

**Alcance:**
1. **`apps/shared`** — `BaseModel` abstracto (UUID v7 + timestamps)
2. **`apps/users`** — staff local de Conciliación (auth JWT, patrón simplejwt +
   cookie HttpOnly de la skill), `Usuario(AbstractUser, BaseModel)`
3. **`apps/conciliacion`** — agregado completo de la sección 3 del plan de datos:
   - Catálogos: `CuentaContable`, `Banco`
   - Ingesta: `EventoPagoRecibido` (dedup por `event_id`)
   - Matching BDV: `ConsultaConciliacionProveedor`, `MovimientoBancario` (genérico)
   - Ledger de doble entrada: `TransaccionLedger`, `LineaLedger`
   - `Discrepancia` (3 FK nullable, `resuelto_por` → `apps.users.Usuario`)
   - `ReporteERP`
   - Servicios: `ingesta.py`, `matching.py`, `ledger.py`
   - Infra: `tasks.py` (worker Celery consumiendo `pago.*` de RabbitMQ, polling a BDV)
   - Endpoints mínimos: listado/detalle de discrepancias, resolución, eventos, ledger

**Decisiones tomadas antes de ejecutar:**
- Auth de staff: usuario propio local en Conciliación (no identidad de otro servicio) —
  `Discrepancia.resuelto_por` es FK real con `SET_NULL`
- Balance-cero del ledger: constraint/trigger a nivel Postgres (consistente con el
  patrón ya aplicado en el Orquestador)
- Relay RabbitMQ→Celery: worker consumiendo directo de la cola (patrón estándar,
  no poller — el poller es específico del lado Orquestador/outbox)

**Gaps de modelado resueltos por `expert_database_conciliacion` antes de este bloque:**
`related_name` faltantes, `on_delete`/tipo de relación de `TransaccionLedger.referencia_evento`,
`on_delete` de las 3 FK nullable de `Discrepancia`, tipado de `Discrepancia.tipo`/`.severidad`
como `TextChoices`, `ReporteERP.payload` como `JSONField`, índices en `referencia_corta` y
`procesado_at`.

**Verificación:** 25/25 tests pasando. Pipeline end-to-end probado contra
infraestructura real (`suit-pagos-rabbitmq-1`): mensaje publicado al exchange
`pago` (topic, routing key `pago.confirmado`) → bootstep `EventoPagoConsumerStep`
→ tarea Celery `consumir_evento_pago` → `IngestaService` → `EventoPagoRecibido`
persistido en Postgres. Bug real encontrado y corregido: Celery 5.6 es
incompatible con RabbitMQ 4.x en el pidbox (`transient_nonexcl_queues`
deprecado, error 541) — fix permanente con `CELERY_WORKER_ENABLE_REMOTE_CONTROL
= False`. Puerto AMQP (5672) del contenedor RabbitMQ publicado en
`deploy/docker-compose.yml` para poder probar contra el broker real desde el host.

**Nota para `suit-orquestador`:** si en algún momento corre un worker Celery
propio contra el mismo RabbitMQ, aplicar el mismo fix de `transient_nonexcl_queues`.

---

### Bloque #2 — Adaptador HTTP real a BDV `getMovement/v2` ✅ COMPLETADO

**Propuesto por:** `suit-conciliacion` · **Estado:** ejecutado (alcance reducido, luego conectado tras el contrato de evento)

**Alcance:** cliente HTTP real hacia la API de conciliación de BDV (`X-API-Key`
propia de Conciliación, manejo del debounce de 30s del banco), conectando la
lógica de interpretación ya lista en `domain/bdv.py`/`MatchingService`. Se
ejecutó primero en alcance reducido (cliente HTTP puro, desconectado del
consumer) mientras `suit-orquestador` definía el contrato de `pago.confirmado`;
conectado en un paso siguiente sin fricción (cambio de una línea en `tasks.py`).

**Auto-auditoría:** tras el smoke test de `suit-panel` (que encontró 4
desvíos reales del contrato), `suit-conciliacion` auditó su propia API contra
esos 4 puntos — confirmó que su implementación ya era correcta en los cuatro
casos; los "desvíos" eran imprecisiones de `CONTRATO-API-ACTUAL.md`, corregidas.

---

## `suit-orquestador` (bloques adicionales tras el resumen)

### Bloque #7 — CRUD de registro de aplicaciones/dominios ✅ COMPLETADO

**Propuesto por:** `suit-backend` · **Estado:** ejecutado y verificado (67/67 tests, Postgres real)

**Alcance:** `AplicacionRegistrada`/`DominioPermitido`/`AplicacionProveedorPermitido`
gestionables vía API, no solo Django admin — desbloquea a `suit-portal`.
`TokenAuthentication` (reutiliza `django.contrib.auth`/`rest_framework.authtoken`,
sin replicar JWT completo para un volumen bajísimo e interno) + `IsAdminUser`.
`app_origen_id` opcional (UUID propio si no llega, hasta que `suit-portal` tenga
su propia entidad `AppConsumidora`).

| Método | Ruta |
|---|---|
| POST | `/api/autorizacion/admin/aplicaciones/` |
| GET | `/api/autorizacion/admin/aplicaciones/` |
| PATCH | `/api/autorizacion/admin/aplicaciones/<uuid:id>/` |

Permisos verificados explícitamente: sin token → 401, usuario no-staff → 403,
staff → 200/201.

---

## `suit-panel`

### Bloque #1 — Login + Discrepancias + Eventos ✅ COMPLETADO Y VERIFICADO E2E

**Propuesto por:** `suit-panel` · **Estado:** verificado contra backend real (commits `a800935`, `f96364e`)

**Alcance:** contra `CONTRATO-API-ACTUAL.md` (endpoints reales de `suit-conciliacion`):
- Auth: NextAuth con relay manual de la cookie `refresh_token` HttpOnly
  (`authorize()` reenvía el `Set-Cookie` del backend), access token en el JWT de
  sesión (nunca expuesto al cliente), refresh automático en el callback `jwt`.
- Módulo `modules/conciliacion/discrepancias/` (Onion completo: domain/application/
  infrastructure/ui) — listado con filtro por `estado_resolucion`/`severidad`
  (SWR + react-hook-form/zod) y acción de resolver (Dialog + server action).
- Módulo `modules/conciliacion/eventos/` — listado de solo lectura con búsqueda.
- `transacciones-ledger` (detail) queda para un bloque #2.
- Dependencias nuevas: `next-auth`, `swr`, `react-hook-form`, `@hookform/resolvers`,
  `zod`, `sonner`, `next-themes`, shadcn (button, card, field, input, select,
  textarea, dialog, alert-dialog, badge, skeleton, separator).

**Verificación end-to-end contra `suit-conciliacion` real** (no mockeada) —
encontró y corrigió 4 desvíos reales del contrato documentado, que un mock
nunca hubiera revelado:
1. Paginación DRF no documentada: `discrepancias/` y `eventos/` devuelven
   `{count, next, previous, results}`, no un array plano.
2. `logout` requiere `Authorization: Bearer` + `refresh` en el body, la cookie
   sola no alcanza.
3. El `refresh` rota el token en cada llamada (viene también en el body) —
   hay que persistir el nuevo valor, no parsear `Set-Cookie` a mano.
4. Nombre de estado real es `abierta`, no `pendiente` (`Discrepancia.EstadoResolucion`).

Flujo de resolver discrepancia probado con datos reales sembrados en la DB de
`suit-conciliacion`: abierta → resuelta, con `resuelto_por`/`resuelto_at`
mapeados correctamente. `CONTRATO-API-ACTUAL.md` actualizado con los 4 hallazgos.

---

## Bloque #8 — Prueba de integración real end-to-end ✅ COMPLETADO — HITO CLAVE

**Coordinado entre** `suit-backend` y `suit-conciliacion` · **Estado:** pipeline completo verificado con infraestructura y BDV reales

**Flujo probado de punta a punta**, sin ningún mock: `validar-acceso` (emite
checkout token) → `cobro/otp` (BDV QA real) → `cobro` (BDV QA real, `IntencionPago`
capturado, `Autorizacion`+`Captura` creadas) → `EventoOutbox` escrito → relay
ejecutado manualmente → publicado a **RabbitMQ real** (`suit-pagos-rabbitmq-1`)
→ worker Celery de Conciliación lo consume → `IngestaService` → `EventoPagoRecibido`
persistido → `BdvConciliacionClient` consulta BDV QA real → `domain/bdv.py`
interpreta la respuesta → `MatchingService` genera `Discrepancia` (el banco QA
respondió "no existe" — esperable, son dos sandboxes aislados sin estado
compartido, no una falla del sistema; el diseño "nunca falla en silencio" hizo
exactamente lo esperado).

**Dos bugs reales de producción encontrados y corregidos en el camino:**
1. BDV QA dummy exige el formato literal del ejemplo del PDF (`"1000.6"`, no
   `"1000.60"`) — documentado como memoria de proyecto, no se tocó el adaptador
   real (que sí genera el formato correcto de 2 decimales para producción).
2. **Colisión de nombres de cola** en `suit-conciliacion`: el bootstep de
   eventos crudos usaba por accidente el mismo nombre que la cola default de
   tareas de Celery — dos consumidores compitiendo generó un loop de reintentos
   amplificándose hasta `EncodeError` por recursión máxima. Cortado a tiempo
   sin daño a datos, colas separadas (`conciliacion.eventos_pago.inbox` vs. la
   cola nativa de Celery), verificado limpio con evento sintético.

`event_id` de referencia para auditoría: `06a90a96-7720-735a-8000-513ba65c1bf3`.

---

## `suit-portal`

### Bloque #1 — Estructura base + docs + formulario mockeado 🔄 EN EJECUCIÓN

**Propuesto por:** `suit-portal` · **Estado:** autorizado, en curso

**Alcance:** desbloqueado pese al gap #1 de `CONTRATO-API-ACTUAL.md` (CRUD de
registro de apps/dominios no existe todavía en el backend):
1. Layout base, nav, landing del portal.
2. Visor de documentación — iframe a `/api/docs/` de `suit-conciliacion` (único
   backend con Swagger hoy), con nota visible de que `suit-orquestador` aún no
   expone docs — el gap se muestra al usuario, no se oculta.
3. Formulario de registro de aplicación/dominio/proveedor (`modules/registro-aplicaciones/`,
   Onion completo), **submit mockeado con `// TODO` explícito** apuntando al gap
   #1 de `CONTRATO-API-ACTUAL.md` — se conecta al endpoint real cuando exista.
4. Tests: unit (schema de validación), E2E (formulario + mensaje mockeado, sin
   aserciones contra persistencia real), a11y.
- Dependencias nuevas: `zod`, `react-hook-form`, `@hookform/resolvers`, `sonner`,
  shadcn (button, input, label, select, card, field).

---

## Infraestructura de despliegue

### `deploy/` — Docker + docker-compose ✅ COMPLETADO (coordinador)

Carpeta creada directamente por el coordinador (infraestructura transversal, no
propia de un solo servicio), siguiendo el patrón de la skill
`despliegue-docker-django-nextjs` (ya copiada a los 4 proyectos), adaptado a las
decisiones reales del proyecto:

- `Dockerfile.backend` (genérico, `SERVICE_DIR` selecciona `suit-orquestador` o
  `suit-conciliacion`), `Dockerfile.celery-worker` (solo Conciliación),
  `Dockerfile.frontend` (genérico, `suit-panel`/`suit-portal`, usa `npm` no `pnpm`)
- `docker-compose.yml`: 2 Postgres separados (`postgres-orquestador`,
  `postgres-conciliacion` — nunca un solo Postgres con schemas), 1 RabbitMQ
  (sin Redis), 4 servicios de aplicación + 1 worker Celery
- `docker-compose.override.yml` para desarrollo (hot reload, código montado)
- `README.md` con variables de entorno, comandos de uso y pre-flight checks

**Pendiente de verificación real** (no se corrió `docker build`/`docker compose up`
todavía — los backends siguen en desarrollo activo): una vez `suit-orquestador` y
`suit-conciliacion` completen sus bloques en curso, correr el checklist de
`deploy/README.md` para validar que el stack completo levanta sin errores.

---

## Cómo se usa este archivo

Cada vez que un agente arma un bloque nuevo, el coordinador lo agrega aquí con:
propuesto por, alcance exacto, decisiones tomadas antes de ejecutar, y estado
(`propuesto` → `autorizado` → `en ejecución` → `completado`/`verificado`). No se
edita retroactivamente el contenido de un bloque ya completado, salvo para
corregir un error — el historial de decisiones queda como registro.
