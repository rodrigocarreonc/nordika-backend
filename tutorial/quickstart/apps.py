"""Registration config of the quickstart app inside Django."""

from django.apps import AppConfig


class QuickstartConfig(AppConfig):
    # Full package path because quickstart is nested inside tutorial/.
    name = 'tutorial.quickstart'
