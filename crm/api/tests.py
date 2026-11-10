from datetime import timedelta
from decimal import Decimal
from io import StringIO
from uuid import uuid4
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from crm.models import Document, Partner, Product, Stock
from crm.services import post_document
from crm.tests import BusinessFixtures


class MobileApiTests(BusinessFixtures):
    def setUp(self):
        super().setUp()
        cache.clear()
        call_command('setup_crm', stdout=StringIO())
        self.seller = User.objects.create_user('mobile-seller', password='Mobile-password-123')
        self.seller.groups.add(Group.objects.get(name='Sotuvchi'))
        self.client = APIClient()
        self.token = Token.objects.create(user=self.seller)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.base = '/api/v1/'

    def payload(self, **changes):
        data = {'client_request_id': str(uuid4()), 'kind': 'sale', 'buyer_name': 'Ali', 'buyer_phone': '+998 (90) 123-45-67', 'warehouse': self.warehouse.pk, 'lines': [{'product': self.product.pk, 'quantity': '2.500', 'price': '1.00'}]}
        data.update(changes)
        return data

    def admin(self):
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_auth_login_me_logout_and_expiry(self):
        self.client.credentials()
        self.assertEqual(self.client.get(self.base + 'products/').status_code, 401)
        response = self.client.post(self.base + 'auth/login/', {'username': self.seller.username, 'password': 'wrong'}, format='json')
        self.assertEqual(response.status_code, 401)
        response = self.client.post(self.base + 'auth/login/', {'username': self.seller.username, 'password': 'Mobile-password-123'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('expires_at', response.data)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {response.data["token"]}')
        self.assertEqual(self.client.get(self.base + 'auth/me/').data['username'], self.seller.username)
        Token.objects.filter(user=self.seller).update(created=timezone.now() - timedelta(days=8))
        self.assertEqual(self.client.get(self.base + 'products/').status_code, 401)
        self.client.credentials()
        response = self.client.post(self.base + 'auth/login/', {'username': self.seller.username, 'password': 'Mobile-password-123'}, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {response.data["token"]}')
        self.assertEqual(self.client.post(self.base + 'auth/logout/').status_code, 204)
        self.assertEqual(self.client.get(self.base + 'products/').status_code, 401)

    def test_login_throttling_and_inactive_users(self):
        self.client.credentials()
        self.seller.is_active = False
        self.seller.save()
        data = {'username': self.seller.username, 'password': 'Mobile-password-123'}
        self.assertEqual(self.client.post(self.base + 'auth/login/', data, format='json').status_code, 401)
        for _ in range(9):
            self.client.post(self.base + 'auth/login/', data, format='json')
        self.assertEqual(self.client.post(self.base + 'auth/login/', data, format='json').status_code, 429)

    def test_paginated_catalog_stock_and_permissions(self):
        self.purchase()
        response = self.client.get(self.base + 'products/?q=C01&page_size=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['sale_price'], '60000.00')
        self.assertNotIn('purchase_price', response.data['results'][0])
        self.assertEqual(self.client.get(self.base + 'warehouses/').status_code, 200)
        self.assertEqual(self.client.get(self.base + 'categories/').status_code, 200)
        self.assertEqual(self.client.get(self.base + f'stocks/?warehouse={self.warehouse.pk}').data['results'][0]['quantity'], '10.000')
        self.assertEqual(self.client.get(self.base + 'stocks/?warehouse=wrong').status_code, 400)
        self.assertEqual(self.client.post(self.base + 'products/', {}, format='json').status_code, 403)
        for endpoint in ('reports/', 'payments/', 'expenses/'):
            self.assertEqual(self.client.get(self.base + endpoint).status_code, 403)

    def test_sale_return_and_idempotent_retry(self):
        self.purchase()
        data = self.payload()
        response = self.client.post(self.base + 'documents/', data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(response.data['total']), Decimal('150000'))
        self.assertEqual(response.data['buyer_phone'], '+998901234567')
        self.assertEqual(response.data['lines'][0]['price'], '60000.00')
        self.assertEqual(Stock.objects.get(product=self.product).quantity, Decimal('7.500'))
        retry = self.client.post(self.base + 'documents/', data, format='json')
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.data['id'], response.data['id'])
        self.assertEqual(Stock.objects.get(product=self.product).quantity, Decimal('7.500'))
        changed = self.client.post(self.base + 'documents/', {**data, 'notes': 'different'}, format='json')
        self.assertEqual(changed.status_code, 409)
        returned = self.client.post(self.base + 'documents/', self.payload(kind='return'), format='json')
        self.assertEqual(returned.status_code, 201, returned.data)
        self.assertEqual(Stock.objects.get(product=self.product).quantity, 10)
        excess = self.client.post(self.base + 'documents/', self.payload(kind='return'), format='json')
        self.assertEqual(excess.status_code, 400)

    def test_invalid_sale_rolls_back_customer_and_document(self):
        data = self.payload(buyer_name='No-stock buyer', buyer_phone='+998991111111')
        response = self.client.post(self.base + 'documents/', data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Document.objects.exists())
        self.assertFalse(Partner.objects.filter(name='No-stock buyer').exists())
        self.assertFalse(Stock.objects.exists())

    def test_document_validation_and_management_restrictions(self):
        for changes in [{'kind': 'purchase'}, {'kind': 'transfer'}, {'partner': self.supplier.pk}, {'lines': []}, {'client_request_id': 'bad'}, {'buyer_phone': 'abc'}, {'lines': [{'product': self.product.pk, 'quantity': '-1'}]}, {'lines': [{'product': self.product.pk, 'quantity': '1'}, {'product': self.product.pk, 'quantity': '1'}]}]:
            with self.subTest(changes=changes):
                response = self.client.post(self.base + 'documents/', self.payload(**changes), format='json')
                self.assertIn(response.status_code, (400, 403), response.data)
        purchase = self.purchase()
        self.assertEqual(self.client.get(self.base + f'documents/{purchase.pk}/').status_code, 404)
        self.assertEqual(self.client.get(self.base + 'documents/').data['count'], 0)
        self.assertEqual(self.client.get(self.base + 'partners/').data['count'], 1)
        self.assertEqual(self.client.post(self.base + 'partners/', {'name': 'Supplier', 'kind': 'supplier'}, format='json').status_code, 400)

    def test_admin_product_creation_payments_expenses_reports(self):
        self.admin()
        response = self.client.post(self.base + 'products/', {'name': 'Mobile product', 'category': self.product.category_id, 'unit': 'dona', 'sale_price': '150', 'sku': 'FORGED'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data['sku'].startswith('TOV-'))
        response = self.client.post(self.base + 'payments/', {'partner': self.customer.pk, 'direction': 'in', 'amount': '100', 'method': 'cash'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        response = self.client.post(self.base + 'expenses/', {'title': 'Delivery', 'amount': '25', 'date': str(timezone.localdate())}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        report = self.client.get(self.base + 'reports/?period=year')
        self.assertEqual(report.status_code, 200)
        self.assertEqual(Decimal(report.data['net']), Decimal('-25'))
        excel = self.client.get(self.base + 'reports/?period=year&export=xlsx')
        self.assertEqual(excel.content[:2], b'PK')
        self.assertEqual(self.client.get(self.base + 'reports/?period=bad').status_code, 400)

    def test_protected_delete_and_permission_removal(self):
        self.purchase()
        self.admin()
        self.assertEqual(self.client.delete(self.base + f'products/{self.product.pk}/').status_code, 409)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.seller.groups.clear()
        self.assertEqual(self.client.get(self.base + 'products/').status_code, 403)

    def test_unknown_users_and_browser_sessions_do_not_authenticate_api(self):
        self.client.credentials()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.base + 'auth/me/').status_code, 401)
