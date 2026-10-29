from django.urls import path
from .views import AuditView, EmployeeView, ManagerView, FinanceView, LoginView
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/login/'), name='home'),
    path('employee/', EmployeeView.as_view(), name='employee-view'),
    path('manager/', ManagerView.as_view(), name='manager-view'),
    path('finance/', FinanceView.as_view(), name='finance-view'),
    path('audit/', AuditView.as_view(), name='audit-view'),
    path('login/', LoginView.as_view(), name='login'),
]
