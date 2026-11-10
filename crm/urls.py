from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('documents/', views.documents, name='documents'),
    path('documents/new/', views.document_create, name='document_create'),
    path('documents/<int:pk>/', views.document_detail, name='document_detail'),
    path('inventory/', views.inventory, name='inventory'),
    path('reports/', views.reports, name='reports'),
    path('products/delete/', views.products_delete, name='products_delete'),
    path('manage/<str:section>/', views.listing, name='listing'),
    path('manage/<str:section>/new/', views.create, name='create'),
]
