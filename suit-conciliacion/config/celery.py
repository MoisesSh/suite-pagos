import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('suit_conciliacion')
app.config_from_object('django.conf:settings', namespace='CELERY')

# La cola de eventos crudos de dominio (`pago.*`, ver infrastructure/bootsteps.py)
# NO debe ser la misma que `task_default_queue`: si comparten nombre, el
# consumer nativo de Celery (protocolo de tareas) y el bootstep custom
# (protocolo de eventos crudos, ver infrastructure/bootsteps.py) compiten por
# la misma cola en RabbitMQ, y cada uno recibe mensajes del otro sin poder
# interpretarlos — confirmado en un smoke test real: reintentos de Celery
# aterrizando en el bootstep como si fueran eventos crudos, generando un loop
# de reintentos amplificante. `task_default_queue` queda con el nombre por
# defecto de Celery (cola de tareas interna, sin binding a ningún exchange de
# dominio) — el bootstep declara su propia cola de forma explícita.

app.autodiscover_tasks(['apps.conciliacion'], related_name='infrastructure.tasks')

# Bootstep que consume los mensajes crudos de `pago.*` (no son tareas Celery
# nativas: los publica el relay del outbox del Orquestador) y los traduce a
# la tarea `consumir_evento_pago`.
from apps.conciliacion.infrastructure.bootsteps import EventoPagoConsumerStep  # noqa: E402

app.steps['consumer'].add(EventoPagoConsumerStep)
