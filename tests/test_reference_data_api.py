from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from apps.accounts.models import Profile
from apps.payment_requests.models import Project
from apps.vendors.models import Vendor


class ReferenceDataApiTests(APITestCase):
    def setUp(self):
        user = User.objects.create_user('alice', password='pw')
        Profile.objects.create(user=user, role=Profile.EMPLOYEE)
        self.user = user
        Vendor.objects.create(name='Metro Hardware Ltd.', service='Materials')
        Vendor.objects.create(name='Old Vendor', service='Retired', is_active=False)
        Project.objects.create(name='Westlands Project')

    def test_vendors_require_login(self):
        self.assertEqual(self.client.get('/api/vendors/').status_code, 401)

    def test_projects_require_login(self):
        self.assertEqual(self.client.get('/api/projects/').status_code, 401)

    def test_vendor_list_excludes_inactive(self):
        self.client.force_authenticate(self.user)
        res = self.client.get('/api/vendors/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual([v['name'] for v in res.data], ['Metro Hardware Ltd.'])

    def test_vendor_list_shape(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(set(self.client.get('/api/vendors/').data[0]), {'id', 'name', 'service'})

    def test_project_list(self):
        self.client.force_authenticate(self.user)
        res = self.client.get('/api/projects/')
        self.assertEqual([p['name'] for p in res.data], ['Westlands Project'])