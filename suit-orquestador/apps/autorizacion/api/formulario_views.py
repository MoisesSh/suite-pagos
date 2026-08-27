import logging
from urllib.parse import urlparse

from django.shortcuts import render
from django.views import View

from apps.autorizacion.api.checkout_token_resolver import resolver_checkout_token
from apps.autorizacion.domain.models import DominioPermitido

logger = logging.getLogger(__name__)

# Único proveedor soportado hoy (FlujoCobroC2PService, BDVPagoMovilC2PAdapter) —
# el formulario no necesita pedirle nada al respecto a la app consumidora.
PROVEEDOR_CODIGO = 'BDV'
BANCO_CODIGO = '0102'


def _extraer_origen_embebedor(request):
    """Origin (preferido) o Referer (fallback) de esta petición GET —
    research-seguridad-iframe.md sección 3: a diferencia del POST de cobro (que
    corre dentro del iframe, mismo origen que el propio formulario), la carga
    inicial del iframe SÍ refleja el origen de la página que lo embebe. Devuelve
    (origen_completo, hostname) o (None, None) si no vino ninguno de los dos
    headers — caso en el que la única defensa es el CSP frame-ancestors."""
    origen = request.META.get('HTTP_ORIGIN')
    if not origen:
        referer = request.META.get('HTTP_REFERER')
        if referer:
            parsed = urlparse(referer)
            if parsed.scheme and parsed.netloc:
                origen = f'{parsed.scheme}://{parsed.netloc}'
    if not origen:
        return None, None
    return origen, urlparse(origen).hostname


class FormularioCobroView(View):
    """Formulario de cobro C2P embebido por <iframe> en la app consumidora.
    GET /api/autorizacion/cobro/formulario/?checkout_token=... — nunca recibe
    monto/moneda por query param: viven atados criptográficamente al
    checkout_token (ver checkout_token_resolver), así que no son editables
    desde la URL del iframe."""

    def get(self, request):
        checkout_token = request.GET.get('checkout_token', '')

        aplicacion, payload, error_response = resolver_checkout_token(checkout_token, PROVEEDOR_CODIGO)
        if error_response is not None:
            motivo = error_response.data.get('error', 'checkout_token_invalido')
            return self._render_error(request, motivo)

        dominios = list(
            DominioPermitido.objects.filter(aplicacion=aplicacion, activo=True).values_list('dominio', flat=True),
        )
        origen_embebedor, hostname_embebedor = _extraer_origen_embebedor(request)

        if hostname_embebedor is not None and hostname_embebedor not in dominios:
            logger.warning(
                'Formulario de cobro: Origin/Referer %s no está en los dominios registrados de la aplicación %s.',
                hostname_embebedor, aplicacion.id,
            )
            return self._render_error(request, 'origen_no_autorizado')

        contexto = {
            'monto': payload['monto'],
            'moneda': payload['moneda'],
            'concepto': payload['concepto'],
            # |json_script en el template serializa esto de forma segura a un
            # <script type="application/json">. parentOrigin=None -> JS null: la
            # plantilla nunca debe caer a postMessage('*').
            'datos_formulario': {
                'checkoutToken': checkout_token,
                'proveedor': PROVEEDOR_CODIGO,
                'bancoCodigo': BANCO_CODIGO,
                'parentOrigin': origen_embebedor,
            },
        }
        response = render(request, 'autorizacion/formulario_cobro.html', contexto)

        # Fallback legacy para navegadores sin soporte de CSP frame-ancestors
        # (research-seguridad-iframe.md sección 6, punto 2) — subordinado al CSP
        # moderno, no lo reemplaza. El resto del proyecto sigue en DENY (default
        # global de Django); esta es la única vista que necesita la excepción.
        response['X-Frame-Options'] = 'SAMEORIGIN'
        if dominios:
            # :* — sin puerto explícito, un host-source de CSP matchea solo el
            # puerto por defecto del scheme; DominioPermitido no guarda puerto, y
            # el host ya es la frontera de autorización real, no el puerto.
            frame_ancestors = ' '.join(f'{dominio}:*' for dominio in dominios)
            response['Content-Security-Policy'] = f'frame-ancestors {frame_ancestors}'
        return response

    def _render_error(self, request, motivo):
        # Sin frame-ancestors permisivo ni X-Frame-Options propio: cae al default
        # global de Django (DENY) — no se pudo validar quién debería poder
        # embeber esto, así que no se permite embeberlo en absoluto.
        return render(request, 'autorizacion/formulario_cobro_error.html', {'motivo': motivo}, status=403)
