# Qurilish CRM

Qurilish mollari do‘koni uchun Django asosidagi boshlang‘ich CRM. Interfeys o‘zbek tilida, hisob-kitoblar UZS da. Ishlab chiqarish serveriga chiqarishdan oldin sozlash va qabul sinovlari kerak.

## Ishga tushirish (Windows PowerShell)

Python 3.12 yoki yangiroq versiya va internet ulanishi kerak. Hozirgi papkada `.venv` mavjud.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py setup_crm
.\.venv\Scripts\python.exe manage.py seed_products
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Brauzer: http://127.0.0.1:8000/ · Admin: http://127.0.0.1:8000/admin/

Yangi muhit kerak bo‘lsa avval `py -m venv .venv` bajaring. Boshlang‘ich migratsiya repozitoriyga kiritilgan. Ushbu ish muhitida tarmoq cheklovi sabab Django 6.0.6 va uning bog‘liqliklari kompyuterdagi mavjud virtual muhitdan mahalliy nusxalandi.

## Mavjud imkoniyatlar

- Bosh sahifa: bugungi savdo, mijozlar, tovarlar, kam qoldiq va oxirgi operatsiyalar.
- Kategoriya, artikul, dona/kg/tonna/m/m²/m³/qop, xarid va sotuv narxlari.
- Admin menyusidagi `Kategoriyalar` orqali yangi kategoriya qo‘shish, nomi bo‘yicha qidirish va tasdiqlab o‘chirish mumkin. Tovarlarga biriktirilgan kategoriya o‘chirilmaydi; avval tovarlarni boshqa kategoriyaga o‘tkazish kerak. Sotuvchi faqat tovar tanlash uchun kategoriyalarni ko‘radi, boshqara olmaydi. Mobil API’da ham POST/DELETE qo‘shilgan.
- Yangi tovar formasi ochilishi bilan artikul avtomatik `TOV-…` formatida yaratiladi va faqat ko‘rish uchun chiqariladi. Saqlanganda ham aynan shu artikul qoladi; forma xatolarida ham o‘zgarmaydi. Artikul imzolangan yashirin qiymat bilan tekshiriladi, admin uni qo‘lda yozmaydi. Mavjud artikullar saqlanadi, tovar tahrirlanganda o‘zgarmaydi. Shtrix-kod maydoni olib tashlangan.
- Mijozlar, yetkazib beruvchilar, telefon, manzil va izohlar.
- Ko‘p omborli hisob: xarid kirimi, sotuv chiqimi va omborlararo ko‘chirish.
- Bir hujjatda bir nechta tovar; kasrli miqdorlar; qator qo‘shish.
- Qoldiq yetishmasligini tekshirish; hujjatni atomar tasdiqlash; qayta tasdiqlashdan himoya.
- Asl sotuvga bog‘langan qaytarish; miqdor va narx tekshiruvi.
- Naqd, karta, bank to‘lovlari; kirim/chiqim; hamkor qarzdorligi va avanslar.
- Xarajatlar, barcha davr uchun savdo tushumi, hisobiy yalpi va sof foyda.
- Ombor qidiruvi, filtri va CSV eksporti; hujjatni chop etish.
- Django autentifikatsiyasi, CSRF himoyasi va serverda tekshiriladigan ruxsatlar.
- Rahbar, sotuvchi, omborchi va hisobchi guruhlari.
- Yorug‘ / qorong‘u rejim: yuqoridagi tugma bilan almashadi, kirish sahifasida ham mavjud. Tanlov brauzerda saqlanadi; dastlab qurilmaning rang rejimi qo‘llanadi.
- Tovarlarni belgilab ommaviy o‘chirish: `Tovarlar` sahifasida tovarlarni yoki joriy sahifadagi barchasini tanlang, so‘ng tekshirish sahifasida tasdiqlang. Faqat `view_product` va `delete_product` ruxsatlari bor foydalanuvchilar o‘chira oladi; sotuvchida bu imkoniyat yo‘q. Hujjat yoki ombor hisobida ishlatilgan tovarlar o‘chirilmaydi, hatto qoldig‘i nol bo‘lsa ham. Aralash tanlovda faqat bog‘lanmagan tovarlar o‘chiriladi, saqlanganlari haqida xabar chiqadi.

## Foydalanish

1. `setup_crm` asosiy ombor va rollarni yaratadi; qayta bajarish mumkin. Standart kategoriyalar kerak bo‘lsa bir marta `setup_crm --seed-categories` bajaring. Oddiy server restarti o‘chirilgan kategoriyalarni qayta yaratmaydi.
2. Admin panelida foydalanuvchilar yarating va guruh biriktiring. Oddiy CRM foydalanuvchisiga `is_staff` shart emas; admin uchun kerak.
3. Tovar va yetkazib beruvchini kiriting. Xarid hujjati orqali boshlang‘ich ombor qoldig‘ini kiriting.
4. Mijoz yarating, sotuv hujjatini saqlang. Sotuv avtomatik to‘lov yaratmaydi: mijozdan kelgan pulni To‘lovlar → Kirim orqali alohida yozing.
5. Yetkazib beruvchiga to‘lovni Chiqim orqali yozing. Mijozga pul qaytarish ham Chiqim; qaytarish hujjati pulni avtomatik qaytarmaydi.
6. Hisobotdagi musbat balans — qarz, manfiy balans — avans. Mijoz balansi va yetkazib beruvchi balansi qarama-qarshi majburiyatlarni bildiradi.

Tasdiqlangan hujjatlar va to‘lovlar admin orqali tahrirlanmaydi yoki o‘chirilmaydi. `add_document` sotuv va mijozdan qaytarishga ruxsat beradi; xarid va omborlararo ko‘chirish uchun qo‘shimcha `manage_inventory_documents` huquqi kerak. Omborchi dastlab faqat ko‘radi. To‘lov xatolarini izohli qarama-qarshi to‘lov bilan tuzatish mumkin.

### Sotuvchi roli

Admin → Foydalanuvchilar orqali xodim yarating va `Sotuvchi` guruhiga qo‘shing. `Superuser`, `Staff` yoki boshqa boshqaruv guruhlarini bermang. Sotuvchi kirganda savdo sahifasi ochiladi; sotuv va mijozdan qaytarish yaratadi, mijoz qo‘shadi, katalog va ombor qoldiqlarini ko‘radi. U xarid, ko‘chirish, tovar tahriri, yetkazib beruvchilar, to‘lovlar, xarajatlar va moliyaviy hisobotlarga kira olmaydi. Cheklovlar serverda ham tekshiriladi. Sotuvchilar barcha sotuv/qaytarish hujjatlarini ko‘ra oladi.

Sotuvchi hujjat formasida hamkor tanlamaydi: xaridor ismi va telefonini kiritadi. Telefon bo‘shliq, qavs va chiziqchalardan tozalanadi; ism va telefon bo‘yicha mavjud mijoz topiladi yoki sotuvda yangisi yaratiladi. Hujjatda xaridor ma’lumotlari ham alohida saqlanadi. Mahsulotlar ro‘yxatida katalog narxi ko‘rinadi; miqdor va jami brauzerda avtomatik hisoblanadi. Sotuvchi uchun birlik narxi serverda katalogdan olinadi, so‘rov orqali yuborilgan boshqa narx qo‘llanmaydi. Admin narxlarni qo‘lda belgilashi mumkin.

Sotuvchi qaytarishda ham xaridorning avvalgi xariddagi ismi va telefonini, ombor, mahsulot va miqdorni kiritadi; `Asl sotuv` maydoni yo‘q. Qaytarish miqdori shu xaridor va ombor bo‘yicha sotilgan, hali qaytarilmagan umumiy miqdordan oshmaydi. Asl hujjatsiz qaytarishda summa joriy katalog narxi, tannarx esa joriy xarid narxi bo‘yicha olinadi. Tarixiy narx bo‘yicha qaytarish kerak bo‘lsa, admin asl sotuvga bog‘langan hujjat yaratishi mumkin. Tovar omborga qaytadi va mijoz qarzi kamayadi; pul qaytarishni hisobchi alohida to‘lov sifatida yozadi.

### Davriy hisobotlar

Hisobotlar sahifasida `Kunlik`, `Haftalik`, `Oylik`, `Yillik`, `Barcha davr` tugmalari bor. Kunlik — bugun; haftalik — joriy haftaning dushanbasidan bugungacha; oylik — joriy oyning birinchi kunidan bugungacha; yillik — 1-yanvardan bugungacha, Asia/Tashkent bo‘yicha. Tanlangan davrga savdo/qaytarish, tushum, tannarx, xarajat, foyda va to‘lov kirim/chiqimi kiradi. Qarzdorlik jadvali doimo joriy, barcha davr balansidir. Sotuvchi moliyaviy hisobotni ko‘ra olmaydi.

Davrni tanlab `Excel yuklab olish (.xlsx)` tugmasini bosing. Haqiqiy Excel faylida 5 ta varaq bor: umumiy ko‘rsatkichlar, tovar qatorlari bo‘yicha savdo va qaytarish, to‘lovlar, xarajatlar va joriy balanslar. Qaytarish summasi va foydasi manfiy yoziladi. Summalar son sifatida, telefon va matnlar formula sifatida bajarilmaydigan matn sifatida saqlanadi. Varaqning birinchi qatori mahkamlangan, filtrlar mavjud. Eksport uchun qo‘shimcha paket kerak emas.

`seed_products` sement M400/M500, ohak, qum, shag‘al, g‘isht, gazoblok, armatura, gipsli suvoq va kafel yelimini yaratadi. Qayta bajarilsa nusxalar yaratmaydi, mavjud narxlarni o‘zgartirmaydi. Yangi mahsulotlarning narxi 0; savdodan oldin admin haqiqiy narxlarni va xarid hujjati orqali qoldiqlarni kiritishi kerak.

## Hisob cheklovlari va keyingi bosqichlar

Hozir tannarx oxirgi xarid narxi bo‘yicha olinadi va sotuv paytida saqlanadi; FIFO yoki o‘rtacha tortilgan tannarx qo‘llanmaydi. QQS, chegirmalar, yetkazib berish, xarid qaytarishi, inventarizatsiya tuzatishlari, kassa smenasi, fiskal chek, ish haqi, Telegram/SMS va tashqi buxgalteriya integratsiyalari hali yo‘q. Bu to‘liq buxgalteriya yoki barcha biznes jarayonlari tayyor bo‘lgan ERP emas.

SQLite mahalliy ishga tushirish uchun. Ko‘p xodim bir vaqtda ishlaydigan serverda PostgreSQL, zaxira nusxa, HTTPS va alohida deploy sozlamalari kerak; SQLite `select_for_update` orqali qator qulfini ta’minlamaydi. Hisobotlar kichik do‘kon uchun yozilgan; katta ma’lumotlarda SQL agregatsiyasini kengaytirish kerak.

Production uchun `DJANGO_DEBUG=0`, tasodifiy `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` muhit o‘zgaruvchilarini belgilang; HTTPS talab qilinadi. `collectstatic` bajaring va ishlab chiqarish WSGI serveridan foydalaning.

## Mobil API

API bazasi: `/api/v1/`. Brauzerda ko‘rish va sinash: `/api/docs/`; OpenAPI JSON: `/api/schema/`. Token bilan kirish, katalog va qoldiqlar, mijozlar, hujjatlar, to‘lovlar, xarajatlar, JSON/Excel hisobotlari mavjud. Rol ruxsatlari tekshiriladi, sotuv/qaytarish so‘rovlarida UUID orqali takroriy yozuvdan himoya bor. Endpointlar, JSON misollar va mobil integratsiya yo‘riqnomasi: [docs/MOBILE_API.md](docs/MOBILE_API.md).

## Railway’ga joylash

`Dockerfile` Python 3.13, Gunicorn va WhiteNoise bilan ilovani ishga tushiradi. `railway.json` deploydan oldin migratsiyalar va `setup_crm` ni bajaradi. `python -m config.start` serverni ochishdan oldin migratsiyalar va rollarni yana tekshiradi; xato bo‘lsa server ochilmaydi. Bu API yangilanishidagi yangi ustunlar qo‘llanmay qolib, logindan so‘ng 500 chiqishining oldini oladi. Mavjud baza o‘chirilmaydi. Statik fayllar Docker build vaqtida yig‘iladi. Ilova Railway bergan `PORT` ni tinglaydi; `/health/` ma’lumotlar bazasi ulanishini tekshiradi.

1. Deploy fayllarini GitHub’ga push qiling.
2. Railway’da `New Project → Deploy from GitHub repo` orqali `qurilishmollari/CRM-qurilish-mollari` va `main` tarmog‘ini tanlang.
3. Shu loyihaga PostgreSQL servisini qo‘shing.
4. Django servisi `Variables` bo‘limida `DJANGO_DEBUG=0`, kamida 50 belgili tasodifiy `DJANGO_SECRET_KEY`, `DATABASE_URL=${{Postgres.DATABASE_URL}}` belgilang. PostgreSQL servisining nomi boshqa bo‘lsa, reference nomini moslang.
5. Deploy qiling, `Networking → Generate Domain` orqali domen yarating. Railway domeni va CSRF manzili avtomatik ruxsatga qo‘shiladi. Custom domen bo‘lsa `DJANGO_ALLOWED_HOSTS` va `DJANGO_CSRF_TRUSTED_ORIGINS` ni moslang.

`DJANGO_CSRF_TRUSTED_ORIGINS` qiymatiga oddiy domen yozilsa, tizim `https://` ni avtomatik qo‘shadi. Masalan `crm-qurilish-mollari-production.up.railway.app` → `https://crm-qurilish-mollari-production.up.railway.app`. To‘liq `http://` yoki `https://` manzillar saqlanadi; ortiqcha bo‘shliqlar, oxirgi `/` va takrorlar tozalanadi. Yo‘l, login/parol yoki query kiritish qabul qilinmaydi. CSRF tekshiruvi o‘chirilmaydi.
6. Railway servisi terminalida bir marta `python manage.py createsuperuser` bajaring. Kerak bo‘lsa `python manage.py seed_products` bilan boshlang‘ich katalogni qo‘shing. Xodimlarni admin panelidan yarating.

`admin` va `sotuvchi` hisoblarini birgalikda sozlash uchun `python manage.py setup_accounts --password PAROL` bor. Railway’da terminal bo‘lmasa, Django servisiga `CRM_SETUP_ACCOUNTS_PASSWORD` muhit o‘zgaruvchisini qo‘shib deploy qiling: shu parol bilan ikkala hisob yaratiladi/yangilanadi. Muvaffaqiyatli sozlangach o‘zgaruvchini o‘chiring, aks holda keyingi restartlarda ham bu parol qo‘llanadi. Sotuvchiga faqat `Sotuvchi` guruhi beriladi. Parol o‘zgartirilsa avvalgi mobil tokenlar bekor qilinadi. O‘zgaruvchi berilmagan odatiy deploy hisob/parollarni o‘zgartirmaydi.

Mahalliy `db.sqlite3`, loginlar, narxlar va savdo yozuvlari Docker/GitHub orqali ko‘chirilmaydi: PostgreSQL yangi baza bo‘ladi. Mavjud biznes ma’lumotlarini ko‘chirish kerak bo‘lsa alohida eksport/import qiling. Serverda `admin/123` kabi boshlang‘ich hisob avtomatik yaratilmaydi.

Mahalliy Docker yoki Railway buildi tarmoq va bog‘liqliklar o‘rnatilishini talab qiladi. `DJANGO_DEBUG=0` bo‘lsa `DATABASE_URL` va `DJANGO_SECRET_KEY` shart; SQLite production uchun avtomatik tanlanmaydi. `.env.example` faqat sozlamalar namunasi, Django uni o‘zi o‘qimaydi.

## Tekshirish

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
```

Sinovlar xarid/sotuv/to‘lov, yetarli bo‘lmagan qoldiq, qayta tasdiqlash, ko‘chirish, qaytarish limiti, sahifalar, ruxsatlar va xato hujjatning to‘liq bekor qilinishini qamrab oladi.
