"""Permisos personalizados de DRF para separar lectura de clientes y escritura de staff."""

from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """Permite leer el catálogo a cualquier cliente autenticado, pero restringe cambios al staff.

    Se usa en recursos compartidos (muebles, categorías, proveedores) junto con IsAuthenticated.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Restringe la modificación de registros personales al usuario dueño o al staff."""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user and request.user.is_staff:
            return True
        if hasattr(obj, 'usuario'):
            return obj.usuario == request.user
        return False
