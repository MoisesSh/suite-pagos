---
name: patrones-drf-implementacion
description: Patrones reales de implementación con Django REST Framework en el backend — serializers, views (generics/APIView, sin ViewSets), permisos, filtros, paginación, errores, drf-spectacular y throttling.
---

# Patrones de implementación DRF (Backend)

Skill para implementar endpoints nuevos siguiendo exactamente el estilo ya usado en el proyecto. Complementa [[arquitectura-onion-feature-scream]] (dónde vive cada capa) con el "cómo" concreto de la capa `api/`.

---

## Regla de oro: no hay ViewSets ni routers

**100% `generics.*View` + `views.APIView`.** No se usa `ModelViewSet`, `ViewSet`, ni `DefaultRouter`. Cada endpoint es una clase explícita registrada a mano en `api/urls.py`. Al crear un endpoint nuevo, sigue este patrón — no introduzcas ViewSets aunque parezcan "más DRY", rompería la consistencia del proyecto.

Clases usadas según el caso:

| Necesitas | Clase base | Ejemplo real |
|---|---|---|
| Listar | `generics.ListAPIView` | `RegistroListView` |
| Listar + crear | `generics.ListCreateAPIView` | `ZonaListCreateView` |
| Ver uno | `generics.RetrieveAPIView` | — |
| Ver + actualizar uno | `generics.RetrieveUpdateAPIView` | `ZonaRetrieveUpdateView` |
| Crear solo | `generics.CreateAPIView` | — |
| Acción que no mapea a CRUD (ej. "solicitar reunión", "responder solicitud") | `views.APIView` con `get`/`post`/`put` | `SolicitarReunionView`, `ResponderSolicitudView`, `MiHabilitacionView` |

---

## Serializers

Solo `serializers.ModelSerializer` y `serializers.Serializer` plano. Un archivo `serializers.py` por app en `api/`. Sin librerías de nested-writable serializers.

### Separar lectura de escritura

Patrón dominante: dos serializers para el mismo recurso.

```python
class ModeloNegocioSerializer(serializers.ModelSerializer):
    """Lectura — anidado, expone relaciones completas."""
    pilar = TipoPilarSerializer(read_only=True)

    class Meta:
        model = ModeloNegocio
        fields = '__all__'


class ModeloNegocioCrearSerializer(serializers.ModelSerializer):
    """Escritura — PrimaryKeyRelatedField, sin anidar."""
    metas_pnt = serializers.PrimaryKeyRelatedField(
        queryset=MetaPNT.objects.all(), many=True, write_only=True,
    )

    class Meta:
        model = ModeloNegocio
        fields = [...]
        read_only_fields = ['id']
```

### Campos calculados con OpenAPI anotado

```python
class XxxSerializer(serializers.ModelSerializer):
    @extend_schema_field(UsuarioResumenSerializer)
    def get_usuario(self, obj):
        return UsuarioResumenSerializer(obj.usuario).data

    usuario = serializers.SerializerMethodField()
```

`@extend_schema_field` es obligatorio en todo `SerializerMethodField` — sin él, drf-spectacular no puede tipar el campo en el schema OpenAPI.

### Validación contextual

```python
class SolicitudReunionSerializer(serializers.ModelSerializer):
    def validate_operador_destino(self, value):
        usuario = self.context['request'].user
        if value.usuario_id == usuario.id:
            raise serializers.ValidationError('No puedes solicitarte una reunión a ti mismo.')
        return value
```

Usa siempre `self.context['request'].user` para reglas que dependen de quién hace la petición — no confíes en datos del body para eso.

### ⚠️ No uses `StringRelatedField` en serializers `AllowAny`

Comentario de seguridad real en el código (referenciado como BE-07): `StringRelatedField` delega en `__str__` del modelo relacionado, que puede filtrar datos sensibles (ej. el email del usuario) en un endpoint público. Usa `SerializerMethodField` explícito para controlar exactamente qué se expone.

### Serializar un resultado que no es un modelo ORM

Cuando el service devuelve un `@dataclass(frozen=True)` (ver [[arquitectura-onion-feature-scream]]), el serializer es `serializers.Serializer` plano, no `ModelSerializer`:

```python
class HabilitacionSerializer(serializers.Serializer):
    rif = serializers.CharField(help_text='RIF en formato presentable')
    estado = serializers.ChoiceField(choices=EstadoHabilitacion.choices)
```

---

## Views

### `get_queryset()` es el patrón estándar de filtrado

No se usa `django_filters.FilterSet` pese a estar `DjangoFilterBackend` configurado globalmente (ver abajo). El filtrado real es manual, override de `get_queryset()`:

```python
class NotificacionListView(generics.ListAPIView):
    serializer_class = NotificacionSerializer

    def get_queryset(self):
        return Notificacion.objects.filter(usuario=self.request.user).order_by('-created_at')
```

### Guard obligatorio para drf-spectacular en `get_queryset()`

Toda vista con `get_queryset()` dependiente de `self.request` necesita este guard, o la introspección de schema de drf-spectacular falla:

```python
def get_queryset(self):
    if getattr(self, 'swagger_fake_view', False):
        return Modelo.objects.none()
    return Modelo.objects.filter(usuario=self.request.user)
```

### Validar recurso padre en rutas anidadas

Patrón reutilizable para URLs tipo `geo/estados/<region_id>/`: una vista base privada con un helper `_padre_o_404` que devuelve 404 explícito si el padre no existe, en vez de una lista vacía silenciosa:

```python
class _GeoListView(generics.ListAPIView):
    pagination_class = None  # ver sección Paginación

    def _padre_o_404(self, modelo, kwarg):
        try:
            return modelo.objects.get(pk=self.kwargs[kwarg])
        except modelo.DoesNotExist:
            raise Http404
```

### `APIView` para lógica de negocio inline

```python
class DatosGobiernoView(views.APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        if request.user.perfil.tipo_perfil != Perfil.TipoPerfil.GOBIERNO:
            return Response({'error': 'No autorizado'}, status=403)
        # delega side-effects a apps.*.application.services
        ...
```

---

## Permisos

Un único archivo compartido por toda la plataforma: `apps/shared/domain/permissions.py`. **No crees `permissions.py` por app** — añade el permiso ahí si es genérico, o revisa [[autenticacion-permisos-jwt]] antes de crear uno nuevo (puede que ya exista lo que necesitas).

```python
permission_classes = [IsAuthenticated, IsVerificado | IsConatelAdmin]
```

Se combinan con operadores lógicos DRF (`|` = OR, `,` en la lista = AND). Ver [[autenticacion-permisos-jwt]] para la tabla completa Permiso→Rol→Endpoints.

---

## Filtros

- `DEFAULT_FILTER_BACKENDS` global incluye `DjangoFilterBackend` + `SearchFilter` + `OrderingFilter`, pero **no hay ni un solo `FilterSet` custom en el proyecto** — es configuración lista para usar pero sin adopción real todavía.
- Lo que sí se usa activamente es `search_fields` de `SearchFilter` por vista:

```python
class ZonaListCreateView(generics.ListCreateAPIView):
    filter_backends = [filters.SearchFilter]
    search_fields = ['nombre', 'codigo']
```

Si necesitas filtros complejos (rangos, múltiples campos combinados), sigues teniendo dos caminos válidos en este proyecto: `get_queryset()` manual (el patrón dominante hoy) o introducir el primer `FilterSet` real — si haces esto último, documéntalo porque sería el primer caso y otros lo copiarán.

---

## Paginación

- Global: `PageNumberPagination`, `PAGE_SIZE = 20`.
- Se desactiva por vista (`pagination_class = None`) en catálogos cerrados/acotados (geografía, servicios) — justificado con docstring: paginar una lista de ~25 estados rompería los selectores en cascada del frontend.

```python
class GeoEstadosPorRegionView(_GeoListView):
    pagination_class = None
```

---

## Manejo de errores

**No hay `EXCEPTION_HANDLER` custom** — se usa el default de DRF. Dos patrones conviven:

1. **Errores de validación de input** → `serializer.is_valid(raise_exception=True)`, formato default `{"campo": ["mensaje"]}`.
2. **Reglas de negocio (403/404/409/503)** → `Response` manual:

```python
try:
    resultado = HabilitacionService.consultar(rif)
except RecaudacionNoDisponible as exc:
    return Response({'error': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
```

Para documentar estas respuestas de error en drf-spectacular, reusa el serializer compartido `MensajeRespuestaSerializer` (`serializers.Serializer` simple con un campo `error`/`mensaje`) en vez de crear uno nuevo por vista:

```python
@extend_schema(responses={200: XSerializer, 403: MensajeRespuestaSerializer, 409: MensajeRespuestaSerializer})
```

---

## drf-spectacular

```python
@extend_schema(
    request=XxxCrearSerializer,
    responses={200: XxxSerializer, 403: MensajeRespuestaSerializer, 409: MensajeRespuestaSerializer},
)
def post(self, request):
    ...
```

Para vistas genéricas (`generics.*View`) que comparten prefijo de URL y colisionarían de `operationId`, anota la **clase**, no el método, con `@extend_schema_view`:

```python
@extend_schema_view(
    get=extend_schema(
        operation_id='geo_estados_por_region',
        summary='Lista los estados de una región',
        description='...',
    ),
)
class GeoEstadosPorRegionView(_GeoListView):
    ...
```

`operation_id` explícito en snake_case descriptivo es obligatorio cuando hay ambigüedad — anotar la clase de una vista genérica sin esto rompe el schema (ya sucedió, está documentado inline en el código).

Enums repetidos entre modelos (campos `estatus`) necesitan `ENUM_NAME_OVERRIDES` en `SPECTACULAR_SETTINGS` porque drf-spectacular no resuelve `.choices` anidados automáticamente — ver [[uso-librerias-backend]].

---

## Throttling

Ver tabla completa de scopes en [[autenticacion-permisos-jwt]] (los de auth) y [[uso-librerias-backend]] (config global). Para aplicar un scope custom a una vista nueva:

```python
class MiVistaSensible(views.APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'mi_scope_nuevo'
```

Y registra `'mi_scope_nuevo': '<n>/<periodo>'` en `DEFAULT_THROTTLE_RATES` (settings.py) — **siempre con un comentario que justifique el número**, es la convención ya establecida en el proyecto (cada scope existente tiene su razón documentada inline).

---

## Convención de nombres — capa `api/`

| Archivo | Contenido |
|---|---|
| `api/urls.py` | `app_name` + `urlpatterns` |
| `api/views.py` | Todas las vistas de la app |
| `api/serializers.py` | Todos los serializers de la app |
| `api/utils.py` | Helpers puntuales (poco común, solo en `shared`) |
| `api/cookies.py` | Helpers de cookies (solo en `users`/`shared`) |

| Clase | Convención | Ejemplo real |
|---|---|---|
| Vista | `<Recurso><Acción>View` | `ZonaListCreateView`, `ZonaRetrieveUpdateView`, `GeoEstadosPorRegionView` |
| Serializer de lectura | `<Recurso>Serializer` | `HabilitacionSerializer` |
| Serializer de escritura | `<Recurso>CrearSerializer` | `ModeloNegocioCrearSerializer` |

---

## Comandos

### 1. Crear un endpoint nuevo

```
@skill crea el endpoint [descripción] en [app]
```

**Flujo:**
1. ¿Es CRUD estándar? → `generics.*View`. ¿Es una acción custom (solicitar/responder/aprobar)? → `views.APIView`.
2. ¿Necesita lógica de negocio no trivial? → delega a un `Service` de `application/` (ver [[arquitectura-onion-feature-scream]]), no la pongas inline en la vista.
3. Define serializer(s) — separa lectura/escritura si el recurso tiene relaciones anidadas en lectura.
4. Define `permission_classes` reusando los de `apps/shared/domain/permissions.py` (ver [[autenticacion-permisos-jwt]]).
5. Si es sensible (auth, acciones destructivas, endpoints públicos costosos), define un `throttle_scope` nuevo con su razón documentada.
6. Anota con `@extend_schema`/`@extend_schema_view` incluyendo respuestas de error con `MensajeRespuestaSerializer`.
7. Registra en `api/urls.py` con `name=` explícito.

### 2. Revisar un endpoint existente

```
@skill revisa el endpoint [nombre] en [app]
```

Verifica: ¿usa `get_queryset()` con el guard `swagger_fake_view`? ¿el serializer de escritura evita `StringRelatedField` en contexto público? ¿la vista delega reglas de negocio a un service en vez de tenerlas inline? ¿tiene `@extend_schema` con los códigos de error reales que puede devolver?
