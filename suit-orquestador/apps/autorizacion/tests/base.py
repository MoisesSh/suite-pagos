from django.core.cache import cache
from rest_framework.test import APITestCase


class BaseAPITestCase(APITestCase):
    """Aísla los contadores de throttling (ScopedRateThrottle usa la caché default —
    locmem mientras no haya Redis configurado en este proyecto) entre tests: sin esto,
    un test que agota un scope (ej. cobro_c2p_otp: 20/hour) puede hacer fallar tests
    subsecuentes sin relación aparente. Heredar de esta clase, no de APITestCase
    directo, en cualquier test que ejercite una vista con throttle_scope."""

    def setUp(self):
        cache.clear()
        super().setUp()
