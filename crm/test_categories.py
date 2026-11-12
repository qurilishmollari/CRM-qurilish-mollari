from io import StringIO
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from .models import Category, Product
from .tests import BusinessFixtures


class CategoryManagementTests(BusinessFixtures):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_admin_creates_and_searches_categories(self):
        url = reverse('create', args=['categories'])
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {'name': 'Yangi kategoriya'})
        self.assertRedirects(response, reverse('listing', args=['categories']))
        response = self.client.get(reverse('listing', args=['categories']), {'q': 'Yangi'})
        self.assertEqual(len(response.context['rows']), 1)
        self.assertContains(response, 'Yangi kategoriya')
        self.assertContains(response, 'O‘chirish')
        self.assertEqual(self.client.post(url, {'name': 'Yangi kategoriya'}).status_code, 200)
        self.assertEqual(Category.objects.filter(name='Yangi kategoriya').count(), 1)
        self.assertEqual(self.client.post(url, {'name': ' '}).status_code, 200)

    def test_delete_requires_confirmation_and_csrf(self):
        category = Category.objects.create(name='Bo‘sh kategoriya')
        url = reverse('category_delete', args=[category.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Category.objects.filter(pk=category.pk).exists())
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(url).status_code, 403)
        self.assertRedirects(self.client.post(url), reverse('listing', args=['categories']))
        self.assertFalse(Category.objects.filter(pk=category.pk).exists())

    def test_used_category_and_new_references_are_protected(self):
        category = self.product.category
        url = reverse('category_delete', args=[category.pk])
        self.assertContains(self.client.get(url), '1 ta tovar')
        response = self.client.post(url, follow=True)
        self.assertContains(response, 'Kategoriya tovarlarga biriktirilgan')
        self.assertTrue(Category.objects.filter(pk=category.pk).exists())
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        empty = Category.objects.create(name='Dastlab bo‘sh')
        url = reverse('category_delete', args=[empty.pk])
        self.client.get(url)
        Product.objects.create(name='Keyin qo‘shilgan', category=empty)
        self.client.post(url)
        self.assertTrue(Category.objects.filter(pk=empty.pk).exists())

    def test_seller_cannot_manage_categories(self):
        call_command('setup_crm', stdout=StringIO())
        seller = User.objects.create_user('category-seller', password='seller-password')
        seller.groups.add(Group.objects.get(name='Sotuvchi'))
        self.client.force_login(seller)
        for url in [reverse('listing', args=['categories']), reverse('create', args=['categories']), reverse('category_delete', args=[self.product.category_id])]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, {'name': 'Forbidden'}).status_code, 403)
        response = self.client.get(reverse('listing', args=['products']))
        self.assertNotContains(response, reverse('listing', args=['categories']))
        api = APIClient()
        token = Token.objects.create(user=seller)
        api.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.assertEqual(api.get('/api/v1/categories/').status_code, 200)
        self.assertEqual(api.post('/api/v1/categories/', {'name': 'Forbidden'}, format='json').status_code, 403)
        self.assertEqual(api.delete(f'/api/v1/categories/{self.product.category_id}/').status_code, 403)

    def test_admin_api_creates_deletes_and_protects_categories(self):
        api = APIClient()
        token = Token.objects.create(user=self.user)
        api.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = api.post('/api/v1/categories/', {'name': 'API kategoriya'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data['id']
        self.assertEqual(api.delete(f'/api/v1/categories/{pk}/').status_code, 204)
        self.assertFalse(Category.objects.filter(pk=pk).exists())
        self.assertEqual(api.delete(f'/api/v1/categories/{self.product.category_id}/').status_code, 409)

    def test_rahbar_group_can_manage_categories_without_superuser(self):
        call_command('setup_crm', stdout=StringIO())
        manager = User.objects.create_user('category-manager', password='manager-password')
        manager.groups.add(Group.objects.get(name='Rahbar'))
        self.client.force_login(manager)
        self.assertEqual(self.client.post(reverse('create', args=['categories']), {'name': 'Rahbar kategoriyasi'}).status_code, 302)

    def test_deleted_default_category_is_not_recreated_on_startup(self):
        call_command('setup_crm', seed_categories=True, stdout=StringIO())
        category = Category.objects.get(name='Bo‘yoqlar')
        self.client.post(reverse('category_delete', args=[category.pk]))
        call_command('setup_crm', stdout=StringIO())
        self.assertFalse(Category.objects.filter(name='Bo‘yoqlar').exists())
