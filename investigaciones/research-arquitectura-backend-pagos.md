# Research — Onion + Screaming + Feature-Sliced en Django/DRF para el Orquestador de Pagos (2026)

Contexto: `suit-backend` ya tiene la skill `arquitectura-onion-feature-scream`, que documenta `apps/{feature}/{domain,application,infrastructure,api}` heredado de un proyecto hermano de Conatel. El roadmap ya nombra los slices `apps/autorizacion`, `apps/conciliacion`, `apps/tokenizacion`. Esta nota valida esa decisión contra evidencia externa 2025-2026 y responde a las tres preguntas planteadas.

---

## 1. ¿Es `apps/{feature}/{domain,application,infrastructure,api}` la forma "correcta" en 2026?

**Sí — es el patrón dominante, con matices.** No hay un único estándar oficial en la comunidad Django (a diferencia de, por ejemplo, Rails con su convención fuerte), pero converge fuerte evidencia hacia lo mismo que ya tienen:

- La comunidad diferencia **Screaming Architecture** (la estructura de carpetas debe gritar el dominio del negocio, no el framework — "un sistema de contabilidad debe gritar 'contabilidad', no 'Spring Boot'") de **Hexagonal/Onion** (separación de capas por dependencia: domain → application → infrastructure/adapters). Son ortogonales y se combinan: Screaming decide el *eje horizontal* (por feature/bounded context), Onion decide el *eje vertical* dentro de cada feature (capas). Esto es exactamente lo que ya hace la skill. [Screaming Architecture — Milan Jovanović](https://milanjovanovic.tech/blog/screaming-architecture), [Frameworks, Architecture & Screaming Architecture — Florian Krämer](https://florian-kraemer.net/software-architecture/2025/03/30/Frameworks-Architecture-and-screaming-Architecture.html)
- Un análisis reciente de folder structures para hexagonal (feb-2026) recomienda explícitamente: **feature primero, capas dentro de cada feature** — "Los splits horizontales encontrarán su lugar *dentro* de cada slice vertical de negocio, si es útil" — y advierte contra anidar demasiado ("too much nesting can impede navigation"). También sugiere diferenciar adapters *inbound* (presentación/API) de *outbound* (persistencia/proveedores externos) en vez de mezclarlos en una sola carpeta `infrastructure`. [codeartify.substack.com — Folder Structures](https://codeartify.substack.com/p/folder-structures)
- Ejemplos concretos de Django con esta misma forma (`domain/`, `application/`, `infrastructure/`, `migrations/` por app) siguen apareciendo en 2025-2026 como el patrón de facto para DDD/Clean Architecture en DRF. [Hexagonal Architecture with Django — André Rufino, feb-2026](https://medium.com/@andremrufino/hexagonal-architecture-with-django-fundamentals-and-comparison-with-clean-architecture-38d74608d961), [drf_api_project_template (GitHub)](https://github.com/onlythompson/drf_api_project_template)

**Matiz importante — no es la única corriente viva.** Existe una corriente opuesta, activamente promovida en 2025-2026 por practicantes Django experimentados (DabApps, 15+ años, 100+ proyectos en producción): **Django RAPID Architecture**, que rechaza deliberadamente domain/application/infrastructure como capas explícitas y en su lugar usa "horizontal encapsulation" ligera (`readers/`, `actions/`, `interfaces/`, modelos delgados) por considerar que el peso de DDD completo no paga su costo en la mayoría de proyectos Django. [Django RAPID Architecture](https://www.django-rapid-architecture.org/structure/), [DabApps — Introducing RAPID](https://www.dabapps.com/insights/introducing-django-rapid-architecture/)

**Conclusión para este proyecto:** dado que el Orquestador tiene invariantes de dominio no triviales (máquina de estados de pago, idempotencia, outbox, futura frontera con un motor Rust vía puertos), el peso extra de Onion completo está justificado — RAPID es más apto para CRUDs sin lógica de dominio densa. La estructura actual de la skill **no necesita cambiar**. Sí vale adoptar la sugerencia de separar adapters inbound/outbound dentro de `infrastructure/` si esa carpeta empieza a mezclar el repositorio de persistencia con el cliente HTTP del proveedor de pago — evitar que `infrastructure/` se vuelva un cajón de sastre.

---

## 2. Consideraciones adicionales de estructura para el dominio de pagos específicamente

La literatura de DDD aplicada a fintech (Airwallex Engineering, Trio.dev, y guías de diseño de sistemas de pago) converge en patrones que **refuerzan, no contradicen**, la estructura ya elegida:

- **Bounded contexts en pagos deben trazarse por responsabilidad de negocio, no por conveniencia técnica**: "Payments should not manage fraud rules; lending should not care how identity checks happen." Aplicado aquí: `autorizacion` (síncrono, cobro), `conciliacion` (async, ledger/matching) y `tokenizacion` (delegado a bóveda PCI externa) son fronteras de negocio genuinas, no un corte arbitrario de capas técnicas — coincide con lo ya definido en `research-brief-pagos.md`. [Trio.dev — DDD in Fintech](https://trio.dev/domain-driven-design-in-fintech/)
- **Authorize-then-capture como separación explícita de conceptos de dominio**, no solo de estados: la práctica estándar es modelar `authorize` (reserva) y `capture` (cobro real) como operaciones/eventos distintos, con una máquina de estados estricta (`INITIATED → AUTHORIZED → CAPTURED/FAILED/REFUNDED`) — esto ya está capturado en `research-brief-pagos.md` §2. Confirma que el agregado de pago en `apps/autorizacion/domain` debe modelar authorize/capture/void/refund como transiciones de un mismo agregado con invariantes explícitas, no como un campo de estado plano.
- **El ledger de doble entrada vive fuera del contexto de autorización** — es su propio bounded context (aquí, `conciliacion`), append-only y balanceado por constraint de DB, nunca mutado directamente por el módulo de cobro. Esto valida que `LedgerBalancePort` NO debería vivir dentro de `apps/autorizacion` sino ser consumido por conciliación, o si autorización necesita *leer* saldo/ledger vía puerto, debe ser una dependencia de solo lectura hacia afuera del bounded context, nunca escritura directa.
- **Los puertos hacia el motor Rust (`MatchingEnginePort`, `LedgerBalancePort`) encajan naturalmente en `application/ports.py` (interfaces) + `infrastructure/adapters/rust_*.py` (implementación gRPC/FFI/HTTP) de cada slice que los consuma** — es la misma mecánica que ya usan para `PaymentProviderPort`. No requieren una carpeta nueva; son puertos de infraestructura como cualquier otro adaptador de salida, solo que el "proveedor externo" es un servicio interno de alto rendimiento en vez de un banco. La única consideración extra: si `MatchingEnginePort` es usado por `conciliacion` y `LedgerBalancePort` es leído (no escrito) por `autorizacion`, cada slice declara su propia interfaz de puerto — no se comparte una carpeta `ports/` global entre slices, para no crear acoplamiento cruzado entre bounded contexts.
- **Eventos de dominio como mecanismo de comunicación entre slices**: el patrón estándar en pagos es que un cambio de estado del agregado dispare un evento de dominio (ej. `PaymentAttemptCapturedEvent`) que otros bounded contexts consumen — coincide exactamente con el outbox pattern ya definido en `research-outbox-vs-cdc.md` / `research-brief-pagos.md`. Confirma que el outbox pertenece al agregado de pago dentro de `apps/autorizacion`, no a un módulo aparte. [DDD Modeling Payments — Airwallex Engineering (vía snippets de búsqueda, artículo con 403 al fetch directo)](https://medium.com/airwallex-engineering/domain-driven-design-practice-modeling-payments-system-f7bc5cf64bb3)

---

## 3. ¿`apps/autorizacion` es apropiado como primer módulo (registro de apps/dominios + agregado de pago + outbox, todo síncrono), o conviene dividirlo ya?

**No dividir todavía — mantenerlo como un solo slice, con vigilancia activa de señales de sobrecrecimiento.** Evidencia:

- La corriente 2025 dominante en arquitectura de sistemas (incluso citando el giro de Shopify/Basecamp/Notion de vuelta a monolitos modulares) es **"empieza con un módulo, extrae cuando el dolor sea específico y documentado"** — la modularización prematura tiene un costo real porque el diseño inicial rara vez captura las abstracciones correctas, y termina forzando refactors de las interfaces entre módulos. [Balancing Microservices and Monolithic Architectures](https://arxiv.org/pdf/2607.03898), búsqueda "modular monolith 2025"
- Los tres elementos propuestos para `apps/autorizacion` (registro de apps/dominios, agregado de pago, outbox) **son cohesivos, no dispares**: todos cambian juntos porque todos son necesarios para completar una sola operación de negocio ("cobrar de forma síncrona con garantía de idempotencia y publicación confiable del resultado"). Esto es justo el criterio positivo para *no* separar: "¿cambia este código junto? ¿lo usa el mismo caso de uso end-to-end?" — si la respuesta es sí, es un solo módulo. [Refactoring Overgrown Bounded Contexts — Milan Jovanović](https://www.milanjovanovic.tech/blog/refactoring-overgrown-bounded-contexts-in-modular-monoliths)
- El registro de apps/dominios (quién puede llamar al Orquestador, con qué API key) es **metadata de autorización de acceso** al servicio, no un dominio de negocio propio con su propia máquina de estados — no alcanza la vara de "bounded context separado"; es razonable que viva como un sub-paquete dentro de `apps/autorizacion/domain` (o incluso como una app Django puramente técnica de auth si se prefiere, pero no un slice DDD propio).

**Señales concretas para saber cuándo SÍ dividir** (aplicar como checklist continuo, no solo al inicio), según la misma fuente:
1. Miedo a tocar el código porque todo está interconectado.
2. Clases/servicios de 1000+ líneas o que hacen operaciones no relacionadas entre sí (ej. un mismo servicio que registra apps, autoriza pagos, Y gestiona el outbox de forma acoplada e inseparable).
3. La misma entidad reutilizada para 4+ casos de uso no relacionados.
4. Partes del código que cambian en cadencias claramente distintas (ej. si el registro de apps/dominios empieza a evolucionar por requisitos de compliance/onboarding de partners a un ritmo muy distinto del agregado de pago).
5. Vocabulario de negocio distinto entre las partes (si los stakeholders empiezan a hablar de "gestión de partners" como algo separado de "procesar un cobro").

**Estrategia de extracción recomendada si aparecen esas señales más adelante:** extraer primero las partes de "bajo riesgo" (ej. registro de apps/dominios, que es efectivamente un efecto lateral/config, no el núcleo transaccional) y reemplazar las llamadas directas por eventos de dominio — no seguir apilando dependencias directas dentro del mismo slice. [Refactoring Overgrown Bounded Contexts — Milan Jovanović](https://www.milanjovanovic.tech/blog/refactoring-overgrown-bounded-contexts-in-modular-monoliths)

**Conclusión:** `apps/autorizacion` con registro de apps/dominios + agregado de pago + outbox, todo síncrono, es la decisión correcta para el día 1. Dividir ahora sería modularización prematura sin dolor documentado. Revisar contra el checklist de arriba en cada retro de arquitectura, no solo una vez.

---

## Fuentes consultadas

- [Screaming Architecture — Milan Jovanović](https://milanjovanovic.tech/blog/screaming-architecture)
- [Frameworks, Architecture & Screaming Architecture — Florian Krämer (mar-2025)](https://florian-kraemer.net/software-architecture/2025/03/30/Frameworks-Architecture-and-screaming-Architecture.html)
- [Hexagonal Architecture with Django — André Rufino (feb-2026)](https://medium.com/@andremrufino/hexagonal-architecture-with-django-fundamentals-and-comparison-with-clean-architecture-38d74608d961)
- [Towards Hexagonal Architecture - Folder Structure — codeartify.substack.com](https://codeartify.substack.com/p/folder-structures)
- [drf_api_project_template (GitHub) — DDD/Clean Architecture template para DRF](https://github.com/onlythompson/drf_api_project_template)
- [Django RAPID Architecture — DabApps](https://www.django-rapid-architecture.org/structure/) / [Introducing Django RAPID Architecture](https://www.dabapps.com/insights/introducing-django-rapid-architecture/)
- [Domain-Driven Design in Fintech — Trio.dev](https://trio.dev/domain-driven-design-in-fintech/)
- [Domain-driven design practice — Modelling the payments system — Airwallex Engineering](https://medium.com/airwallex-engineering/domain-driven-design-practice-modeling-payments-system-f7bc5cf64bb3) (contenido vía resultados de búsqueda; fetch directo bloqueado con 403)
- [Refactoring Overgrown Bounded Contexts in Modular Monoliths — Milan Jovanović](https://www.milanjovanovic.tech/blog/refactoring-overgrown-bounded-contexts-in-modular-monoliths)
- [Balancing Microservices and Monolithic Architectures (arXiv, 2026)](https://arxiv.org/pdf/2607.03898)
