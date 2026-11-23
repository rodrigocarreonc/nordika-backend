"""Configuración de registro de la aplicación quickstart dentro de Django."""

from django.apps import AppConfig


class QuickstartConfig(AppConfig):
    # Ruta completa del paquete porque quickstart vive anidada dentro de tutorial/.
    name = 'tutorial.quickstart'

    def ready(self):
        # Registra las señales del dominio para difundir cambios por SSE al iniciar Django.
        from .realtime import register_signals

        register_signals()
