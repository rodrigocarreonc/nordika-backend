"""Paginación configurable por query string para listas de la API."""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class ConfigurablePageNumberPagination(PageNumberPagination):
    """Permite al cliente elegir cuantos elementos pedir vía `?page_size=` (hasta 100).

    Se exponen `total_pages` y `current_page` además del formato estándar de DRF para que
    la barra de paginación en la app muestre números de página sin recalcularlos.
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.get_page_size(self.request),
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })
