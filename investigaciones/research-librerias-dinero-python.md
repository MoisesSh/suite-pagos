# Investigación — Librerías Python para manejo de dinero (Django/DRF)

**Aclaración de alcance recibida**: el proyecto NO hará conversión de moneda ni cálculo de tasas de cambio — se descarta la preocupación sobre normativa BCV de redondeo de conversión mencionada en `research-manejo-dinero-bd.md` sección 3. VES es la moneda activa; USD queda como campo reservado en la API de BDV (`cuentaDivisa`) pero sin lógica de conversión en este sistema. Esto cambia el criterio de evaluación: ya no se necesita una librería que resuelva *aritmética entre monedas distintas* — el problema real a resolver es más acotado: evitar float, comparación segura de decimales, aritmética exacta, y (opcionalmente) representar moneda+monto como una sola unidad en el modelo/API.

Se evaluaron las librerías pedidas más las que aparecieron como relevantes en la búsqueda.

## 1. `django-money` (djmoney)

- **Qué es**: extensión de Django que añade `MoneyField` a modelos y formularios, usando `py-moneyed` internamente como implementación de `Money`/`Currency`. Un solo `MoneyField` en el modelo crea **dos columnas reales en la base de datos** (monto decimal + código de moneda), expuestas como un único objeto `Money` en Python vía un descriptor (`MoneyFieldProxy`).
- **Mantenimiento**: activo. Última versión estable en el índice de PyPI es una serie 3.6.x (con beta reciente, 3.6.0b3); el proyecto está migrando su repositorio principal a Codeberg (anunciado junio 2026) — señal de comunidad viva, no de abandono, aunque vale la pena verificar al momento de instalar que la dependencia apunte al nuevo home si el traslado ya se completó.
- **Integración con el ORM de Django**: nativa y de primera clase — es exactamente su propósito. `MoneyField` hereda comportamiento de `DecimalField` para la parte numérica.
- **Value Object moneda+monto**: sí, de forma explícita y es su característica central — `Money` encapsula monto y moneda como una sola unidad manipulable (suma, comparación, formateo), evitando el error de "operar un monto sin saber en qué moneda está" mencionado como trampa en `research-manejo-dinero-bd.md` sección 5.
- **Compatibilidad con DRF**: existe soporte oficial (`djmoney.contrib.django_rest_framework`, registra un `MoneyField` de serializer si `rest_framework` está instalado), pero con matices documentados en issues abiertos del propio repo: el campo de serializer generado automáticamente por un `ModelSerializer` puede marcarse como no-requerido incorrectamente (issue #240), y ha habido pedidos de mejor soporte DRF nativo (issue #550) — es decir, **funciona, pero no es tan pulido como el resto de la librería**, y probablemente requiera declarar el campo del serializer explícitamente en vez de confiar en la generación automática.
- **Dado que este proyecto no hace conversión de moneda**, el valor agregado real de esta librería se reduce a: (a) el value object `Money` como ergonomía de código, y (b) el patrón de dos columnas (monto + moneda) ya recomendado de todas formas en `research-brief-pagos.md`. No aporta nada respecto a lógica de conversión, que es su fuerza principal en otros proyectos.

Fuentes: [GitHub — django-money/django-money](https://github.com/django-money/django-money), [PyPI — django-money](https://pypi.org/project/django-money/), [GitHub issue #179 — DRF support](https://github.com/django-money/django-money/issues/179), [GitHub issue #240 — MoneyField not required](https://github.com/django-money/django-money/issues/240), [GitHub issue #550 — proper DRF support](https://github.com/django-money/django-money/issues/550)

## 2. `py-moneyed`

- **Qué es**: la librería base de `Money`/`Currency` que `django-money` usa internamente — se puede usar de forma independiente, sin Django, si solo se necesita el value object en la capa de dominio (coherente con la arquitectura Onion del roadmap, donde el dominio no debería depender de Django).
- **Mantenimiento**: versión estable 3.0, publicada hace aproximadamente 3 años respecto a la fecha de esta investigación (ago-2026) — **ritmo de releases notablemente más lento** que `django-money`. El changelog reciente muestra actividad de mantenimiento real pero de bajo volumen (limpieza de código deprecado, type hints, automatización de publicación) — no abandonada, pero tampoco con el mismo nivel de actividad.
- **Integración con el ORM de Django**: ninguna nativa — es agnóstica de framework por diseño (esa es su ventaja si se quiere en el dominio puro, y su desventaja si se busca algo listo para usar con el ORM sin capa intermedia).
- **Value Object moneda+monto**: sí, es su propósito central (`Money(amount, currency)`).
- **Compatibilidad con DRF**: ninguna oficial. Existe un paquete de terceros separado, `rest-framework-money-field`, que sí serializa objetos `Money` de `py-moneyed` a JSON con `amount`/`currency` anidados — pero es una dependencia adicional, de un mantenedor distinto, que hay que evaluar por separado (no se encontró evidencia de actividad reciente robusta en la búsqueda).

Fuentes: [GitHub — py-moneyed/py-moneyed](https://github.com/py-moneyed/py-moneyed), [py-moneyed Changelog](https://py-moneyed.readthedocs.io/en/latest/history.html), [PyPI — rest-framework-money-field](https://pypi.org/project/rest-framework-money-field/)

## 3. `dinero` (dinero-python)

- **Qué es**: librería inspirada en `dinero.js`, enfocada en dar una API "más limpia e intuitiva" sobre `Decimal` para crear, manipular, testear y formatear valores monetarios — su propia documentación reconoce explícitamente que "`Decimal` de la librería estándar alcanza para cálculos monetarios básicos", posicionándose como una capa de ergonomía sobre `Decimal`, no como un reemplazo estructural.
- **Mantenimiento**: versiones tempranas (0.1.x–0.2.x observadas) — **señal de proyecto joven/inmaduro**, no de una librería con historial largo de producción como `django-money`.
- **Integración con el ORM de Django**: ninguna — no tiene noción de Django ni de campos de modelo.
- **Value Object moneda+monto**: parcial — da soporte a más de 100 monedas y aritmética precisa, pero está más orientada a operaciones puntuales sobre un valor que a modelar el par moneda+monto como una unidad persistente en un esquema de datos.
- **Compatibilidad con DRF**: ninguna, ni oficial ni de terceros encontrada en la búsqueda.
- **Veredicto**: no recomendable para este proyecto — inmadurez de versión y ausencia total de integración con el stack (Django/DRF) la dejan por debajo de las otras opciones sin una ventaja compensatoria clara.

Fuente: [Dinero docs](https://wilfredinni.github.io/dinero/), [PyPI — dinero](https://pypi.org/project/dinero)

## 4. Otras opciones encontradas (mención breve)

- **`stockholm`**: librería moderna, con buena cobertura de tests (100% declarado) y soporte nativo para transportes tipo GraphQL/Protocol Buffers — interesante si el proyecto usara esos protocolos, pero **no es el caso** (el roadmap define REST/GraphQL solo como opción de gateway, y las integraciones reales son REST/JSON con BDV). Sin integración Django/DRF documentada.
- **`py-money` (vimeo) / `real-money` (fork)**: el original de Vimeo aparece sin mantenimiento activo; el fork `real-money` es la versión recomendada por la comunidad en su lugar. Sin integración Django/DRF. Aporta una validación estricta de decimales por moneda (ej. rechaza `3.678 USD` porque USD solo admite 2 decimales) — una garantía interesante pero que se puede replicar con una validación de dominio propia sin añadir una dependencia externa de mantenimiento incierto.
- **`t-money`**: `dataclass` simple de Python 3.10+ para pares monto/moneda con aritmética que valida que ambos operandos sean de la misma moneda — minimalista, pero sin tracción ni evidencia de adopción amplia, y sin integración Django/DRF.

Ninguna de estas tres aporta algo que justifique evaluarla más a fondo frente a `django-money` para este proyecto específico.

Fuentes: [GitHub — kalaspuff/stockholm](https://github.com/kalaspuff/stockholm), [GitHub — Sighery/real-money](https://github.com/Sighery/real-money), [PyPI — t-money](https://pypi.org/project/t-money)

## 5. Recomendación concreta

**No hace falta ninguna librería externa de "money" para este proyecto. Alcanza con `Decimal` nativo de Python bien disciplinado, más una convención propia y explícita de moneda+monto en el modelo y en los serializers de DRF.**

Razonamiento:

1. **El problema que estas librerías resuelven mejor que `Decimal` puro es la aritmética y comparación *entre monedas distintas* (evitar sumar USD + VES por error, conversión, formateo multi-moneda)**. Con la aclaración de alcance de que este proyecto **no hace conversión de moneda**, ese es exactamente el problema que ya no existe aquí. Lo que sí sigue siendo necesario — evitar float, comparación exacta, aritmética exacta — **ya lo resuelve `Decimal` de la librería estándar de Python de forma completa y sin dependencias adicionales**, como ya se documentó en `research-manejo-dinero-bd.md`.
2. **`django-money` es la opción técnicamente más sólida de las evaluadas** (mantenimiento activo, integración ORM nativa, DRF soportado aunque con matices) — si el equipo decide que la ergonomía de tener `Money` como un objeto único en el código de dominio vale la pena, es la elección correcta entre las alternativas. Pero es una dependencia adicional para resolver un problema (par moneda+monto) que se puede modelar igual de bien con dos campos explícitos en el modelo (`amount: DecimalField`, `currency: CharField` con choices/catálogo, ya recomendado en `research-brief-pagos.md` sección 4.3) y una función de validación de dominio simple que garantice que ambos siempre viajan juntos.
3. **Costo de no usar la librería**: ninguno significativo dado el alcance acotado — el catálogo de monedas de este proyecto es pequeño (VES activo, USD reservado sin lógica de conversión), no hay aritmética compleja entre monedas, y el patrón "dos columnas, una función de validación" es simple de mantener con disciplina de código y tests, sin añadir una dependencia externa cuya API hay que aprender y cuyo ciclo de releases hay que monitorear (relevante dado que este es un sistema con cumplimiento PCI-DSS donde cada dependencia nueva es superficie a auditar).
4. **Costo de usarla igual, si se prefiere por ergonomía**: bajo y aceptable — `django-money` es la única de las evaluadas con mantenimiento activo real e integración Django/DRF documentada (aunque con los matices de las issues #240/#550 ya señalados). Si el equipo prefiere el value object `Money` en el código por legibilidad, esta es la elección correcta y no hay motivo técnico para preferir `py-moneyed` standalone, `dinero`, u otra alternativa de las evaluadas.

**Recomendación final**: empezar sin dependencia externa (`Decimal` + convención propia de dos campos `amount`/`currency` con validación de dominio y serializers DRF explícitos), y solo adoptar `django-money` más adelante si en la práctica el equipo encuentra que repetir la validación "moneda+monto siempre juntos" en múltiples modelos genera fricción real — no adoptarla de forma preventiva. Esto es consistente con el principio ya aplicado en otras decisiones de este proyecto (`research-rust-vs-django.md`): no añadir una pieza de infraestructura o dependencia hasta que el problema que resuelve sea real y medible en este proyecto específico, no hipotético.

| Librería | Mantenimiento | Integración ORM Django | Value Object moneda+monto | DRF | Recomendación |
|---|---|---|---|---|---|
| Ninguna (Decimal nativo + convención propia) | N/A (stdlib) | Manual, simple | Manual (2 campos + validación) | Manual, control total | **Recomendado para empezar** |
| `django-money` | Activo (3.6.x, 2026) | Nativa | Sí (`Money`) | Soportada, con matices documentados | Opción a futuro si hay fricción real |
| `py-moneyed` | Lento (~3 años sin major) | Ninguna | Sí (`Money`) | Solo vía paquete de terceros | No aporta sobre django-money para este stack |
| `dinero` | Inmaduro (0.x) | Ninguna | Parcial | Ninguna | Descartado |
| `stockholm` / `real-money` / `t-money` | Variable, sin tracción amplia | Ninguna | Sí, en distinto grado | Ninguna | Descartado |

Este archivo complementa `research-manejo-dinero-bd.md` (tipo de dato, precisión, redondeo) con la capa de librerías/ergonomía de código — la recomendación de tipo de dato (`Decimal`/`DECIMAL`) de ese documento no cambia; aquí solo se resuelve si conviene envolverlo en una librería de terceros.
