from io import StringIO
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.authtoken.models import Token


class SetupAccountsTests(TestCase):
    def test_accounts_password_roles_and_repeated_execution(self):
        call_command('setup_accounts', password='123', stdout=StringIO())
        User = get_user_model()
        admin = User.objects.get(username='admin')
        seller = User.objects.get(username='sotuvchi')
        self.assertTrue(admin.check_password('123'))
        self.assertTrue(admin.is_superuser)
        self.assertTrue(seller.check_password('123'))
        self.assertFalse(seller.is_superuser)
        self.assertFalse(seller.is_staff)
        self.assertTrue(seller.has_perm('crm.add_document'))
        self.assertFalse(seller.has_perm('crm.manage_inventory_documents'))
        token = Token.objects.create(user=seller)
        call_command('setup_accounts', password='123', stdout=StringIO())
        self.assertEqual(User.objects.count(), 2)
        self.assertTrue(Token.objects.filter(pk=token.pk).exists())
        call_command('setup_accounts', password='new-password', stdout=StringIO())
        seller.refresh_from_db()
        self.assertTrue(seller.check_password('new-password'))
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())

    def test_password_required(self):
        from unittest.mock import patch
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(CommandError):
                call_command('setup_accounts', stdout=StringIO())
