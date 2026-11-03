from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    CategoriaViewSet,
    FavoritoViewSet,
    MuebleViewSet,
    ProveedorViewSet,
)

router = DefaultRouter()
router.register(r'muebles', MuebleViewSet, basename='mueble')
router.register(r'categorias', CategoriaViewSet, basename='categoria')
router.register(r'proveedores', ProveedorViewSet, basename='proveedor')
router.register(r'favoritos', FavoritoViewSet, basename='favorito')

urlpatterns = [
    path('', include(router.urls)),
]
