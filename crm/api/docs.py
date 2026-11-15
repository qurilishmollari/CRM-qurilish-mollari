from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


def endpoints():
    sale = {'client_request_id': 'NEW_UUID', 'kind': 'sale', 'buyer_name': 'Ali Valiyev', 'buyer_phone': '+998901234567', 'warehouse': 1, 'lines': [{'product': 1, 'quantity': '2.000'}]}
    items = [
        {'method': 'POST', 'path': 'auth/login/', 'title': 'Kirish va token olish', 'group': 'Kirish', 'body': {'username': '', 'password': ''}, 'public': True},
        {'method': 'GET', 'path': 'auth/me/', 'title': 'Profil va ruxsatlar', 'group': 'Kirish'},
        {'method': 'POST', 'path': 'auth/logout/', 'title': 'Tokenni bekor qilish', 'group': 'Kirish', 'body': {}},
    ]
    for resource, group in [('products', 'Tovarlar'), ('categories', 'Kategoriyalar'), ('warehouses', 'Omborlar'), ('stocks', 'Qoldiqlar'), ('partners', 'Hamkorlar'), ('documents', 'Hujjatlar'), ('payments', 'To‘lovlar'), ('expenses', 'Xarajatlar')]:
        items.extend([
            {'method': 'GET', 'path': f'{resource}/', 'title': f'{group} ro‘yxati', 'group': group, 'query': 'page=1&page_size=30'},
            {'method': 'GET', 'path': f'{resource}/{{id}}/', 'title': f'{group}: tafsilot', 'group': group},
        ])
    for resource, body in [
        ('categories', {'name': 'Yangi kategoriya'}),
        ('products', {'name': 'Yangi tovar', 'category': 1, 'unit': 'dona', 'purchase_price': '10000.00', 'sale_price': '15000.00', 'minimum_stock': '2', 'opening_quantity': '0', 'active': True}),
        ('partners', {'name': 'Ali Valiyev', 'kind': 'customer', 'phone': '+998901234567'}),
        ('documents', sale),
        ('payments', {'partner': 1, 'direction': 'in', 'amount': '50000.00', 'method': 'cash', 'notes': ''}),
        ('expenses', {'title': 'Transport', 'amount': '10000.00', 'date': 'YYYY-MM-DD', 'notes': ''}),
    ]:
        group = next(item['group'] for item in items if item['path'] == f'{resource}/')
        items.append({'method': 'POST', 'path': f'{resource}/', 'title': f'{group}: yangi yozuv', 'group': group, 'body': body})
    items.extend([
        {'method': 'GET', 'path': 'products/', 'title': 'Tanlangan ombordagi mavjud miqdor va kam qoldiq', 'group': 'Tovarlar', 'query': 'warehouse=1&page=1'},
        {'method': 'GET', 'path': 'stocks/', 'title': 'Ombor va mahsulot bo‘yicha qoldiq', 'group': 'Qoldiqlar', 'query': 'warehouse=1&product=1'},
        {'method': 'POST', 'path': 'products/bulk-delete/', 'title': 'Tanlangan tovarlarni o‘chirish (admin)', 'group': 'Tovarlar', 'body': {'products': [1, 2]}},
        {'method': 'POST', 'path': 'products/', 'title': 'Boshlang‘ich qoldiq bilan yangi tovar (admin)', 'group': 'Tovarlar', 'body': {'name': 'Yangi sement', 'category': 1, 'unit': 'qop', 'purchase_price': '40000.00', 'sale_price': '60000.00', 'minimum_stock': '5.000', 'opening_quantity': '20.000', 'opening_warehouse': 1, 'active': True}},
        {'method': 'POST', 'path': 'documents/', 'title': 'Mavjud tovar uchun boshlang‘ich kirim (admin)', 'group': 'Hujjatlar', 'body': {'client_request_id': 'NEW_UUID', 'kind': 'opening', 'warehouse': 1, 'lines': [{'product': 1, 'quantity': '20.000'}]}},
        {'method': 'POST', 'path': 'documents/', 'title': 'Xarid / kirim (admin)', 'group': 'Hujjatlar', 'body': {'client_request_id': 'NEW_UUID', 'kind': 'purchase', 'partner': 1, 'warehouse': 1, 'lines': [{'product': 1, 'quantity': '10.000', 'price': '40000.00'}]}},
        {'method': 'POST', 'path': 'documents/', 'title': 'Omborlararo ko‘chirish (admin)', 'group': 'Hujjatlar', 'body': {'client_request_id': 'NEW_UUID', 'kind': 'transfer', 'warehouse': 1, 'destination': 2, 'lines': [{'product': 1, 'quantity': '2.000'}]}},
        {'method': 'POST', 'path': 'documents/', 'title': 'Mijozdan tovar qaytarish', 'group': 'Hujjatlar', 'body': {**sale, 'kind': 'return'}},
        {'method': 'PATCH', 'path': 'products/{id}/', 'title': 'Tovarni tahrirlash', 'group': 'Tovarlar', 'body': {'sale_price': '18000.00'}},
        {'method': 'DELETE', 'path': 'products/{id}/', 'title': 'Tovarni o‘chirish', 'group': 'Tovarlar'},
        {'method': 'DELETE', 'path': 'categories/{id}/', 'title': 'Bo‘sh kategoriyani o‘chirish', 'group': 'Kategoriyalar'},
        {'method': 'GET', 'path': 'reports/', 'title': 'Kunlik / haftalik / oylik / yillik hisobot', 'group': 'Hisobotlar', 'query': 'period=day'},
        {'method': 'GET', 'path': 'reports/', 'title': 'Excel hisobotini yuklash', 'group': 'Hisobotlar', 'query': 'period=year&export=xlsx'},
    ])
    return sorted(items, key=lambda item: item['group'])


@require_GET
def docs(request):
    response = render(request, 'crm/api_docs.html', {'endpoints': endpoints()})
    response['Cache-Control'] = 'no-store'
    return response


@require_GET
def schema(request):
    paths = {}
    for item in endpoints():
        path = '/' + item['path']
        method = item['method'].lower()
        if method in paths.get(path, {}):
            if 'body' in item:
                examples = paths[path][method]['requestBody']['content']['application/json']['examples']
                examples[f'example_{len(examples) + 1}'] = {'summary': item['title'], 'value': item['body']}
            continue
        op = {'summary': item['title'], 'tags': [item['group']], 'security': [] if item.get('public') else [{'TokenAuth': []}], 'responses': {'200': {'description': 'OK'}, '400': {'description': 'Validation error'}, '401': {'description': 'Missing or expired token'}, '403': {'description': 'Permission denied'}}}
        if '{id}' in path:
            op['parameters'] = [{'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'integer', 'minimum': 1}}]
        if method == 'get' and path == '/reports/':
            op['parameters'] = [{'name': 'period', 'in': 'query', 'schema': {'type': 'string', 'enum': ['day', 'week', 'month', 'year', 'all']}}, {'name': 'export', 'in': 'query', 'schema': {'type': 'string', 'enum': ['xlsx']}}]
        if method == 'get' and path in ('/products/', '/products/{id}/', '/stocks/'):
            op.setdefault('parameters', []).append({'name': 'warehouse', 'in': 'query', 'description': 'Ombor ID. Products javobidagi available_stock shu omborga tegishli; filtrsiz jami qoldiq.', 'schema': {'type': 'integer', 'minimum': 1}})
        if method == 'get' and path == '/stocks/':
            op['parameters'].append({'name': 'product', 'in': 'query', 'schema': {'type': 'integer', 'minimum': 1}})
        if 'body' in item:
            body_schema = {'type': 'object'}
            if method == 'post' and path in ('/products/', '/documents/', '/products/bulk-delete/'):
                name = {'/products/': 'ProductCreate', '/documents/': 'DocumentCreate', '/products/bulk-delete/': 'ProductBulkDelete'}[path]
                body_schema = {'$ref': '#/components/schemas/' + name}
            op['requestBody'] = {'required': True, 'content': {'application/json': {'schema': body_schema, 'examples': {'example_1': {'summary': item['title'], 'value': item['body']}}}}}
        if method == 'post' and item['path'] != 'auth/login/':
            if item['path'] != 'products/bulk-delete/':
                op['responses']['204' if item['path'] == 'auth/logout/' else '201'] = {'description': 'Success'}
        if method == 'post' and path == '/documents/':
            op['responses']['200'] = {'description': 'Same client_request_id and payload: existing document, no second stock change'}
            op['responses']['409'] = {'description': 'client_request_id already used for a different request'}
        if method == 'post' and path == '/products/bulk-delete/':
            op['responses']['200'] = {'description': 'deleted: removed IDs; protected: IDs linked to stock or documents', 'content': {'application/json': {'example': {'deleted': [1], 'protected': [2]}}}}
        if method == 'delete':
            op['responses']['204'] = {'description': 'Deleted'}
            op['responses']['409'] = {'description': 'Object is protected'}
        paths.setdefault(path, {})[method] = op
    return JsonResponse({'openapi': '3.0.3', 'info': {'title': 'Qurilish CRM Mobile API', 'version': '1.1', 'description': 'JSON API. Authorization: Token <token>. Token lifetime: 7 days. Every document POST requires a new UUID client_request_id; retries must preserve both UUID and payload. Seller prices are calculated on the server. Product total_stock is all warehouses, available_stock respects warehouse query, low_stock compares available_stock to minimum_stock.'}, 'servers': [{'url': '/api/v1'}], 'components': {'schemas': request_schemas(), 'securitySchemes': {'TokenAuth': {'type': 'apiKey', 'in': 'header', 'name': 'Authorization', 'description': 'Token <token>'}}}, 'paths': paths})


def request_schemas():
    from crm.models import Document, Product
    identifier = {'type': 'integer', 'minimum': 1}
    quantity = {'type': 'string', 'description': 'Decimal, max 18 digits, 3 decimal places', 'example': '10.000'}
    money = {'type': 'string', 'description': 'Nonnegative decimal, max 18 digits, 2 decimal places', 'example': '60000.00'}
    return {
        'ProductCreate': {'type': 'object', 'required': ['name', 'category'], 'properties': {
            'name': {'type': 'string', 'maxLength': 180}, 'category': identifier,
            'unit': {'type': 'string', 'enum': list(Product.Unit.values)},
            'purchase_price': money, 'sale_price': money, 'minimum_stock': quantity,
            'opening_quantity': quantity, 'opening_warehouse': {**identifier, 'description': 'Required if opening_quantity > 0; create only; admin inventory permission required'},
            'active': {'type': 'boolean'}, 'sku': {'type': 'string', 'readOnly': True, 'description': 'Generated automatically'},
            'total_stock': {**quantity, 'readOnly': True}, 'available_stock': {**quantity, 'readOnly': True}, 'low_stock': {'type': 'boolean', 'readOnly': True}}},
        'DocumentCreate': {'type': 'object', 'required': ['client_request_id', 'kind', 'warehouse', 'lines'], 'description': 'Seller: sale/return only, buyer_name and buyer_phone required, partner/destination/original forbidden. Manager: partner required for sale/purchase/return; no partner for opening/transfer. Transfer requires a different destination. Opening defaults price to purchase_price; purchase requires explicit price. Stock changes are atomic.', 'properties': {
            'client_request_id': {'type': 'string', 'format': 'uuid'},
            'kind': {'type': 'string', 'enum': list(Document.Kind.values)},
            'warehouse': identifier, 'destination': identifier, 'partner': identifier, 'original': identifier,
            'buyer_name': {'type': 'string', 'maxLength': 180}, 'buyer_phone': {'type': 'string', 'example': '+998901234567'},
            'notes': {'type': 'string', 'maxLength': 5000},
            'lines': {'type': 'array', 'minItems': 1, 'maxItems': 100, 'items': {'type': 'object', 'required': ['product', 'quantity'], 'properties': {'product': identifier, 'quantity': quantity, 'price': money}}}}},
        'ProductBulkDelete': {'type': 'object', 'required': ['products'], 'properties': {'products': {'type': 'array', 'minItems': 1, 'maxItems': 100, 'uniqueItems': True, 'items': identifier}}},
    }
