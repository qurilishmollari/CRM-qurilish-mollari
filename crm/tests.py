from decimal import Decimal
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from .models import Category, Document, DocumentLine, Partner, Payment, Product, Stock, Warehouse
from .services import partner_balance, post_document
from django.core.management import call_command
from django.contrib.auth.models import Group
from io import StringIO

class BusinessFixtures(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('owner', 'owner@example.com', 'test-password-123')
        self.warehouse = Warehouse.objects.create(name='Asosiy')
        self.other = Warehouse.objects.create(name='Filial')
        self.customer = Partner.objects.create(name='Ali', kind='customer', phone='+998901234567')
        self.supplier = Partner.objects.create(name='Zavod', kind='supplier')
        self.product = Product.objects.create(name='Sement', sku='C01', category=Category.objects.create(name='Sement'), sale_price=60000, purchase_price=40000)

    def document(self, kind, quantity, price, **kwargs):
        doc = Document.objects.create(kind=kind, warehouse=self.warehouse, created_by=self.user, **kwargs)
        DocumentLine.objects.create(document=doc, product=self.product, quantity=quantity, price=price)
        return doc

    def purchase(self):
        doc = self.document('purchase', 10, 40000, partner=self.supplier)
        post_document(doc.pk)
        return doc

class BusinessFlowTests(BusinessFixtures):
    def test_purchase_sale_and_payment_balances(self):
        self.purchase()
        sale = self.document('sale', 3, 60000, partner=self.customer)
        post_document(sale.pk)
        self.assertEqual(Stock.objects.get(product=self.product, warehouse=self.warehouse).quantity, 7)
        self.assertEqual(partner_balance(self.customer), Decimal('180000'))
        Payment.objects.create(partner=self.customer, direction='in', amount=100000, created_by=self.user)
        self.assertEqual(partner_balance(self.customer), Decimal('80000'))
        self.assertEqual(partner_balance(self.supplier), Decimal('400000'))

    def test_insufficient_stock_rolls_back(self):
        self.purchase()
        sale = self.document('sale', 11, 60000, partner=self.customer)
        with self.assertRaises(ValidationError): post_document(sale.pk)
        sale.refresh_from_db()
        self.assertFalse(sale.posted)
        self.assertEqual(Stock.objects.get(product=self.product, warehouse=self.warehouse).quantity, 10)

    def test_cannot_post_twice(self):
        doc = self.purchase()
        with self.assertRaises(ValidationError): post_document(doc.pk)
        self.assertEqual(Stock.objects.get(product=self.product, warehouse=self.warehouse).quantity, 10)

    def test_transfer_preserves_total_stock(self):
        self.purchase()
        transfer = self.document('transfer', 4, 0, destination=self.other)
        post_document(transfer.pk)
        self.assertEqual(Stock.objects.get(warehouse=self.warehouse).quantity, 6)
        self.assertEqual(Stock.objects.get(warehouse=self.other).quantity, 4)

    def test_return_cannot_exceed_sale(self):
        self.purchase()
        sale = self.document('sale', 3, 60000, partner=self.customer)
        post_document(sale.pk)
        returned = self.document('return', 2, 60000, partner=self.customer, original=sale)
        post_document(returned.pk)
        self.assertEqual(partner_balance(self.customer), Decimal('60000'))
        excess = self.document('return', 2, 60000, partner=self.customer, original=sale)
        with self.assertRaises(ValidationError): post_document(excess.pk)
        self.assertEqual(Stock.objects.get(warehouse=self.warehouse).quantity, 9)

    def test_authenticated_pages_render(self):
        self.client.force_login(self.user)
        doc = self.purchase()
        for name, args in [('dashboard', []), ('documents', []), ('document_create', []), ('document_detail', [doc.pk]), ('inventory', []), ('reports', []), ('listing', ['products']), ('listing', ['partners']), ('listing', ['payments']), ('create', ['products'])]:
            with self.subTest(page=name, args=args):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)

    def test_login_and_permissions(self):
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)
        user = User.objects.create_user('viewer', password='test-password-123')
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('document_create')).status_code, 403)
        self.assertEqual(self.client.get(reverse('reports')).status_code, 403)

    def test_invalid_document_http_does_not_persist(self):
        self.client.force_login(self.user)
        data = {'kind': 'sale', 'partner': self.customer.pk, 'warehouse': self.warehouse.pk, 'lines-TOTAL_FORMS': '1', 'lines-INITIAL_FORMS': '0', 'lines-MIN_NUM_FORMS': '1', 'lines-MAX_NUM_FORMS': '1000', 'lines-0-product': self.product.pk, 'lines-0-quantity': '1', 'lines-0-price': '60000'}
        response = self.client.post(reverse('document_create'), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'qoldiq yetarli emas')
        self.assertEqual(Document.objects.count(), 0)

    def test_valid_document_http_updates_stock(self):
        self.purchase()
        self.client.force_login(self.user)
        data = {'kind': 'sale', 'partner': self.customer.pk, 'warehouse': self.warehouse.pk, 'lines-TOTAL_FORMS': '1', 'lines-INITIAL_FORMS': '0', 'lines-MIN_NUM_FORMS': '1', 'lines-MAX_NUM_FORMS': '1000', 'lines-0-product': self.product.pk, 'lines-0-quantity': '2.500', 'lines-0-price': '60000'}
        response = self.client.post(reverse('document_create'), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Stock.objects.get(product=self.product, warehouse=self.warehouse).quantity, Decimal('7.500'))
        self.assertEqual(partner_balance(self.customer), Decimal('150000'))

    def test_later_line_failure_rolls_back_earlier_line(self):
        self.purchase()
        missing = Product.objects.create(name='G‘isht', sku='B01', category=self.product.category)
        sale = self.document('sale', 1, 60000, partner=self.customer)
        DocumentLine.objects.create(document=sale, product=missing, quantity=1, price=1000)
        with self.assertRaises(ValidationError): post_document(sale.pk)
        self.assertEqual(Stock.objects.get(product=self.product, warehouse=self.warehouse).quantity, 10)
        self.assertFalse(Stock.objects.filter(product=missing).exists())


class SellerRoleTests(BusinessFixtures):
    def setUp(self):
        super().setUp()
        call_command('setup_crm', stdout=StringIO())
        self.seller = User.objects.create_user('seller', password='test-password-123')
        self.seller.groups.add(Group.objects.get(name='Sotuvchi'))
        self.client.force_login(self.seller)

    def seller_data(self, kind='sale', **extra):
        data = {'kind': kind, 'buyer_name': self.customer.name, 'buyer_phone': self.customer.phone, 'warehouse': self.warehouse.pk, 'lines-TOTAL_FORMS': '1', 'lines-INITIAL_FORMS': '0', 'lines-MIN_NUM_FORMS': '1', 'lines-MAX_NUM_FORMS': '1000', 'lines-0-product': self.product.pk, 'lines-0-quantity': '2', 'lines-0-price': '60000'}
        data.update(extra)
        return data

    def test_seller_can_sell_and_return(self):
        self.purchase()
        response = self.client.post(reverse('document_create'), self.seller_data())
        self.assertEqual(response.status_code, 302)
        sale = Document.objects.get(kind='sale')
        self.assertEqual(sale.created_by, self.seller)
        response = self.client.get(reverse('document_create'), {'kind': 'return', 'original': sale.pk})
        self.assertNotIn('original', response.context['form'].fields)
        self.assertNotIn('partner', response.context['form'].fields)
        response = self.client.post(reverse('document_create'), self.seller_data('return', original=sale.pk))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Stock.objects.get(product=self.product, warehouse=self.warehouse).quantity, 10)
        self.assertEqual(partner_balance(self.customer), 0)
        self.assertIsNone(Document.objects.get(kind='return').original_id)

    def test_buyer_created_and_price_calculated_on_server(self):
        self.purchase()
        response = self.client.post(reverse('document_create'), self.seller_data(buyer_name='Vali', buyer_phone='+998 (91) 123-45-67', **{'lines-0-price': '1', 'lines-0-quantity': '2.5'}))
        self.assertEqual(response.status_code, 302)
        sale = Document.objects.get(kind='sale')
        self.assertEqual(sale.total, Decimal('150000'))
        self.assertEqual(sale.buyer_name, 'Vali')
        self.assertEqual(sale.buyer_phone, '+998911234567')
        self.assertEqual(sale.partner.phone, '+998911234567')

    def test_buyer_required_and_invalid_sale_rolls_back_customer(self):
        response = self.client.post(reverse('document_create'), self.seller_data(buyer_name='', buyer_phone='abc'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Document.objects.exists())
        response = self.client.post(reverse('document_create'), self.seller_data(buyer_name='New buyer', buyer_phone='+998991234567'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Partner.objects.filter(name='New buyer').exists())

    def test_return_without_sale_or_above_remaining_is_rejected(self):
        self.purchase()
        response = self.client.post(reverse('document_create'), self.seller_data('return'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Document.objects.filter(kind='return').exists())
        self.client.post(reverse('document_create'), self.seller_data())
        self.client.post(reverse('document_create'), self.seller_data('return'))
        response = self.client.post(reverse('document_create'), self.seller_data('return'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Document.objects.filter(kind='return').count(), 1)

    def test_seller_form_shows_prices_and_totals_without_partner(self):
        response = self.client.get(reverse('document_create'))
        self.assertContains(response, 'Xaridor ismi')
        self.assertContains(response, 'Telefon raqami')
        self.assertContains(response, '60,000.00')
        self.assertContains(response, 'document-total')
        self.assertNotContains(response, 'name="partner"')
        self.assertNotContains(response, 'name="original"')

    def test_seller_cannot_create_purchase_or_transfer(self):
        for kind in ['purchase', 'transfer']:
            with self.subTest(kind=kind):
                self.assertEqual(self.client.get(reverse('document_create'), {'kind': kind}).status_code, 403)
                self.assertEqual(self.client.post(reverse('document_create'), self.seller_data(kind)).status_code, 403)
        self.assertEqual(Document.objects.count(), 0)

    def test_seller_service_cannot_bypass_permissions(self):
        doc = self.document('purchase', 10, 40000, partner=self.supplier)
        doc.created_by = self.seller
        doc.save()
        with self.assertRaises(ValidationError): post_document(doc.pk)
        self.assertFalse(Stock.objects.exists())

    def test_seller_sees_no_purchase_documents_or_supplier(self):
        purchase = self.purchase()
        response = self.client.get(reverse('documents'))
        self.assertEqual(list(response.context['page']), [])
        self.assertEqual(self.client.get(reverse('document_detail', args=[purchase.pk])).status_code, 404)
        response = self.client.get(reverse('listing', args=['partners']))
        self.assertEqual(len(response.context['rows']), 1)
        self.assertEqual(response.context['rows'][0]['id'], self.customer.pk)

    def test_seller_denied_management_and_finance(self):
        for url in [reverse('reports'), reverse('listing', args=['payments']), reverse('create', args=['payments']), reverse('listing', args=['expenses']), reverse('create', args=['products']), reverse('listing', args=['warehouses'])]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        response = self.client.get(reverse('documents'))
        self.assertNotContains(response, reverse('reports'))
        self.assertNotContains(response, reverse('listing', args=['payments']))
        self.assertContains(response, 'Tovar qaytarish')
        self.assertRedirects(self.client.get(reverse('dashboard')), reverse('documents'))

    def test_seller_cannot_create_supplier(self):
        response = self.client.post(reverse('create', args=['partners']), {'name': 'Hidden supplier', 'kind': 'supplier'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Partner.objects.filter(name='Hidden supplier').exists())


class CatalogSeedTests(TestCase):
    def test_catalog_is_repeatable_and_does_not_overwrite_prices(self):
        call_command('seed_products', stdout=StringIO())
        self.assertEqual(Product.objects.count(), 10)
        cement = Product.objects.get(sku='SEM-400')
        cement.sale_price = 55000
        cement.save()
        call_command('seed_products', stdout=StringIO())
        cement.refresh_from_db()
        self.assertEqual(Product.objects.count(), 10)
        self.assertEqual(cement.sale_price, 55000)
        self.assertEqual(Product.objects.get(sku='QUM-001').unit, 'm3')
        self.assertFalse(Stock.objects.exists())


class PeriodReportTests(BusinessFixtures):
    def test_day_week_month_boundaries_and_expenses(self):
        from datetime import date, datetime
        from unittest.mock import patch
        from django.utils import timezone
        from .models import Expense
        self.client.force_login(self.user)
        dates = ['2026-11-18', '2026-11-16', '2026-11-15', '2026-10-31', '2026-11-19']
        for day in dates:
            doc = self.document('sale', 1, 100, partner=self.customer)
            stamp = timezone.make_aware(datetime.fromisoformat(day + 'T12:00:00'))
            Document.objects.filter(pk=doc.pk).update(posted=True, created_at=stamp)
            doc.lines.update(cost=40)
            Expense.objects.create(title='Transport', amount=5, date=day, created_by=self.user)
            payment = Payment.objects.create(partner=self.customer, direction='in', amount=10, created_by=self.user)
            Payment.objects.filter(pk=payment.pk).update(created_at=stamp)
        with patch('crm.views.timezone.localdate', return_value=date(2026, 11, 18)):
            for period, count in [('day', 1), ('week', 2), ('month', 3), ('all', 5)]:
                with self.subTest(period=period):
                    response = self.client.get(reverse('reports'), {'period': period})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.context['sale_count'], count)
                    self.assertEqual(response.context['revenue'], count * 100)
                    self.assertEqual(response.context['expenses'], count * 5)
                    self.assertEqual(response.context['net'], count * 55)
                    self.assertEqual(response.context['incoming'], count * 10)
            response = self.client.get(reverse('reports'), {'period': 'invalid'})
            self.assertEqual(response.context['period'], 'day')

    def test_reports_subtract_returns_in_selected_period(self):
        self.purchase()
        sale = self.document('sale', 3, 60000, partner=self.customer)
        post_document(sale.pk)
        returned = self.document('return', 1, 60000, partner=self.customer)
        post_document(returned.pk)
        self.client.force_login(self.user)
        response = self.client.get(reverse('reports'), {'period': 'day'})
        self.assertEqual(response.context['revenue'], Decimal('120000'))
        self.assertEqual(response.context['profit'], Decimal('40000'))
        self.assertEqual(response.context['return_count'], 1)
