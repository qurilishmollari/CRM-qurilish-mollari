import hashlib
import json
from uuid import UUID
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from crm.excel import report_workbook
from crm.models import Category, Document, DocumentLine, Expense, Partner, Payment, Product, Stock, Warehouse
from crm.permissions import visible_documents
from crm.reporting import build_report
from crm.services import post_document
from .auth import TOKEN_LIFETIME
from .permissions import ModelPermissions
from .serializers import (CategorySerializer, DocumentInputSerializer, DocumentSerializer, ExpenseSerializer,
                          LoginSerializer, PartnerSerializer, PaymentSerializer, ProductSerializer,
                          StockSerializer, WarehouseSerializer)


def user_info(user):
    return {'id': user.pk, 'username': user.username, 'name': user.get_full_name(), 'groups': list(user.groups.values_list('name', flat=True)), 'permissions': sorted(user.get_all_permissions())}


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'mobile_login'
    def get_authenticate_header(self, request):
        return 'Token'
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        with transaction.atomic():
            # Serialize token rotation for concurrent logins by the same user.
            type(user).objects.select_for_update().get(pk=user.pk)
            token, _ = Token.objects.get_or_create(user=user)
            if token.created + TOKEN_LIFETIME <= timezone.now():
                token.delete()
                token = Token.objects.create(user=user)
        response = Response({'token': token.key, 'token_type': 'Token', 'expires_at': token.created + TOKEN_LIFETIME, 'user': user_info(user)})
        response['Cache-Control'] = 'no-store'
        return response


class LogoutView(APIView):
    def post(self, request):
        request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(user_info(request.user))


class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [ModelPermissions]
    serializer_class = ProductSerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    def get_queryset(self):
        qs = Product.objects.select_related('category').order_by('name', 'pk')
        if not self.request.user.has_perm('crm.change_product'):
            qs = qs.filter(active=True)
        q = self.request.query_params.get('q', '')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q))
        return qs
    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({'detail': 'Tovar ombor yoki hujjatlarga bog‘langan.'}, status=409)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    def check_permissions(self, request):
        super().check_permissions(request)
        if not request.user.has_perm('crm.view_product'):
            raise PermissionDenied()


class WarehouseViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WarehouseSerializer
    queryset = Warehouse.objects.all().order_by('pk')
    def check_permissions(self, request):
        super().check_permissions(request)
        if not (request.user.has_perm('crm.view_stock') or request.user.has_perm('crm.view_warehouse')):
            raise PermissionDenied()


class PartnerViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = PartnerSerializer
    permission_classes = [ModelPermissions]
    def get_queryset(self):
        qs = Partner.objects.all()
        if not self.request.user.has_perm('crm.manage_inventory_documents'):
            qs = qs.filter(kind='customer')
        q = self.request.query_params.get('q', '')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q))
        return qs


class StockViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StockSerializer
    permission_classes = [ModelPermissions]
    def get_queryset(self):
        qs = Stock.objects.select_related('product', 'warehouse').order_by('product__name', 'pk')
        for field in ('warehouse', 'product'):
            value = self.request.query_params.get(field)
            if value:
                if not value.isdigit() or len(value) > 18:
                    raise ValidationError({field: 'Butun son kiriting.'})
                qs = qs.filter(**{f'{field}_id': value})
        q = self.request.query_params.get('q', '')
        if q:
            qs = qs.filter(Q(product__name__icontains=q) | Q(product__sku__icontains=q))
        return qs


class DocumentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [ModelPermissions]
    serializer_class = DocumentSerializer
    def get_serializer_class(self):
        return DocumentInputSerializer if self.action == 'create' else DocumentSerializer
    def get_queryset(self):
        qs = visible_documents(self.request.user).select_related('partner', 'warehouse').prefetch_related('lines__product')
        kind = self.request.query_params.get('kind')
        return qs.filter(kind=kind) if kind else qs

    def replay(self, existing, fingerprint):
        if existing.created_by_id != self.request.user.pk or existing.api_request_hash != fingerprint:
            return Response({'detail': 'client_request_id boshqa so‘rov uchun ishlatilgan.'}, status=409)
        return Response(DocumentSerializer(existing).data)

    def create(self, request, *args, **kwargs):
        if not isinstance(request.data, dict):
            raise ValidationError('JSON obyekt yuboring.')
        try:
            request_id = UUID(str(request.data.get('client_request_id', '')))
        except (ValueError, TypeError):
            raise ValidationError({'client_request_id': 'Yangi operatsiya uchun UUID yuboring.'})
        fingerprint = hashlib.sha256(json.dumps(request.data, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        existing = Document.objects.filter(api_request_id=request_id).first()
        if existing:
            return self.replay(existing, fingerprint)
        serializer = DocumentInputSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data.pop('client_request_id')
        lines = data.pop('lines')
        manager = request.user.has_perm('crm.manage_inventory_documents')
        try:
            with transaction.atomic():
                if not manager:
                    partner = Partner.objects.select_for_update().filter(kind='customer', name__iexact=data['buyer_name'], phone=data['buyer_phone']).first()
                    if partner is None:
                        if data['kind'] == 'return':
                            raise ValidationError({'buyer_phone': 'Bu xaridorning avvalgi xaridi topilmadi.'})
                        partner = Partner.objects.create(name=data['buyer_name'], phone=data['buyer_phone'], kind='customer')
                    data['partner'] = partner
                document = Document.objects.create(**data, created_by=request.user, api_request_id=request_id, api_request_hash=fingerprint)
                for line in lines:
                    product = line['product']
                    price = line.get('price', product.sale_price) if manager else product.sale_price
                    DocumentLine.objects.create(document=document, product=product, quantity=line['quantity'], price=price)
                post_document(document.pk)
                document.refresh_from_db()
        except DjangoValidationError as exc:
            raise ValidationError({'detail': exc.messages})
        except IntegrityError:
            existing = Document.objects.filter(api_request_id=request_id).first()
            if existing:
                return self.replay(existing, fingerprint)
            return Response({'detail': 'Ma’lumotlar to‘qnashuvi. So‘rovni tekshiring.'}, status=409)
        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)


class PaymentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [ModelPermissions]
    queryset = Payment.objects.select_related('partner').all()
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ExpenseViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [ModelPermissions]
    queryset = Expense.objects.all()
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ReportView(APIView):
    def get(self, request):
        if not request.user.has_perms(['crm.view_document', 'crm.view_payment', 'crm.view_expense', 'crm.view_partner']):
            raise PermissionDenied()
        period = request.query_params.get('period', 'day')
        if period not in ('day', 'week', 'month', 'year', 'all'):
            raise ValidationError({'period': 'day, week, month, year yoki all tanlang.'})
        context, docs, payments, expenses = build_report(period)
        if request.query_params.get('export') == 'xlsx':
            response = HttpResponse(report_workbook(context, docs, payments, expenses), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="hisobot-{period}-{context["today"].isoformat()}.xlsx"'
            response['Cache-Control'] = 'private, no-store'
            return response
        data = {key: str(value) if key in ('revenue', 'profit', 'expenses', 'net', 'incoming', 'outgoing') else value for key, value in context.items() if key != 'balances'}
        data['balances'] = [{'partner': row['partner'].pk, 'name': row['partner'].name, 'kind': row['partner'].kind, 'balance': str(row['balance'])} for row in context['balances']]
        return Response(data)
