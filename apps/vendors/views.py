from django.db.models import QuerySet
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Vendor
from .serializers import VendorSerializer


class VendorList(generics.ListAPIView):
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[Vendor]:
        return Vendor.objects.filter(is_active=True).order_by('name')