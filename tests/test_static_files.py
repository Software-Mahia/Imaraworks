"""Static files are served with DEBUG off (found by Lewis on #22).

Django serves static files itself only while DEBUG is on. The deployed demo
runs with DEBUG off, so without WhiteNoise /static/frontend/auth.js is a 404,
and the login page and every role page break. The test runner always uses
DEBUG=False, so these tests see what the deployed demo sees.
"""

from django.conf import settings
from django.test import SimpleTestCase, override_settings

# On the server, collectstatic copies every app's static files into
# STATIC_ROOT and WhiteNoise serves them from there. Running collectstatic in a
# test copies hundreds of admin files (about 17 seconds), so the test points
# STATIC_ROOT at the frontend's own static folder instead: same URL, same
# middleware, no copying.
FRONTEND_STATIC = settings.BASE_DIR / 'frontend' / 'static'


class StaticFilesTests(SimpleTestCase):

    @override_settings(STATIC_ROOT=FRONTEND_STATIC)
    def test_frontend_script_is_served_with_debug_off(self):
        resp = self.client.get('/static/frontend/auth.js')

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'const AUTH', b''.join(resp.streaming_content))

    def test_static_root_is_set_for_collectstatic(self):
        # collectstatic refuses to run without it, which would fail the deploy.
        self.assertEqual(settings.STATIC_ROOT, settings.BASE_DIR / 'staticfiles')
