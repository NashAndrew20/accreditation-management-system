from django.urls import path

from . import views

app_name = 'intelligence'

urlpatterns = [
    path('reports/', views.ReportsMonitoringView.as_view(), name='reports_monitoring'),
    path('reports/export/', views.ReportsMonitoringExportView.as_view(), name='reports_export'),
    path('smart-companion/', views.SmartCompanionView.as_view(), name='smart_companion'),
]
