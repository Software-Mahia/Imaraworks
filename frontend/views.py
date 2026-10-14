from django.views.generic import TemplateView

class EmployeeView(TemplateView):
    template_name = "frontend/employee.html"

class ManagerView(TemplateView):
    template_name = "frontend/manager.html"

class FinanceView(TemplateView):
    template_name = "frontend/finance.html"



class LoginView(TemplateView):
    template_name = "frontend/login.html"
# Create your views here.

