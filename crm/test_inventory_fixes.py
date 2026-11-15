from decimal import Decimal
from django.test import override_settings
from django.urls import reverse
from crm.forms import ProductForm
from crm.models import Document, Product, Stock
from crm.services import post_document
from crm import tests as fixtures


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class OpeningStockTests(fixtures.BusinessFixtures):
    def data(self, **kwargs):
        form = ProductForm()
        data = dict(name='Qum yangi', category=self.product.category_id, unit='m3',
                    purchase_price='10000', sale_price='15000', minimum_stock='2',
                    active='on', sku_token=form.initial['sku_token'],
                    opening_quantity='12.500', opening_warehouse=self.warehouse.pk)
        data.update(kwargs)
        return data

    def test_opening_stock_and_sale_end_to_end(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('create', args=['products']), self.data())
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(name='Qum yangi')
        self.assertEqual(product.minimum_stock, 2)
        self.assertEqual(Stock.objects.get(product=product).quantity, Decimal('12.500'))
        opening = Document.objects.get(kind='opening')
        self.assertTrue(opening.posted)
        self.assertEqual(self.client.get(reverse('document_detail', args=[opening.pk])).status_code, 200)
        sale = self.document('sale', 1, 60000, partner=self.customer)
        sale.lines.update(product=product)
        post_document(sale.pk)
        self.assertEqual(Stock.objects.get(product=product).quantity, Decimal('11.500'))
        report = self.client.get(reverse('reports'))
        self.assertEqual(report.context['revenue'], Decimal('60000'))

    def test_warehouse_required_and_negative_quantity_rejected(self):
        for kwargs in [dict(opening_warehouse=''), dict(opening_quantity='-1')]:
            form = ProductForm(data=self.data(**kwargs))
            self.assertFalse(form.is_valid())
        self.assertFalse(Stock.objects.exists())

    def test_existing_product_cannot_reset_stock(self):
        form = ProductForm(instance=self.product)
        self.assertNotIn('opening_quantity', form.fields)
        self.client.force_login(self.user)
        response = self.client.get(reverse('admin:crm_product_change', args=[self.product.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="opening_quantity"')

    def test_django_admin_can_record_opening_stock(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('admin:crm_product_add'), self.data())
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(name='Qum yangi')
        self.assertEqual(Stock.objects.get(product=product).quantity, Decimal('12.500'))

    def test_invalid_opening_transaction_leaves_no_product(self):
        from unittest.mock import patch
        from django.core.exceptions import ValidationError
        self.client.force_login(self.user)
        with patch('crm.views.record_opening_stock', side_effect=ValidationError({'quantity': ['Invalid stock']})):
            response = self.client.post(reverse('create', args=['products']), self.data())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid stock')
        self.assertFalse(Product.objects.filter(name='Qum yangi').exists())

    def test_transfer_detail_without_partner(self):
        self.purchase()
        transfer = self.document('transfer', 2, 0, destination=self.other)
        post_document(transfer.pk)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('document_detail', args=[transfer.pk])).status_code, 200)

    def test_api_opening_quantity_is_atomic_and_readonly_on_edit(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(self.user)
        data = self.data()
        data.pop('sku_token')
        data['active'] = True
        response = client.post('/api/v1/products/', data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        product_id = response.data['id']
        self.assertEqual(Stock.objects.get(product_id=product_id).quantity, Decimal('12.500'))
        response = client.patch(f'/api/v1/products/{product_id}/', {'opening_quantity': '99'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Stock.objects.get(product_id=product_id).quantity, Decimal('12.500'))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SellerBrowserFormTests(fixtures.BusinessFixtures):
    def setUp(self):
        super().setUp()
        from django.contrib.auth.models import User, Group
        from django.core.management import call_command
        from io import StringIO
        call_command('setup_crm', stdout=StringIO())
        self.seller = User.objects.create_user('seller', password='test-password-123')
        self.seller.groups.add(Group.objects.get(name='Sotuvchi'))
        self.client.force_login(self.seller)

    seller_data = fixtures.SellerRoleTests.seller_data
    def test_sale_with_browser_blank_extra_rows(self):
        self.purchase()
        response = self.client.get(reverse('document_create'))
        formset = response.context['formset']
        data = self.seller_data(**{'lines-TOTAL_FORMS': str(formset.total_form_count())})
        for index in range(1, formset.total_form_count()):
            data.update({f'lines-{index}-product': '', f'lines-{index}-quantity': ''})
        response = self.client.post(reverse('document_create'), data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Document.objects.filter(kind='sale', posted=True).count(), 1)
        self.assertEqual(Stock.objects.get(product=self.product).quantity, 8)

    def test_browser_retry_does_not_double_sell(self):
        self.purchase()
        response = self.client.get(reverse('document_create'))
        data = self.seller_data(submission_token=response.context['form'].initial['submission_token'])
        for _ in range(2):
            self.assertEqual(self.client.post(reverse('document_create'), data).status_code, 302)
        self.assertEqual(Document.objects.filter(kind='sale').count(), 1)
        self.assertEqual(Stock.objects.get(product=self.product).quantity, 8)

    def test_insufficient_stock_renders_error_without_changing_records(self):
        self.purchase()
        response = self.client.post(reverse('document_create'), self.seller_data(**{'lines-0-quantity': '11'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'qoldiq yetarli emas')
        self.assertFalse(Document.objects.filter(kind='sale').exists())
        self.assertEqual(Stock.objects.get(product=self.product).quantity, 10)
