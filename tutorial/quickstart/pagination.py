"""Query-string configurable pagination for API lists."""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class ConfigurablePageNumberPagination(PageNumberPagination):
    """Lets the client choose how many items to request via `?page_size=` (up to 100).

    `total_pages` and `current_page` are exposed on top of the standard DRF format so the
    app's pagination bar can show page numbers without recomputing them.
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
