import csv
from datetime import timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q, Sum
from django.db.models.deletion import ProtectedError
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .forms import DocumentForm, ExpenseForm, LineFormSet, PartnerForm, PaymentForm, ProductForm, WarehouseForm, ProductDeleteForm
from .models import Category, Document, Expense, Partner, Payment, Product, Stock, Warehouse
from .services import partner_balance, post_document
from .permissions import allowed_document_kinds, visible_documents

@login_required
@permission_required('crm.view_document', raise_exception=True)
def dashboard(request):
    if not request.user.has_perm('crm.manage_inventory_documents'):
        return redirect('documents')
    docs = Document.objects.filter(posted=True).prefetch_related('lines')
    today = timezone.localdate()
    sales = docs.filter(kind='sale', created_at__date=today)
    revenue = sum((d.total for d in sales), Decimal('0'))
    low = Product.objects.filter(active=True).annotate(remaining=Sum('stock__quantity', default=0)).filter(remaining__lte=F('minimum_stock'))
    return render(request, 'crm/dashboard.html', {'revenue': revenue, 'sale_count': sales.count(), 'product_count': Product.objects.filter(active=True).count(), 'customer_count': Partner.objects.filter(kind='customer').count(), 'low': low[:8], 'recent': docs.select_related('partner', 'warehouse')[:8]})

SECTIONS = {
    'products': (Product, ProductForm, 'Tovarlar', ['name', 'sku', 'category', 'unit', 'sale_price']),
    'partners': (Partner, PartnerForm, 'Mijozlar va yetkazib beruvchilar', ['name', 'kind', 'phone', 'address']),
    'warehouses': (Warehouse, WarehouseForm, 'Omborlar', ['name', 'address']),
    'payments': (Payment, PaymentForm, 'To‘lovlar', ['partner', 'direction', 'amount', 'method', 'created_at']),
    'expenses': (Expense, ExpenseForm, 'Xarajatlar', ['title', 'amount', 'date']),
}

@login_required
def listing(request, section):
    if section not in SECTIONS:
        from django.http import Http404
        raise Http404
    model, _, title, fields = SECTIONS[section]
    if not request.user.has_perm(f'crm.view_{model._meta.model_name}'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    qs = model.objects.all()
    if section == 'partners' and not request.user.has_perm('crm.manage_inventory_documents'):
        qs = qs.filter(kind=Partner.Kind.CUSTOMER)
        title = 'Mijozlar'
    query = request.GET.get('q', '').strip()
    if query:
        if section == 'products': qs = qs.filter(Q(name__icontains=query) | Q(sku__icontains=query))
        elif section in ('partners', 'warehouses'): qs = qs.filter(name__icontains=query)
        elif section == 'payments': qs = qs.filter(partner__name__icontains=query)
        else: qs = qs.filter(title__icontains=query)
    page = Paginator(qs.order_by('-pk'), 30).get_page(request.GET.get('page'))
    rows = []
    for obj in page:
        cells = [getattr(obj, f'get_{field}_display', lambda: getattr(obj, field))() for field in fields]
        rows.append({'id': obj.pk, 'cells': cells})
    return render(request, 'crm/list.html', {'title': title, 'section': section, 'headers': [model._meta.get_field(f).verbose_name for f in fields], 'rows': rows, 'page': page, 'q': query, 'can_add': request.user.has_perm(f'crm.add_{model._meta.model_name}'), 'can_delete_products': section == 'products' and request.user.has_perm('crm.delete_product')})


@login_required
@permission_required(['crm.view_product', 'crm.delete_product'], raise_exception=True)
@require_POST
def products_delete(request):
    form = ProductDeleteForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'O‘chirish uchun ro‘yxatdan tovarlarni tanlang. Tanlov eskirgan bo‘lsa, qayta tanlang.')
        return redirect('listing', section='products')
    products = list(form.cleaned_data['products'])
    if request.POST.get('confirm') != 'yes':
        deletable, protected = [], []
        for product in products:
            target = protected if product.stock_set.exists() or product.documentline_set.exists() else deletable
            target.append(product)
        return render(request, 'crm/products_delete.html', {'form': form, 'deletable': deletable, 'protected': protected})
    deleted, protected_count = 0, 0
    for product in products:
        try:
            with transaction.atomic():
                product.delete()
        except ProtectedError:
            protected_count += 1
        else:
            deleted += 1
    if deleted:
        messages.success(request, f'{deleted} ta tovar o‘chirildi.')
    if protected_count:
        messages.warning(request, f'{protected_count} ta tovar ombor yoki hujjatlarga bog‘langanligi uchun o‘chirilmadi.')
    return redirect('listing', section='products')

@login_required
def create(request, section):
    if section not in SECTIONS:
        from django.http import Http404
        raise Http404
    model, form_class, title, _ = SECTIONS[section]
    if not request.user.has_perm(f'crm.add_{model._meta.model_name}'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    form = form_class(request.POST or None)
    if section == 'partners' and not request.user.has_perm('crm.manage_inventory_documents'):
        form.fields['kind'].choices = [(Partner.Kind.CUSTOMER, 'Mijoz')]
        form.fields['kind'].initial = Partner.Kind.CUSTOMER
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        if hasattr(obj, 'created_by_id'): obj.created_by = request.user
        obj.save()
        messages.success(request, 'Ma’lumot saqlandi.')
        return redirect('listing', section=section)
    return render(request, 'crm/form.html', {'form': form, 'title': f'{title} — yangi yozuv'})

@login_required
@permission_required('crm.add_document', raise_exception=True)
def document_create(request):
    kind = request.POST.get('kind') if request.method == 'POST' else request.GET.get('kind', 'sale')
    if kind not in allowed_document_kinds(request.user):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    initial = {'kind': kind}
    manager = request.user.has_perm('crm.manage_inventory_documents')
    if manager and request.method == 'GET' and kind == Document.Kind.RETURN and request.GET.get('original'):
        original = get_object_or_404(visible_documents(request.user), pk=request.GET['original'], kind=Document.Kind.SALE, posted=True)
        initial.update(original=original, partner=original.partner, warehouse=original.warehouse)
    form = DocumentForm(request.POST or None, initial=initial, user=request.user)
    formset = LineFormSet(request.POST or None, form_kwargs={'user': request.user})
    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        try:
            with transaction.atomic():
                document = form.save(commit=False)
                document.created_by = request.user
                if not manager:
                    customers = Partner.objects.filter(kind=Partner.Kind.CUSTOMER, name__iexact=document.buyer_name, phone=document.buyer_phone)
                    document.partner = customers.first()
                    if document.partner is None:
                        if kind == Document.Kind.RETURN:
                            raise ValidationError('Bu ism va telefon bilan xaridorning avvalgi xaridi topilmadi.')
                        document.partner = Partner.objects.create(name=document.buyer_name, phone=document.buyer_phone, kind=Partner.Kind.CUSTOMER)
                document.save()
                formset.instance = document
                formset.save()
                post_document(document.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Hujjat tasdiqlandi. Ombor qoldig‘i yangilandi.')
            return redirect('document_detail', pk=document.pk)
    prices = {str(p.pk): str(p.sale_price) for p in Product.objects.filter(active=True)}
    return render(request, 'crm/form.html', {'form': form, 'formset': formset, 'product_prices': prices, 'title': 'Yangi savdo / ombor hujjati' if manager else 'Sotuv / tovar qaytarish'})

@login_required
@permission_required('crm.view_document', raise_exception=True)
def documents(request):
    qs = visible_documents(request.user).select_related('partner', 'warehouse').prefetch_related('lines')
    kind = request.GET.get('kind', '')
    if kind in Document.Kind.values: qs = qs.filter(kind=kind)
    kinds = [(value, label) for value, label in Document.Kind.choices if value in allowed_document_kinds(request.user)]
    return render(request, 'crm/documents.html', {'page': Paginator(qs, 30).get_page(request.GET.get('page')), 'kinds': kinds, 'kind': kind})

@login_required
@permission_required('crm.view_document', raise_exception=True)
def document_detail(request, pk):
    return render(request, 'crm/document.html', {'doc': get_object_or_404(visible_documents(request.user).select_related('partner', 'warehouse', 'created_by').prefetch_related('lines__product'), pk=pk)})

@login_required
@permission_required('crm.view_stock', raise_exception=True)
def inventory(request):
    qs = Stock.objects.select_related('product', 'warehouse').order_by('product__name')
    q = request.GET.get('q', '')
    warehouse = request.GET.get('warehouse', '')
    if q: qs = qs.filter(Q(product__name__icontains=q) | Q(product__sku__icontains=q))
    if warehouse.isdigit(): qs = qs.filter(warehouse_id=warehouse)
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="ombor.csv"'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(['Tovar', 'Artikul', 'Ombor', 'Qoldiq', 'Birlik'])
        for s in qs:
            values = [s.product.name, s.product.sku, s.warehouse.name, str(s.quantity), s.product.unit]
            writer.writerow(["'" + v if v.startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else v for v in values])
        return response
    return render(request, 'crm/inventory.html', {'page': Paginator(qs, 40).get_page(request.GET.get('page')), 'warehouses': Warehouse.objects.all(), 'q': q, 'selected': warehouse})

@login_required
@permission_required(['crm.view_document', 'crm.view_payment', 'crm.view_expense', 'crm.view_partner'], raise_exception=True)
def reports(request):
    today = timezone.localdate()
    period = request.GET.get('period', 'day')
    if period not in ['day', 'week', 'month', 'year', 'all']:
        period = 'day'
    start = {'day': today, 'week': today - timedelta(days=today.weekday()), 'month': today.replace(day=1), 'year': today.replace(month=1, day=1), 'all': None}[period]
    period_label = {'day': 'Bugun', 'week': 'Shu hafta', 'month': 'Shu oy', 'year': 'Shu yil', 'all': 'Barcha davr'}[period]
    docs = Document.objects.filter(posted=True, kind__in=['sale', 'return']).select_related('partner', 'warehouse').prefetch_related('lines__product')
    expense_qs = Expense.objects.all()
    payment_qs = Payment.objects.all()
    if start:
        docs = docs.filter(created_at__date__range=(start, today))
        expense_qs = expense_qs.filter(date__range=(start, today))
        payment_qs = payment_qs.filter(created_at__date__range=(start, today))
    revenue, profit = Decimal('0'), Decimal('0')
    for doc in docs:
        sign = -1 if doc.kind == 'return' else 1
        revenue += sign * doc.total
        profit += sign * sum(((l.price - l.cost) * l.quantity for l in doc.lines.all()), Decimal('0'))
    expenses = expense_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    incoming = payment_qs.filter(direction='in').aggregate(total=Sum('amount'))['total'] or Decimal('0')
    outgoing = payment_qs.filter(direction='out').aggregate(total=Sum('amount'))['total'] or Decimal('0')
    balances = [{'partner': p, 'balance': partner_balance(p)} for p in Partner.objects.prefetch_related('payment_set')]
    context = {'revenue': revenue, 'profit': profit, 'expenses': expenses, 'net': profit - expenses, 'balances': balances, 'period': period, 'period_label': period_label, 'start': start, 'today': today, 'incoming': incoming, 'outgoing': outgoing, 'sale_count': sum(d.kind == 'sale' for d in docs), 'return_count': sum(d.kind == 'return' for d in docs)}
    if request.GET.get('export') == 'xlsx':
        from .excel import report_workbook
        response = HttpResponse(report_workbook(context, docs, payment_qs.select_related('partner'), expense_qs), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="hisobot-{period}-{today.isoformat()}.xlsx"'
        response['Cache-Control'] = 'private, no-store'
        return response
    return render(request, 'crm/reports.html', context)
