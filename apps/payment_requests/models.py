from django.contrib.auth.models import User
from django.db import models

from apps.vendors.models import Vendor


class Project(models.Model):
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name


class PaymentRequest(models.Model):
    DRAFT = 'DRAFT'
    SUBMITTED = 'SUBMITTED'
    PENDING_APPROVAL = 'PENDING_APPROVAL'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    PROCESSING = 'PROCESSING'
    PAID = 'PAID'
    FAILED = 'FAILED'
    STATUS_CHOICES = [
        (DRAFT, 'Draft'),
        (SUBMITTED, 'Submitted'),
        (PENDING_APPROVAL, 'Pending Approval'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
        (PROCESSING, 'Processing'),
        (PAID, 'Paid'),
        (FAILED, 'Failed'),
    ]

    MPESA = 'MPESA'
    BANK_TRANSFER = 'BANK_TRANSFER'
    CASH = 'CASH'
    PAYMENT_METHOD_CHOICES = [
        (MPESA, 'M-Pesa'),
        (BANK_TRANSFER, 'Bank Transfer'),
        (CASH, 'Cash'),
    ]

    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name='payment_requests')
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='payment_requests')
    requester = models.ForeignKey(User, on_delete=models.PROTECT, related_name='payment_requests')

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=500)
    invoice_number = models.CharField(max_length=100)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    date = models.DateField()
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['vendor', 'invoice_number'], name='unique_vendor_invoice')
        ]

    def __str__(self):
        return f"{self.vendor.name} - {self.invoice_number} - {self.amount}"