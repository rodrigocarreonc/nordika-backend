"""Enrutamiento raíz del backend: combina autenticación, recursos REST y media."""

from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path
from django.views.static import serve
from tutorial.quickstart.views import (
    ChangePasswordView,
    CrearClienteView,
    CustomAuthToken,
    LogoutView,
    RegisterView,
    ResetTokenView,
    me,
)

# Endpoints de sesión y cuenta agrupados para montarlos tanto en raíz como bajo /api/.
auth_urlpatterns = [
    path('api-token-auth/', CustomAuthToken.as_view(), name='api_token_auth'),
    path('api-register/', RegisterView.as_view(), name='api_register'),
    path('users/crear_cliente/', CrearClienteView.as_view(), name='crear_cliente'),
    path('me/', me, name='me'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('reset-token/', ResetTokenView.as_view(), name='reset_token'),
]

# Se exponen las rutas en raíz y bajo /api/ para mantener compatibilidad con
# clientes anteriores y convenciones REST con prefijo.
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    *auth_urlpatterns,
    path('', include('tutorial.quickstart.urls')),
    path('api/', include('tutorial.quickstart.urls')),
    path('api/', include(auth_urlpatterns)),
]

# Sirve imágenes subidas incluso con DEBUG=False en Azure App Service, donde no hay
# un servidor de archivos media dedicado (como S3 o Nginx) delante de Django.
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
