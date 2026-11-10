from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction
from crm.models import Category, Warehouse

class Command(BaseCommand):
    help = 'Boshlang‘ich ombor, kategoriyalar va xodim rollarini yaratadi.'

    @transaction.atomic
    def handle(self, *args, **options):
        Warehouse.objects.get_or_create(name='Asosiy ombor')
        for name in ['Sement va qorishmalar', 'Metall va armatura', 'G‘isht va bloklar', 'Yog‘och', 'Bo‘yoqlar', 'Santexnika', 'Elektr mollari', 'Asbob-uskunalar']:
            Category.objects.get_or_create(name=name)
        roles = {
            'Rahbar': list(Permission.objects.filter(content_type__app_label='crm').values_list('codename', flat=True)),
            'Sotuvchi': ['view_document', 'add_document', 'view_product', 'view_stock', 'view_partner', 'add_partner'],
            'Omborchi': ['view_document', 'view_product', 'view_stock', 'view_warehouse'],
            'Hisobchi': ['view_document', 'view_product', 'view_stock', 'view_partner', 'view_payment', 'add_payment', 'view_expense', 'add_expense'],
        }
        # Sotuvchi faqat sotuv va mijozdan qaytarish hujjatlarini yaratadi.
        for name, codes in roles.items():
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.set(Permission.objects.filter(content_type__app_label='crm', codename__in=codes))
        self.stdout.write(self.style.SUCCESS('Ombor, kategoriyalar va 4 ta rol tayyor.'))
