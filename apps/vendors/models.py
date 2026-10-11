from django.db import models


class Vendor(models.Model):
    name = models.CharField(max_length=200, unique=True)
    service = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
