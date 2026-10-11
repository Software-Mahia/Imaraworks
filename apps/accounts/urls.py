from django.urls import path
from .views import health_check, current_user

urlpatterns = [
    path('health/', health_check),
    path('auth/me/', current_user),
]