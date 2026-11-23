"""Broker SSE en memoria y señales de dominio para actualizaciones en tiempo real."""

from contextlib import contextmanager
import json
import queue
import threading

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.utils import timezone

# Intervalo de keepalive para evitar cierres por inactividad en navegadores y proxies.
SSE_KEEPALIVE_SECONDS = 15

# Límite por cliente para que un consumidor lento nunca acumule memoria sin control.
SUBSCRIBER_QUEUE_MAXSIZE = 100

# Mapeo modelo -> recurso del contrato SSE compartido con el frontend.
_MODEL_RESOURCE_MAP = {}


class RealtimeBroker:
    """Pub/sub en proceso seguro para hilos que difunde eventos a clientes SSE activos."""

    def __init__(self, max_queue_size=SUBSCRIBER_QUEUE_MAXSIZE):
        self._max_queue_size = max_queue_size
        self._lock = threading.Lock()
        self._subscribers = set()

    @property
    def subscriber_count(self):
        """Devuelve el número de clientes SSE conectados actualmente."""
        with self._lock:
            return len(self._subscribers)

    @contextmanager
    def subscribe(self):
        """Registra una cola acotada para un cliente y garantiza su limpieza al desconectar."""
        subscriber_queue = queue.Queue(maxsize=self._max_queue_size)
        with self._lock:
            self._subscribers.add(subscriber_queue)
        try:
            yield subscriber_queue
        finally:
            self.unsubscribe(subscriber_queue)

    def unsubscribe(self, subscriber_queue):
        """Elimina la cola del suscriptor sin lanzar error si ya había sido removida."""
        with self._lock:
            self._subscribers.discard(subscriber_queue)

    def publish(self, resource, action, obj_id=None):
        """Difunde un evento a todas las colas activas, descartando el más viejo si está llena."""
        event = {
            'resource': resource,
            'action': action,
            'id': obj_id,
            'timestamp': timezone.now().isoformat(),
        }
        # Se toma una copia de las colas bajo candado para no bloquear registros durante el envío.
        with self._lock:
            subscribers = list(self._subscribers)

        for subscriber_queue in subscribers:
            try:
                subscriber_queue.put_nowait(event)
            except queue.Full:
                # Si el cliente va atrasado, descartamos el evento más antiguo para conservar los recientes.
                try:
                    subscriber_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    subscriber_queue.put_nowait(event)
                except queue.Full:
                    pass
        return event


# Instancia compartida por todos los hilos WSGI del proceso Django.
broker = RealtimeBroker()


def format_sse_event(event_name, data):
    """Formatea un evento según el estándar text/event-stream (event + data JSON + doble salto)."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_name}\ndata: {payload}\n\n"


def publish_event(resource, action, obj_id=None):
    """Programa la publicación tras confirmar la transacción para no emitir cambios revertidos."""
    transaction.on_commit(lambda: broker.publish(resource, action, obj_id))


def _handle_post_save(sender, instance, created, raw=False, **kwargs):
    """Emite evento created/updated al guardar cualquier modelo observado del catálogo."""
    # En carga de fixtures (raw=True) se omite para no saturar clientes con datos iniciales.
    if raw:
        return
    resource = _MODEL_RESOURCE_MAP.get(sender)
    if resource:
        action = 'created' if created else 'updated'
        publish_event(resource, action, instance.pk)


def _handle_post_delete(sender, instance, **kwargs):
    """Emite evento deleted cuando se elimina un registro de un modelo observado."""
    resource = _MODEL_RESOURCE_MAP.get(sender)
    if resource:
        publish_event(resource, 'deleted', instance.pk)


def register_signals():
    """Conecta post_save y post_delete de forma idempotente para los modelos del dominio."""
    # Importación local para evitar dependencias circulares durante el arranque de Django.
    from .models import Apartado, Categoria, Favorito, Mueble, Proveedor

    watched_models = (
        (Mueble, 'mueble'),
        (Categoria, 'categoria'),
        (Proveedor, 'proveedor'),
        (Apartado, 'apartado'),
        (Favorito, 'favorito'),
    )

    for model, resource in watched_models:
        _MODEL_RESOURCE_MAP[model] = resource
        # dispatch_uid evita duplicar receptores si ready() se invoca más de una vez;
        # weak=False garantiza que los handlers no sean recolectados por el GC.
        post_save.connect(
            _handle_post_save,
            sender=model,
            weak=False,
            dispatch_uid=f'nordika_sse_post_save_{resource}',
        )
        post_delete.connect(
            _handle_post_delete,
            sender=model,
            weak=False,
            dispatch_uid=f'nordika_sse_post_delete_{resource}',
        )
