import django_filters
from .models import Mueble, MovimientoInventario


class MuebleFilter(django_filters.FilterSet):
    precio_min = django_filters.NumberFilter(field_name='precio', lookup_expr='gte')
    precio_max = django_filters.NumberFilter(field_name='precio', lookup_expr='lte')
    categoria = django_filters.NumberFilter(field_name='categoria__id')
    categoria_nombre = django_filters.CharFilter(field_name='categoria__nombre', lookup_expr='icontains')
    proveedor = django_filters.NumberFilter(field_name='proveedor__id')
    en_stock = django_filters.BooleanFilter(method='filter_en_stock')

    class Meta:
        model = Mueble
        fields = ['categoria', 'proveedor', 'precio_min', 'precio_max', 'en_stock']

    def filter_en_stock(self, queryset, name, value):
        if value is True:
            return queryset.filter(stock__gt=0)
        elif value is False:
            return queryset.filter(stock=0)
        return queryset


class MovimientoInventarioFilter(django_filters.FilterSet):
    mueble = django_filters.NumberFilter(field_name='mueble__id')
    tipo = django_filters.CharFilter(field_name='tipo_movimiento', lookup_expr='iexact')
    fecha_desde = django_filters.DateTimeFilter(field_name='fecha_movimiento', lookup_expr='gte')
    fecha_hasta = django_filters.DateTimeFilter(field_name='fecha_movimiento', lookup_expr='lte')

    class Meta:
        model = MovimientoInventario
        fields = ['mueble', 'tipo', 'fecha_desde', 'fecha_hasta']
