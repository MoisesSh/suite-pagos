from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.shared.domain.models import BaseModel


class Usuario(AbstractUser, BaseModel):
    """Staff de Conciliación: opera la cola de discrepancias y el ledger."""

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    email = models.EmailField(unique=True)

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return self.email
