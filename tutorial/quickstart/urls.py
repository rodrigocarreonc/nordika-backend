"""Registro de ViewSets en el router REST de la aplicación quickstart."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    ApartadoViewSet,
    CategoriaViewSet,
    FavoritoViewSet,
    MuebleViewSet,
    ProveedorViewSet,
)

# DefaultRouter genera automáticamente las rutas CRUD y las acciones @action de cada recurso.
router = DefaultRouter()
router.register(r'muebles', MuebleViewSet, basename='mueble')
router.register(r'categorias', CategoriaViewSet, basename='categoria')
router.register(r'proveedores', ProveedorViewSet, basename='proveedor')
router.register(r'favoritos', FavoritoViewSet, basename='favorito')
router.register(r'apartados', ApartadoViewSet, basename='apartado')

urlpatterns = [
    path('', include(router.urls)),
]
