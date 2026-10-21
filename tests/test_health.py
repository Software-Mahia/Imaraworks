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