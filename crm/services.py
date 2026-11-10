from collections import defaultdict
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from .models import Document, Product, Stock

@transaction.atomic
def post_document(document_id):
    document = Document.objects.select_for_update().get(pk=document_id)
    from .permissions import allowed_document_kinds
    if not document.created_by.has_perm('crm.add_document') or document.kind not in allowed_document_kinds(document.created_by):
        raise ValidationError('Bu turdagi hujjatni yaratishga ruxsat yo‘q.')
    if document.posted:
        raise ValidationError('Hujjat allaqachon tasdiqlangan.')
    lines = list(document.lines.select_related('product').order_by('product_id'))
    if not lines:
        raise ValidationError('Kamida bitta tovar kiriting.')
    if document.kind == Document.Kind.TRANSFER:
        if not document.destination_id or document.destination_id == document.warehouse_id:
            raise ValidationError('Boshqa qabul qiluvchi omborni tanlang.')
    else:
        if not document.partner_id:
            raise ValidationError('Hamkorni tanlang.')
        expected = 'supplier' if document.kind == Document.Kind.PURCHASE else 'customer'
        if document.partner.kind != expected:
            raise ValidationError('Hujjat uchun hamkor turi noto‘g‘ri.')
    if document.kind == Document.Kind.RETURN:
        for line in lines:
            history = Document.objects.filter(partner=document.partner, warehouse=document.warehouse, posted=True)
            sold_qty = history.filter(kind=Document.Kind.SALE, lines__product_id=line.product_id).aggregate(total=Sum('lines__quantity'))['total'] or Decimal('0')
            returned_qty = history.filter(kind=Document.Kind.RETURN, lines__product_id=line.product_id).aggregate(total=Sum('lines__quantity'))['total'] or Decimal('0')
            if line.quantity > sold_qty - returned_qty:
                raise ValidationError(f'{line.product.name}: qaytarish miqdori xaridorning qaytarilmagan xarididan oshmasligi kerak.')
            line.cost = line.product.purchase_price
    if document.kind == Document.Kind.RETURN and document.original_id:
        original = Document.objects.select_for_update().get(pk=document.original_id)
        if not original.posted or original.kind != Document.Kind.SALE or original.partner_id != document.partner_id or original.warehouse_id != document.warehouse_id:
            raise ValidationError('Asl sotuv, mijoz va ombor mos kelishi kerak.')
        sold = {line.product_id: line for line in original.lines.all()}
        returned = defaultdict(Decimal)
        for row in Document.objects.filter(original=original, posted=True, kind=Document.Kind.RETURN).values('lines__product_id').annotate(qty=Sum('lines__quantity')):
            returned[row['lines__product_id']] = row['qty'] or Decimal('0')
        for line in lines:
            source = sold.get(line.product_id)
            if not source or line.quantity + returned[line.product_id] > source.quantity or line.price != source.price:
                raise ValidationError('Qaytarish miqdori yoki narxi asl sotuvga mos emas.')
            line.cost = source.cost
    for line in lines:
        line.full_clean()
        product = Product.objects.select_for_update().get(pk=line.product_id)
        stock, _ = Stock.objects.get_or_create(product=product, warehouse=document.warehouse)
        stock = Stock.objects.select_for_update().get(pk=stock.pk)
        outbound = document.kind in (Document.Kind.SALE, Document.Kind.TRANSFER)
        if outbound and stock.quantity < line.quantity:
            raise ValidationError(f'{product.name}: qoldiq yetarli emas ({stock.quantity} {product.unit}).')
        if document.kind != Document.Kind.RETURN:
            line.cost = line.price if document.kind == Document.Kind.PURCHASE else product.purchase_price
        line.save(update_fields=['cost'])
        stock.quantity += -line.quantity if outbound else line.quantity
        stock.save(update_fields=['quantity'])
        if document.kind == Document.Kind.TRANSFER:
            target, _ = Stock.objects.get_or_create(product=product, warehouse=document.destination)
            target = Stock.objects.select_for_update().get(pk=target.pk)
            target.quantity += line.quantity
            target.save(update_fields=['quantity'])
        if document.kind == Document.Kind.PURCHASE:
            product.purchase_price = line.price
            product.save(update_fields=['purchase_price'])
    document.posted = True
    document.save(update_fields=['posted'])
    return document

def partner_balance(partner):
    balance = Decimal('0')
    for doc in Document.objects.filter(partner=partner, posted=True).prefetch_related('lines'):
        balance += -doc.total if doc.kind == Document.Kind.RETURN else doc.total
    for payment in partner.payment_set.all():
        settles = (partner.kind == 'customer' and payment.direction == 'in') or (partner.kind == 'supplier' and payment.direction == 'out')
        balance += -payment.amount if settles else payment.amount
    return balance
