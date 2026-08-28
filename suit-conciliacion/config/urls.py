from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.decorators.clickjacking import xframe_options_exempt

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.users.api.urls')),
    path('api/conciliacion/', include('apps.conciliacion.api.urls')),
]


def embebible_desde_portal(view):
    """Permite embeber esta vista por iframe solo desde `PORTAL_ORIGIN`
    (Developer Portal) — documentación interna, no un flujo de pago crítico,
    así que alcanza con un origen fijo por env var (a diferencia del
    formulario de cobro del Orquestador: catálogo dinámico + token firmado).
    Resto del proyecto sigue en X-Frame-Options: DENY por default
    (XFrameOptionsMiddleware global, sin tocar). A nivel de módulo (no
    anidada en el `if settings.DEBUG` de abajo) para poder testearla directo
    sin pelear con el timing de import del urlconf bajo `manage.py test`
    (que fuerza DEBUG=False durante toda la corrida)."""

    @xframe_options_exempt
    def wrapper(request, *args, **kwargs):
        response = view(request, *args, **kwargs)
        response['Content-Security-Policy'] = f"frame-ancestors 'self' {settings.PORTAL_ORIGIN}"
        return response

    return wrapper


if settings.DEBUG:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

    urlpatterns += [
        path('api/schema/', embebible_desde_portal(SpectacularAPIView.as_view()), name='schema'),
        path('api/docs/', embebible_desde_portal(SpectacularSwaggerView.as_view(url_name='schema')), name='swagger-ui'),
    ]
