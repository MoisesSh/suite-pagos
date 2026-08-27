# Investigación — Schemas separados vs. bases de datos separadas en Postgres (database-per-service)

Evaluación de si "dos schemas en la misma instancia Postgres" es un compromiso razonable para implementar el patrón database-per-service entre Orquestador y Conciliación (ya recomendado en `research-brief-pagos.md`), o si rompe el principio que se busca proteger.

## 1. Diferencia fundamental: qué aísla cada uno

- Una **base de datos** en Postgres es un contenedor aislado con sus propias conexiones, su propio espacio de nombres completo, y (críticamente) es la unidad atómica de backup/restore nativo de Postgres.
- Un **schema** es solo un namespace *dentro* de una base de datos — organiza tablas/vistas/funciones, pero **comparte instancia de proceso, memoria compartida, catálogo del sistema, y ciclo de vida del motor** con todos los demás schemas de esa misma base de datos.
- Postgres no soporta queries cross-database de forma nativa (sin `dblink`/`postgres_fdw`) — así que si en algún punto se necesitaran queries que crucen el límite Orquestador/Conciliación, solo los schemas lo permiten de forma directa. **Pero esto es exactamente lo que el diseño de este proyecto busca evitar**: el roadmap y `research-brief-pagos.md` ya establecen que la única frontera entre ambos servicios debe ser el bus de eventos, no una consulta directa a datos del otro servicio — así que esta "ventaja" de los schemas es, para este proyecto específico, una tentación a evitar, no un beneficio real.

Fuentes: [QueryGlow — Schema vs Database in PostgreSQL](https://queryglow.com/blog/schema-vs-database-postgresql), [Reintech — PostgreSQL in Microservices Architecture](https://reintech.io/blog/postgresql-microservices-architecture)

## 2. Aislamiento real de fallos — el punto que más importa para este proyecto

Este es el criterio decisivo dado el requisito explícito del roadmap: *"una conciliación lenta o un banco caído nunca bloqueen un cobro"* (sección 01 del roadmap, y Fig. 1 — "el Orquestador nunca llama a Conciliación de forma directa").

- **Con bases de datos separadas** (instancias/procesos Postgres distintos, aunque estén en el mismo host físico o en hosts distintos): un pico de carga, un lock prolongado, una tabla corrupta, un vacuum agresivo, o un crash del proceso Postgres de Conciliación **no afecta al proceso Postgres del Orquestador** — son procesos independientes con su propia memoria compartida (`shared_buffers`), sus propios checkpoints, su propio WAL. Esto es aislamiento real a nivel de motor.
- **Con schemas en la misma instancia**: ambos servicios comparten el mismo proceso `postgres`, el mismo `shared_buffers`, el mismo conjunto de conexiones máximas (`max_connections`), el mismo WAL, y el mismo ciclo de vacuum/checkpoint. Un query pesado de Conciliación (ej. un reproceso batch de 6 meses de historial, mencionado explícitamente como caso de uso en el roadmap: *"si mañana la conciliación necesita reprocesar 6 meses de historial, lo hace releyendo el log de eventos"*) puede consumir recursos de I/O, CPU y locks del catálogo compartido que sí impactan la latencia del Orquestador — **exactamente el escenario que el roadmap dice que no debe poder pasar**.
- Una fuente lo resume con precisión: base de datos separada garantiza el nivel más estricto de separación entre los datos gestionados por microservicios distintos, y es la forma más simple de escalar el almacenamiento de cada microservicio de forma independiente en caso de crecimiento significativo — además de facilitar backup/restore y cambios de esquema de un servicio sin impacto en el otro.

**Veredicto de este punto: bases de datos separadas dan aislamiento de fallos real; schemas separados dan aislamiento lógico/organizacional, pero comparten el mismo dominio de fallo físico.** Para un sistema donde el requisito explícito es que Conciliación nunca pueda degradar al Orquestador, esto no es un matiz — es la diferencia entre cumplir o no cumplir el requisito de diseño ya declarado.

Fuentes: [DEV Community — Does your microservice deserve its own database?](https://dev.to/lbelkind/does-your-microservice-deserve-its-own-database-np2), [OpenSourceDB — PostgreSQL Database Choices](https://opensource-db.com/postgresql-database-choices-shared-vs-separate-for-microservices/)

## 3. Garantía de que no haya JOIN/FK cruzada accidental

- Con **bases de datos separadas**, es estructuralmente imposible declarar una FK o hacer un JOIN entre una tabla del Orquestador y una de Conciliación — Postgres simplemente no lo permite entre bases de datos distintas sin `dblink`/`postgres_fdw` explícitamente instalado y configurado. **La restricción arquitectónica está impuesta por el motor, no por disciplina del equipo.**
- Con **schemas en la misma base de datos**, un JOIN o FK cruzada entre schemas es técnicamente trivial (`SELECT * FROM orquestador.pagos JOIN conciliacion.movimientos ...`) — no hay ninguna barrera técnica que lo impida, solo convención de equipo y revisión de código. Esto es precisamente el tipo de "atajo" que un desarrollador bajo presión de fecha puede tomar sin mala intención, y que rompe silenciosamente el principio de database-per-service sin que ninguna herramienta lo detecte automáticamente.
- Riesgo adicional documentado: usar `SET search_path` para cambiar de schema dinámicamente genera un enrutamiento no determinístico de queries — la recomendación encontrada es usar un connection pool dedicado por servicio/app en vez de depender de `search_path`, lo cual en la práctica ya empieza a parecerse operativamente a tener bases separadas, sin obtener el beneficio real de aislamiento de fallos.

**Veredicto: solo las bases de datos separadas convierten el principio "no cruzar datos entre servicios" en una garantía técnica; con schemas, es una regla de disciplina de equipo, más frágil ante el paso del tiempo y la rotación de desarrolladores.**

Fuentes: [DEV.to — Best Practices for Multiple Schemas](https://dev.to/haraf/best-practices-for-handling-multiple-schemas-in-the-same-database-across-applications-with-1bkp), [Medium — Schema vs Database for Platform Teams](https://medium.com/@sudhir.bvk07/schema-vs-database-whats-the-right-choice-for-platform-teams-running-workflow-orchestrations-bbf4bccffe79)

## 4. Complejidad operativa: backups, failover, connection pooling

Aquí sí hay un costo real del lado de "bases separadas" que hay que reconocer con honestidad, no minimizar:

- **Backups**: con bases separadas, cada servicio tiene su propio ciclo de backup/restore independiente (ventaja para RPO/RTO diferenciado — Conciliación podría tener una política de backup distinta a Orquestador si su criticidad de recuperación es distinta). Con schemas, un solo backup de la instancia cubre ambos, más simple operativamente pero acopla las políticas de recuperación de ambos servicios entre sí.
- **Failover**: con instancias separadas, cada una puede tener su propia topología de alta disponibilidad (réplicas, failover automático) ajustada a su criticidad — el Orquestador (camino síncrono crítico, SLO 99.9% ya definido en el roadmap) puede justificar una topología de HA más agresiva/costosa que Conciliación (async, tolera más downtime). Con una sola instancia compartida, ambos servicios quedan atados al mismo SLA de disponibilidad de infraestructura, lo cual es exactamente lo opuesto a la razón de ser de separar los servicios.
- **Connection pooling (PgBouncer)**: cada instancia separada necesita su propio pool, lo cual es más piezas de infraestructura a desplegar y monitorear — pero también evita que ambos servicios compitan por el mismo límite de `max_connections` del mismo pool. Un patrón real documentado (schema-per-tenant en sistemas multi-tenant) confirma que aunque las conexiones de un tenant no impactan directamente a otro con schemas separados, sí consumen slots del mismo pool compartido — mismo problema aplicado a este caso: un pico de conexiones de Conciliación puede agotar el pool compartido y dejar sin conexiones disponibles al Orquestador.
- **Costo de infraestructura**: dos instancias significa más procesos corriendo (más memoria base reservada por cada instancia de Postgres, más contenedores/VMs a mantener, más superficie de monitoreo) — el argumento más legítimo a favor de schemas es eficiencia de recursos en etapas tempranas de bajo volumen.

Fuentes: [Crunchy Data — Postgres at Scale: Running Multiple PgBouncers](https://www.crunchydata.com/blog/postgres-at-scale-running-multiple-pgbouncers), [DZone — PgBouncer at Scale: Multi-Tenant Postgres](https://dzone.com/articles/database-connection-pooling-at-scale-pgbouncer-mul)

## 5. Consideración adicional específica de este proyecto: alcance PCI-DSS

- El roadmap fija como mitigación explícita al riesgo de "ampliación no controlada del alcance PCI-DSS": tokenización desde el día 1, con revisión de alcance trimestral. Aunque ni Orquestador ni Conciliación almacenan PAN (solo referencias de token, ver `research-brief-pagos.md` sección 4.3), **el alcance de auditoría PCI-DSS se define por segmentación real, no por convención lógica** — un auditor QSA evaluando el alcance de "qué sistemas tocan o están cerca de datos de tarjeta" tiende a tratar con más escepticismo una única instancia compartida (aunque los datos sensibles no estén ahí) que dos instancias con segmentación de red y de infraestructura demostrable. No es una descalificación automática de los schemas, pero sí un argumento adicional a favor de bases separadas en un proyecto que ya tiene auditoría PCI-DSS formal planeada para T4.
- Nota: la guía oficial de PCI-DSS aclara que la segmentación no es un requisito obligatorio en sí misma, sino una herramienta para *reducir* alcance — lo cual reafirma que la elección aquí es estratégica (facilitar una auditoría más simple y con menor alcance) y no una exigencia normativa dura por sí sola.

Fuentes: [SecurityMetrics — Understanding PCI DSS Scope and Segmentation](https://www.securitymetrics.com/blog/pci-dss-supplemental-guide-scope-understanding-pci-dss-scope-and-segmentation), [PCI Security Standards Council — Guidance for Scoping and Segmentation](https://listings.pcisecuritystandards.org/documents/Guidance-PCI-DSS-Scoping-and-Segmentation_v1.pdf)

## 6. ¿"Dos schemas en la misma instancia" es un compromiso razonable o rompe el principio?

**Rompe el principio, no es un compromiso equivalente — con honestidad, esto es el hallazgo central de esta investigación.** El patrón database-per-service existe específicamente para lograr dos cosas que el roadmap ya declaró como requisitos explícitos: (a) que la caída/degradación de un servicio no afecte al otro, y (b) que no exista acoplamiento de datos entre servicios. Los schemas en la misma instancia comprometen ambas garantías:

- (a) se rompe porque ambos servicios comparten el mismo proceso, memoria y recursos físicos de Postgres — un servicio lento sí puede degradar al otro, contradiciendo la Fig. 1 del roadmap.
- (b) se rompe porque nada a nivel de motor impide un JOIN/FK cruzada — la separación depende de disciplina de equipo, no de una garantía técnica.

Es un patrón legítimo y usado en la industria — pero típicamente como una decisión consciente de **multi-tenancy** (muchos tenants pequeños y homogéneos compartiendo infraestructura por eficiencia de costos) o como paso intermedio de migración, no como la forma de implementar dos servicios con requisitos de aislamiento de fallos explícitamente distintos como Orquestador y Conciliación.

## 7. Recomendación final

**Usar dos bases de datos Postgres completamente separadas (instancias/procesos distintos), no dos schemas en la misma instancia**, para el patrón database-per-service entre Orquestador y Conciliación. Esta recomendación refuerza, sin cambios, lo que ya estaba implícito en `research-brief-pagos.md` sección 2 ("Database-per-service — separación estricta... Ningún JOIN cross-servicio a nivel de DB").

Justificación resumida:
1. El requisito de diseño explícito del roadmap (una caída/degradación de Conciliación no debe afectar al Orquestador) solo se cumple con procesos Postgres físicamente separados — con schemas, ambos comparten el mismo dominio de fallo.
2. La prohibición de JOIN/FK cruzada solo es una garantía técnica real con bases separadas; con schemas es una convención que se erosiona con el tiempo.
3. Permite políticas de HA, backup y connection pooling diferenciadas según la criticidad real de cada servicio (Orquestador con SLO 99.9%, Conciliación con tolerancia mayor a downtime) — con una instancia compartida, ambos quedan atados al mismo nivel de servicio de infraestructura.
4. Facilita una historia de segmentación más limpia de cara a la auditoría PCI-DSS formal ya planeada para T4.
5. El costo real de esta recomendación (más infraestructura, más piezas a operar) es aceptable en este proyecto: no es un sistema de decenas de microservicios pequeños donde la eficiencia de recursos sería el factor dominante — son solo dos servicios de datos, con requisitos de aislamiento ya declarados como críticos por el propio roadmap. El ahorro operativo de compartir instancia no compensa el riesgo que introduce en el componente donde el roadmap mismo dice que ese riesgo es inaceptable.
