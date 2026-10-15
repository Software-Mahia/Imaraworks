from django.urls import path
from .views import PaymentRequestListCreate, PaymentRequestDetail

urlpatterns = [
    path('', PaymentRequestListCreate.as_view()),
    path('<int:pk>/', PaymentRequestDetail.as_view()),
]