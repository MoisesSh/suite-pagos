---
name: autenticacion-permisos-jwt
description: Modelo Usuario/Perfil, registro y verificación de email, login/refresh/logout con simplejwt + cookie HttpOnly, permisos custom (IsConatelAdmin, IsVerificado) y throttling de seguridad en endpoints de auth.
---

# Autenticación, roles y permisos (Backend)

---

## Modelo Usuario y roles

`apps/shared/domain/models.py` — `class Usuario(AbstractUser, BaseModel)`. `USERNAME_FIELD = 'email'`, `REQUIRED_FIELDS = ['username']`.

Campos propios relevantes: `perfil` (FK a `Perfil`, `on_delete=PROTECT`), `rif`, `razon_social`, `nombre_comercial`, `trazabilidad` (único, autogenerado, formato `FTV-OPE-2026-00001`), `estatus`, `email_verificado`.

```python
class Usuario(AbstractUser, BaseModel):
    class Estatus(models.TextChoices):
        CREADO = 'creado'
        PERFIL_COMPLETO = 'perfil_completo'
        REGISTRO_COMPLETO = 'registro_completo'
        PENDIENTE_VERIFICACION = 'pendiente_verificacion'
        VERIFICADO = 'verificado'
        RECHAZADO = 'rechazado'
        OBSERVADO = 'observado'
```

**El rol NO es un choice en `Usuario`** — es una FK a `Perfil`:

```python
class Perfil(BaseModel):
    class TipoPerfil(models.TextChoices):
        OPERADOR = 'operador', 'Operador de Telecomunicaciones'
        INVERSOR = 'inversor', 'Inversor'
        GOBIERNO = 'gobierno', 'Ente de Gobierno'
        CONATEL = 'conatel', 'CONATEL'

    tipo_perfil = models.CharField(max_length=20, choices=TipoPerfil.choices, unique=True)
```

Cada `tipo_perfil` tiene un modelo de datos específico 1-a-1: `DatosOperador`, `DatosInversor`, `DatosGobierno`. **CONATEL no tiene modelo de datos propio** — se identifica por `is_superuser` o pertenencia al grupo `'conatel'` (ver permiso `IsConatelAdmin` abajo).

Para saber el rol de un usuario en código: `usuario.perfil.tipo_perfil == Perfil.TipoPerfil.OPERADOR`.

---

## Registro y verificación de email

`RegistroView` (`apps/users/api/views.py`) → `RegistroService.crear_usuario()` (`apps/users/application/services.py`):

1. Crea `Usuario` + el modelo de datos específico según `tipo_perfil` (`DatosOperador`/`DatosInversor`/`DatosGobierno`).
2. Crea el registro de verificación vía `VerificacionService.crear_para_usuario()`.
3. Registra en historial vía `HistorialService.registrar()`.
4. Emite el evento `events.usuario_registrado`.
5. Todo dentro de una transacción, con reintento si colisiona el secuencial de `trazabilidad`.

**Verificación de email**: `VerificacionEmailService` (`apps/shared/application/services/verificacion_email.py`) usa `django.core.signing.TimestampSigner` (salt propio) con caducidad de **72 horas** — no es JWT, es un token de firma simple de Django.

```python
def generar_token(usuario_id) -> str: ...
def verificar_token(token) -> int | None: ...   # retorna usuario_id o None si expiró/inválido
```

**Reenvío**: `ReenviarVerificacionView` dispara `reenviar_verificacion_email.delay(usuario_id=...)` directo (única excepción documentada al patrón de eventos+receivers, ver [[uso-librerias-backend]]), con throttle scope `reenvio_verificacion` (5/hora).

---

## Login / JWT

`LoginView` (`apps/users/api/views.py`):

```python
usuario = authenticate(request, username=email, password=password)
refresh = RefreshToken.for_user(usuario)
```

Usa `django.contrib.auth.authenticate()` + `RefreshToken.for_user()` de simplejwt **directo** — **no hay `TokenObtainPairView` ni serializer custom, ni `get_token()` override**. El rol/estatus **no van dentro del JWT** — se devuelven en el body de la respuesta de login (`tipo_perfil`, `estatus`, `email_verificado`).

⚠️ Si necesitas el rol/estatus del usuario en una petición autenticada posterior, **no lo busques en el payload del token** — consulta `request.user.perfil.tipo_perfil` / `request.user.estatus` directo, es la fuente de verdad y siempre está actualizada (a diferencia de un claim embebido en un JWT de 15 minutos que podría quedar desactualizado si el estatus cambia).

### Cookie HttpOnly + doble entrega (transición)

El refresh token se entrega tanto en el body como en una cookie HttpOnly — es una transición documentada, no el estado final:

```python
# apps/users/api/cookies.py
set_refresh_cookie(response, refresh_token)     # setea la cookie
clear_refresh_cookie(response)                  # logout
get_refresh_from_request(request)               # lee cookie, si no existe cae al body
```

```python
JWT_REFRESH_COOKIE = {
    'NAME': 'refresh_token',
    'HTTPONLY': True,
    'SECURE': not DEBUG,
    'SAMESITE': 'Strict',
    'PATH': '/api/auth/',
}
```

`SIMPLE_JWT`: access **15 min**, refresh **7 días**, `ROTATE_REFRESH_TOKENS=True`, `BLACKLIST_AFTER_ROTATION=True`.

**Cuando el frontend termine de migrar a leer solo la cookie**, se puede eliminar la entrega del refresh en el body — no lo hagas unilateralmente sin confirmar que el frontend ya no lo lee.

### Refresh y logout

```python
class CookieTokenRefreshView(TokenRefreshView):   # override de simplejwt
    throttle_scope = 'refresh'   # 600/hora — ver nota BE-02 abajo
    ...
```

`LogoutView` blacklistea el refresh (`RefreshToken(refresh).blacklist()`) y limpia la cookie.

---

## Permisos custom — tabla completa

Solo existen **2 permisos custom** en todo el proyecto, ambos en `apps/shared/domain/permissions.py`. Antes de crear uno nuevo, confirma que de verdad no puedes componer estos dos con `IsAuthenticated`.

| Permiso | Lógica (`has_permission`) | Rol requerido | Dónde se usa |
|---|---|---|---|
| `IsConatelAdmin` | `request.user.is_superuser` OR pertenece al grupo `'conatel'` | Staff CONATEL | Las 9 vistas de `apps/conatel/api/views.py`; combinado en `apps/shared/api/views.py` para catálogos/dashboard admin |
| `IsVerificado` | `request.user.estatus == Usuario.Estatus.VERIFICADO` | Cualquier perfil ya verificado por CONATEL | `apps/inversor/api/views.py` (matchmaking); 6 vistas de `apps/shared/api/views.py` (proyectos, matchmaking); casi siempre combinado con OR: `IsVerificado \| IsConatelAdmin` (para que CONATEL también entre) |

**No hay permiso por tipo de perfil individual** (operador/inversor/gobierno) a nivel de clase de permiso. El scoping por rol se hace **dentro de cada vista/servicio**, filtrando por `request.user.perfil.tipo_perfil` o restringiendo `get_queryset()` a `self.request.user` (patrón en `RepresentanteViewSet`, `PropuestaAlianzaViewSet`, `NotificacionListView`).

El resto de endpoints usa `IsAuthenticated` simple (la mayoría de `users`/`operador`/`inversor`/`gobierno`) o `AllowAny` (registro, login, catálogos geo/servicios públicos).

**Si necesitas restringir un endpoint a un `tipo_perfil` específico**, sigue el patrón existente (chequeo inline en la vista) en vez de crear `IsOperador`/`IsInversor`/`IsGobierno` como clases de permiso nuevas — sería inconsistente con cómo se resolvió hasta ahora, a menos que el chequeo se repita en 3+ vistas, en cuyo caso sí vale la pena extraerlo (avísalo explícitamente si lo haces).

---

## Habilitación de operador (cambio reciente — ya no es autodeclarada)

`DatosOperador` **ya no almacena autodeclaración** del operador. Ahora es un espejo de solo lectura de la BD externa RECAUDACION:

```python
class DatosOperador(BaseModel):
    estado_habilitacion = models.CharField(choices=EstadoHabilitacion.choices, ...)
    # HABILITADO | NO_HABILITADO | EN_TRAMITE | SIN_REGISTRO_HABILITACION | NO_REGISTRADO
    consultado_at = models.DateTimeField(null=True)
```

Estos dos campos se escriben **únicamente** desde `HabilitacionService.sincronizar()`. Nunca los edites desde una vista o serializer directamente — rompería la garantía de que siempre reflejan lo que dice RECAUDACION en el momento de la última sincronización. Ver [[integracion-bd-recaudacion]] para el detalle completo de esa integración.

---

## Throttling de seguridad — scopes de auth

| Scope | Límite | Vista | Nota |
|---|---|---|---|
| `login` | 10/min | `LoginView` | — |
| `registro` | 20/hour | `RegistroView` | — |
| `refresh` | 600/hour | `CookieTokenRefreshView` | Scope propio necesario: sin él, una petición sin `Authorization` válido cae en el scope `anon` (20/hour global) y puede expulsar usuarios legítimos en refresh (bug real corregido, referenciado como BE-02) |
| `reenvio_verificacion` | 5/hour | `ReenviarVerificacionView` | — |
| `geo` | 600/hour | Catálogo territorial (`/api/geo/`) | Público, se consulta antes del login |
| `anon` (default) | 20/hour | — | Es **global**, no por IP, mientras `TRUSTED_PROXY_COUNT=0` (pendiente, referenciado como BE-03) |
| `user` (default) | 1000/hour | — | — |

Al crear un endpoint público nuevo con volumen de tráfico esperado alto (catálogos, búsquedas), **no lo dejes en el scope `anon` global** — créale su propio `throttle_scope` como se hizo con `geo`, con el límite justificado en un comentario.

---

## Referencia cruzada perdida

Varios comentarios en el código (`BE-02`, `BE-03`, `§3.10`, etc.) referencian un archivo `AUDITORIA_BACKEND.md` que **no existe en disco** en este repo. Documenta decisiones de seguridad de auth con más detalle del que hay en el código mismo. Si el usuario tiene acceso a él en otro lugar (wiki, GitLab, otro repo), vale la pena recuperarlo — varias decisiones aquí documentadas (por qué 10/min en login, por qué 600/hora en refresh) probablemente tienen contexto adicional ahí.

---

## Comandos

### 1. Proteger un endpoint nuevo por rol

```
@skill protege [endpoint] para que solo [rol] pueda acceder
```

1. Si el rol es "verificado" o "staff CONATEL" → usa `IsVerificado`/`IsConatelAdmin` directo o combinados con `|`.
2. Si el rol es un `tipo_perfil` específico (operador/inversor/gobierno) → chequeo inline `request.user.perfil.tipo_perfil == Perfil.TipoPerfil.X` dentro de la vista, salvo que ya se repita en 3+ vistas (en ese caso, proponer extraerlo).
3. Nunca leas el rol desde el JWT — siempre desde `request.user` en la petición actual.

### 2. Añadir un flujo de verificación/token nuevo

```
@skill agrega verificación de [algo] por email/token
```

Sigue el patrón de `VerificacionEmailService`: `TimestampSigner` con salt propio y expiración explícita, no reutilices el JWT de sesión para esto — son mecanismos distintos con propósitos distintos en este proyecto.
