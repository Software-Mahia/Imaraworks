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
            ('/audit/', 'frontend/audit.html'),
        ]:
            with self.subTest(path=path):
                res = self.client.get(path)
                self.assertEqual(res.status_code, 200)
                self.assertTemplateUsed(res, template)

    def test_home_redirects_to_login(self):
        self.assertRedirects(self.client.get('/'), '/login/')


class LoginPageTests(TestCase):
    def test_login_can_reveal_the_password(self):
        res = self.client.get('/login/')
        self.assertContains(res, 'id="pw-toggle"')
        self.assertContains(res, 'aria-pressed="false"')
        self.assertContains(res, 'id="i-eye-off"')


class ShellTests(TestCase):
    """The shell is a top app bar with tab panels (no permanent sidebar)."""

    def test_role_pages_use_the_shared_shell(self):
        for path in ['/employee/', '/manager/', '/finance/', '/audit/']:
            with self.subTest(path=path):
                res = self.client.get(path)
                self.assertContains(res, 'id="page"')
                self.assertContains(res, 'id="guide-modal"')
                self.assertContains(res, 'role="tab"')

    def test_role_pages_expose_their_workspace_controls(self):
        # IDs are the contract between the templates and app.js, unlike styling classes.
        pages = {
            '/employee/': ['panel-requests', 'panel-payments', 'requests-list', 'new-request-btn'],
            '/manager/': ['panel-approvals', 'panel-requests', 'queue-list', 'recent-feed'],
            '/finance/': ['panel-payments', 'panel-requests', 'queue-list', 'results-list'],
            '/audit/': ['audit-feed', 'audit-search', 'scope-select', 'export-btn'],
        }
        for path, element_ids in pages.items():
            with self.subTest(path=path):
                res = self.client.get(path)
                for element_id in element_ids:
                    with self.subTest(element=element_id):
                        self.assertContains(res, f'id="{element_id}"')


class AuditPageTests(TestCase):
    """Admins get the audit trail with its feed filters and export."""

    def test_audit_page_keeps_its_feed_filters_and_export(self):
        res = self.client.get('/audit/')
        for element in [
            'id="kpi-total"',
            'id="daily-chart"',
            'id="action-chart"',
            'id="action-pills"',
            'id="audit-feed"',
            'id="audit-search"',
            'id="scope-select"',
            'id="export-btn"',
            'id="refresh-btn"',
        ]:
            with self.subTest(element=element):
                self.assertContains(res, element)
