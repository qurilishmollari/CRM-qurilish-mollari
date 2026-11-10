from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

POSITIVE = MinValueValidator(Decimal('0.001'))
MONEY = MinValueValidator(Decimal('0'))

class Category(models.Model):
    name = models.CharField('Nomi', max_length=120, unique=True)
    class Meta:
        verbose_name = 'Kategoriya'
        verbose_name_plural = 'Kategoriyalar'
        ordering = ['name']
    def __str__(self): return self.name

class Warehouse(models.Model):
    name = models.CharField('Nomi', max_length=120, unique=True)
    address = models.CharField('Manzil', max_length=255, blank=True)
    class Meta:
        verbose_name = 'Ombor'
        verbose_name_plural = 'Omborlar'
    def __str__(self): return self.name

class Partner(models.Model):
    class Kind(models.TextChoices):
        CUSTOMER = 'customer', 'Mijoz'
        SUPPLIER = 'supplier', 'Yetkazib beruvchi'
    name = models.CharField('Ism / tashkilot', max_length=180)
    kind = models.CharField('Turi', max_length=15, choices=Kind.choices)
    phone = models.CharField('Telefon', max_length=40, blank=True)
    address = models.CharField('Manzil', max_length=255, blank=True)
    notes = models.TextField('Izoh', blank=True)
    class Meta:
        verbose_name = 'Hamkor'
        verbose_name_plural = 'Hamkorlar'
        ordering = ['name']
    def __str__(self): return self.name

class Product(models.Model):
    class Unit(models.TextChoices):
        PIECE = 'dona', 'Dona'
        KG = 'kg', 'Kilogramm'
        TON = 'tonna', 'Tonna'
        M = 'm', 'Metr'
        M2 = 'm2', 'Kvadrat metr'
        M3 = 'm3', 'Kub metr'
        BAG = 'qop', 'Qop'
    name = models.CharField('Tovar nomi', max_length=180)
    sku = models.CharField('Artikul', max_length=60, unique=True)
    barcode = models.CharField('Shtrix-kod', max_length=80, blank=True)
    category = models.ForeignKey(Category, verbose_name='Kategoriya', on_delete=models.PROTECT)
    unit = models.CharField('O‘lchov', max_length=10, choices=Unit.choices, default=Unit.PIECE)
    purchase_price = models.DecimalField('Xarid narxi', max_digits=18, decimal_places=2, validators=[MONEY], default=0)
    sale_price = models.DecimalField('Sotuv narxi', max_digits=18, decimal_places=2, validators=[MONEY], default=0)
    minimum_stock = models.DecimalField('Minimal qoldiq', max_digits=18, decimal_places=3, validators=[MONEY], default=0)
    active = models.BooleanField('Faol', default=True)
    class Meta:
        verbose_name = 'Tovar'
        verbose_name_plural = 'Tovarlar'
        ordering = ['name']
    def __str__(self): return f'{self.name} ({self.sku})'

class Stock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='Tovar')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, verbose_name='Ombor')
    quantity = models.DecimalField('Qoldiq', max_digits=18, decimal_places=3, default=0)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['product', 'warehouse'], name='unique_stock'), models.CheckConstraint(condition=Q(quantity__gte=0), name='nonnegative_stock')]
        verbose_name = 'Ombor qoldig‘i'
        verbose_name_plural = 'Ombor qoldiqlari'
    def __str__(self): return f'{self.product}: {self.quantity}'

class Document(models.Model):
    class Kind(models.TextChoices):
        SALE = 'sale', 'Sotuv'
        PURCHASE = 'purchase', 'Xarid / kirim'
        TRANSFER = 'transfer', 'Omborlararo ko‘chirish'
        RETURN = 'return', 'Mijozdan qaytarish'
    kind = models.CharField('Turi', max_length=15, choices=Kind.choices)
    partner = models.ForeignKey(Partner, verbose_name='Hamkor', on_delete=models.PROTECT, blank=True, null=True)
    buyer_name = models.CharField('Xaridor ismi', max_length=180, blank=True)
    buyer_phone = models.CharField('Telefon raqami', max_length=40, blank=True)
    warehouse = models.ForeignKey(Warehouse, verbose_name='Ombor', on_delete=models.PROTECT, related_name='documents')
    destination = models.ForeignKey(Warehouse, verbose_name='Qabul qiluvchi ombor', on_delete=models.PROTECT, related_name='incoming_documents', blank=True, null=True)
    original = models.ForeignKey('self', verbose_name='Asl sotuv', on_delete=models.PROTECT, blank=True, null=True)
    created_at = models.DateTimeField('Sana', auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='Xodim')
    posted = models.BooleanField('Tasdiqlangan', default=False)
    notes = models.TextField('Izoh', blank=True)
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Hujjat'
        verbose_name_plural = 'Hujjatlar'
        permissions = [('manage_inventory_documents', 'Xarid va ombor ko‘chirish hujjatlarini boshqarish')]
    @property
    def total(self): return sum((line.quantity * line.price for line in self.lines.all()), Decimal('0'))
    def __str__(self): return f'#{self.pk} — {self.get_kind_display()}'

class DocumentLine(models.Model):
    document = models.ForeignKey(Document, related_name='lines', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, verbose_name='Tovar', on_delete=models.PROTECT)
    quantity = models.DecimalField('Miqdor', max_digits=18, decimal_places=3, validators=[POSITIVE])
    price = models.DecimalField('Birlik narxi', max_digits=18, decimal_places=2, validators=[MONEY])
    cost = models.DecimalField('Tannarx', max_digits=18, decimal_places=2, default=0)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0), name='positive_line_quantity'), models.CheckConstraint(condition=Q(price__gte=0), name='nonnegative_line_price'), models.UniqueConstraint(fields=['document', 'product'], name='unique_document_product')]

class Payment(models.Model):
    class Direction(models.TextChoices):
        IN = 'in', 'Kirim'
        OUT = 'out', 'Chiqim'
    partner = models.ForeignKey(Partner, verbose_name='Hamkor', on_delete=models.PROTECT)
    direction = models.CharField('Yo‘nalish', max_length=3, choices=Direction.choices)
    amount = models.DecimalField('Summa', max_digits=18, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    method = models.CharField('To‘lov usuli', max_length=10, choices=[('cash', 'Naqd'), ('card', 'Karta'), ('bank', 'Bank')], default='cash')
    notes = models.CharField('Izoh', max_length=255, blank=True)
    created_at = models.DateTimeField('Sana', auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    class Meta:
        ordering = ['-created_at']
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name='positive_payment')]
        verbose_name = 'To‘lov'
        verbose_name_plural = 'To‘lovlar'

class Expense(models.Model):
    title = models.CharField('Xarajat nomi', max_length=180)
    amount = models.DecimalField('Summa', max_digits=18, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    date = models.DateField('Sana')
    notes = models.TextField('Izoh', blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    class Meta:
        ordering = ['-date']
        verbose_name = 'Xarajat'
        verbose_name_plural = 'Xarajatlar'
