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
        ('products', {'name': 'Yangi tovar', 'category': 1, 'unit': 'dona', 'sale_price': '15000.00', 'minimum_stock': '0', 'active': True}),
        ('partners', {'name': 'Ali Valiyev', 'kind': 'customer', 'phone': '+998901234567'}),
        ('documents', sale),
        ('payments', {'partner': 1, 'direction': 'in', 'amount': '50000.00', 'method': 'cash', 'notes': ''}),
        ('expenses', {'title': 'Transport', 'amount': '10000.00', 'date': 'YYYY-MM-DD', 'notes': ''}),
    ]:
        group = next(item['group'] for item in items if item['path'] == f'{resource}/')
        items.append({'method': 'POST', 'path': f'{resource}/', 'title': f'{group}: yangi yozuv', 'group': group, 'body': body})
    items.extend([
        {'method': 'POST', 'path': 'documents/', 'title': 'Mijozdan tovar qaytarish', 'group': 'Hujjatlar', 'body': {**sale, 'kind': 'return'}},
        {'method': 'PATCH', 'path': 'products/{id}/', 'title': 'Tovarni tahrirlash', 'group': 'Tovarlar', 'body': {'sale_price': '18000.00'}},
        {'method': 'DELETE', 'path': 'products/{id}/', 'title': 'Tovarni o‘chirish', 'group': 'Tovarlar'},
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
            continue
        op = {'summary': item['title'], 'tags': [item['group']], 'security': [] if item.get('public') else [{'TokenAuth': []}], 'responses': {'200': {'description': 'OK'}, '400': {'description': 'Validation error'}, '401': {'description': 'Missing or expired token'}, '403': {'description': 'Permission denied'}}}
        if '{id}' in path:
            op['parameters'] = [{'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'integer', 'minimum': 1}}]
        if method == 'get' and path == '/reports/':
            op['parameters'] = [{'name': 'period', 'in': 'query', 'schema': {'type': 'string', 'enum': ['day', 'week', 'month', 'year', 'all']}}, {'name': 'export', 'in': 'query', 'schema': {'type': 'string', 'enum': ['xlsx']}}]
        if 'body' in item:
            op['requestBody'] = {'required': True, 'content': {'application/json': {'schema': {'type': 'object'}, 'example': item['body']}}}
        if method == 'post' and item['path'] != 'auth/login/':
            op['responses']['204' if item['path'] == 'auth/logout/' else '201'] = {'description': 'Success'}
        if method == 'delete':
            op['responses']['204'] = {'description': 'Deleted'}
            op['responses']['409'] = {'description': 'Object is protected'}
        paths.setdefault(path, {})[method] = op
    return JsonResponse({'openapi': '3.0.3', 'info': {'title': 'Qurilish CRM Mobile API', 'version': '1.0', 'description': 'JSON API. Authorization: Token <token>. Token lifetime: 7 days. Sale/return POST requires a new UUID client_request_id; retries must preserve it.'}, 'servers': [{'url': '/api/v1'}], 'components': {'securitySchemes': {'TokenAuth': {'type': 'apiKey', 'in': 'header', 'name': 'Authorization', 'description': 'Token <token>'}}}, 'paths': paths})
