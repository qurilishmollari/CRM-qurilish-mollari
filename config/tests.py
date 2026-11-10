import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

from django.db import OperationalError
from django.test import SimpleTestCase, TestCase

from .database import postgres_database


class DeploymentSettingsTests(SimpleTestCase):
    def settings(self, **environment):
        spec = importlib.util.spec_from_file_location('config.railway_test_settings', Path(__file__).with_name('settings.py'))
        module = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, environment, clear=True):
            spec.loader.exec_module(module)
        return module

    def test_postgres_url_and_encoded_credentials(self):
        database = postgres_database('postgresql://crm%40user:a%3Ab%40c@postgres.railway.internal:5432/crm?sslmode=require')
        self.assertEqual(database['USER'], 'crm@user')
        self.assertEqual(database['PASSWORD'], 'a:b@c')
        self.assertEqual(database['HOST'], 'postgres.railway.internal')
        self.assertEqual(database['OPTIONS'], {'sslmode': 'require'})
        for url in ['sqlite:///db.sqlite3', 'https://example.com/database', 'postgresql://localhost']:
            with self.assertRaises(ValueError):
                postgres_database(url)

    def test_production_domain_proxy_and_static_settings(self):
        settings = self.settings(RAILWAY_ENVIRONMENT_ID='production', RAILWAY_PUBLIC_DOMAIN='crm.up.railway.app', DATABASE_URL='postgresql://user:pass@database/crm', DJANGO_SECRET_KEY='test-production-secret')
        self.assertFalse(settings.DEBUG)
        self.assertIn('crm.up.railway.app', settings.ALLOWED_HOSTS)
        self.assertIn('healthcheck.railway.app', settings.ALLOWED_HOSTS)
        self.assertIn('https://crm.up.railway.app', settings.CSRF_TRUSTED_ORIGINS)
        self.assertEqual(settings.SECURE_PROXY_SSL_HEADER, ('HTTP_X_FORWARDED_PROTO', 'https'))
        self.assertTrue(settings.SESSION_COOKIE_SECURE)
        self.assertIn('whitenoise.middleware.WhiteNoiseMiddleware', settings.MIDDLEWARE)
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.postgresql')

    def test_local_sqlite_and_missing_production_configuration(self):
        self.assertEqual(self.settings().DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        with self.assertRaisesRegex(RuntimeError, 'DATABASE_URL'):
            self.settings(DJANGO_DEBUG='0')
        with self.assertRaisesRegex(RuntimeError, 'DJANGO_SECRET_KEY'):
            self.settings(DJANGO_DEBUG='0', DATABASE_URL='postgresql://user:pass@database/crm')


class HealthTests(TestCase):
    def test_public_health_endpoint(self):
        response = self.client.get('/health/', HTTP_HOST='healthcheck.railway.app')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_database_failure_does_not_expose_credentials(self):
        with patch('config.health.connection.cursor', side_effect=OperationalError('private connection detail')):
            response = self.client.get('/health/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})
