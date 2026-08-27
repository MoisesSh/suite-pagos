# Investigación — Rust vs. Django para el backend del sistema de pagos

Evaluación honesta de Rust (axum/actix-web) frente a Django/DRF (ya elegido en el roadmap) para el Orquestador de Pagos, específicamente en el camino síncrono crítico (autorizar/capturar/revertir). El objetivo es cuestionar la elección, no confirmarla por inercia.

## 1. ¿Dónde está realmente el cuello de botella de este sistema?

Este es el punto que decide casi todo lo demás, y la evidencia es clara: **un sistema de pagos como el descrito en el roadmap es predominantemente I/O-bound, no CPU-bound.**

- El camino síncrono crítico (autorizar → capturar) consiste en: recibir el request, validar/tokenizar, y **hacer una llamada de red saliente al proveedor externo** (BDV C2P, ver `research-brief-pagos.md` sección 4.1) que devuelve en cientos de milisegundos o segundos — el tiempo dominante de la transacción lo define la latencia de red hacia el banco, no el procesamiento local en el orquestador.
- Fuentes coinciden en que la mayoría de las aplicaciones web no están limitadas por la velocidad del lenguaje sino por queries a base de datos, latencia de red y llamadas a APIs de terceros — y señalan explícitamente que **los sistemas de pago son típicamente I/O-bound** por sus operaciones de base de datos y llamadas al gateway de pago externo.
- Rust gana de forma contundente cuando el cuello de botella es cómputo puro (parsing masivo, criptografía intensiva, procesamiento de streams de datos a gran volumen) o cuando se necesitan decenas de miles de conexiones concurrentes en un solo servidor. Ninguno de esos dos escenarios describe el volumen ni el patrón de carga de este proyecto en su horizonte de MVP (piloto Homologación con 5-10% de tráfico, luego Conatel en Línea).

**Conclusión de este punto: el argumento de performance de Rust no aplica al 95% del trabajo real de este sistema**, porque el tiempo no lo consume el lenguaje sino la espera de la respuesta del banco.

Fuentes: [Rustify — Rust vs Python Performance 2026](https://rustify.rs/articles/rust-vs-python-performance-2026), [Tech Insider — Python vs Rust 2026](https://tech-insider.org/python-vs-rust-2026/)

## 2. Velocidad de desarrollo vs. curva de aprendizaje del equipo

- El repo ya tiene el stack DRF montado y skills de equipo documentadas explícitamente para arquitectura Onion+feature-sliced sobre Django, patrones DRF, y testing de backend Django — es decir, **hay inversión de conocimiento ya hecha y aplicable directamente**, no una hipótesis.
- La curva de Rust es real y bien documentada, no folclore: un desarrollador nuevo típicamente tarda semanas a meses "peleando con el borrow checker" antes de que su modelo mental de ownership se alinee con lo que Rust exige — en contraste con lenguajes como Go (1-2 semanas a productivo). Esto impacta directamente el roadmap: T1 ya tiene ruta crítica ajustada (ADRs + esqueleto + integración C2P en sandbox en el mismo trimestre); introducir Rust ahí significa absorber esa curva de aprendizaje exactamente cuando el roadmap necesita velocidad.
- Evidencia de mercado: contratar Rust implica un pool de candidatos más pequeño, tiempos de ramp-up más largos para nuevas contrataciones, y un estándar de revisión de código más alto — fricción de equipo adicional para un proyecto que ya tiene squad y stack definidos.
- Cita relevante de una fuente neutral: *"si lo que estás construyendo es una REST API con backend PostgreSQL y tráfico normal, [otro lenguaje] te lleva ahí en la mitad del tiempo con un pool de candidatos diez veces más grande"* — describe con precisión el perfil de este proyecto en su fase de MVP.

Fuentes: [KORE1 — Hiring Rust Developers 2026](https://www.kore1.com/hire-rust-developers-2026/), [Sumit Agrawal — Is Rust Worth Learning in 2026](https://sumitagrawal.dev/blog/rust-programming-2026-guide/)

## 3. Ecosistema de librerías para integraciones bancarias/PCI

- El ecosistema Rust para desarrollo web maduró notablemente: Axum y Actix Web son ambos estables y usados en producción a escala, con soporte sólido de ORMs (SeaORM, Diesel, SQLx), serialización (`serde`), cliente HTTP (`reqwest`), autenticación y tracing — la infraestructura básica de un backend ya no es un problema en Rust.
- **Pero no se encontró evidencia de librerías, SDKs o tooling específico de PCI-DSS/integraciones bancarias maduro en el ecosistema Rust** — a diferencia de Python, donde el volumen de integraciones ya construidas (SDKs de pasarelas, clientes REST genéricos bien probados, herramientas de testing de contratos HTTP) es mucho mayor simplemente por antigüedad y adopción en el dominio fintech.
- Para las integraciones puntuales de este proyecto (BDV C2P, conciliación BDV — ambas APIs REST/JSON simples, ver `research-brief-pagos.md`), **ninguno de los dos lenguajes tiene una ventaja estructural real**: son llamadas HTTP con JSON, algo que tanto `requests`/DRF como `reqwest`/axum resuelven igual de bien. La ventaja de "ecosistema" para este caso específico es marginal.

Fuentes: [Yalantis — Best Rust Web Frameworks Compared](https://yalantis.com/blog/rust-web-frameworks/), [Aarambh Dev Hub — Rust Web Frameworks 2026](https://aarambhdevhub.medium.com/rust-web-frameworks-in-2026-axum-vs-actix-web-vs-rocket-vs-warp-vs-salvo-which-one-should-you-2db3792c79a2)

## 4. Una limitación real de Django que sí vale la pena documentar (aunque no cambie la recomendación)

- DRF no tiene soporte async real, y el ORM de Django tampoco es async por defecto (`await MyModel.objects.all()` falla salvo con las APIs async específicas introducidas progresivamente) — esto es una limitación concreta si en el futuro el orquestador necesitara manejar alta concurrencia de conexiones simultáneas de forma más eficiente que el modelo WSGI síncrono tradicional.
- En la práctica esto se mitiga con el patrón operativo estándar: workers WSGI (Gunicorn) suficientes para el volumen esperado, con timeouts agresivos y circuit breakers por proveedor — que es, de hecho, **la mitigación que el propio roadmap ya define como respuesta al riesgo "Alta" de latencia del Orquestador** (timeouts + circuit breaker + confirmación async con estado "pendiente" en vez de bloquear al usuario). Es decir, el roadmap ya diseñó alrededor de esta limitación sin necesitar cambiar de lenguaje ni de framework.
- Si en un futuro lejano el volumen de conexiones concurrentes creciera órdenes de magnitud (miles de conexiones simultáneas sostenidas en un solo proceso), ahí sí valdría reconsiderar — pero no es el perfil de carga de este MVP ni de los próximos 1-2 años según el roadmap.

Fuentes: [Django Docs — Asynchronous support](https://docs.djangoproject.com/en/6.0/topics/async/), [Loopwerk — Async Django: a solution in search of a problem?](https://www.loopwerk.io/articles/2025/async-django-why/)

## 5. Recomendación honesta

**Django/DRF es la elección correcta para este proyecto en su horizonte actual — no por inercia del roadmap, sino porque la evidencia técnica y organizacional apunta en la misma dirección:**

1. El cuello de botella real del sistema es I/O de red hacia proveedores externos (bancos, pasarelas), no cómputo — el escenario exacto donde la ventaja de performance de Rust deja de importar en la práctica.
2. El equipo ya tiene skills y arquitectura (Onion + feature-sliced) aplicadas y documentadas sobre Django — cambiar de lenguaje en T1 significaría reconstruir esa base de conocimiento exactamente cuando el roadmap exige velocidad para cumplir la ruta crítica.
3. El ecosistema de librerías no da una ventaja decisiva a ninguno de los dos lados para las integraciones concretas de este proyecto (APIs REST/JSON simples de BDV).
4. La limitación conocida de DRF (no-async) ya está mitigada por el propio diseño de resiliencia del roadmap (timeouts, circuit breakers, confirmación asíncrona) — no requiere cambiar de stack para resolverse.

**Dónde Rust sí tendría sentido, si el proyecto creciera en esa dirección** (no como recomendación para el MVP, sino como nota honesta para el futuro): un componente aislado, muy específico y con cuello de botella de cómputo real — por ejemplo, un motor de matching/reconciliación de alto volumen si Conciliación llegara a procesar millones de movimientos por lote con comparación intensiva, o un servicio de validación criptográfica de alta frecuencia. El patrón de mercado emergente para esto no es "reescribir todo en Rust", sino un **híbrido Python+Rust**: mantener la orquestación y el 95% del sistema en Python/Django, y extraer solo el componente de cómputo intensivo a Rust, expuesto vía FFI (PyO3/maturin) o como microservicio aparte. Esto no es necesario para el MVP descrito en el roadmap, pero es la opción a evaluar si el volumen de Conciliación T3-T4 llegara a un punto donde el matching se vuelva medible y realmente CPU-bound — decisión a tomar con datos reales de esa etapa, no de forma anticipada.

Fuente adicional: [Medium — Revisiting Rust in 2026 (hybrid Python+Rust pattern)](https://mdwdotla.medium.com/revisiting-rust-in-2026-ae8720cc7f2c)
