"""Backend root routing: combines authentication, REST resources and media."""

from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path
from django.views.static import serve
from tutorial.quickstart.views import (
    ChangePasswordView,
    CreateCustomerView,
    CustomAuthToken,
    LogoutView,
    RegisterView,
    ResetTokenView,
    me,
)

# Session and account endpoints grouped so they can be mounted both at the root and under /api/.
auth_urlpatterns = [
    path('api-token-auth/', CustomAuthToken.as_view(), name='api_token_auth'),
    path('api-register/', RegisterView.as_view(), name='api_register'),
    path('users/create_customer/', CreateCustomerView.as_view(), name='create_customer'),
    path('me/', me, name='me'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('reset-token/', ResetTokenView.as_view(), name='reset_token'),
]

# Routes are exposed both at the root and under /api/ to stay compatible with
# older clients and with prefixed REST conventions.
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    *auth_urlpatterns,
    path('', include('tutorial.quickstart.urls')),
    path('api/', include('tutorial.quickstart.urls')),
    path('api/', include(auth_urlpatterns)),
]

# Serves uploaded images even with DEBUG=False on Azure App Service, where there is no
# dedicated media file server (such as S3 or Nginx) in front of Django.
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
