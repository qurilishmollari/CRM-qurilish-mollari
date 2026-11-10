import re
from decimal import Decimal
from django.contrib.auth import authenticate
from rest_framework import serializers
from crm.models import Category, Document, DocumentLine, Expense, Partner, Payment, Product, Stock, Warehouse


def phone_number(value):
    value = re.sub(r'[\s()\-]', '', value)
    if not re.fullmatch(r'\+?\d{9,15}', value):
        raise serializers.ValidationError('Telefon 9–15 raqamdan iborat bo‘lsin, masalan +998901234567.')
    return value


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=1024)

    def validate(self, attrs):
        user = authenticate(request=self.context['request'], **attrs)
        if user is None:
            from rest_framework.exceptions import AuthenticationFailed
            raise AuthenticationFailed('Login yoki parol noto‘g‘ri.')
        return {'user': user}


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'category', 'category_name', 'unit', 'purchase_price', 'sale_price', 'minimum_stock', 'active']
        read_only_fields = ['id', 'sku']

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if not request or not request.user.has_perm('crm.manage_inventory_documents'):
            fields.pop('purchase_price')
        return fields


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ['id', 'name', 'address']


class PartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partner
        fields = ['id', 'name', 'kind', 'phone', 'address', 'notes']
        read_only_fields = ['id']
    def validate_kind(self, value):
        if value != Partner.Kind.CUSTOMER and not self.context['request'].user.has_perm('crm.manage_inventory_documents'):
            raise serializers.ValidationError('Faqat xaridor qo‘shish mumkin.')
        return value
    def validate_phone(self, value):
        return phone_number(value) if value else value


class StockSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name')
    sku = serializers.CharField(source='product.sku')
    unit = serializers.CharField(source='product.unit')
    sale_price = serializers.DecimalField(source='product.sale_price', max_digits=18, decimal_places=2)
    warehouse_name = serializers.CharField(source='warehouse.name')
    class Meta:
        model = Stock
        fields = ['id', 'product', 'product_name', 'sku', 'unit', 'sale_price', 'warehouse', 'warehouse_name', 'quantity']


class DocumentLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name')
    sku = serializers.CharField(source='product.sku')
    unit = serializers.CharField(source='product.unit')
    total = serializers.SerializerMethodField()
    def get_total(self, obj):
        return str(obj.quantity * obj.price)
    class Meta:
        model = DocumentLine
        fields = ['product', 'product_name', 'sku', 'unit', 'quantity', 'price', 'total']


class DocumentSerializer(serializers.ModelSerializer):
    lines = DocumentLineSerializer(many=True)
    total = serializers.SerializerMethodField()
    warehouse_name = serializers.CharField(source='warehouse.name')
    partner_name = serializers.CharField(source='partner.name', default=None)
    def get_total(self, obj):
        return str(obj.total)
    class Meta:
        model = Document
        fields = ['id', 'kind', 'buyer_name', 'buyer_phone', 'partner', 'partner_name', 'warehouse', 'warehouse_name', 'destination', 'original', 'notes', 'posted', 'created_at', 'created_by', 'api_request_id', 'lines', 'total']


class LineInputSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.filter(active=True))
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3, min_value=Decimal('0.001'))
    price = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal('0'), required=False)


class DocumentInputSerializer(serializers.Serializer):
    client_request_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=Document.Kind.choices)
    buyer_name = serializers.CharField(max_length=180, required=False)
    buyer_phone = serializers.CharField(max_length=40, required=False)
    partner = serializers.PrimaryKeyRelatedField(queryset=Partner.objects.all(), required=False)
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    destination = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all(), required=False)
    original = serializers.PrimaryKeyRelatedField(queryset=Document.objects.filter(posted=True, kind='sale'), required=False)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=5000)
    lines = LineInputSerializer(many=True, allow_empty=False, max_length=100)

    def validate_buyer_phone(self, value):
        return phone_number(value)

    def validate(self, attrs):
        from crm.permissions import allowed_document_kinds
        from rest_framework.exceptions import PermissionDenied
        user = self.context['request'].user
        if attrs['kind'] not in allowed_document_kinds(user):
            raise PermissionDenied('Bu hujjat turiga ruxsat yo‘q.')
        if not user.has_perm('crm.manage_inventory_documents'):
            if any(key in self.initial_data for key in ('partner', 'destination', 'original')):
                raise serializers.ValidationError('Xaridor ismi va telefonini kiriting; hamkor yoki asl sotuv yubormang.')
            for field in ('buyer_name', 'buyer_phone'):
                if not attrs.get(field):
                    raise serializers.ValidationError({field: 'Bu maydon majburiy.'})
        elif attrs['kind'] != 'transfer' and not attrs.get('partner'):
            raise serializers.ValidationError({'partner': 'Hamkorni tanlang.'})
        ids = [line['product'].pk for line in attrs['lines']]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError({'lines': 'Bir tovarni bir hujjatda takrorlamang.'})
        if user.has_perm('crm.manage_inventory_documents') and attrs['kind'] == 'purchase':
            if any('price' not in line for line in attrs['lines']):
                raise serializers.ValidationError({'lines': 'Xarid narxlarini kiriting.'})
        return attrs


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'partner', 'direction', 'amount', 'method', 'notes', 'created_at']
        read_only_fields = ['id', 'created_at']


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = ['id', 'title', 'amount', 'date', 'notes']
        read_only_fields = ['id']
