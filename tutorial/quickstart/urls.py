"""Registers the quickstart app ViewSets in the REST router."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet,
    FavoriteViewSet,
    FurnitureViewSet,
    ReservationViewSet,
    SupplierViewSet,
)

# DefaultRouter generates the CRUD routes and the @action routes of each resource.
router = DefaultRouter()
router.register(r'furniture', FurnitureViewSet, basename='furniture')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'favorites', FavoriteViewSet, basename='favorite')
router.register(r'reservations', ReservationViewSet, basename='reservation')

urlpatterns = [
    path('', include(router.urls)),
]
