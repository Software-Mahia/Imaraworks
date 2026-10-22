from unittest import mock

from django.db import OperationalError
from django.test import TestCase


class HealthTests(TestCase):
    def test_health_is_ok_without_logging_in(self):
        res = self.client.get('/health/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {'status': 'ok'})

    def test_ready_is_ok_when_the_database_answers(self):
        res = self.client.get('/ready/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {'status': 'ok'})

    def test_ready_reports_503_when_the_database_is_down(self):
        with mock.patch('imaraworks.health.connection') as conn:
            conn.cursor.side_effect = OperationalError('database down')
            res = self.client.get('/ready/')
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json(), {'status': 'unavailable'})

    def test_post_is_not_allowed(self):
        self.assertEqual(self.client.post('/health/').status_code, 405)
        self.assertEqual(self.client.post('/ready/').status_code, 405)

    def test_responses_are_never_cached(self):
        self.assertIn('no-store', self.client.get('/health/')['Cache-Control'])

    def test_a_failed_readiness_check_is_logged(self):
        with mock.patch('imaraworks.health.connection') as conn:
            conn.cursor.side_effect = OperationalError('database down')
            with self.assertLogs('imaraworks.health', level='ERROR'):
                self.client.get('/ready/')