# Mobil ilova API — v1

Deploydan keyingi asosiy manzil:

```text
https://crm-qurilish-mollari-production.up.railway.app/api/v1/
```

Mahalliy sinov: `http://127.0.0.1:8000/api/v1/`. Barcha manzillarning oxirida `/` bor. API JSON qabul qiladi va qaytaradi. Excel eksporti bundan mustasno. Veb-sayt login cookie-si API uchun ishlamaydi. Serverga yangi kod deploy qilinmaguncha bu endpointlar jonli saytda mavjud bo‘lmaydi.

Brauzerda interaktiv hujjatlar: `/api/docs/` (`/api/docs` ham ishlaydi). OpenAPI 3.0 JSON: `/api/schema/`. Hujjatlarni ko‘rish uchun login kerak emas; haqiqiy ma’lumot so‘rovlari token/ruxsat talab qiladi. Kirish endpointidan token avtomatik olinib faqat sahifa xotirasida saqlanadi. So‘rov tanasini va query parametrlarini tahrirlab sinash, Excel yuklash mumkin. Yozish/o‘chirish amallari haqiqiy bazaga ta’sir qiladi va tasdiqlash so‘raydi. Hujjat yaratish uchun yangi UUID tugmasini faqat yangi operatsiya boshlaganda bosing; retry paytida o‘zgartirmang. UI qo‘shimcha CDN/paketlarsiz ishlaydi.

## Kirish

`POST auth/login/`

```json
{"username": "sotuvchi", "password": "OZ_PAROLINGIZ"}
```

Javob:

```json
{
  "token": "SERVER_QAYTARGAN_TOKEN",
  "token_type": "Token",
  "expires_at": "2026-11-17T12:00:00+05:00",
  "user": {"id": 2, "username": "sotuvchi", "name": "", "groups": ["Sotuvchi"], "permissions": ["crm.view_product", "crm.add_document"]}
}
```

Keyingi barcha so‘rovlarda:

```http
Authorization: Token SERVER_QAYTARGAN_TOKEN
Content-Type: application/json
```

`GET auth/me/` — foydalanuvchi, guruhlar va ruxsatlar. `POST auth/logout/` — tokenni bekor qiladi, `204` qaytaradi. Token 7 kun amal qiladi; muddati tugasa `401`, qayta login kerak. Bir foydalanuvchi uchun bitta token mavjud: bir nechta qurilmadagi login bir tokenni ishlatadi, logout barchasini chiqaradi. Mobil ilovada tokenni Keychain/Keystore kabi himoyalangan xotirada saqlang va faqat HTTPS ishlating. Username/parol mavjud server foydalanuvchisiga tegishli bo‘lishi kerak.

## Endpointlar

| Metod | Manzil | Vazifasi |
|---|---|---|
| POST | `auth/login/` | Kirish |
| POST | `auth/logout/` | Chiqish |
| GET | `auth/me/` | Profil va ruxsatlar |
| GET | `products/`, `products/{id}/` | Katalog, narx, artikul, o‘lchov |
| POST | `products/` | Tovar yaratish; artikul avtomatik |
| PATCH | `products/{id}/` | Tovarni tahrirlash |
| DELETE | `products/{id}/` | Hisobda ishlatilmagan tovarni o‘chirish |
| GET | `categories/`, `categories/{id}/` | Kategoriyalar |
| GET | `warehouses/`, `warehouses/{id}/` | Omborlar |
| GET | `stocks/`, `stocks/{id}/` | Qoldiqlar |
| GET, POST | `partners/` | Mijoz / hamkorlar |
| GET | `partners/{id}/` | Hamkor tafsiloti |
| GET, POST | `documents/` | Hujjatlar / yangi operatsiya |
| GET | `documents/{id}/` | Hujjat va qatorlari |
| GET, POST | `payments/` | To‘lovlar |
| GET | `payments/{id}/` | To‘lov tafsiloti |
| GET, POST | `expenses/` | Xarajatlar |
| GET | `expenses/{id}/` | Xarajat tafsiloti |
| GET | `reports/?period=day` | Moliyaviy hisobot |
| GET | `reports/?period=year&export=xlsx` | Excel fayli |

Ruxsatlar serverdagi Django guruhlariga bog‘liq. `Sotuvchi` mahsulotlar, kategoriyalar, omborlar, qoldiqlar, mijozlar va sotuv/qaytarish hujjatlarini ko‘radi. U mijoz hamda sotuv/qaytarish yaratishi mumkin. Tovar tahriri/o‘chirish, xarid/ko‘chirish, to‘lov, xarajat va moliyaviy hisobotlarga ruxsati yo‘q. Xarid narxi sotuvchiga chiqarilmaydi. Admin tegishli imkoniyatlardan foydalanadi. Standart holatda sotuvchilar barcha sotuv/qaytarishlarni ko‘ra oladi; boshqa sotuvchilar bo‘yicha ajratish yo‘q.

## Ro‘yxat, qidiruv va sonlar

Ro‘yxat javobi:

```json
{"count": 100, "next": "https://example.com/api/v1/products/?page=2", "previous": null, "results": []}
```

`page=2&page_size=30` ishlaydi; maksimal sahifa hajmi 100. Mahsulotda `?q=sement` yoki artikul; hamkorda `?q=Ali` yoki telefon; qoldiqda `?q=sement&warehouse=1&product=2`; hujjatda `?kind=sale` yoki `return`. Qidiruv va pagination parametrlarini birga ishlatish mumkin.

Pul va miqdor maydonlari aniqlik yo‘qolmasligi uchun JSON **string** sifatida qaytariladi. `quantity` ko‘pi bilan 3 kasr, `price` ko‘pi bilan 2 kasr. Mobil tarafda Decimal yoki kichik pul birliklarini qo‘llang. `created_at` vaqt zonasiga ega ISO 8601; hisobot davrlari Asia/Tashkent bo‘yicha.

## Sotuv yaratish

Avval `products/`, `warehouses/`, `stocks/` orqali haqiqiy ID va qoldiqlarni oling. `POST documents/`:

```json
{
  "client_request_id": "3a6ea277-30d8-4ed7-bb74-53166cb42b2e",
  "kind": "sale",
  "buyer_name": "Ali Valiyev",
  "buyer_phone": "+998901234567",
  "warehouse": 1,
  "notes": "Mobil ilovadan",
  "lines": [
    {"product": 1, "quantity": "2.500"},
    {"product": 2, "quantity": "1.000"}
  ]
}
```

Javob `201`: `id`, `kind`, xaridor, `posted`, `created_at`, `lines` (`product`, `quantity`, `price`, `total`) va hujjat `total` summasini qaytaradi. Xaridor ism/telefon bo‘yicha topiladi yoki yaratiladi. Sotuvchi `price` yuborishi shart emas; server katalog narxini qo‘llaydi. Miqdor yetmasa `400`, hech qanday hujjat yoki qoldiq o‘zgarishi saqlanmaydi. Narx katalogda 0 bo‘lsa server 0 ishlatadi — savdodan oldin admin haqiqiy narxlarni belgilashi kerak.

**Takroriy so‘rovlar:** har yangi operatsiyaga mobil ilova yangi UUID `client_request_id` yaratadi. Aloqa uzilsa aynan shu UUID va JSON qiymatlarini qayta yuboring: oldingi hujjat `200` bilan qaytadi, qoldiq ikkinchi marta o‘zgarmaydi. Bitta UUID bilan boshqa ma’lumot yuborilsa `409`. Yangi operatsiyada eski UUID ni qayta ishlatmang. UUID ni so‘rov bilan birga saqlang; qayta urinishda yangi UUID yaratsangiz, bu boshqa sotuv bo‘ladi.

## Qaytarish

Xuddi yuqoridagi so‘rovni yangi UUID bilan `kind: "return"` qilib yuboring. Asl xaridorning ismi/telefoni, ombor va qaytgan miqdorni kiriting. `original` yoki `partner` kerak emas va sotuvchida qabul qilinmaydi. Qaytarish miqdori sotilgan va qaytarilmagan miqdordan oshmaydi. Tovar omborga qaytadi, xaridor qarzi kamayadi; pulni qaytarish hisobchi tomonidan alohida qayd qilinadi. Asl sotuvsiz qaytarish joriy katalog narxida hisoblanadi.

## Admin operatsiyalari

- Tovar POST: `name`, `category` (ID), `unit`, `purchase_price`, `sale_price`, `minimum_stock`, `active`. Artikul read-only; `barcode` yo‘q.
- Hamkor POST: `name`, `kind` (`customer`/`supplier`), `phone`, `address`, `notes`. Sotuvchi faqat `customer` qo‘shadi.
- Xarid hujjati: `kind=purchase`, `partner` (supplier ID), `warehouse`, har bir qatorda `product`, `quantity`, `price`, yangi `client_request_id`.
- Ombor ko‘chirish: `kind=transfer`, `warehouse`, `destination`, `lines`, yangi `client_request_id`.
- To‘lov POST: `partner`, `direction` (`in`/`out`), `amount`, `method` (`cash`/`card`/`bank`), `notes`.
- Xarajat POST: `title`, `amount`, `date` (`YYYY-MM-DD`), `notes`.

Tasdiqlangan hujjatlar, to‘lov va xarajatlar uchun API tahrirlash/o‘chirish endpointi yo‘q. Tovar ombor/hujjatga bog‘liq bo‘lsa DELETE `409` qaytaradi.

Idempotency hozir **faqat hujjat yaratish** uchun mavjud. To‘lov/xarajat POST so‘rovlarini timeoutdan keyin ko‘r-ko‘rona qayta yubormang; avval ro‘yxatdan tekshiring.

## Hisobotlar

`GET reports/?period=day|week|month|year|all`: `revenue`, `profit`, `expenses`, `net`, `incoming`, `outgoing`, `sale_count`, `return_count`, `start`, `today`, `balances`. Hisoblash veb interfeys bilan bir xil funksiyadan olinadi. `balances` doimo joriy barcha davr balansidir.

Excel uchun shu so‘rovga `&export=xlsx` qo‘shing. Javob JSON emas, `.xlsx` baytlari va `Content-Disposition` fayl nomi. Mobil ilovada fayl sifatida saqlang/ulashing.

## Xatolar

- `400`: noto‘g‘ri maydon yoki qoldiq/qaytarish xatosi; maydonlar bo‘yicha xabar JSON.
- `401`: login/token xatosi yoki token muddati tugagan.
- `403`: rolga bu amal taqiqlangan.
- `404`: obyekt yo‘q yoki ushbu rolga ko‘rinmaydi.
- `409`: himoyalangan tovar / takroriy UUID bilan boshqa ma’lumot.
- `429`: so‘rovlar chegarasi; `Retry-After` ga amal qiling.

Login cheklovi IP bo‘yicha 10/minut, qolgan API foydalanuvchi bo‘yicha 300/minut. Hozir Django mahalliy memory cache ishlatiladi: bir nechta server/workerlarda limitlar umumiy emas; katta ommaviy yuklama uchun umumiy Redis cache va proxy darajasidagi limitlar kerak.

## O‘rnatish va deploy

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py setup_crm
.\.venv\Scripts\python.exe manage.py test crm.api.tests
```

`rest_framework.authtoken` migratsiyalari va `crm.0006` migratsiyasi qo‘llanadi. Railway `preDeployCommand` buni avtomatik bajaradi. Mahalliy cheklangan muhitda DRF 3.17.1 kompyuterdagi mavjud paketlardan nusxalangan; server uni requirements orqali o‘rnatadi.

Native Flutter/React Native/Android/iOS ilovalari JSON HTTP mijozidan foydalanadi. Flutter Web yoki boshqa domendagi brauzer ilovasi kerak bo‘lsa CORS domenlarini alohida sozlash kerak; hozir ochiq CORS berilmagan.
