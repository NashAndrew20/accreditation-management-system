from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('notifications/', views.NotificationsView.as_view(), name='notifications'),
    path('audit-history/', views.AuditHistoryView.as_view(), name='audit_history'),
    path('privacy-notice/', views.PrivacyNoticeView.as_view(), name='privacy_notice'),
    path('consent/', views.ConsentView.as_view(), name='consent'),
    path('consent/accept/', views.ConsentAcceptView.as_view(), name='consent_accept'),
    path('policies/<str:slug>/', views.PolicyDetailView.as_view(), name='policy_detail'),
]
