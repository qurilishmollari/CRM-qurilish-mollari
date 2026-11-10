from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'mobile_api'
router = DefaultRouter()
router.register('products', views.ProductViewSet, basename='product')
router.register('categories', views.CategoryViewSet, basename='category')
router.register('warehouses', views.WarehouseViewSet, basename='warehouse')
router.register('partners', views.PartnerViewSet, basename='partner')
router.register('stocks', views.StockViewSet, basename='stock')
router.register('documents', views.DocumentViewSet, basename='document')
router.register('payments', views.PaymentViewSet, basename='payment')
router.register('expenses', views.ExpenseViewSet, basename='expense')
urlpatterns = [path('auth/login/', views.LoginView.as_view(), name='login'), path('auth/logout/', views.LogoutView.as_view(), name='logout'), path('auth/me/', views.MeView.as_view(), name='me'), path('reports/', views.ReportView.as_view(), name='report'), path('', include(router.urls))]
