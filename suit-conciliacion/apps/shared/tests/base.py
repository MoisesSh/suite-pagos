from django.core.cache import cache
from rest_framework.test import APITestCase


class BaseAPITestCase(APITestCase):
    """Limpia la caché (contadores de throttling de DRF) antes de cada test."""

    def setUp(self):
        cache.clear()
        super().setUp()
