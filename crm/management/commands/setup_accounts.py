import os
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = 'Admin va sotuvchi hisoblarini berilgan parol bilan yaratadi yoki yangilaydi.'

    def add_arguments(self, parser):
        parser.add_argument('--password', help='Har ikki hisob paroli; alternativ CRM_SETUP_ACCOUNTS_PASSWORD muhit o‘zgaruvchisi.')

    @transaction.atomic
    def handle(self, *args, **options):
        password = options.get('password') or os.environ.get('CRM_SETUP_ACCOUNTS_PASSWORD')
        if not password:
            raise CommandError('--password yoki CRM_SETUP_ACCOUNTS_PASSWORD kerak.')
        call_command('setup_crm', stdout=self.stdout)
        User = get_user_model()
        for username, admin, group in [('admin', True, 'Rahbar'), ('sotuvchi', False, 'Sotuvchi')]:
            user, _ = User.objects.get_or_create(username=username)
            user = User.objects.select_for_update().get(pk=user.pk)
            if not user.check_password(password):
                user.set_password(password)
                Token.objects.filter(user=user).delete()
            user.is_active = True
            user.is_staff = admin
            user.is_superuser = admin
            user.save()
            user.groups.set([Group.objects.get(name=group)])
            user.user_permissions.clear()
            self.stdout.write(self.style.SUCCESS(f'{username} hisobi tayyor.'))
