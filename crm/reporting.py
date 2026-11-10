from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone
from .models import Document, Expense, Partner, Payment
from .services import partner_balance


def build_report(period='day'):
    today = timezone.localdate()
    if period not in ['day', 'week', 'month', 'year', 'all']:
        period = 'day'
    start = {'day': today, 'week': today - timedelta(days=today.weekday()), 'month': today.replace(day=1), 'year': today.replace(month=1, day=1), 'all': None}[period]
    label = {'day': 'Bugun', 'week': 'Shu hafta', 'month': 'Shu oy', 'year': 'Shu yil', 'all': 'Barcha davr'}[period]
    docs = Document.objects.filter(posted=True, kind__in=['sale', 'return']).select_related('partner', 'warehouse').prefetch_related('lines__product')
    expenses = Expense.objects.all()
    payments = Payment.objects.select_related('partner')
    if start:
        docs = docs.filter(created_at__date__range=(start, today))
        expenses = expenses.filter(date__range=(start, today))
        payments = payments.filter(created_at__date__range=(start, today))
    revenue, profit = Decimal('0'), Decimal('0')
    for doc in docs:
        sign = -1 if doc.kind == 'return' else 1
        revenue += sign * doc.total
        profit += sign * sum(((line.price - line.cost) * line.quantity for line in doc.lines.all()), Decimal('0'))
    expense_total = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    incoming = payments.filter(direction='in').aggregate(total=Sum('amount'))['total'] or Decimal('0')
    outgoing = payments.filter(direction='out').aggregate(total=Sum('amount'))['total'] or Decimal('0')
    balances = [{'partner': p, 'balance': partner_balance(p)} for p in Partner.objects.prefetch_related('payment_set')]
    context = {'revenue': revenue, 'profit': profit, 'expenses': expense_total, 'net': profit - expense_total, 'balances': balances, 'period': period, 'period_label': label, 'start': start, 'today': today, 'incoming': incoming, 'outgoing': outgoing, 'sale_count': sum(d.kind == 'sale' for d in docs), 'return_count': sum(d.kind == 'return' for d in docs)}
    return context, docs, payments, expenses
