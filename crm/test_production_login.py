from io import StringIO
from tempfile import TemporaryDirectory
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import override_settings
from crm.tests import BusinessFixtures


class ProductionLoginTests(BusinessFixtures):
    def test_admin_and_seller_can_log_in_and_open_landing_pages(self):
        self.purchase()
        call_command('setup_crm', stdout=StringIO())
        seller = User.objects.create_user('production-seller', password='Mobile-password-123')
        seller.groups.add(Group.objects.get(name='Sotuvchi'))
        with TemporaryDirectory() as root:
            with override_settings(DEBUG=False, STATIC_ROOT=root, SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True, SECURE_SSL_REDIRECT=True, SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'), STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'}}):
                call_command('collectstatic', interactive=False, verbosity=0, stdout=StringIO())
                for username, password, landing in [('owner', 'test-password-123', '/'), ('production-seller', 'Mobile-password-123', '/documents/')]:
                    with self.subTest(user=username):
                        self.client.logout()
                        response = self.client.get('/login/', secure=True)
                        self.assertEqual(response.status_code, 200)
                        response = self.client.post('/login/', {'username': username, 'password': password}, secure=True, follow=True)
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response.wsgi_request.path, landing)
