"""Nordika REST views and ViewSets: authentication, catalog, favorites and reservation lifecycle."""

import uuid

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import ProtectedError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import APIView, ObtainAuthToken
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .filters import FurnitureFilter, ReservationFilter
from .models import Category, Favorite, Furniture, Reservation, Supplier
from .pagination import ConfigurablePageNumberPagination
from .permissions import IsAdminOrReadOnly
from .serializers import (
    CategorySerializer,
    CustomerCreateSerializer,
    FavoriteSerializer,
    FurnitureSerializer,
    RegisterSerializer,
    ReservationSerializer,
    SupplierSerializer,
    UserProfileSerializer,
    UserSerializer,
    validate_password_rules,
)


# ==========================================
# 1. AUTHENTICATION AND USERS
# ==========================================

class CustomAuthToken(ObtainAuthToken):
    """Logs in and returns the token along with the profile to avoid a second call to /me/."""
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': user.is_staff,
        }, status=status.HTTP_200_OK)


class RegisterView(APIView):
    """Public sign-up (AllowAny) that creates the customer and returns their session token right away."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            user = serializer.save()
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_staff': user.is_staff,
                'detail': 'Usuario registrado exitosamente.'
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CreateCustomerView(APIView):
    """Lets staff create customers from the admin panel without granting staff permissions."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = CustomerCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'id': user.id,
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_staff': user.is_staff,
                'date_joined': user.date_joined,
                'detail': 'Cliente registrado exitosamente.'
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def me(request):
    """Reads, partially edits or deactivates the authenticated user's account."""
    user = request.user
    if request.method == 'GET':
        serializer = UserProfileSerializer(user)
        return Response(serializer.data)

    if request.method == 'DELETE':
        # 400 and not 401: the app logs out on any 401
        if not user.check_password(request.data.get('password') or ''):
            return Response({'detail': 'La contraseña es incorrecta.'}, status=status.HTTP_400_BAD_REQUEST)
        # Deactivate instead of delete: Sale.reservation is PROTECT and the sales history must be kept
        with transaction.atomic():
            # Frees username and email so they can sign up again; uuid avoids clashes with real usernames
            user.username = f'deleted_{uuid.uuid4().hex}'
            user.email = ''
            user.is_active = False
            user.save(update_fields=['username', 'email', 'is_active'])
            Token.objects.filter(user=user).delete()
        # After deactivating: if something fails here, pending reservations still expire on their own after 5 days
        for reservation in Reservation.objects.filter(user=user, status=Reservation.PENDING):
            reservation.close(Reservation.CANCELLED)
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = UserProfileSerializer(user, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """Revokes the user's token on the server to invalidate the session immediately."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            if hasattr(request.user, 'auth_token'):
                request.user.auth_token.delete()
        except Exception:
            pass
        return Response({'detail': 'Sesión cerrada exitosamente.'}, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    """Updates the password and rotates the token to invalidate previous sessions on other devices."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        new_password = request.data.get('new_password') or ''
        if not user.check_password(request.data.get('current_password') or ''):
            return Response({'detail': 'La contraseña actual es incorrecta.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password_rules(new_password, user)
        except ValidationError as e:
            return Response({'detail': ' '.join(e.detail['password'])}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save(update_fields=['password'])
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)
        return Response({'token': token.key, 'detail': 'Contraseña actualizada.'}, status=status.HTTP_200_OK)


class ResetTokenView(APIView):
    """Rotates the access token without logging out the current client, invalidating old tokens."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        token = Token.objects.create(user=request.user)
        return Response({
            'token': token.key,
            'detail': 'Token restablecido exitosamente.'
        }, status=status.HTTP_200_OK)


# ==========================================
# 2. SUPPLIERS AND CATEGORIES
# ==========================================

class SupplierViewSet(viewsets.ModelViewSet):
    """Supplier CRUD (staff-only writes); catches ProtectedError and answers a readable 409."""
    queryset = Supplier.objects.all().order_by('name')
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]
    pagination_class = None  # small catalog: the app uses it whole in filters and forms
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'contact_name', 'email', 'phone']
    ordering_fields = ['name', 'created_at']

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError as e:
            count = len(e.protected_objects)
            plural = "muebles asociados" if count != 1 else "mueble asociado"
            return Response(
                {'detail': f"No se puede eliminar: el proveedor tiene {count} {plural}."},
                status=status.HTTP_409_CONFLICT
            )


class CategoryViewSet(viewsets.ModelViewSet):
    """Category CRUD without pagination to fill selects and filter chips in one go."""
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]
    pagination_class = None  # small catalog: the app uses it whole in filters and forms
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name']


# ==========================================
# 3. FURNITURE (CATALOG, CRUD AND CUSTOM ACTIONS)
# ==========================================

class FurnitureViewSet(viewsets.ModelViewSet):
    """Furniture catalog with filters, pagination and favorite/featured actions.

    Uses select_related to fetch category and supplier in a single SQL query.
    """
    queryset = Furniture.objects.select_related('category', 'supplier').all()
    serializer_class = FurnitureSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]
    pagination_class = ConfigurablePageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = FurnitureFilter
    search_fields = ['name', 'description', 'category__name', 'supplier__name']
    ordering_fields = ['price', 'stock', 'created_at', 'name']
    ordering = ['-created_at']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # Releases the stock of expired reservations before showing it.
        Reservation.cancel_expired()

    def destroy(self, request, *args, **kwargs):
        """
        Deletes a furniture item while respecting the protection of active or sold reservations.

        - Reservation.furniture keeps on_delete=models.PROTECT so no reservation ends up
          with furniture=null in API responses (e.g. reservations.tsx).
        - If there are PENDING or ACCEPTED reservations, or ones with a Sale, it answers
          409 Conflict and blocks the deletion.
        - If there are only REJECTED or CANCELLED reservations without a sale, it deletes them
          in the same atomic transaction before deleting the furniture (204 No Content),
          so those records stop showing in the history.
        """
        instance = self.get_object()
        # Only pending or accepted/sold reservations block the deletion.
        # Rejected or cancelled reservations without a sale allow deleting the furniture.
        blocking_count = instance.reservations.exclude(
            status__in=[Reservation.REJECTED, Reservation.CANCELLED],
            sale__isnull=True,
        ).count()
        if blocking_count > 0:
            plural = "apartados asociados" if blocking_count != 1 else "apartado asociado"
            return Response(
                {'detail': f"No se puede eliminar: el mueble tiene {blocking_count} {plural}."},
                status=status.HTTP_409_CONFLICT
            )
        try:
            with transaction.atomic():
                instance.reservations.filter(
                    status__in=[Reservation.REJECTED, Reservation.CANCELLED],
                    sale__isnull=True,
                ).delete()
                instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError as e:
            count = len(e.protected_objects)
            plural = "apartados asociados" if count != 1 else "apartado asociado"
            return Response(
                {'detail': f"No se puede eliminar: el mueble tiene {count} {plural}."},
                status=status.HTTP_409_CONFLICT
            )

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def toggle_favorite(self, request, pk=None):
        """Toggles the favorite state of the furniture for the authenticated user."""
        furniture = self.get_object()
        # Delete first and create with get_or_create: with exists() + create(), a double tap
        # made both requests try to create and the second one hit unique_together (500).
        deleted, _ = Favorite.objects.filter(user=request.user, furniture=furniture).delete()
        is_favorite = not deleted
        if is_favorite:
            Favorite.objects.get_or_create(user=request.user, furniture=furniture)
        msg = "Mueble agregado a favoritos." if is_favorite else "Mueble eliminado de favoritos."

        return Response({
            'furniture_id': furniture.id,
            'is_favorite': is_favorite,
            'favorites_count': furniture.favorites.count(),
            'detail': msg
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my_favorites(self, request):
        """Returns the paginated list of furniture the current user has marked as favorite."""
        furniture = Furniture.objects.filter(favorites__user=request.user).select_related('category', 'supplier')
        page = self.paginate_queryset(furniture)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(furniture, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Returns the 6 most recently updated in-stock items for the home featured section."""
        featured = Furniture.objects.filter(stock__gt=0).select_related('category', 'supplier').order_by('-updated_at')[:6]
        serializer = self.get_serializer(featured, many=True)
        return Response(serializer.data)


# ==========================================
# 4. FAVORITES
# ==========================================

class FavoriteViewSet(viewsets.ModelViewSet):
    """Direct favorites management: staff sees all of them and each customer only their own."""
    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ConfigurablePageNumberPagination

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Favorite.objects.select_related('furniture', 'user', 'furniture__category', 'furniture__supplier').all()
        return Favorite.objects.filter(user=user).select_related('furniture', 'furniture__category', 'furniture__supplier')


# ==========================================
# 5. RESERVATIONS
# ==========================================

class ReservationViewSet(mixins.CreateModelMixin,
                         mixins.ListModelMixin,
                         mixins.RetrieveModelMixin,
                         viewsets.GenericViewSet):
    """Reservation lifecycle without direct PUT/PATCH/DELETE so stock is never changed uncontrolled.

    - The customer creates a reservation (deducts stock) and only sees their own.
    - Staff sees all of them and resolves them via /accept/ (creates a Sale) or /reject/ (restocks).
    - Pending ones expire after 5 days and return their stock automatically.
    """
    serializer_class = ReservationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ConfigurablePageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ReservationFilter
    search_fields = ['furniture__name', 'user__username']
    ordering_fields = ['created_at', 'quantity']
    ordering = ['-created_at']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # Lazy expiration check on API entry; avoids needing an external cron.
        Reservation.cancel_expired()

    def get_queryset(self):
        qs = Reservation.objects.select_related('furniture', 'user', 'furniture__category', 'furniture__supplier', 'sale')
        if self.request.user.is_staff:
            return qs
        return qs.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Reservations are for customers only; staff just manages and resolves them.
        if self.request.user.is_staff:
            raise PermissionDenied('El administrador no puede apartar muebles.')
        serializer.save()

    # Centralizes the atomic accept/reject transition and prevents concurrent double resolution.
    def _resolve(self, pk, new_status):
        reservation = Reservation.objects.filter(pk=pk).first()
        if reservation is None:
            return Response({'detail': 'Apartado no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        if not reservation.close(new_status):
            reservation.refresh_from_db(fields=['status'])
            return Response(
                {'detail': f'El apartado ya fue {reservation.get_status_display().lower()}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        reservation = self.get_queryset().get(pk=reservation.pk)
        return Response(self.get_serializer(reservation).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def accept(self, request, pk=None):
        return self._resolve(pk, Reservation.ACCEPTED)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def reject(self, request, pk=None):
        return self._resolve(pk, Reservation.REJECTED)
