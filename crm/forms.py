from django import forms
from django.forms import inlineformset_factory
import re
from .models import Document, DocumentLine, Expense, Partner, Payment, Product, Warehouse

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['kind', 'buyer_name', 'buyer_phone', 'partner', 'warehouse', 'destination', 'original', 'notes']
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
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
    class Meta:
        model = Product
        fields = ['name', 'sku', 'barcode', 'category', 'unit', 'purchase_price', 'sale_price', 'minimum_stock', 'active']

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
