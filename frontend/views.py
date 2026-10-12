from django.shortcuts import render
from django.views.generic import TemplateView

class EmployeeView(TemplateView):
    template_name = "frontend/employee.html"

class ManagerView(TemplateView):
    template_name = "frontend/manager.html"

class FinanceView(TemplateView):
    template_name = "frontend/finance.html"
# Create your views here.
