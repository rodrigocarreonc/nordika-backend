from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path
from django.views.static import serve
from tutorial.quickstart.views import (
    CustomAuthToken,
    LogoutView,
    RegisterView,
    ResetTokenView,
    me,
)

auth_urlpatterns = [
    path('api-token-auth/', CustomAuthToken.as_view(), name='api_token_auth'),
    path('api-register/', RegisterView.as_view(), name='api_register'),
    path('me/', me, name='me'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('reset-token/', ResetTokenView.as_view(), name='reset_token'),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    # Auth endpoints at root
    *auth_urlpatterns,
    # Router endpoints at root
    path('', include('tutorial.quickstart.urls')),
    # Also available under /api/ prefix for standard REST convention
    path('api/', include('tutorial.quickstart.urls')),
    path('api/', include(auth_urlpatterns)),
]

# Media files serving (works in development and Azure Web App)
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
