"""Funciones de creación de objetos de prueba. Cuando existe un service de
aplicación real que valida/orquesta la creación, se pasa por él (mismo
camino que producción) — ver apps/conciliacion/application/services/ingesta.py.
`Usuario` no tiene todavía un service de alta (solo se crea por admin/fixture),
así que se crea directo por ORM."""

import uuid

from apps.conciliacion.application.services.ingesta import IngestaService
from apps.conciliacion.domain.models import Banco, CuentaContable
from apps.users.domain.models import Usuario


def crear_usuario(**overrides):
    defaults = {
        'username': f'staff-{uuid.uuid4().hex[:8]}',
        'email': f'staff-{uuid.uuid4().hex[:8]}@conciliacion.test',
        'password': 'ClaveSegura123!',
    }
    defaults.update(overrides)
    password = defaults.pop('password')

    usuario = Usuario.objects.create(**defaults)
    usuario.set_password(password)
    usuario.save(update_fields=['password'])
    return usuario


def crear_banco(**overrides):
    defaults = {'codigo': '0102', 'nombre': 'Banco de Venezuela', 'activo': True}
    defaults.update(overrides)
    banco, _creado = Banco.objects.get_or_create(codigo=defaults['codigo'], defaults=defaults)
    return banco


def crear_cuenta_contable(**overrides):
    defaults = {'codigo': '1105', 'nombre': 'Banco - Cuenta recaudadora', 'activa': True}
    defaults.update(overrides)
    cuenta, _creado = CuentaContable.objects.get_or_create(codigo=defaults['codigo'], defaults=defaults)
    return cuenta


def crear_evento_pago(**overrides):
    defaults = {
        'event_id': uuid.uuid4(),
        'event_type': 'pago.confirmado',
        'payload': {'monto': '120.00', 'aplicacion_id': str(uuid.uuid4())},
        'schema_version': 1,
    }
    defaults.update(overrides)
    evento, _creado = IngestaService.registrar_evento(**defaults)
    return evento
