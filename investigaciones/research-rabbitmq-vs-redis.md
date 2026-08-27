# Investigación — RabbitMQ vs. Redis (Pub/Sub y Streams) como bus de eventos `pago.*`

Cuestionamiento explícito de la elección de RabbitMQ hecha en el roadmap original (`conatel-suite-pagos-roadmap.html`), que no evaluó Redis de forma explícita. Objetivo: decidir con evidencia, no por inercia del documento inicial, si RabbitMQ sigue siendo la elección correcta para el bus de eventos entre el Orquestador (síncrono) y Conciliación (async), dado el requisito duro de *at-least-once*, colas durables, dead-letter, y el riesgo ya identificado como "Alta severidad" en el roadmap: **doble contabilidad / discrepancias si se pierde un evento**.

## 1. Redis Pub/Sub puro — por qué NO aplica a este caso

Evidencia consistente y sin ambigüedad en múltiples fuentes:

- Redis Pub/Sub **no persiste nada**. Un mensaje se entrega a quien esté conectado en ese instante exacto, y luego desaparece — no hay buffer, no hay cola, no hay disco de por medio.
- Garantía de entrega: **at-most-once**. Si el suscriptor está desconectado, lento, o su buffer de salida se llena, el mensaje se descarta en silencio — la documentación de Redis lo dice literalmente: "the message is forever lost".
- **No hay replay**: un consumidor que se reconecta después de una caída no recupera lo que se publicó durante la ventana en que estuvo desconectado. No hay acknowledgment, no hay reintento.
- Para este proyecto esto es una descalificación directa, no un matiz: si Conciliación (o su worker Celery) está caída, reiniciándose, o simplemente lenta procesando un pico de tráfico, **cualquier evento `pago.confirmado` publicado en esa ventana se pierde de forma permanente y silenciosa** — exactamente el escenario que el roadmap marca como riesgo "Alta" (doble contabilidad).
- Conclusión de la propia documentación técnica consultada: "si tu aplicación no puede tolerar pérdida de mensajes, usa Redis Streams" — es decir, incluso las fuentes pro-Redis descalifican Pub/Sub puro para este tipo de caso de uso.

**Veredicto: Redis Pub/Sub puro queda descartado sin ambigüedad.** No es una alternativa real a evaluar contra RabbitMQ — ni siquiera compite en la misma categoría de garantías.

Fuentes: [OneUptime — Troubleshoot Redis Pub/Sub Message Loss](https://oneuptime.com/blog/post/2026-03-31-redis-troubleshoot-redis-pubsub-message-loss/view), [Ably — Redis pub/sub limitations](https://ably.com/topic/ai-stack/temporal-redis-pubsub-limitations), [Stanza — Pub/Sub Message Persistence and Limitations](https://www.stanza.dev/courses/redis-messaging/pubsub-fundamentals/redis-messaging-pubsub-persistence)

## 2. Redis Streams — ¿resuelve las limitaciones del Pub/Sub?

Sí, en gran medida a nivel de modelo de datos y semántica de API. Redis Streams es una estructura de datos distinta (append-only log, similar en espíritu a Kafka), con:

- **Persistencia real del log de eventos** (a diferencia de Pub/Sub) — los mensajes quedan almacenados en el stream, no solo se entregan y desaparecen.
- **Consumer groups** (`XREADGROUP`) con cursor por consumidor — varios workers pueden repartirse el trabajo del mismo stream, y varios grupos distintos pueden leer el mismo stream de forma independiente (útil si en el futuro más de un servicio necesita consumir `pago.*`, no solo Conciliación).
- **Acknowledgment explícito** (`XACK`) mediante una Pending Entries List (PEL): el mensaje queda "pendiente" hasta que el consumidor confirma que terminó de procesarlo. Si el consumidor se cae a mitad de proceso, el mensaje permanece en el PEL.
- **Recuperación de mensajes huérfanos** (`XCLAIM` / `XAUTOCLAIM`, y desde Redis 8.4 `XREADGROUP ... CLAIM` en un solo paso): otro consumidor del mismo grupo puede reclamar mensajes pendientes que superaron un tiempo mínimo de inactividad — mecanismo funcionalmente equivalente al re-delivery de RabbitMQ.
- Esto da **at-least-once delivery real**, no at-most-once — la limitación estructural de Pub/Sub queda resuelta.

**Sí es, en principio, una alternativa real a evaluar** — no se puede descartar Redis Streams con el mismo argumento que descarta Pub/Sub. La pregunta relevante pasa a ser una comparación honesta de garantías y madurez operativa, no de si "tiene o no tiene" las features básicas.

Fuentes: [Redis Docs — Redis Streams](https://redis.io/docs/latest/develop/data-types/streams/), [Redis Docs — Redis streaming use case](https://redis.io/docs/latest/develop/use-cases/streaming/), [Redis Blog — Single-shot reliable consumers with XREADGROUP CLAIM in Redis 8.4](https://redis.io/blog/single-shot-reliable-consumers-with-xreadgroup-claim-in-redis-84/), [XACK docs](https://redis.io/docs/latest/commands/xack/), [XPENDING docs](https://redis.io/docs/latest/commands/xpending/)

## 3. Comparación honesta: RabbitMQ vs. Redis Streams

### Garantías de entrega y durabilidad — la diferencia real

Esta es la diferencia que más importa para un sistema de pagos, y aquí sí hay una asimetría real entre ambos, no solo una diferencia de preferencia:

- **RabbitMQ (con publisher confirms + colas durables/quorum)**: el ACK que el publicador recibe de RabbitMQ significa, literalmente, que el mensaje **ya fue escrito a disco y fsync-eado en quorum de nodos** (en un cluster típico de 3 nodos, escrito y confirmado en al menos 2). Es una confirmación de durabilidad física, no solo de "recibido en memoria". Ver `research-stack-mensajeria.md` sección 4 para la recomendación de quorum queues ya hecha.
- **Redis**: la persistencia (RDB o AOF) es **opcional y debe configurarse explícitamente** — por defecto, Redis no garantiza que un dato esté en disco antes de responder OK a un comando. Incluso con AOF configurado en el modo más estricto (`fsync always`), el modelo de consistencia de Redis y su mecanismo de replicación (asíncrona por defecto entre primario y réplicas) no dan la misma garantía de "confirmado = persistido en quorum" que el publisher confirm de RabbitMQ. Requiere configuración cuidadosa y explícita para acercarse a ese nivel de garantía — no es el comportamiento por defecto, y es fácil de configurar mal sin darse cuenta.
- Conclusión de una de las fuentes comparativas: *"si perder un mensaje significa perder dinero, la recomendación es RabbitMQ; si se quiere la latencia más baja posible y ya se opera Redis, Redis es la mejor opción"* — es exactamente el criterio de decisión que aplica a este proyecto, y apunta a RabbitMQ.

### Dead-letter queues

- **RabbitMQ**: DLQ es una feature de primera clase, nativa del broker — enrutamiento automático a un Dead Letter Exchange según triggers declarativos (TTL expirado, nack, cola llena, máximo de reintentos), sin código adicional más allá de la configuración de la cola (ver `research-stack-mensajeria.md` sección 4).
- **Redis Streams**: no existe un concepto nativo de dead-letter queue. El patrón se **debe construir a mano**: inspeccionar el PEL con `XPENDING`, decidir cuándo un mensaje superó su máximo de reintentos, y moverlo manualmente (vía `XADD`) a un stream separado que haga de "DLQ". Es un patrón de aplicación, no una garantía del motor — más código propio, más superficie de bugs, y una responsabilidad que en RabbitMQ recae en el broker y aquí recae en el equipo de Conatel.

### Complejidad operativa

- **RabbitMQ**: nodos forman un único broker lógico; el modelo de exchanges/routing/quorum queues es más rico para enrutamiento complejo (topics como `pago.*` ya asumidos en el roadmap), pero tiene una curva de aprendizaje propia (exchanges, bindings, políticas).
- **Redis (cluster)**: distribuye datos vía hash slots fijos, con buen soporte de escalamiento horizontal, pero el escalamiento no es perfectamente lineal para todas las cargas, y los streams no se comportan igual que otras estructuras de datos de Redis bajo cluster (particionamiento de un stream entre slots requiere diseño cuidadoso si se necesita paralelismo real).
- Punto operativo adicional no cubierto por el roadmap: **licenciamiento**. Redis pasó de licencia BSD permisiva a términos "source-available" (SSPL/RSALv2) en 2024, y solo reincorporó una opción real de open source (AGPLv3) con Redis 8 en 2025 — AGPLv3 tiene implicaciones de "copyleft de red" (obliga a publicar código fuente de modificaciones si el software se ofrece sobre la red) que vale la pena revisar con el equipo legal/compliance de Conatel antes de adoptarlo como pieza central de infraestructura, dado el contexto regulado (PCI-DSS, normativa BCV) del proyecto. RabbitMQ (Mozilla Public License 2.0) no tiene esta ambigüedad.
- Conclusión de una fuente comparativa neutral: *"RabbitMQ se gana su costo operativo cuando el enrutamiento se complica o quando perder un mensaje es inaceptable; es excesivo para un caché transitorio o una lista de trabajos que se puede reconstruir sin problema"* — describe exactamente la asimetría de este caso: el bus `pago.*` no es un caché transitorio, es el mecanismo que previene doble contabilidad.

### ¿Tiene sentido usar Redis únicamente (eliminando RabbitMQ)?

**No, para el bus de eventos crítico.** La evidencia no respalda reemplazar RabbitMQ por Redis Streams en el camino `pago.*`:
- La garantía de durabilidad de RabbitMQ (fsync en quorum, confirmado antes del ACK) es más fuerte por diseño que la de Redis, que requiere configuración explícita para acercarse y aun así no iguala esa semántica.
- DLQ nativa vs. DLQ construida a mano es una diferencia operativa real, no cosmética, en un sistema donde cada mensaje fallido debe poder auditarse y reprocesar sin ambigüedad.
- El roadmap ya invierte en RabbitMQ desde T1 (contrato de eventos `pago.*`, ruta crítica ítem #4) — cambiarlo no es gratis, y la evidencia no muestra una ganancia que justifique ese costo de cambio para el componente de mayor criticidad del sistema.

**Sí tiene sentido usar Redis como complemento**, exactamente en el rol ya recomendado en `research-stack-mensajeria.md`: cache, locks distribuidos, rate limiting del API Gateway — problemas donde perder un dato no es catastrófico y la velocidad/simplicidad de Redis sí es una ventaja real. Esa recomendación se sostiene sin cambios tras esta investigación.

Fuentes: [Airbyte — Redis vs RabbitMQ](https://airbyte.com/data-engineering-resources/redis-vs-rabbitmq), [Svix — RabbitMQ vs Redis](https://www.svix.com/resources/faq/rabbitmq-vs-redis/), [OneUptime — Redis vs RabbitMQ for Job Queues](https://oneuptime.com/blog/post/2026-03-31-redis-vs-rabbitmq-for-job-queues/view), [RabbitMQ Blog — How are messages stored](https://www.rabbitmq.com/blog/2025/01/17/how-are-the-messages-stored), [AWS — Best practices for message durability RabbitMQ](https://docs.aws.amazon.com/en_us/amazon-mq/latest/developer-guide/best-practices-message-reliability.html), [Redis Licenses](https://redis.io/legal/licenses/), [Index.dev — Redis Pub/Sub vs Kafka vs RabbitMQ 2026](https://www.index.dev/skill-vs-skill/redis-pubsub-vs-kafka-vs-rabbitmq)

## 4. Recomendación final razonada

**Mantener RabbitMQ como bus de eventos `pago.*` entre Orquestador y Conciliación.** No es una confirmación reflexiva de lo que ya decía el roadmap — es la conclusión a la que lleva la evidencia al comparar objetivamente:

1. El requisito no negociable de este sistema es que **perder un evento de pago es inaceptable** (riesgo "Alta" ya identificado: doble contabilidad). RabbitMQ da esa garantía por diseño y por defecto (publisher confirms = persistido en disco + quorum). Redis Streams puede acercarse, pero exige configuración explícita y cuidadosa, y el margen de error de "configurarlo mal sin darse cuenta" es mayor porque la persistencia no es el comportamiento por defecto de Redis.
2. Dead-letter queues nativas en RabbitMQ vs. construidas a mano en Redis Streams es una diferencia de riesgo de implementación relevante para un equipo que recién empieza el proyecto (T1-T2 del roadmap) — menos superficie propia de bugs en el camino crítico de conciliación.
3. El patrón ya definido (outbox pattern en el Orquestador, ver `research-brief-pagos.md`) asume un relay que publica a un broker con garantías fuertes — cambiar a Redis Streams no elimina la necesidad del outbox ni simplifica esa pieza, así que no hay una ganancia de simplicidad neta al cambiar de broker.
4. La complicación de licenciamiento de Redis (AGPLv3 desde Redis 8) es un factor adicional, no decisivo por sí solo, pero sí relevante para un proyecto con cumplimiento PCI-DSS y normativa BCV — vale la pena que legal/compliance lo revise si en algún momento se considera usar Redis para algo más que cache/locks/rate-limiting.
5. **Redis sigue siendo la elección correcta para su rol complementario** (cache, locks distribuidos, rate limiting — ya recomendado en `research-stack-mensajeria.md`): ahí sus trade-offs (velocidad sobre durabilidad garantizada) son una ventaja, no un riesgo, porque perder un lock o un contador de rate-limit no genera una discrepancia contable.

**En una frase:** Redis Streams es una alternativa técnicamente seria y ya no debe descartarse por prejuicio ("Redis es solo cache") — pero para el bus de eventos específico de este proyecto, donde la garantía de durabilidad es el requisito dominante y no la latencia, la evidencia sigue favoreciendo a RabbitMQ. La decisión del roadmap era correcta, pero no lo era por default — esta investigación la confirma con comparación real, no por inercia.

Este archivo complementa `research-stack-mensajeria.md` (que ya recomendaba Redis en rol complementario, no como broker) — esa recomendación queda reforzada, no contradicha, por esta investigación.
