"""Filtros de consulta (django-filter) para el catálogo de muebles y los apartados."""

import django_filters
from .models import Apartado, Mueble


class MuebleFilter(django_filters.FilterSet):
    """Filtros combinables del catálogo: rango de precio, categoría, proveedor y stock."""
    precio_min = django_filters.NumberFilter(field_name='precio', lookup_expr='gte')
    precio_max = django_filters.NumberFilter(field_name='precio', lookup_expr='lte')
    categoria = django_filters.NumberFilter(field_name='categoria__id')
    categoria_nombre = django_filters.CharFilter(field_name='categoria__nombre', lookup_expr='icontains')
    proveedor = django_filters.NumberFilter(field_name='proveedor__id')
    en_stock = django_filters.BooleanFilter(method='filter_en_stock')

    class Meta:
        model = Mueble
        fields = ['categoria', 'proveedor', 'precio_min', 'precio_max', 'en_stock']

    # Traduce el booleano a stock > 0 o agotados (0); None deja el queryset sin filtrar.
    def filter_en_stock(self, queryset, name, value):
        if value is True:
            return queryset.filter(stock__gt=0)
        elif value is False:
            return queryset.filter(stock=0)
        return queryset


class ApartadoFilter(django_filters.FilterSet):
    """Filtros para separar apartados activos (pendientes) del historial resuelto."""
    estado = django_filters.CharFilter(field_name='estado')
    estado__in = django_filters.BaseInFilter(field_name='estado')
    historial = django_filters.BooleanFilter(method='filter_historial')
    mueble = django_filters.NumberFilter(field_name='mueble')

    class Meta:
        model = Apartado
        fields = ['estado', 'mueble', 'historial']

    # Permite a las pestañas de la app pedir resueltos (historial=true) o pendientes (false)
    # sin tener que enumerar cada estado terminal en el cliente.
    def filter_historial(self, queryset, name, value):
        if value is True:
            return queryset.exclude(estado=Apartado.PENDIENTE)
        elif value is False:
            return queryset.filter(estado=Apartado.PENDIENTE)
        return queryset

