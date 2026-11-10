from django.contrib import admin
from .forms import ProductForm
from .models import Category, Document, DocumentLine, Expense, Partner, Payment, Product, Stock, Warehouse

admin.site.site_header = 'Qurilish CRM boshqaruvi'
admin.site.site_title = 'Qurilish CRM'

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductForm
    readonly_fields = ['sku']
    list_display = ['name', 'sku', 'category', 'unit', 'sale_price', 'active']
    search_fields = ['name', 'sku']
    list_filter = ['category', 'active']

@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ['name', 'kind', 'phone']
    search_fields = ['name', 'phone']
    list_filter = ['kind']
    def get_readonly_fields(self, request, obj=None):
        return ['kind'] if obj and (obj.document_set.exists() or obj.payment_set.exists()) else []

class ImmutableAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

class LineInline(admin.TabularInline):
    model = DocumentLine
    extra = 0
    readonly_fields = ['product', 'quantity', 'price', 'cost']
    can_delete = False
    def has_add_permission(self, request, obj=None): return False

@admin.register(Document)
class DocumentAdmin(ImmutableAdmin):
    list_display = ['id', 'kind', 'partner', 'warehouse', 'created_at', 'posted']
    list_filter = ['kind', 'warehouse', 'posted']
    inlines = [LineInline]

@admin.register(Stock)
class StockAdmin(ImmutableAdmin):
    list_display = ['product', 'warehouse', 'quantity']
    list_filter = ['warehouse']
    search_fields = ['product__name', 'product__sku']

@admin.register(Payment)
class PaymentAdmin(ImmutableAdmin):
    list_display = ['partner', 'direction', 'amount', 'method', 'created_at']

@admin.register(Expense)
class ExpenseAdmin(ImmutableAdmin):
    list_display = ['title', 'amount', 'date']

admin.site.register(Category)
admin.site.register(Warehouse)
