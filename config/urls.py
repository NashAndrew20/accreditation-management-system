"""
URL configuration for the JMCFI AMS project.

Each feature lives in its own app with its own urls.py. This file only
wires apps together under a namespace/prefix, so new modules (e.g. a
future `submissions` app) can be added here without touching anything
else.
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from accounts import views as account_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', account_views.PortalLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    path('register/', account_views.RegisterView.as_view(), name='register'),
    path('api/auth/', include('accounts.api_urls')),
    path('api/evidence/', include('accreditation.api_urls')),

    path('', include('dashboard.urls')),
    path('', include('core.urls')),
    path('accreditation/', include('accreditation.urls')),
    path('resources/', include('resources.urls')),
    path('intelligence/', include('intelligence.urls')),
    path('account/', include('accounts.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
