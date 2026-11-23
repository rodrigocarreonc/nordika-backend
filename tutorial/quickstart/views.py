"""Vistas y ViewSets REST de Nordika: autenticación, catálogo, favoritos, apartados y SSE."""

import queue
import uuid

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import ProtectedError
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_GET
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import APIView, ObtainAuthToken
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from . import realtime
from .filters import ApartadoFilter, MuebleFilter
from .models import Apartado, Categoria, Favorito, Mueble, Proveedor
from .pagination import ConfigurablePageNumberPagination
from .permissions import IsAdminOrReadOnly
from .realtime import broker, format_sse_event, publish_event
from .serializers import (
    ApartadoSerializer,
    CategoriaSerializer,
    ClienteCreateSerializer,
    FavoritoSerializer,
    MuebleSerializer,
    ProveedorSerializer,
    RegisterSerializer,
    UserProfileSerializer,
    UserSerializer,
    validar_password,
)


# ==========================================
# 1. AUTENTICACIÓN Y USUARIOS
# ==========================================

class CustomAuthToken(ObtainAuthToken):
    """Inicia sesión y devuelve el token junto con el perfil para evitar una segunda llamada a /me/."""
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
    """Autoregistro público (AllowAny) que crea al cliente y devuelve su token de sesión al instante."""
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


class CrearClienteView(APIView):
    """Permite al staff dar de alta clientes desde el panel admin sin otorgar permisos de staff."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = ClienteCreateSerializer(data=request.data)
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
    """Consulta, edita parcialmente o desactiva la cuenta del usuario autenticado."""
    user = request.user
    if request.method == 'GET':
        serializer = UserProfileSerializer(user)
        return Response(serializer.data)

    if request.method == 'DELETE':
        # 400 y no 401: la app cierra sesión ante cualquier 401
        if not user.check_password(request.data.get('password') or ''):
            return Response({'detail': 'La contraseña es incorrecta.'}, status=status.HTTP_400_BAD_REQUEST)
        # Se desactiva en vez de borrar: Venta.apartado es PROTECT y el historial de ventas debe conservarse
        with transaction.atomic():
            # Libera username y email para que puedan volver a registrarse; uuid evita choques con usernames reales
            user.username = f'eliminado_{uuid.uuid4().hex}'
            user.email = ''
            user.is_active = False
            user.save(update_fields=['username', 'email', 'is_active'])
            Token.objects.filter(user=user).delete()
        # Después de desactivar: si algo falla aquí, los pendientes igual vencen solos a los 5 días
        for apartado in Apartado.objects.filter(usuario=user, estado=Apartado.PENDIENTE):
            apartado.cerrar(Apartado.CANCELADO)
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = UserProfileSerializer(user, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """Revoca el token del usuario en servidor para invalidar la sesión inmediatamente."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            if hasattr(request.user, 'auth_token'):
                request.user.auth_token.delete()
        except Exception:
            pass
        return Response({'detail': 'Sesión cerrada exitosamente.'}, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    """Actualiza la contraseña y rota el token para invalidar sesiones previas en otros dispositivos."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        new_password = request.data.get('new_password') or ''
        if not user.check_password(request.data.get('current_password') or ''):
            return Response({'detail': 'La contraseña actual es incorrecta.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validar_password(new_password, user)
        except ValidationError as e:
            return Response({'detail': ' '.join(e.detail['password'])}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save(update_fields=['password'])
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)
        return Response({'token': token.key, 'detail': 'Contraseña actualizada.'}, status=status.HTTP_200_OK)


class ResetTokenView(APIView):
    """Rota el token de acceso sin cerrar sesión al cliente actual, invalidando tokens viejos."""
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
    """CRUD de proveedores (solo escritura staff); captura ProtectedError y responde 409 legible."""
    queryset = Proveedor.objects.all().order_by('nombre')
    serializer_class = ProveedorSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]
    pagination_class = None  # catálogo chico: la app lo usa completo en filtros y formularios
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'contacto', 'email', 'telefono']
    ordering_fields = ['nombre', 'creado_en']

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


class CategoriaViewSet(viewsets.ModelViewSet):
    """CRUD de categorías sin paginación para poblar selects y chips de filtro de una sola vez."""
    queryset = Categoria.objects.all().order_by('nombre')
    serializer_class = CategoriaSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]
    pagination_class = None  # catálogo chico: la app lo usa completo en filtros y formularios
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'descripcion']
    ordering_fields = ['nombre']


# ==========================================
# 3. MUEBLES (CATÁLOGO, CRUD Y CUSTOM ACTIONS)
# ==========================================

class MuebleViewSet(viewsets.ModelViewSet):
    """Catálogo de muebles con filtros, paginación y acciones de favoritos/destacados.

    Usa select_related para traer categoría y proveedor en una sola consulta SQL.
    """
    queryset = Mueble.objects.select_related('categoria', 'proveedor').all()
    serializer_class = MuebleSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]
    pagination_class = ConfigurablePageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = MuebleFilter
    search_fields = ['nombre', 'descripcion', 'categoria__nombre', 'proveedor__nombre']
    ordering_fields = ['precio', 'stock', 'creado_en', 'nombre']
    ordering = ['-creado_en']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # Libera el stock de apartados vencidos antes de mostrarlo.
        Apartado.cancelar_vencidos()

    def destroy(self, request, *args, **kwargs):
        """
        Elimina un mueble respetando la protección de apartados activos o vendidos.

        - Apartado.mueble mantiene on_delete=models.PROTECT para que ningún apartado
          quede con mueble=null en respuestas de la API (p. ej. apartados.tsx).
        - Si existen apartados PENDIENTE, ACEPTADO o con Venta asociada, responde
          409 Conflict y bloquea la eliminación.
        - Si solo existen apartados RECHAZADO o CANCELADO sin venta, los elimina
          en la misma transacción atómica antes de borrar el mueble (204 No Content),
          por lo que esos registros dejan de mostrarse en el historial.
        """
        instance = self.get_object()
        # Solo bloquean eliminación los apartados pendientes o aceptados/vendidos.
        # Apartados ya rechazados o cancelados sin venta permiten eliminar el mueble.
        blocking_count = instance.apartados.exclude(
            estado__in=[Apartado.RECHAZADO, Apartado.CANCELADO],
            venta__isnull=True,
        ).count()
        if blocking_count > 0:
            plural = "apartados asociados" if blocking_count != 1 else "apartado asociado"
            return Response(
                {'detail': f"No se puede eliminar: el mueble tiene {blocking_count} {plural}."},
                status=status.HTTP_409_CONFLICT
            )
        try:
            with transaction.atomic():
                apartados_eliminados, _ = instance.apartados.filter(
                    estado__in=[Apartado.RECHAZADO, Apartado.CANCELADO],
                    venta__isnull=True,
                ).delete()
                if apartados_eliminados:
                    # Asegura el aviso de borrado masivo de apartados cerrados tras confirmar el commit.
                    publish_event('apartado', 'deleted', None)
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
    def toggle_favorito(self, request, pk=None):
        """Alterna el estado de favorito del mueble para el usuario autenticado."""
        mueble = self.get_object()
        # Borrar primero y crear con get_or_create: con exists() + create(), un doble toque
        # hacía que ambas peticiones intentaran crear y la segunda chocaba con unique_together (500).
        borrados, _ = Favorito.objects.filter(usuario=request.user, mueble=mueble).delete()
        is_favorito = not borrados
        if is_favorito:
            favorito, creado = Favorito.objects.get_or_create(usuario=request.user, mueble=mueble)
            if not creado:
                # Si hubo carrera por doble toque, emitimos igual el favorito para sincronizar clientes.
                publish_event('favorito', 'created', favorito.pk)
        # Notificamos el mueble porque cambian sus campos derivados (is_favorito y favoritos_count).
        publish_event('mueble', 'updated', mueble.pk)
        msg = "Mueble agregado a favoritos." if is_favorito else "Mueble eliminado de favoritos."

        total_favoritos = mueble.favoritos.count()
        return Response({
            'mueble_id': mueble.id,
            'is_favorito': is_favorito,
            'total_favoritos': total_favoritos,
            'detail': msg
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def mis_favoritos(self, request):
        """Devuelve la lista paginada de muebles que el usuario actual ha marcado como favoritos."""
        muebles = Mueble.objects.filter(favoritos__usuario=request.user).select_related('categoria', 'proveedor')
        page = self.paginate_queryset(muebles)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(muebles, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def destacados(self, request):
        """Devuelve los 6 muebles con stock más recientes para la sección destacada del inicio."""
        destacados = Mueble.objects.filter(stock__gt=0).select_related('categoria', 'proveedor').order_by('-actualizado_en')[:6]
        serializer = self.get_serializer(destacados, many=True)
        return Response(serializer.data)


# ==========================================
# 4. FAVORITOS
# ==========================================

class FavoritoViewSet(viewsets.ModelViewSet):
    """Gestion directa de favoritos: el staff ve todos y cada cliente solo los suyos."""
    serializer_class = FavoritoSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ConfigurablePageNumberPagination

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Favorito.objects.select_related('mueble', 'usuario', 'mueble__categoria', 'mueble__proveedor').all()
        return Favorito.objects.filter(usuario=user).select_related('mueble', 'mueble__categoria', 'mueble__proveedor')


# ==========================================
# 5. APARTADOS
# ==========================================

class ApartadoViewSet(mixins.CreateModelMixin,
                      mixins.ListModelMixin,
                      mixins.RetrieveModelMixin,
                      viewsets.GenericViewSet):
    """Ciclo de vida de apartados sin PUT/PATCH/DELETE directos para no alterar stock sin control.

    - El cliente crea un apartado (descuenta stock) y consulta solo los propios.
    - El staff consulta todos y los resuelve vía /aceptar/ (crea Venta) o /rechazar/ (repone stock).
    - Los pendientes vencen a los 5 días y devuelven su stock automáticamente.
    """
    serializer_class = ApartadoSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ConfigurablePageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ApartadoFilter
    search_fields = ['mueble__nombre', 'usuario__username']
    ordering_fields = ['creado_en', 'cantidad']
    ordering = ['-creado_en']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # Evaluación perezosa de vencimientos al entrar a la API; evita requerir un cron externo.
        Apartado.cancelar_vencidos()

    def get_queryset(self):
        qs = Apartado.objects.select_related('mueble', 'usuario', 'mueble__categoria', 'mueble__proveedor', 'venta')
        if self.request.user.is_staff:
            return qs
        return qs.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        # El inventario de apartados esta reservado a clientes; el staff solo administra y resuelve.
        if self.request.user.is_staff:
            raise PermissionDenied('El administrador no puede apartar muebles.')
        serializer.save()

    # Centraliza la transición atómica de aceptar/rechazar y evita doble resolución concurrente.
    def _resolver(self, pk, nuevo_estado):
        apartado = Apartado.objects.filter(pk=pk).first()
        if apartado is None:
            return Response({'detail': 'Apartado no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        if not apartado.cerrar(nuevo_estado):
            apartado.refresh_from_db(fields=['estado'])
            return Response(
                {'detail': f'El apartado ya fue {apartado.estado.lower()}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        apartado = self.get_queryset().get(pk=apartado.pk)
        return Response(self.get_serializer(apartado).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def aceptar(self, request, pk=None):
        return self._resolver(pk, Apartado.ACEPTADO)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def rechazar(self, request, pk=None):
        return self._resolver(pk, Apartado.RECHAZADO)


# ==========================================
# 6. TIEMPO REAL (SERVER-SENT EVENTS)
# ==========================================

def _authenticate_sse_token(request):
    """Valida el token DRF desde Authorization o ?token= para soportar EventSource en web.

    EventSource en navegadores no permite cabeceras personalizadas, así que se acepta
    el token por query string únicamente cuando no viene cabecera Authorization.
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '').strip()
    token_key = None
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == 'token':
            token_key = parts[1]
    else:
        token_key = (request.GET.get('token') or '').strip()

    if not token_key:
        return None

    token = (
        Token.objects.select_related('user')
        .filter(key=token_key, user__is_active=True)
        .first()
    )
    return token.user if token else None


@require_GET
def events_stream(request):
    """Entrega un flujo SSE en vivo con cambios de catálogo, apartados y favoritos.

    Se define como vista estándar de Django (sin @api_view de DRF) para que la negociación
    de contenido de DRF nunca rechace `Accept: text/event-stream` con 406.
    """
    user = _authenticate_sse_token(request)
    if user is None:
        return JsonResponse(
            {'detail': 'Credenciales de autenticación inválidas o ausentes.'},
            status=401,
        )

    # Permite cerrar el flujo justo tras el handshake en pruebas o chequeos rápidos (?once=1).
    once = request.GET.get('once', '').lower() in ('1', 'true', 'yes')

    def event_generator():
        # Suscribe al broker antes del handshake para no perder eventos durante el arranque del flujo.
        with broker.subscribe() as subscriber_queue:
            yield format_sse_event('connected', {'status': 'ok'})
            if once:
                return
            while True:
                try:
                    event = subscriber_queue.get(timeout=realtime.SSE_KEEPALIVE_SECONDS)
                    yield format_sse_event('update', event)
                except queue.Empty:
                    # Comentario SSE periódico para mantener viva la conexión sin alterar el estado del cliente.
                    yield ': keepalive\n\n'

    response = StreamingHttpResponse(
        event_generator(),
        content_type='text/event-stream; charset=utf-8',
    )
    # Evita caché y buffering en proxies; no se fija `Connection` porque WSGI prohíbe cabeceras hop-by-hop.
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response
