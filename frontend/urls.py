from django.urls import path
from .views import EmployeeView, ManagerView, FinanceView

urlpatterns = [
    path('employee/', EmployeeView.as_view(), name='employee-view'),
    path('manager/', ManagerView.as_view(), name='manager-view'),
    path('finance/', FinanceView.as_view(), name='finance-view'),
]