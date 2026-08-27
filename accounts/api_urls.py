from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .api import PortalTokenObtainPairSerializer
from .api_throttles import LoginRateThrottle
from .api_views import CurrentUserAPIView


class PortalTokenObtainPairView(TokenObtainPairView):
    serializer_class = PortalTokenObtainPairSerializer
    throttle_classes = (LoginRateThrottle,)


app_name = 'api_auth'

urlpatterns = [
    path('token/', PortalTokenObtainPairView.as_view(), name='token'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', CurrentUserAPIView.as_view(), name='me'),
]
