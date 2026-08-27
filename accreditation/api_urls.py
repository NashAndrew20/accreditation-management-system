from django.urls import path

from .api_views import EvidenceSubmissionListAPIView


app_name = 'api_evidence'

urlpatterns = [
    path('', EvidenceSubmissionListAPIView.as_view(), name='list'),
]
