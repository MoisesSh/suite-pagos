# Investigación — Stack de mensajería (RabbitMQ + Celery, ¿falta Redis?)

Verificación del stack técnico declarado en el roadmap (`RabbitMQ` como bus de eventos entre Orquestador y Conciliación, `Celery` como runtime de workers dentro de Conciliación) antes de que backend empiece a desarrollar. El roadmap no menciona Redis en ningún punto — se investiga si eso es un vacío o una omisión razonable.

## 1. Versiones estables actuales (verificado ago-2026)

- **RabbitMQ**: serie estable actual **4.3.x** (4.3.4 publicada 23/jul/2026; 4.3.5 como mantenimiento más reciente de esa serie). La serie **4.2.x** sigue mantenida en paralelo (4.2.10, 18/ago/2026) para quienes no puedan saltar aún a 4.3. **Requisito de infraestructura importante**: desde la 4.2.9, la versión mínima soportada de Erlang/OTP es **27.0** — Erlang/OTP 26 ya llegó a EOL y no se soporta. Recomendación: partir directo en RabbitMQ 4.3.x con Erlang/OTP 27+, para no arrastrar una versión próxima a EOL desde el día 1 de un proyecto nuevo.
  Fuentes: [RabbitMQ Release Information](https://www.rabbitmq.com/release-information), [GitHub Releases — rabbitmq-server](https://github.com/rabbitmq/rabbitmq-server/releases)

- **Celery**: serie estable actual **5.6.x** (5.6.3, 26/mar/2026). Desde 5.6.0 se dropeó soporte a Python 3.8 (EOL) — mínimo Python 3.9. Soporta Django 2.2 LTS en adelante (compatible sin problema con cualquier Django moderno que use el proyecto), con mejoras recientes en pooling de conexiones Django y limpieza de conexiones innecesarias. Recomendación: fijar Celery ≥5.6 desde el inicio.
  Fuentes: [Celery Django docs](https://docs.celeryq.dev/en/stable/django/index.html), [Celery Changelog](https://github.com/celery/celery/blob/main/Changelog.rst)

## 2. ¿Celery necesita result backend? ¿Basta RabbitMQ solo, sin Redis?

**Depende de si el flujo necesita consultar el resultado de una tarea después de que termina.** Celery separa dos roles:
- **Broker** (obligatorio): transporta los mensajes de tarea. Aquí RabbitMQ ya cumple ese rol en el diseño del roadmap.
- **Result backend** (opcional): almacena el resultado/estado de cada tarea para que algo externo lo consulte más tarde (`task.get()`, `AsyncResult`). **No es necesario si nada necesita leer el resultado de una tarea Celery después de que se ejecutó** — que es exactamente el caso de conciliación descrito: es un pipeline fire-and-forget que persiste su resultado en la propia base de datos de Conciliación (matching, discrepancias), no algo que otro proceso consulte vía Celery.

Opciones si en algún punto se necesitara backend, sin depender de Redis:
- **`rpc://`** (backend RPC vía RabbitMQ/AMQP): usa el mismo broker, sin infraestructura adicional, pero entrega el resultado como mensaje transitorio (no persistente a largo plazo) — sirve solo si algo está escuchando en el momento.
- **Backend Django ORM / SQLAlchemy (Postgres)**: persiste resultados en la misma base de datos del servicio — coherente con el patrón "database per service" ya definido en el brief de arquitectura, sin añadir un componente de infraestructura nuevo.
- Redis, Memcached, MongoDB también son opciones soportadas, pero no son necesarias si no se requiere ese backend.

Fuente: [Celery — Backends and Brokers](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/index.html)

**Conclusión para este caso de uso:** RabbitMQ solo, sin result backend (o como mucho un backend Postgres si se quiere trazabilidad de ejecución de tareas), es funcionalmente suficiente para el pipeline de Conciliación tal como está descrito en el roadmap — no hay necesidad técnica de Redis únicamente por el hecho de tener Celery.

## 3. ¿Conviene agregar Redis de todas formas (cache, locks, rate limiting)?

Aunque no es un requisito duro de Celery+RabbitMQ, hay tres usos de Redis que sí son relevantes para *otras* partes del sistema descritas en el roadmap y que valdría la pena decidir explícitamente (no dejar como omisión implícita):

- **Locks distribuidos**: el roadmap exige explícitamente "idempotency keys en cada evento" y "matching automático con alerta ante cualquier diferencia > 0" como mitigación al riesgo de doble contabilidad. Si dos workers Celery pueden procesar concurrentemente el mismo pago (reintento + entrega duplicada del broker, dado que RabbitMQ/outbox solo garantiza *at-least-once*), un lock distribuido (`SETNX` vía `django-redis` `cache.lock()`) es el mecanismo estándar para evitar procesamiento duplicado a nivel de aplicación — complementa, no reemplaza, la unicidad a nivel de DB (`idempotency_keys`, constraint UNIQUE) ya recomendada en `research-brief-pagos.md`.
- **Rate limiting**: relevante para el API Gateway / Developer Portal (T2 del roadmap) — limitar por API key es un requisito típico de un gateway público, y Redis es la base estándar para contadores de ventana fija/deslizante compartidos entre instancias.
- **Cache general**: el Developer Portal y el API Gateway (métricas de uso, catálogos de bancos/monedas de solo lectura mencionados en `research-brief-pagos.md`) se benefician de cache compartido entre réplicas, algo que Django's cache framework local-memory no resuelve en un despliegue con más de una instancia.

**Recomendación:** agregar Redis como componente de infraestructura del proyecto, pero con un rol explícitamente distinto y acotado — cache/locks/rate-limiting — **no** como broker ni como result backend de Celery. Esto evita que el roadmap tenga una omisión implícita ("¿por qué no está Redis?") y separa responsabilidades: RabbitMQ sigue siendo el único bus de eventos entre Orquestador y Conciliación (decisión de diseño ya fijada y correcta), Redis resuelve problemas transversales de infraestructura que ningún otro componente del stack cubre bien.

Fuente: [Redis + Celery + RabbitMQ roles](https://dev.to/topunix/django-redis-caching-patterns-pitfalls-and-real-world-lessons-m7o), [Distributed Locking in Django — Lincoln Loop](https://lincolnloop.com/blog/distributed-locking-django/)

## 4. Colas durables y dead-letter queues — mejores prácticas

### Tipo de cola: quorum, no classic
- RabbitMQ recomienda **quorum queues** (basadas en consenso Raft, replicadas entre nodos) para cualquier carga que necesite durabilidad real — que es exactamente el requisito del bus `pago.*` entre Orquestador y Conciliación. Las **classic queues** ya no se recomiendan para cargas durables desde RabbitMQ 4.x; su uso legítimo queda limitado a colas transitorias/exclusivas (RPC reply queues, colas temporales con nombre autogenerado).
- Celery detecta automáticamente el uso de quorum queues (`worker_detect_quorum_queues`, activado por defecto) y ajusta su comportamiento — incluyendo **Native Delayed Delivery** automático al detectarlas, útil para reintentos con backoff sin necesitar el plugin de delayed-message-exchange por separado.
- Trade-off a documentar: classic queues tienen mayor throughput y menor latencia; quorum queues priorizan seguridad de datos vía replicación. Dado que este es un sistema de pagos donde perder un mensaje de `pago.confirmado` es inaceptable (riesgo "Alta" de doble contabilidad ya identificado en el roadmap), **quorum queues es la elección correcta** para las colas del bus `pago.*`, aceptando el costo de throughput.
  Fuentes: [RabbitMQ — Quorum Queues](https://www.rabbitmq.com/docs/quorum-queues), [RabbitMQ — Classic Queues](https://www.rabbitmq.com/docs/classic-queues), [Celery — Using RabbitMQ](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/rabbitmq.html)

### Dead-letter queues (DLQ)
- Declarar explícitamente `x-dead-letter-exchange` y, si aplica, `x-dead-letter-routing-key` como argumentos de la cola al crearla — así RabbitMQ enruta automáticamente ahí los mensajes rechazados (nack), expirados por TTL, o que excedan el largo máximo de cola.
- Tanto el exchange de dead-letter como la cola de dead-letter deben declararse `durable=True` — de lo contrario un reinicio del broker pierde los mensajes fallidos, justo el escenario que la DLQ existe para prevenir.
- Patrón recomendado para Celery: `acks_late=True` + `task_reject_on_worker_lost=True`, de forma que el ACK solo se envíe tras confirmar la ejecución completa de la tarea (no al recibir el mensaje); si el worker muere a mitad de proceso, el mensaje se re-encola o cae a la DLQ según la política, en vez de perderse silenciosamente. Combinar con `worker_prefetch_multiplier=1` para que un worker lento no acapare mensajes que otros workers libres podrían procesar antes.
- Para el caso específico de Conciliación (consumo async, reprocesable): una tarea que falla repetidamente (ej. error persistente al llamar `getMovement/v2` del proveedor BDV, ver `research-brief-pagos.md` sección 4.2) debe caer a DLQ tras un número máximo de reintentos con backoff exponencial — no reintentar indefinidamente — para permitir revisión manual, coherente con el patrón de `discrepancies`/`matching_exceptions` ya recomendado en el brief de base de datos.
  Fuentes: [OneUptime — RabbitMQ Dead Letter Queues](https://oneuptime.com/blog/post/2026-02-20-rabbitmq-dead-letter-queues/view), [OneUptime — Dead Letter Exchanges](https://oneuptime.com/blog/post/2026-01-25-rabbitmq-dead-letter-exchanges/view), [Towards Data Science — RabbitMQ & Celery queue optimization](https://towardsdatascience.com/deep-dive-into-rabbitmq-pythons-celery-how-to-optimise-your-queues/)

## 5. Resumen — recomendación para backend

| Decisión | Recomendación |
|---|---|
| Versión RabbitMQ | 4.3.x, con Erlang/OTP 27+ (no partir en una serie próxima a EOL) |
| Versión Celery | ≥5.6.x, Python ≥3.9 |
| Result backend de Celery | No usar Redis solo por esto. Si se necesita trazabilidad de tareas, usar backend Postgres/Django ORM (coherente con "database per service") o `rpc://`; si no se necesita consultar resultados, omitir backend |
| ¿Agregar Redis? | Sí, pero con rol acotado: cache compartido, locks distribuidos (deduplicación complementaria a idempotency keys), rate limiting del API Gateway/Portal. Nunca como broker ni result backend de Celery |
| Tipo de cola RabbitMQ | Quorum queues para el bus `pago.*` (durabilidad > throughput, dado el riesgo de doble contabilidad ya señalado en el roadmap) |
| Dead-letter queues | Declarar DLQ durable con `x-dead-letter-exchange`; Celery con `acks_late=True`, `task_reject_on_worker_lost=True`, `worker_prefetch_multiplier=1`, reintentos con backoff exponencial y tope antes de caer a DLQ |

Este archivo complementa (no reemplaza) `research-brief-pagos.md` — el punto de outbox pattern, idempotency keys y contrato de eventos versionado de ese brief siguen aplicando sin cambios; aquí solo se resuelve la capa de infraestructura de mensajería que los soporta.
