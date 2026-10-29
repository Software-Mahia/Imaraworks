from django.views.generic import TemplateView


class EmployeeView(TemplateView):
    template_name = "frontend/employee.html"


class ManagerView(TemplateView):
    template_name = "frontend/manager.html"


class FinanceView(TemplateView):
    template_name = "frontend/finance.html"


class AuditView(TemplateView):
    """ADMIN-only in the browser (the guard in auth.js redirects other roles).

    Convenience only: /api/audit/ itself enforces Profile.role == ADMIN, and the
    payload is redacted, so this page can never show payment data.
    """

    template_name = "frontend/audit.html"


class LoginView(TemplateView):
    template_name = "frontend/login.html"
