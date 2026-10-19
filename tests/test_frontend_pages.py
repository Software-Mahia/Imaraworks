from django.test import TestCase


class PageRouteTests(TestCase):
    """The pages are plain templates (the role check runs in the browser), so each route must render."""

    def test_login_page_renders(self):
        res = self.client.get('/login/')
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'frontend/login.html')

    def test_role_pages_render(self):
        for path, template in [
            ('/employee/', 'frontend/employee.html'),
            ('/manager/', 'frontend/manager.html'),
            ('/finance/', 'frontend/finance.html'),
        ]:
            with self.subTest(path=path):
                res = self.client.get(path)
                self.assertEqual(res.status_code, 200)
                self.assertTemplateUsed(res, template)

    def test_home_redirects_to_login(self):
        self.assertRedirects(self.client.get('/'), '/login/')