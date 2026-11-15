from decimal import Decimal
from uuid import uuid4
from django.contrib.auth.models import Permission, User
from django.test import override_settings
from rest_framework.test import APIClient
from crm import tests as fixtures
from crm.models import Document, Product, Stock


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class InventoryApiTests(fixtures.BusinessFixtures):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_product_stock_total_and_warehouse_availability(self):
        self.purchase()
        Stock.objects.create(product=self.product, warehouse=self.other, quantity=4)
        response = self.api.get('/api/v1/products/')
        row = response.data['results'][0]
        self.assertEqual(row['total_stock'], '14.000')
        self.assertEqual(row['available_stock'], '14.000')
        self.assertFalse(row['low_stock'])
        response = self.api.get(f'/api/v1/products/{self.product.pk}/?warehouse={self.other.pk}')
        self.assertEqual(response.data['available_stock'], '4.000')
        self.assertEqual(response.data['total_stock'], '14.000')

    def test_empty_stock_and_invalid_warehouse(self):
        response = self.api.get(f'/api/v1/products/?warehouse={self.warehouse.pk}')
        self.assertEqual(response.data['results'][0]['available_stock'], '0.000')
        self.assertTrue(response.data['results'][0]['low_stock'])
        for value in ['-1', 'abc', '9999999999999999999999', '99999']:
            self.assertEqual(self.api.get('/api/v1/products/', {'warehouse': value}).status_code, 400)

    def test_opening_document_uses_cost_and_retries_once(self):
        data = {'client_request_id': str(uuid4()), 'kind': 'opening', 'warehouse': self.warehouse.pk,
                'lines': [{'product': self.product.pk, 'quantity': '12.500'}]}
        response = self.api.post('/api/v1/documents/', data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['lines'][0]['price'], '40000.00')
        self.assertEqual(self.api.post('/api/v1/documents/', data, format='json').status_code, 200)
        self.assertEqual(Document.objects.count(), 1)
        self.assertEqual(Stock.objects.get(product=self.product).quantity, Decimal('12.500'))
        data['lines'][0]['quantity'] = '13.000'
        self.assertEqual(self.api.post('/api/v1/documents/', data, format='json').status_code, 409)
        report = self.api.get('/api/v1/reports/')
        self.assertEqual(Decimal(str(report.data['revenue'])), 0)

    def test_bulk_delete_preserves_stock_history(self):
        self.purchase()
        spare = Product.objects.create(name='Spare', category=self.product.category)
        spare_id = spare.pk
        response = self.api.post('/api/v1/products/bulk-delete/', {'products': [self.product.pk, spare_id]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data, {'deleted': [spare_id], 'protected': [self.product.pk]})
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.assertFalse(Product.objects.filter(pk=spare_id).exists())
        self.assertEqual(Stock.objects.get(product=self.product).quantity, 10)

    def test_bulk_missing_or_duplicate_ids_do_not_delete(self):
        for ids in [[self.product.pk, 99999], [self.product.pk, self.product.pk], [], list(range(1, 102))]:
            response = self.api.post('/api/v1/products/bulk-delete/', {'products': ids}, format='json')
            self.assertEqual(response.status_code, 400)
            self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_bulk_delete_checks_delete_permission(self):
        user = User.objects.create_user('deleter')
        user.user_permissions.add(Permission.objects.get(content_type__app_label='crm', codename='delete_product'))
        self.api.force_authenticate(user)
        response = self.api.post('/api/v1/products/bulk-delete/', {'products': [self.product.pk]}, format='json')
        self.assertEqual(response.status_code, 200)

    def test_seller_reads_stock_but_cannot_open_or_delete(self):
        from django.core.management import call_command
        from django.contrib.auth.models import Group
        from io import StringIO
        call_command('setup_crm', stdout=StringIO())
        user = User.objects.create_user('seller')
        user.groups.add(Group.objects.get(name='Sotuvchi'))
        self.api.force_authenticate(user)
        response = self.api.get('/api/v1/products/')
        self.assertIn('available_stock', response.data['results'][0])
        self.assertNotIn('purchase_price', response.data['results'][0])
        self.assertEqual(self.api.post('/api/v1/products/bulk-delete/', {'products': [self.product.pk]}, format='json').status_code, 403)
        data = {'client_request_id': str(uuid4()), 'kind': 'opening', 'warehouse': self.warehouse.pk,
                'lines': [{'product': self.product.pk, 'quantity': '1'}]}
        self.assertEqual(self.api.post('/api/v1/documents/', data, format='json').status_code, 403)
        self.assertFalse(Stock.objects.exists())

    def test_document_examples_and_typed_schema(self):
        schema = self.client.get('/api/schema/').json()
        op = schema['paths']['/documents/']['post']
        examples = op['requestBody']['content']['application/json']['examples']
        self.assertEqual({item['value']['kind'] for item in examples.values()}, {'sale', 'return', 'opening', 'purchase', 'transfer'})
        self.assertIn('ProductCreate', schema['components']['schemas'])
        self.assertIn('/products/bulk-delete/', schema['paths'])
        self.assertIn('409', op['responses'])
