from django.db import models
from uuid6 import uuid7


class BaseModel(models.Model):
    """Modelo abstracto base: UUIDv7 ordenable en el tiempo + timestamps."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
