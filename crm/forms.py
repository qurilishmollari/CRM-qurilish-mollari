from django import forms
from django.core import signing
from django.forms import inlineformset_factory
import re
from uuid import uuid4
from .models import Category, Document, DocumentLine, Expense, Partner, Payment, Product, Warehouse

class DocumentForm(forms.ModelForm):
    submission_token = forms.CharField(widget=forms.HiddenInput, required=False)
    class Meta:
        model = Document
        fields = ['kind', 'buyer_name', 'buyer_phone', 'partner', 'warehouse', 'destination', 'original', 'notes']
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial['submission_token'] = signing.dumps(str(uuid4()), salt='crm.document.submit')
        self.fields['original'].queryset = Document.objects.filter(kind='sale', posted=True)
        if user is not None:
            from .permissions import allowed_document_kinds
            allowed = allowed_document_kinds(user)
            self.fields['kind'].choices = [(value, label) for value, label in Document.Kind.choices if value in allowed]
            if not user.has_perm('crm.manage_inventory_documents'):
                self.fields.pop('destination')
                self.fields.pop('partner')
                self.fields.pop('original')
                self.fields['buyer_name'].required = True
                self.fields['buyer_phone'].required = True
            else:
                self.fields.pop('buyer_name')
                self.fields.pop('buyer_phone')

    def clean_buyer_phone(self):
        phone = re.sub(r'[\s()\-]', '', self.cleaned_data.get('buyer_phone', ''))
        if phone and not re.fullmatch(r'\+?\d{9,15}', phone):
            raise forms.ValidationError('Telefon raqamini 9–15 ta raqam bilan kiriting, masalan +998901234567.')
        return phone

    def clean_submission_token(self):
        token = self.cleaned_data.get('submission_token')
        if token:
            try:
                from uuid import UUID
                return UUID(signing.loads(token, salt='crm.document.submit'))
            except (signing.BadSignature, ValueError, TypeError):
                raise forms.ValidationError('Sahifani yangilang va qayta yuboring.')
        return None

class ProductChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, product):
        return f'{product.name} ({product.sku}) — {product.sale_price:,.2f} so‘m / {product.unit}'

class LineForm(forms.ModelForm):
    product = ProductChoiceField(queryset=Product.objects.none(), label='Tovar')
    class Meta:
        model = DocumentLine
        fields = ['product', 'quantity', 'price']
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(active=True)
        if user is not None and not user.has_perm('crm.manage_inventory_documents'):
            self.fields['price'].disabled = True
            product_id = self.data.get(self.add_prefix('product')) if self.is_bound else self.initial.get('product')
            product = self.fields['product'].queryset.filter(pk=product_id).first() if str(product_id).isdigit() else None
            self.initial['price'] = product.sale_price if product else None
            self.fields['price'].widget.attrs['data-auto-price'] = 'true'

LineFormSet = inlineformset_factory(Document, DocumentLine, form=LineForm, extra=5, can_delete=True, min_num=1, validate_min=True)

class PartnerForm(forms.ModelForm):
    class Meta:
        model = Partner
        fields = ['name', 'kind', 'phone', 'address', 'notes']

class ProductForm(forms.ModelForm):
    opening_quantity = forms.DecimalField(label='Ombordagi boshlang‘ich miqdor', max_digits=18, decimal_places=3, min_value=0, required=False, initial=0)
    opening_warehouse = forms.ModelChoiceField(label='Boshlang‘ich qoldiq ombori', queryset=Warehouse.objects.all(), required=False)
    sku = forms.CharField(label='Artikul', required=False, disabled=True)
    sku_token = forms.CharField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = Product
        fields = ['name', 'category', 'unit', 'purchase_price', 'sale_price', 'minimum_stock', 'active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sku_token_error = False
        self.fields['minimum_stock'].help_text = 'Kam qoldiq ogohlantirishi chegarasi; ombordagi haqiqiy miqdor emas.'
        if self.instance.pk:
            self.fields.pop('opening_quantity')
            self.fields.pop('opening_warehouse')
        if not self.instance.pk:
            self.fields['sku_token'].required = True
            if self.is_bound:
                try:
                    sku = signing.loads(self.data.get(self.add_prefix('sku_token'), ''), salt='crm.product.sku')
                    if not isinstance(sku, str) or not re.fullmatch(r'TOV-[0-9A-F]{32}', sku):
                        raise signing.BadSignature
                    self.instance.sku = sku
                except signing.BadSignature:
                    self._sku_token_error = True
            else:
                self.initial['sku_token'] = signing.dumps(self.instance.sku, salt='crm.product.sku')
        self.initial['sku'] = self.instance.sku
        self.order_fields(['name', 'sku', 'category', 'unit', 'purchase_price', 'sale_price', 'opening_quantity', 'opening_warehouse', 'minimum_stock', 'active', 'sku_token'])

    def clean(self):
        data = super().clean()
        if data.get('opening_quantity') and not data.get('opening_warehouse'):
            self.add_error('opening_warehouse', 'Boshlang‘ich miqdor uchun omborni tanlang.')
        return data

    def clean_sku_token(self):
        token = self.cleaned_data.get('sku_token', '')
        if not self.instance.pk:
            if self._sku_token_error:
                raise forms.ValidationError('Artikul tasdig‘i noto‘g‘ri. Tovar qo‘shish sahifasini qayta oching.')
            if Product.objects.filter(sku=self.instance.sku).exists():
                raise forms.ValidationError('Bu artikul bilan mahsulot saqlangan. Yangi mahsulot uchun sahifani qayta oching.')
        return token

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['partner', 'direction', 'amount', 'method', 'notes']

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['title', 'amount', 'date', 'notes']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}

class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = ['name', 'address']


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']


class ProductDeleteForm(forms.Form):
    products = forms.ModelMultipleChoiceField(queryset=Product.objects.all(), label='Tovarlar', widget=forms.MultipleHiddenInput)
