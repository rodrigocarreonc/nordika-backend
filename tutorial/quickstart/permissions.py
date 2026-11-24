"""Custom DRF permissions that separate customer reads from staff writes."""

from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """Lets any authenticated customer read the catalog, but restricts changes to staff.

    Used on shared resources (furniture, categories, suppliers) together with IsAuthenticated.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Restricts changes to personal records to the owner user or to staff."""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user and request.user.is_staff:
            return True
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False
