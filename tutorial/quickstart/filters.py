"""Query filters (django-filter) for the furniture catalog and reservations."""

import django_filters
from .models import Furniture, Reservation


class FurnitureFilter(django_filters.FilterSet):
    """Combinable catalog filters: price range, category, supplier and stock."""
    price_min = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    price_max = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    category = django_filters.NumberFilter(field_name='category__id')
    category_name = django_filters.CharFilter(field_name='category__name', lookup_expr='icontains')
    supplier = django_filters.NumberFilter(field_name='supplier__id')
    in_stock = django_filters.BooleanFilter(method='filter_in_stock')

    class Meta:
        model = Furniture
        fields = ['category', 'supplier', 'price_min', 'price_max', 'in_stock']

    # Maps the boolean to stock > 0 or sold out (0); None leaves the queryset unfiltered.
    def filter_in_stock(self, queryset, name, value):
        if value is True:
            return queryset.filter(stock__gt=0)
        elif value is False:
            return queryset.filter(stock=0)
        return queryset


class ReservationFilter(django_filters.FilterSet):
    """Filters to split active (pending) reservations from the resolved history."""
    status = django_filters.CharFilter(field_name='status')
    status__in = django_filters.BaseInFilter(field_name='status')
    history = django_filters.BooleanFilter(method='filter_history')
    furniture = django_filters.NumberFilter(field_name='furniture')

    class Meta:
        model = Reservation
        fields = ['status', 'furniture', 'history']

    # Lets the app tabs ask for resolved (history=true) or pending (false) reservations
    # without listing every terminal status on the client.
    def filter_history(self, queryset, name, value):
        if value is True:
            return queryset.exclude(status=Reservation.PENDING)
        elif value is False:
            return queryset.filter(status=Reservation.PENDING)
        return queryset
