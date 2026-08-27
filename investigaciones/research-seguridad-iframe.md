# Investigación — Seguridad de formularios de cobro embebidos por iframe (Django, 2026)

Investigación de mejores prácticas para servir el formulario de cobro (Pago Móvil C2P, ver `research-brief-pagos.md` sección 4.1) embebido por `<iframe>` dentro de las apps consumidoras (Conatel en Línea, Homologación, futuras apps), con validación backend de qué dominios pueden embeberlo. Aplica directamente al slice `autorizacion/` del Orquestador y al Developer Portal (registro de apps/dominios).

## 1. CSP `frame-ancestors` vs `X-Frame-Options` — cuál usar

- `X-Frame-Options` es el header histórico (2008), con solo dos valores útiles: `DENY` y `SAMEORIGIN`. **No soporta lista de múltiples orígenes** — no sirve para el caso de este proyecto, donde varias apps consumidoras distintas deben poder embeber el mismo formulario.
- `Content-Security-Policy: frame-ancestors` es el mecanismo moderno (soportado en navegadores desde 2018) y **sí acepta una lista de orígenes permitidos**. Cuando ambos headers están presentes, los navegadores modernos priorizan `frame-ancestors` e ignoran `X-Frame-Options` por completo.
- **Recomendación para este proyecto**: usar `frame-ancestors` con la whitelist real de dominios registrados como mecanismo primario, y mantener `X-Frame-Options: SAMEORIGIN` únicamente como fallback defensivo para navegadores muy antiguos que no soporten CSP — nunca como control principal.
- Regla general útil para el resto del sistema: en páginas sensibles que **no** deben embeberse nunca (login administrativo, backoffice, Developer Portal fuera del flujo de widget), usar `frame-ancestors 'none'` / `X-Frame-Options: DENY`. El formulario de cobro es la única superficie que necesita esta excepción, y debe ser explícita y acotada.

Fuentes: [MDN — CSP frame-ancestors](https://developer.mozilla.org/docs/Web/HTTP/Headers/Content-Security-Policy/frame-ancestors), [Pragmatic Web Security — Preventing framing with policies](https://pragmaticwebsecurity.com/articles/securitypolicies/preventing-framing-with-policies.html), [Shai Alon — CSP frame-ancestors vs X-Frame-Options](https://medium.com/@shaialon/csp-frame-ancestors-vs-x-frame-options-for-clickjacking-prevention-30383a713772)

## 2. Whitelist dinámica por app consumidora — el problema real a resolver

El reto específico de este proyecto es que `frame-ancestors` no es un valor estático de config: **debe calcularse por request**, según qué app consumidora (identificada por su API key / client_id del Developer Portal) está solicitando el formulario, contra una whitelist de dominios registrados para esa app específica — no una lista global fija de todos los dominios de todas las apps.

Enfoques encontrados para Django:
- **Django nativo**: `XFrameOptionsMiddleware` solo soporta `DENY`/`SAMEORIGIN` estáticos por vista (decoradores `@xframe_options_deny`, `@xframe_options_sameorigin`) — insuficiente para una whitelist dinámica multi-dominio.
- **`django-csp` (Mozilla, paquete estándar de facto)**: soporta `CSP_FRAME_ANCESTORS` como lista estática en settings, y decoradores (`@csp_update`) para override por vista — pero sigue siendo configuración estática por vista, no por valor de negocio calculado en runtime.
- **Patrón recomendado — computar el header a mano en la vista**: dado que se necesita resolver "qué dominio(s) están registrados para esta app_id/API key" contra la base de datos del Developer Portal en cada request, la forma más directa y explícita es: (a) la vista que sirve el formulario de cobro identifica la app consumidora (por el parámetro/token que recibe en la URL o en la sesión del flujo de checkout), (b) consulta la tabla de dominios autorizados de esa app, (c) **construye el header `Content-Security-Policy: frame-ancestors <dominio(s) exactos de esa app>` manualmente en la respuesta**, en vez de depender de una lista global estática de middleware. Existen paquetes de terceros (`django-csp-advanced`) que permiten pasar callables `(request, response) -> valor` para resolver esto a nivel de middleware, pero dado que es lógica de negocio específica (join contra la tabla de apps/dominios), construirlo explícitamente en la vista o en un middleware propio y simple es más trazable que depender de un paquete de terceros poco mantenido para el camino crítico de seguridad de un pago.
- **Importante**: nunca usar `*` ni un wildcard amplio en `frame-ancestors` para "simplificar" — cada valor debe ser un origen exacto (`https://appconsumidora.conatel.gob.ve`), resuelto contra el registro real de dominios de esa app en el Developer Portal.

Fuentes: [django-csp — Configuration](https://django-csp.readthedocs.io/en/latest/configuration.html), [django-csp-advanced (PyPI)](https://pypi.org/project/django-csp-advanced)

## 3. Validación backend adicional: Referer/Origin como defensa en profundidad

`frame-ancestors` es un control de navegador (evita que el navegador cargue el iframe si el padre no está en la lista), pero **no es una validación de servidor** — un cliente que no sea un navegador estándar, o un navegador viejo sin soporte CSP, puede ignorarlo. Por eso se recomienda una segunda capa server-side:

- En la petición que carga el formulario (y especialmente en el POST que ejecuta el cobro — ver flujo C2P de `research-brief-pagos.md`), **validar en el backend el header `Origin` (preferido) o `Referer` (fallback) contra la misma whitelist de dominios de la app consumidora**, rechazando la operación si no coincide, independientemente de que el navegador ya haya (o no) respetado `frame-ancestors`.
- Cuando el request llega dentro de un iframe, el navegador setea el `Referer` como el host del contenido enmarcado (el propio formulario), no el del padre que lo embebe — por eso la validación de "qué dominio embebe" debe hacerse en la carga inicial del iframe (donde el `Referer`/`Origin` sí refleja la página contenedora) y comunicarse al backend del formulario vía el token de sesión de checkout, no re-derivarse en cada submit posterior.
- Usar `referrerpolicy="strict-origin-when-cross-origin"` (o más estricto) en el propio `<iframe>` para no filtrar la URL completa de la app consumidora (que podría contener tokens de sesión propios de esa app) hacia el formulario de cobro — solo el origen, no el path completo.
- Esto complementa (no reemplaza) el control de navegador: es la misma filosofía de "defensa en profundidad" ya aplicada en el brief de base de datos (idempotencia a nivel de app + a nivel de DB).

Fuentes: [Invicti — iframe security best practices](https://www.invicti.com/blog/web-security/iframe-security-best-practices), [feeding.cloud.geek.nz — sandbox, referrer, feature policy](https://feeding.cloud.geek.nz/posts/restricting-third-party-iframes-sandbox-referrer-feature-policy/)

## 4. Comunicación segura padre↔iframe vía `postMessage`

El formulario embebido necesita comunicar al menos: resultado del cobro (éxito/error/pendiente), altura del iframe para auto-resize, y eventos de cierre/cancelación — todo vía `postMessage`, dado que padre e iframe están en orígenes distintos (no hay acceso directo al DOM cruzado).

Reglas no negociables encontradas en la investigación:

- **Nunca usar `targetOrigin: '*'` al enviar mensajes desde el iframe hacia el padre.** El formulario de cobro debe conocer el origen exacto de la app consumidora (ya resuelto en el paso 2 contra la whitelist) y enviar el mensaje solo a ese origen: `window.parent.postMessage(payload, "https://appconsumidora.conatel.gob.ve")`. Usar `'*'` permite que cualquier ventana reciba el resultado del pago, incluyendo datos potencialmente sensibles del estado de la transacción.
- **Siempre validar `event.origin` al recibir un mensaje**, tanto en el script embebido en la app consumidora (validando que el mensaje viene del origen real del formulario de Conatel, no de un iframe malicioso suplantado) como — si el formulario alguna vez recibe mensajes del padre (ej. para pasar parámetros de checkout) — en el propio formulario, validando que el `event.origin` coincide con el dominio registrado de esa app específica.
- **Tratar el `data` recibido como entrada no confiable**: validar estructura/tipo antes de usarlo (nunca `eval`, nunca inyectar directo en el DOM sin sanitizar) — previene XSS vía mensajes maliciosos aunque el origen esté validado.
- **Estructura de mensaje explícita y versionada**: usar un objeto con un campo de tipo/versión (ej. `{type: "pago.completado", version: 1, payload: {...}}`) en vez de strings sueltos, para poder evolucionar el contrato sin romper integraciones existentes — mismo principio de contrato de eventos versionado ya aplicado al bus RabbitMQ en `research-brief-pagos.md`.
- Enfoque de "triple capa" recomendado en la industria: CSP (`frame-ancestors`) + validación de origen en el handshake HTTP (Origin/Referer) + validación de origen en el handler de `postMessage` — ninguna de las tres reemplaza a las otras.

Fuentes: [postmessage.dev — Window postMessage Security Guide](https://postmessage.dev/), [Secure Ideas — Being Safe and Secure with Cross-Origin Messaging](https://www.secureideas.com/blog/being-safe-and-secure-with-cross-origin-messaging), [Bindbee — Securing Cross-Window Communication](https://bindbee.dev/blog/secure-cross-window-communication)

## 5. Protección anti-clickjacking adicional (más allá de frame-ancestors)

- `frame-ancestors`/`X-Frame-Options` evita el embebido no autorizado a nivel de navegador, pero el patrón clásico de clickjacking (overlay transparente sobre el iframe legítimo) se mitiga mejor combinando:
  - **Atributo `sandbox`** en el `<iframe>` del lado de la app consumidora, con el set mínimo de permisos necesario (ej. `allow-scripts allow-forms allow-same-origin` — evaluar cuidadosamente si `allow-same-origin` es realmente necesario, ya que combinado con `allow-scripts` puede debilitar el sandboxing si el origen coincide).
  - **Frame-busting defensivo del lado del formulario** (JS que verifica `window.top !== window.self` y compara contra el origen esperado) como capa adicional — nunca como sustituto de `frame-ancestors`, porque JS puede deshabilitarse o bypassearse, pero añade una señal más.
  - **Confirmación explícita de usuario antes de la acción sensible** (el flujo C2P ya lo tiene de forma nativa: requiere el OTP como segundo factor antes de ejecutar el cobro — ver `research-brief-pagos.md` 4.1 — lo cual ya mitiga buena parte del riesgo de clickjacking puro, porque un clic robado no basta sin la clave OTP real del usuario).
- Dado que el flujo ya exige OTP, el foco de la protección anti-clickjacking en este proyecto no es tanto "evitar el cobro fraudulento con un clic" (el OTP ya lo impide) sino **evitar que un dominio no autorizado embeba el formulario para phishing** (capturar cédula/teléfono/OTP del usuario simulando ser una app legítima) — razón adicional por la que la whitelist estricta de `frame-ancestors` por app es el control más importante de esta sección, más que el sandboxing en sí.

Fuentes: [didit.me — Embedded iFrame Security Best Practices](https://didit.me/blog/embedded-iframe-security-best-practices/), [Invicti — iframe security best practices](https://www.invicti.com/blog/web-security/iframe-security-best-practices)

## 6. Resumen — recomendaciones concretas para backend

1. Servir el formulario de cobro con `Content-Security-Policy: frame-ancestors <dominios exactos de la app consumidora>` calculado dinámicamente por request contra una tabla `dominios_autorizados` (FK a la app/API key del Developer Portal) — nunca un valor estático global ni wildcard.
2. Mantener `X-Frame-Options: DENY` como default global del proyecto (todas las vistas que no sean el formulario de cobro), y `SAMEORIGIN` como fallback legacy únicamente en la vista del formulario, subordinado a `frame-ancestors`.
3. Validar `Origin`/`Referer` en el backend en la carga inicial del iframe (no solo confiar en el control de navegador), contra la misma tabla de dominios autorizados.
4. Todo `postMessage` saliente del formulario debe especificar el origen exacto de destino (nunca `'*'`); todo `postMessage` entrante debe validar `event.origin` contra la whitelist antes de procesar el `data`.
5. Definir un contrato de mensaje versionado (`{type, version, payload}`) para la comunicación padre↔iframe, con el mismo criterio de gobernanza de contratos ya aplicado al bus de eventos RabbitMQ (dueño único, cambios no rompen consumidores existentes).
6. Modelar `dominios_autorizados` como tabla propia del Developer Portal (no hardcodear en settings de Django) — cada app consumidora gestiona su(s) dominio(s) de embebido igual que gestiona su API key, con la misma superficie de auditoría/rotación.
7. Complementar con `sandbox` en el iframe del lado de la app consumidora y `referrerpolicy="strict-origin-when-cross-origin"`, documentados como requisito de integración en el Developer Portal (no algo que el Orquestador pueda forzar del lado del embebedor, pero sí exigir como parte del checklist de onboarding de nueva app — KPI "< 2 semanas" ya mencionado en el roadmap).

Este archivo complementa `research-brief-pagos.md` (contratos de datos/eventos) y `research-stack-mensajeria.md` (infraestructura de mensajería) — aquí se cubre específicamente la superficie de seguridad del formulario embebido, relevante tanto para el slice `autorizacion/` del Orquestador como para el diseño de la tabla de apps/dominios del Developer Portal.
