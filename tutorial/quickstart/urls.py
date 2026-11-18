from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter
from .views import (
    ApartadoViewSet,
    CategoriaViewSet,
    CrearClienteView,
    FavoritoViewSet,
    MuebleViewSet,
    ProveedorViewSet,
)

router = DefaultRouter()
router.register(r'muebles', MuebleViewSet, basename='mueble')
router.register(r'categorias', CategoriaViewSet, basename='categoria')
router.register(r'proveedores', ProveedorViewSet, basename='proveedor')
router.register(r'favoritos', FavoritoViewSet, basename='favorito')
router.register(r'apartados', ApartadoViewSet, basename='apartado')

urlpatterns = [
    path('users/crear_cliente/', CrearClienteView.as_view(), name='crear_cliente'),
    re_path(r'^users/crear_cliente/?$', CrearClienteView.as_view(), name='crear_cliente_slash_optional'),
    path('', include(router.urls)),
]
