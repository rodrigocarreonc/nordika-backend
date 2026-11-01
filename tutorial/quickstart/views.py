from django.contrib.auth.models import User
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import APIView, ObtainAuthToken
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from .filters import MuebleFilter, MovimientoInventarioFilter
from .models import Categoria, Favorito, MovimientoInventario, Mueble, Proveedor
from .pagination import ConfigurablePageNumberPagination
from .permissions import IsAuthenticatedOrReadOnly
from .serializers import (
    CategoriaSerializer,
    FavoritoSerializer,
    MovimientoInventarioSerializer,
    MuebleSerializer,
    ProveedorSerializer,
    RegisterSerializer,
    UserSerializer,
)


# ==========================================
# 1. AUTENTICACIÓN Y USUARIOS
# ==========================================

class CustomAuthToken(ObtainAuthToken):
    """
    Inicia sesión con username y password, devolviendo el token y datos del usuario.
    """
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
    """
    Registra un nuevo usuario y devuelve el token de sesión inmediatamente.
    """
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


@api_view(['GET', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def me(request):
    """
    Obtiene o actualiza el perfil del usuario autenticado.
    """
    user = request.user
    if request.method == 'GET':
        serializer = UserSerializer(user)
        return Response(serializer.data)

    data = request.data
    if 'email' in data:
        email = data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            return Response({'email': ['Este correo ya está en uso.']}, status=status.HTTP_400_BAD_REQUEST)
        user.email = email

    if 'first_name' in data:
        user.first_name = data['first_name']

    if 'last_name' in data:
        user.last_name = data['last_name']

    user.save()
    serializer = UserSerializer(user)
    return Response(serializer.data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    Cierra la sesión del usuario actual eliminando su token.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            if hasattr(request.user, 'auth_token'):
                request.user.auth_token.delete()
        except Exception:
            pass
        return Response({'detail': 'Sesión cerrada exitosamente.'}, status=status.HTTP_200_OK)


class ResetTokenView(APIView):
    """
    Regenera el token de autenticación del usuario.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        token = Token.objects.create(user=request.user)
        return Response({
            'token': token.key,
            'detail': 'Token restablecido exitosamente.'
        }, status=status.HTTP_200_OK)


# ==========================================
# 2. PROVEEDORES Y CATEGORÍAS
# ==========================================

class ProveedorViewSet(viewsets.ModelViewSet):
    queryset = Proveedor.objects.all().order_by('nombre')
    serializer_class = ProveedorSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = ConfigurablePageNumberPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'contacto', 'email', 'telefono']
    ordering_fields = ['nombre', 'creado_en']


class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all().order_by('nombre')
    serializer_class = CategoriaSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = ConfigurablePageNumberPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'descripcion']
    ordering_fields = ['nombre']


# ==========================================
# 3. MUEBLES (CATÁLOGO, CRUD Y CUSTOM ACTIONS)
# ==========================================

class MuebleViewSet(viewsets.ModelViewSet):
    """
    ViewSet para Muebles:
    - Búsqueda por nombre, descripción, categoría y proveedor.
    - Filtros por categoría, proveedor, rango de precio (precio_min, precio_max) y en_stock.
    - Ordenamiento por precio, stock, nombre, creado_en.
    - Paginación configurable.
    - Custom actions: toggle_favorito, mis_favoritos, destacados, registrar_movimiento.
    """
    queryset = Mueble.objects.select_related('categoria', 'proveedor').all()
    serializer_class = MuebleSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = ConfigurablePageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = MuebleFilter
    search_fields = ['nombre', 'descripcion', 'categoria__nombre', 'proveedor__nombre']
    ordering_fields = ['precio', 'stock', 'creado_en', 'nombre']
    ordering = ['-creado_en']

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def toggle_favorito(self, request, pk=None):
        """
        Alterna el estado de favorito del mueble para el usuario autenticado.
        """
        mueble = self.get_object()
        favorito_qs = Favorito.objects.filter(usuario=request.user, mueble=mueble)

        if favorito_qs.exists():
            favorito_qs.delete()
            is_favorito = False
            msg = "Mueble eliminado de favoritos."
        else:
            Favorito.objects.create(usuario=request.user, mueble=mueble)
            is_favorito = True
            msg = "Mueble agregado a favoritos."

        total_favoritos = mueble.favoritos.count()
        return Response({
            'mueble_id': mueble.id,
            'is_favorito': is_favorito,
            'total_favoritos': total_favoritos,
            'detail': msg
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def mis_favoritos(self, request):
        """
        Devuelve la lista paginada de muebles que el usuario actual ha marcado como favoritos.
        """
        muebles = Mueble.objects.filter(favoritos__usuario=request.user).select_related('categoria', 'proveedor')
        page = self.paginate_queryset(muebles)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(muebles, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def destacados(self, request):
        """
        Devuelve los muebles destacados (los primeros 6 con stock disponible).
        """
        destacados = Mueble.objects.filter(stock__gt=0).select_related('categoria', 'proveedor').order_by('-actualizado_en')[:6]
        serializer = self.get_serializer(destacados, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def registrar_movimiento(self, request, pk=None):
        """
        Registra un movimiento de inventario directamente para este mueble.
        """
        mueble = self.get_object()
        data = request.data.dict() if hasattr(request.data, 'dict') else dict(request.data)
        cleaned_data = {}
        for k, v in data.items():
            cleaned_data[k] = v[0] if isinstance(v, list) and len(v) == 1 else v
        cleaned_data['mueble_id'] = mueble.id

        serializer = MovimientoInventarioSerializer(
            data=cleaned_data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        movimiento = serializer.save()
        return Response({
            'movimiento': MovimientoInventarioSerializer(movimiento).data,
            'stock_actual': mueble.stock,
            'detail': 'Movimiento registrado correctamente.'
        }, status=status.HTTP_201_CREATED)


# ==========================================
# 4. FAVORITOS
# ==========================================

class FavoritoViewSet(viewsets.ModelViewSet):
    serializer_class = FavoritoSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ConfigurablePageNumberPagination

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Favorito.objects.select_related('mueble', 'usuario', 'mueble__categoria', 'mueble__proveedor').all()
        return Favorito.objects.filter(usuario=user).select_related('mueble', 'mueble__categoria', 'mueble__proveedor')


# ==========================================
# 5. MOVIMIENTOS DE INVENTARIO
# ==========================================

class MovimientoInventarioViewSet(viewsets.ModelViewSet):
    queryset = MovimientoInventario.objects.select_related('mueble', 'usuario').all()
    serializer_class = MovimientoInventarioSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ConfigurablePageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = MovimientoInventarioFilter
    search_fields = ['mueble__nombre', 'motivo', 'usuario__username']
    ordering_fields = ['fecha_movimiento', 'cantidad']
    ordering = ['-fecha_movimiento']
