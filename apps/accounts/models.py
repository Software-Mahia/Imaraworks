from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    EMPLOYEE = 'EMPLOYEE'
    MANAGER = 'MANAGER'
    FINANCE = 'FINANCE'
    ADMIN = 'ADMIN'
    ROLE_CHOICES = [
        (EMPLOYEE, 'Employee'),
        (MANAGER, 'Manager'),
        (FINANCE, 'Finance Officer'),
        (ADMIN, 'Administrator'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.username} ({self.role})"
