from django.core.management.base import BaseCommand
from django.db import transaction
from crm.models import Category, Product


class Command(BaseCommand):
    help = 'Qurilish mahsulotlarini narx va qoldiqni o‘zgartirmasdan katalogga qo‘shadi.'

    @transaction.atomic
    def handle(self, *args, **options):
        products = [
            ('SEM-400', 'Sement M400 (50 kg)', 'Sement va qorishmalar', 'qop'),
            ('SEM-500', 'Sement M500 (50 kg)', 'Sement va qorishmalar', 'qop'),
            ('OHK-001', 'Ohak', 'Sement va qorishmalar', 'kg'),
            ('QUM-001', 'Qum', 'Qum va shag‘al', 'm3'),
            ('SHG-001', 'Shag‘al', 'Qum va shag‘al', 'm3'),
            ('GIS-001', 'Pishiq g‘isht', 'G‘isht va bloklar', 'dona'),
            ('BLO-001', 'Gazoblok', 'G‘isht va bloklar', 'dona'),
            ('ARM-012', 'Armatura 12 mm', 'Metall va armatura', 'm'),
            ('GIP-001', 'Gipsli suvoq (30 kg)', 'Sement va qorishmalar', 'qop'),
            ('YEL-001', 'Kafel yelimi (25 kg)', 'Sement va qorishmalar', 'qop'),
        ]
        created = 0
        for sku, name, category_name, unit in products:
            category, _ = Category.objects.get_or_create(name=category_name)
            _, added = Product.objects.get_or_create(sku=sku, defaults={'name': name, 'category': category, 'unit': unit})
            created += added
        self.stdout.write(self.style.SUCCESS(f'{created} ta yangi mahsulot qo‘shildi. Narx va haqiqiy qoldiqni kiriting.'))
