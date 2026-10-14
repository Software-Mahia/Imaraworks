from django.urls import path

from .views import VendorList

urlpatterns = [
    path('', VendorList.as_view()),
]