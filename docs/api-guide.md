# راهنمای کامل API — تلنتیک (Talentick)

این سند تمام endpoint های بک‌اند (FastAPI) رو به زبان ساده توضیح می‌ده: کجاست، چه کسی مجاز به صداکردنشه، چی می‌فرسته، چی برمی‌گردونه و چه نکاتی داره.

> Swagger زنده و همیشه به‌روز هم در دسترسه: `/api/docs` (Redoc: `/api/redoc`, JSON schema خام: `/api/openapi.json`). این سند مکمل آن‌هاست — همون داده‌ها رو با توضیح فارسی و نکات کاربردی جمع کرده.

---

## فهرست مطالب

1. [کلیات (Base URL، احراز هویت، نقش‌ها، خطاها، صفحه‌بندی)](#کلیات)
2. [احراز هویت — `/api/auth`](#احراز-هویت)
3. [سازمان‌ها — `/api/orgs`](#سازمانها)
4. [کاربران — `/api/users`](#کاربران)
5. [واحدهای سازمانی — `/api/departments`](#واحدهای-سازمانی)
6. [سمت‌ها — `/api/positions`](#سمتها)
7. [محتوا (دوره/مقاله/پادکست/کتاب) — `/api/contents`](#محتوا)
8. [کتابخانه اسناد — `/api/documents`](#کتابخانه-اسناد)
9. [آزمون‌ها — `/api/quizzes`](#آزمونها)
10. [اطلاعیه‌ها — `/api/announcements`](#اطلاعیهها)
11. [گالری‌ها — `/api/galleries`](#گالریها)
12. [آنبوردینگ / مسیر آشنایی سازمانی — `/api/onboarding`](#آنبوردینگ)
13. [آنبوردینگ کارمند جدید — `/api/employee-onboarding`](#آنبوردینگ-کارمند-جدید)
14. [تیکت‌ها (پنل مدیریت) — `/api/tickets`](#تیکتها-پنل-مدیریت)
15. [امتیازات (پنل مدیریت) — `/api/points`](#امتیازات-پنل-مدیریت)
16. [جایزه‌ها (پنل مدیریت) — `/api/rewards`](#جایزهها-پنل-مدیریت)
17. [درخواست‌های تبدیل امتیاز (پنل مدیریت) — `/api/redemptions`](#درخواستهای-تبدیل-امتیاز-پنل-مدیریت)
18. [داشبورد و گزارش‌ها — `/api/dashboard` و `/api/reports`](#داشبورد-و-گزارشها)
19. [فایل‌ها — `/api/files`](#فایلها)
20. [پرتال کاربر عادی «من» — `/api/me`](#پرتال-من)

---

## کلیات

### Base URL
همه‌ی endpoint ها زیر مسیر `/api/...` هستند. بک‌اند و فرانت روی یک دامنه سرو می‌شن (uvicorn هم API رو جواب می‌ده هم فایل‌های استاتیک فرانت رو)، پس معمولاً کافیه از مسیر نسبی استفاده کنید، مثل:

```js
fetch('/api/me/contents')
```

### احراز هویت (Authentication)
بعد از لاگین (`POST /api/auth/login`) یک `access_token` و `refresh_token` می‌گیرید. برای هر درخواست بعدی این هدر رو بفرستید:

```
Authorization: Bearer <access_token>
```

وقتی `access_token` منقضی شد (401 می‌گیرید)، با `refresh_token` یک جفت توکن جدید بگیرید (`POST /api/auth/refresh`) — نکته: refresh هم **rotate** می‌شه، یعنی هر بار refresh_token قبلی باطل می‌شه و باید همیشه آخرین refresh_token رو ذخیره کنید.

### سه «گیت» که روی تقریباً همه endpoint ها به‌صورت خودکار اعمال می‌شن
فرانت باید این سه حالت رو همیشه هندل کنه، چون هر API‌ای (نه فقط login) ممکنه این‌ها رو برگردونه:

| کد | یعنی چی | فرانت چیکار کنه |
|---|---|---|
| `401` | توکن نامعتبر/منقضیه | با refresh_token تلاش کن؛ اگه اون هم fail شد → کاربر رو به صفحه‌ی ورود بفرست |
| `428` | ادمین رمز کاربر رو ست کرده و کاربر هنوز عوضش نکرده | کاربر رو مجبور به صفحه‌ی «تغییر رمز» کن — تا وقتی این کار نشه، همه‌ی API ها (به‌جز `/api/auth/me`, `/api/auth/logout`, `/api/auth/change-password`) همین خطا رو می‌دن |
| `403` با بدنه‌ی `{"code": "employee_onboarding_required", "message": "..."}` | کاربر باید اول «فرآیند ورود کارمند جدید» (Employee Onboarding) رو تموم کنه | کاربر رو به صفحه‌ی «مسیر ورود من» هدایت کن. این خطا رو با `error.detail.code` تشخیص بده، نه با پارس‌کردن متن فارسی |

مسیرهایی که از گیت سوم معافن (همیشه در دسترسن حتی اگه کاربر مسدود باشه): `/api/auth/*`, `/api/me/onboarding*`, `/api/employee-onboarding/me/*`, `/api/files/*`.

### نقش‌ها (Role Hierarchy)
هر نقش شامل دسترسی‌های نقش‌های پایین‌تر هم هست:

```
super_admin (100)  >  org_admin (50)  >  manager (30)  >  employee (10)
```

- **super_admin**: مدیر پلتفرم — به همه‌ی سازمان‌ها دسترسی داره، فقط اون می‌تونه سازمان بسازه/حذف کنه، محتوای Public بسازه، قوانین امتیازدهی سراسری رو تنظیم کنه.
- **org_admin**: مدیر یک سازمان — CRUD کامل روی محتوا/کاربران/تنظیمات همون سازمان.
- **manager**: دسترسی گزارش‌گیری/مشاهده‌ی تیم (کاربران، واحدها، سمت‌ها) اما نه ساخت محتوای مدیریتی.
- **employee**: کاربر عادی — فقط پرتال شخصی (`/api/me/...`).

قانون Tenant Isolation: هر نقش به‌جز `super_admin` فقط به داده‌های سازمان خودش دسترسی داره؛ تلاش برای دسترسی به سازمان دیگه → `403`.

### فرمت خطاها
FastAPI استاندارد:
```json
{ "detail": "پیام خطا به فارسی" }
```
یا برای خطای اعتبارسنجی (`422`):
```json
{ "detail": [ { "loc": [...], "msg": "...", "type": "..." } ] }
```
استثنا: خطای گیت آنبوردینگ (`403`) که در بالا گفته شد، `detail` یک آبجکت با `code` هست نه رشته.

نکته: در بیشتر جاها اگه چیزی «پیدا نشه یا متعلق به سازمان دیگه‌ای باشه» به‌جای `403`، همون `404 "یافت نشد"` برمی‌گرده (که وجود رکورد رو لو نده) — پس روی کد `404` هم منطق «آیتم پیدا نشد / دسترسی نداری» رو یکسان هندل کنید.

### الگوی صفحه‌بندی (Pagination) — در همه‌ی لیست‌ها یکسانه
Query params: `page` (پیش‌فرض ۱)، `page_size` (پیش‌فرض معمولاً ۲۰، حداکثر ۱۰۰).
Response:
```json
{
  "items": [ ... ],
  "total": 137,
  "page": 1,
  "page_size": 20,
  "total_pages": 7
}
```

### آپلود فایل — دو الگوی متفاوت در پروژه
1. **آپلود مستقیم (multipart از طریق خود API)**: فرم `multipart/form-data` با فیلد `file` به یک endpoint مثل `POST /api/contents/{id}/cover` یا `POST /api/documents/upload` می‌فرستید؛ جواب یک `url` هست.
2. **Presigned URL (فقط برای فایل‌های حجیم مثل ویدیوی محتوا)**: اول `POST /api/contents/upload` رو با نام فایل صدا می‌زنید، یک `upload_url` (لینک مستقیم به MinIO) می‌گیرید و خود فرانت مستقیماً با `PUT` فایل رو اونجا آپلود می‌کنه (بدون رد شدن از سرور اپ) — بعد `url` برگشتی رو (نه upload_url رو) در فرم محتوا ذخیره می‌کنید.

⚠️ هیچ‌کدوم از این‌ها لینک عمومی و همیشگی MinIO برنمی‌گردونن — همه‌ی فایل‌ها (کاور، ویدیو، PDF، آواتار...) فقط از طریق `GET /api/files/{object_path}` (نیازمند توکن) قابل مشاهده‌ن. جزئیات در [بخش ۱۹](#فایلها).

---

## احراز هویت
**پیشوند:** `/api/auth`

| متد و مسیر | دسترسی | کار |
|---|---|---|
| `POST /api/auth/login` | عمومی | ورود با شماره‌موبایل/ایمیل + رمز |
| `POST /api/auth/refresh` | عمومی (با refresh_token) | گرفتن توکن جدید |
| `POST /api/auth/change-password` | لاگین‌شده | تغییر رمز خودم (با دونستن رمز فعلی) |
| `POST /api/auth/logout` | لاگین‌شده | خروج از یک یا همه‌ی session ها |
| `GET /api/auth/me` | لاگین‌شده | پروفایل کامل خودم |
| `POST /api/auth/forgot-password` | عمومی | درخواست کد OTP پیامکی |
| `POST /api/auth/reset-password` | عمومی (با کد OTP) | تعیین رمز جدید با کد و ورود خودکار |
| `POST /api/auth/welcome-complete` | لاگین‌شده | علامت‌زدن ۳ اسلاید خوش‌آمدگویی به‌عنوان دیده‌شده |

### `POST /api/auth/login`
فرم `application/x-www-form-urlencoded` (نه JSON — استاندارد OAuth2):
- `username` (رشته، الزامی) — شماره موبایل یا ایمیل
- `password` (رشته، الزامی)

خروجی (`TokenResponse`):
```json
{
  "access_token": "...", "refresh_token": "...", "token_type": "bearer",
  "expires_in": 3600,
  "user_id": "...", "org_id": "..." /* یا null برای کاربر General */,
  "role": "employee", "full_name": "...",
  "must_change_password": false, "has_seen_welcome": true
}
```
نکات: محدودیت ۵ تلاش هر ۵ دقیقه (روی IP+شناسه) → بعدش `429`. پیام خطای رمز/کاربر اشتباه یکسانه (برای جلوگیری از حدس‌زدن شماره‌های معتبر).

### `POST /api/auth/refresh`
Body: `{ "refresh_token": "..." }` → خروجی مثل login. refresh_token قبلی بلافاصله باطل می‌شه (rotation).

### `POST /api/auth/change-password`
Body: `{ "current_password": "...", "new_password": "..." }` (حداقل ۸ کاراکتر) → خروجی: جفت توکن جدید (نیازی به لاگین مجدد نیست). همه‌ی session های دیگه باطل می‌شن. `400` اگه رمز فعلی اشتباه باشه.

### `POST /api/auth/logout`
Body اختیاری: `{ "refresh_token": "..." }` — اگه بفرستید فقط همون session خارج می‌شه، اگه خالی/نده همه‌ی device ها خارج می‌شن. خروجی: `204`.

### `GET /api/auth/me`
بدون ورودی. خروجی (`MeResponse`):
```json
{
  "id": "...", "org_id": "...", "org_name": "...",
  "email": "...", "full_name": "...", "role": "employee",
  "is_active": true, "avatar_url": null,
  "phone": "09...", "department": "فروش", "position": "کارشناس",
  "last_login_at": "...", "must_change_password": false, "has_seen_welcome": true
}
```

### `POST /api/auth/forgot-password`
Body: `{ "phone": "09..." }` → `{ "message": "...", "expires_in_seconds": 120 }` — جواب همیشه یکسانه چه شماره وجود داشته باشه چه نه.

### `POST /api/auth/reset-password`
Body: `{ "phone": "09...", "code": "1234", "new_password": "..." }` → مثل login، ورود خودکار با توکن جدید. `400` اگه کد اشتباه/منقضی/تعداد تلاش زیاد باشه.

### `POST /api/auth/welcome-complete`
بدون بدنه → `204`. فقط یک flag نمایشی‌ه، بلاک‌کننده نیست.

---

## سازمان‌ها
**پیشوند:** `/api/orgs`

| متد و مسیر | دسترسی | کار |
|---|---|---|
| `GET /api/orgs/me` | org_admin+ | پروفایل سازمان خودم |
| `PATCH /api/orgs/me` | org_admin+ | ویرایش پروفایل سازمان خودم |
| `GET /api/orgs/` | super_admin | لیست همه‌ی سازمان‌ها |
| `POST /api/orgs/` | super_admin | ساخت سازمان جدید |
| `GET /api/orgs/{org_id}` | super_admin | جزئیات یک سازمان |
| `PATCH /api/orgs/{org_id}` | super_admin | ویرایش هر سازمان (شامل فعال/غیرفعال کردن) |
| `DELETE /api/orgs/{org_id}` | super_admin | ⚠️ حذف کامل و برگشت‌ناپذیر سازمان |

فیلدهای `OrganizationResponse`: `id, slug, name, name_en, logo_url, description, mission, vision, values, culture, history, website, phone, address, employee_count, plan, is_active, created_at`.

نکات:
- `POST /` نیاز به `name` و `slug` (باید یکتا باشه در کل پلتفرم) داره؛ بقیه‌ی فیلدها اختیاری.
- توی `PATCH /api/orgs/me` فیلد `is_active` نادیده گرفته می‌شه — org_admin نمی‌تونه سازمان خودش رو غیرفعال کنه؛ این کار فقط از طریق `PATCH /api/orgs/{id}` توسط super_admin ممکنه.
- `DELETE` **مخرب و بی‌بازگشته** — همه‌ی کاربران/واحدها/سمت‌ها/محتوای اون سازمان هم پاک می‌شن. حتماً یک تأییدیه‌ی دو-مرحله‌ای (مثلاً تایپ نام سازمان) توی UI بذارید.

---

## کاربران
**پیشوند:** `/api/users`

| متد و مسیر | دسترسی | کار |
|---|---|---|
| `GET /api/users/me` | هر کاربر فعال | پروفایل خودم (نسخه‌ی مدیریتی، شبیه `/api/auth/me`) |
| `GET /api/users/all` | فقط super_admin | لیست کاربران کل پلتفرم (همه‌ی سازمان‌ها) |
| `GET /api/users/` | manager+ | لیست کاربران سازمان خودم |
| `GET /api/users/template` | org_admin+ | دانلود فایل نمونه‌ی اکسل برای Import |
| `GET /api/users/export` | manager+ | خروجی اکسل کاربران فیلترشده |
| `POST /api/users/import` | org_admin+ | Import گروهی کاربران از اکسل |
| `GET /api/users/{id}` | manager+ | جزئیات یک کاربر |
| `POST /api/users/` | org_admin+ | ساخت کاربر جدید |
| `PATCH /api/users/{id}` | manager+ | ویرایش کاربر |
| `DELETE /api/users/{id}` | manager+ | غیرفعال‌کردن (soft-delete) |
| `PATCH /api/users/{id}/toggle-active` | manager+ | فعال/غیرفعال toggle (برای بازگردوندن حذف‌شده هم همینه) |
| `POST /api/users/{id}/reset-password` | manager+ | ادمین رمز کاربر رو ریست می‌کنه |

### `GET /api/users/` و `/all`
Query: `page, per_page, search, role, org_id, dept_id, position_id, is_active`.
نکته مهم: `is_active` پیش‌فرض فقط کاربرهای فعال رو نشون می‌ده — برای دیدن کاربرهای غیرفعال/حذف‌شده باید صریحاً `is_active=false` بفرستید.
`org_id` فقط برای super_admin معنی داره؛ برای بقیه نادیده گرفته می‌شه (همیشه org خودشونه).

خروجی هر آیتم (`UserListItem`): `id, full_name, email, phone, role, department, position, org_id, org_name, is_active, created_at`.

### `POST /api/users/`
Body (`UserCreateRequest`):
```json
{
  "phone": "09121234567",        // الزامی — همون شناسه ورود
  "email": "a@b.com",            // اختیاری
  "full_name": "علی محمدی",       // الزامی
  "role": "employee",            // super_admin|org_admin|manager|employee — پیش‌فرض employee
  "org_id": "...",               // اختیاری (فقط super_admin می‌تونه هر org یا null=General بده)
  "password": "...",             // الزامی، حداقل ۸ کاراکتر
  "dept_id": "...", "position_id": "...", "manager_id": "...",  // اختیاری
  "employee_onboarding_program_id": "..."  // اختیاری — با ثبتش کاربر خودکار توی اون مسیر Employee Onboarding enroll می‌شه
}
```
نکات دسترسی:
- `org_admin` فقط می‌تونه توی سازمان خودش و فقط نقش‌های *پایین‌تر* از خودش بسازه (manager/employee — نه org_admin/super_admin) وگرنه `403`.
- `super_admin` می‌تونه هر نقشی و هر سازمانی (یا `org_id=null` برای کاربر General) بسازه.
- `dept_id/position_id/manager_id` باید متعلق به همون سازمان باشن وگرنه `400`.
- تکراری‌بودن ایمیل یا موبایل → `400`.

### `PATCH /api/users/{id}`
همون فیلدهای بالا اما همه اختیاری. نکته‌ی مهم UI: برای **پاک‌کردن** `dept_id`/`position_id`/`manager_id` باید رشته‌ی خالی `""` بفرستید — نفرستادن فیلد یعنی «بدون تغییر»، نه پاک‌کردن. فقط super_admin می‌تونه `org_id` رو عوض کنه.

### `DELETE /api/users/{id}` در مقابل `toggle-active`
هر دو در واقع soft-delete هستن (چیزی واقعاً از دیتابیس پاک نمی‌شه، تاریخچه‌ی یادگیری/آنبوردینگ حفظ می‌مونه). `DELETE` مستقیم `is_active=false` می‌کنه؛ `toggle-active` بین true/false سوییچ می‌کنه (برای فعال‌کردن دوباره از همین استفاده کنید). نمی‌شه حساب خودتون رو حذف/غیرفعال کنید (`400`).

### `POST /api/users/{id}/reset-password`
بدون بدنه. خروجی: `{ "user_id": "...", "temp_password": "Xk92#pQ1", "message": "..." }`. **این رمز فقط همین یک‌بار نشون داده می‌شه** — سیستم ایمیل/پیامک نداره، ادمین باید دستی به کاربر برسونه. بعدش کاربر با همون رمز باید لاگین کنه و بلافاصله flag `must_change_password=true` مجبورش می‌کنه رمزش رو عوض کنه (گیت ۴۲۸ بالا).

### Import/Export اکسل
`GET /template` یک اکسل نمونه با ستون‌های درست می‌ده. `POST /import` همون فرمت رو با `multipart file` می‌گیره + query `org_id` (الزامی برای super_admin) و `update_existing` (پیش‌فرض false — یعنی کاربر تکراری skip می‌شه، با true آپدیت می‌شه). خروجی شامل `errors[]` (ردیف‌های خطادار) و `created_users[]` با `temp_password` هرکدوم — این‌ها هم فقط همین یک‌بار نشون داده می‌شن.

---

## واحدهای سازمانی
**پیشوند:** `/api/departments` — دسترسی همه‌جا: manager+ (با محدودیت به سازمان خودش)

| متد و مسیر | کار |
|---|---|
| `GET /api/departments/` | لیست ساده (flat) |
| `GET /api/departments/tree` | ساختار درختی (چارت سازمانی) |
| `POST /api/departments/` | ساخت واحد جدید |
| `GET /api/departments/{id}` | جزئیات |
| `PATCH /api/departments/{id}` | ویرایش |
| `DELETE /api/departments/{id}` | حذف |

`DepartmentTreeNode` بازگشتی: `{ id, name, manager_name, user_count, is_active, children: [...] }` — مستقیم برای رندر چارت سازمانی قابل استفاده‌ست.

`DepartmentCreate/Update`: `name (۲-۲۵۵ کاراکتر)، description، parent_id، manager_id، order_index، is_active`. `parent_id` نباید خود واحد یا واحدی از سازمان دیگه باشه (`400`).

نکته: با حذف یک واحد، زیرواحدها و کاربرانی که بهش وصل بودن پاک نمی‌شن — فقط `dept_id`شون خالی (null) می‌شه.

---

## سمت‌ها
**پیشوند:** `/api/positions` — دسترسی همه‌جا: manager+ (با محدودیت به سازمان خودش)

| متد و مسیر | کار |
|---|---|
| `GET /api/positions/` | لیست (فیلتر با `dept_id` اختیاری) |
| `POST /api/positions/` | ساخت سمت جدید |
| `GET /api/positions/template` | دانلود اکسل نمونه |
| `GET /api/positions/export` | خروجی اکسل |
| `POST /api/positions/import` | Import گروهی از اکسل (تطبیق بر اساس نام) |
| `GET /api/positions/{id}` | جزئیات |
| `PATCH /api/positions/{id}` | ویرایش |
| `DELETE /api/positions/{id}` | حذف |

`PositionCreate/Update`: `name، description، dept_id، level (عدد ۱ تا ۸؛ ۱=کارمند ... ۸=مدیرعامل)، is_active`.
`PositionResponse` هم `dept_name` و `user_count` رو محاسبه‌شده برمی‌گردونه.

---

## محتوا
**پیشوند:** `/api/contents` — این بخش **پنل مدیریت** محتواست (دوره/مقاله/پادکست/کتاب). نسخه‌ی کاربر عادی برای *دیدن* محتوا در [بخش «پرتال من»](#محتوای-من) هست.

| متد و مسیر | دسترسی | کار |
|---|---|---|
| `GET /api/contents/` | employee+ | لیست محتوا (با فیلتر/جست‌وجو) |
| `POST /api/contents/` | org_admin+ | ساخت محتوای جدید |
| `GET /api/contents/{id}` | employee+ | جزئیات محتوا + آیتم‌ها |
| `PATCH /api/contents/{id}` | org_admin+ | ویرایش |
| `DELETE /api/contents/{id}` | org_admin+ | حذف |
| `POST /api/contents/upload` | org_admin+ | گرفتن presigned URL (برای فایل حجیم مثل ویدیو) |
| `POST /api/contents/{id}/cover` | org_admin+ | آپلود مستقیم کاور (تصویر) |
| `DELETE /api/contents/{id}/cover` | org_admin+ | حذف کاور |
| `POST /api/contents/{id}/items` | org_admin+ | افزودن آیتم (درس) به محتوا |
| `PATCH /api/contents/items/{item_id}` | org_admin+ | ویرایش آیتم |
| `DELETE /api/contents/items/{item_id}` | org_admin+ | حذف آیتم |

### `GET /api/contents/`
Query: `page, page_size, search, type (course|article|podcast|book), status (draft|published|archived), org_id (فقط super_admin), sort_by, sort_order`.
نکته: کاربر `employee` اگه `status` نده، خودکار محدود به `published` می‌شه؛ org_admin/manager همه‌چیز رو (هر وضعیتی) توی سازمان خودشون می‌بینن.

### `POST /api/contents/` (ساخت)
فیلدهای مهم `ContentCreate`:
```json
{
  "title": "دوره فروش حرفه‌ای",     // الزامی
  "type": "course",                // course|article|podcast|book — الزامی
  "description": "...", "thumbnail_url": "...",
  "author": "...", "instructor_name": "...", "instructor_avatar_url": "...",
  "tags": ["فروش", "مقدماتی"],
  "status": "draft",               // draft|published|archived
  "level": "beginner",
  "total_duration_min": 45,
  "is_featured": false,
  "sequential_progress": false,     // true = آیتم‌ها به‌ترتیب باز می‌شن (قفل ترتیبی)
  "points_override": 50,            // خالی = امتیاز پیش‌فرض سراسری
  "org_id": "...",                  // فقط super_admin
  "is_public": false,               // فقط super_admin — محتوای عمومیِ بدون سازمان
  "targets": [ { "target_type": "department", "target_id": "..." } ]
}
```
`target_type` می‌تونه `department`، `position` یا `user` باشه.

**قانون دیده‌شدن محتوا برای کارمند (خیلی مهم برای UI مدیریت دسترسی):**
- اگه `targets` خالی باشه → محتوا برای کل سازمان قابل دیدنه.
- اگه فقط `target_type=user` دارید → *فقط* همون کاربرهای مشخص‌شده می‌بینن (نه کل سازمان).
- اگه `department` و/یا `position` تارگت دارید → کاربر باید با **همه‌ی** بُعدهایی که ست شده مچ باشه (AND، نه OR)، مگراینکه با `user` هم به‌صورت جداگانه whitelist شده باشه.
- در `PATCH`، فرستادن `targets` یعنی جایگزینی کامل لیست قبلی؛ `targets: []` یعنی پاک‌کردن (بازگشت به «کل سازمان»)؛ نفرستادن فیلد یعنی بدون تغییر.

### آیتم‌های محتوا (`POST/PATCH/DELETE .../items`)
`ContentItemCreate`:
```json
{
  "title": "جلسه اول",
  "type": "video",           // text|video|pdf|image|link|file|quiz_ref
  "body": "...", "media_url": "...",
  "quiz_id": "...",          // فقط وقتی type=quiz_ref
  "duration_min": 12,
  "order_index": 0,          // ترتیب نمایش + مبنای قفل ترتیبی
  "is_free": true,           // نمونه‌ی رایگان/پیش‌نمایش
  "points_override": 10
}
```
نکته: خودِ منطق «قفل بودن آیتم بعدی تا تکمیل قبلی» توی این router پیاده نشده — اونجا فقط تعریف می‌شه (`sequential_progress` روی محتوا + `order_index` روی آیتم‌ها)؛ اجرای واقعی قفل توی سمت کاربر (`/api/me/contents/{id}`) اتفاق می‌افته.

### آپلود کاور و فایل ویدیو
- کاور (عکس کوچیک): مستقیم `POST /api/contents/{id}/cover` با `multipart file` (باید `image/*` باشه).
- فایل حجیم (ویدیو و مشابه): اول `POST /api/contents/upload` با body `{ "filename": "video.mp4" }`، جواب `{ upload_url, url, object_name }` می‌گیرید؛ با `PUT` مستقیم فایل رو به `upload_url` بفرستید (بدون هدر Authorization — این لینک خودش امضاشده و موقته)، بعد `url` رو در `media_url` آیتم ذخیره کنید.

---

## کتابخانه اسناد
**پیشوند:** `/api/documents` — دسترسی همه‌جا: manager+ (پنل مدیریت اسناد/آیین‌نامه‌ها). نسخه‌ی کاربر: [`/api/me/documents`](#سازمان-من-چارت-و-اسناد).

| متد و مسیر | کار |
|---|---|
| `GET /api/documents/categories` | لیست دسته‌بندی‌ها |
| `POST /api/documents/categories` | ساخت دسته‌بندی |
| `PATCH /api/documents/categories/{id}` | ویرایش دسته‌بندی |
| `DELETE /api/documents/categories/{id}` | حذف دسته‌بندی (اسناد داخلش فقط بی‌دسته می‌شن، پاک نمی‌شن) |
| `POST /api/documents/upload` | آپلود مستقیم فایل سند |
| `GET /api/documents/` | لیست کامل اسناد سازمان (بدون فیلتر دسترسی — این پنل مدیریته) |
| `POST /api/documents/` | ثبت رکورد سند (بعد از آپلود فایل) |
| `GET /api/documents/{id}` | جزئیات |
| `PATCH /api/documents/{id}` | ویرایش (شامل `targets`) |
| `DELETE /api/documents/{id}` | حذف |

`DocumentCreate`: `title، description، category_id، file_url (الزامی، از /upload گرفته می‌شه)، file_name، file_size، file_type، is_public (فقط super_admin)، targets`.

**قانون دیده‌شدن سند** ساده‌تر از محتواست — فقط OR (نه AND): اگه `targets` خالی باشه کل سازمان می‌بینه؛ در غیر این‌صورت هر تارگتی که مچ باشه کافیه. `target_type` اینجا `department` یا `role` (یکی از super_admin|org_admin|manager|employee) هست — نه `user`.

---

## آزمون‌ها
**پیشوند:** `/api/quizzes` — دسترسی همه‌جا: org_admin+ (پنل مدیریت/سازنده‌ی آزمون). صفحه‌ی «شرکت در آزمون» برای کاربر عادی در [`/api/me/quizzes`](#آزمونهای-من) هست.

| متد و مسیر | کار |
|---|---|
| `GET /api/quizzes/` | لیست آزمون‌ها |
| `POST /api/quizzes/` | ساخت آزمون (فقط تنظیمات؛ سوال‌ها جدا اضافه می‌شن) |
| `GET /api/quizzes/{id}` | جزئیات **شامل پاسخ صحیح** (این نسخه‌ی ادمینه) |
| `PATCH /api/quizzes/{id}` | ویرایش تنظیمات |
| `DELETE /api/quizzes/{id}` | حذف |
| `POST /api/quizzes/{id}/questions` | افزودن سوال |
| `PATCH /api/quizzes/questions/{qid}` | ویرایش سوال |
| `DELETE /api/quizzes/questions/{qid}` | حذف سوال |
| `GET /api/quizzes/{id}/attempts` | گزارش همه‌ی تلاش‌های کاربران روی این آزمون |

`QuizCreate`: `title، description، pass_score (۰-۱۰۰، پیش‌فرض ۷۰ — درصد قبولی)، time_limit_min (خالی=بدون محدودیت)، shuffle_questions، shuffle_options، is_onboarding، max_attempts (خالی=نامحدود)، points_override، is_public (فقط super_admin)`.

`QuestionCreate`:
```json
{
  "body": "پایتخت ایران کجاست؟",
  "type": "single_choice",   // single_choice|multi_choice|true_false|short_text|single_image_choice
  "explanation": "...",
  "score": 1,
  "order_index": 0,
  "options": [
    { "body": "تهران", "is_correct": true, "order_index": 0 },
    { "body": "شیراز", "is_correct": false, "order_index": 1 }
  ]
}
```
`QuestionOptionCreate` علاوه بر `body`، فیلد اختیاری `image_url` هم دارد — فقط برای `single_image_choice`. مقدارش باید همان `url` برگشتی از `POST /api/quizzes/upload` (multipart، فیلد `file`، عکس؛ `org_id` اختیاری برای super_admin) باشد.

**قوانین اعتبارسنجی سوال (وگرنه `400`):**
- `short_text`: نباید option داشته باشه (نمره‌دهی خودکار نداره — همیشه ۰ می‌گیره، تصحیح دستی هنوز پیاده نشده).
- `single_choice` و `true_false`: باید دقیقاً **۱** گزینه‌ی درست داشته باشن.
- `true_false`: باید دقیقاً **۲** گزینه داشته باشه.
- `multi_choice`: حداقل **۱** گزینه‌ی درست، و همه‌ی انواع چندگزینه‌ای حداقل ۲ گزینه.
- `single_image_choice`: منطقش مثل `single_choice` (دقیقاً **۱** گزینه‌ی درست)، ولی هر گزینه باید `image_url` داشته باشه؛ `body` (کپشن زیر تصویر) اختیاریه.

نکته: `PATCH` سوال، اگه `options` بفرستید کل گزینه‌های قبلی جایگزین می‌شن.

منطق شرکت در آزمون/نمره‌دهی/`max_attempts` توی [`/api/me/quizzes`](#آزمونهای-من) پیاده شده، نه اینجا.

---

## اطلاعیه‌ها
**پیشوند:** `/api/announcements` — دسترسی: org_admin+. بنرهای تک‌عکس/ویدیو که در صفحه‌ی خانه‌ی کارمند نشون داده می‌شن. نسخه‌ی کاربر: [`/api/me/announcements`](#اطلاعیههای-من-صفحه-خانه).

| متد و مسیر | کار |
|---|---|
| `GET /api/announcements/` | لیست |
| `POST /api/announcements/upload` | آپلود عکس/ویدیو (پسوند مجاز: jpg,jpeg,png,webp,gif,mp4,webm,mov) |
| `POST /api/announcements/` | ساخت اطلاعیه (بعد از آپلود) |
| `GET /api/announcements/{id}` | جزئیات |
| `PATCH /api/announcements/{id}` | ویرایش |
| `DELETE /api/announcements/{id}` | حذف |

`AnnouncementCreate`: `title، description، media_url (الزامی)، media_type (image|video، الزامی)، starts_at/ends_at (بازه‌ی نمایش، اختیاری)، is_active، targets` — قانون دیده‌شدنش دقیقاً مثل اسناد (OR روی `department`/`role`). بازه‌ی `starts_at`/`ends_at` هم فقط توی نمای کاربر عادی چک می‌شه.

---

## گالری‌ها
**پیشوند:** `/api/galleries` — دسترسی: org_admin+. مجموعه‌عکس (مثل گالری رویدادها).

| متد و مسیر | کار |
|---|---|
| `GET /api/galleries/` | لیست |
| `POST /api/galleries/upload` | آپلود یک عکس (jpg,jpeg,png,webp,gif) |
| `POST /api/galleries/` | ساخت گالری + عکس‌های اولیه |
| `GET /api/galleries/{id}` | جزئیات |
| `PATCH /api/galleries/{id}` | ویرایش (فرستادن `photos` یعنی جایگزینی کامل) |
| `DELETE /api/galleries/{id}` | حذف |

نکته: گالری‌ها هیچ سیستم `targets` ندارن (بر‌خلاف محتوا/سند/اطلاعیه) — یا کلاً برای سازمان نمایانن یا Public، بدون محدودیت واحد/نقش/کاربر خاص.

---

## آنبوردینگ
**پیشوند:** `/api/onboarding` — دسترسی: org_admin+. این پنل «برنامه‌های آشنایی سازمانی» (Learning Journey چندمرحله‌ای) رو مدیریت می‌کنه — هم برنامه‌های یادگیری عمومی (`purpose=learning`) و هم مسیر ورود کارمند جدید (`purpose=employee_onboarding`) از همینجا ساخته می‌شن.

| متد و مسیر | کار |
|---|---|
| `GET /api/onboarding/programs` | لیست برنامه‌ها (فیلتر با `purpose`) |
| `POST /api/onboarding/programs` | ساخت برنامه |
| `GET /api/onboarding/programs/{id}` | جزئیات + مراحل |
| `PATCH /api/onboarding/programs/{id}` | ویرایش برنامه |
| `DELETE /api/onboarding/programs/{id}` | حذف برنامه |
| `POST /api/onboarding/programs/{id}/steps` | افزودن مرحله |
| `PATCH /api/onboarding/steps/{step_id}` | ویرایش مرحله |
| `DELETE /api/onboarding/steps/{step_id}` | حذف مرحله |
| `GET /api/onboarding/programs/{id}/enrollments` | پیگیری پیشرفت کارمندهای ثبت‌نام‌شده |
| `POST /api/onboarding/programs/{id}/enroll` | ثبت‌نام دستی چند کاربر مشخص |

`OnboardingProgramCreate`:
```json
{
  "name": "آشنایی با فروش",
  "purpose": "learning",        // learning | employee_onboarding — بعد از ساخت غیرقابل‌تغییره
  "target_roles": [],           // فقط learning — خالی = همه‌ی نقش‌ها
  "target_dept_id": null,       // فقط learning — خالی = همه‌ی واحدها
  "target_dept_ids": [],        // فقط employee_onboarding — واحدهایی که این آنبوردینگ رو می‌بینن؛ خالی = کل سازمان
  "is_default": false,          // فقط learning — true = هر کارمند جدید با این نقش/واحد خودکار enroll می‌شه
  "deadline_days": 14,          // مهلت تکمیل از لحظه‌ی ثبت‌نام
  "points_override": 100,
  "is_public": false            // فقط super_admin، و employee_onboarding نمی‌تونه public باشه
}
```

`ProgramStepCreate` (هر مرحله):
```json
{
  "title": "معرفی سازمان",
  "type": "content",           // content | quiz | document_upload | custom
  "content_id": "...",         // وقتی type=content
  "quiz_id": "...",            // وقتی type=quiz
  "is_required": true,
  "order_index": 0,
  "points_override": 20
}
```
نکته: مرحله‌ی نوع `document_upload` عملاً از کاتالوگ مدارک ماژول Employee Onboarding میاد (بخش بعد) — این router فقط ساختار کلی برنامه/مرحله رو مدیریت می‌کنه.

`POST /programs/{id}/enroll`: `{ "user_ids": ["...", "..."] }` — برای برنامه‌هایی که `is_default=false` هستن (اون‌ها خودکار enroll می‌شن) یا برای ثبت‌نام مجدد یک نفر خاص.

---

## آنبوردینگ کارمند جدید
**پیشوند:** `/api/employee-onboarding` — این router مکمل بخش قبله، فقط دو چیز رو اضافه می‌کنه که اونجا نیست: **کاتالوگ مدارک** و **مانیتورینگ**. ساخت/ویرایش خود مسیر و مراحلش هنوز از `/api/onboarding/programs?purpose=employee_onboarding` انجام می‌شه.

### بخش مدیریتی (فقط super_admin/org_admin)

| متد و مسیر | کار |
|---|---|
| `GET /api/employee-onboarding/document-types` | کاتالوگ مدارک موردنیاز سازمان |
| `POST /api/employee-onboarding/document-types` | افزودن قلم جدید به کاتالوگ |
| `GET /api/employee-onboarding/document-types/{id}` | جزئیات یک قلم |
| `PATCH /api/employee-onboarding/document-types/{id}` | ویرایش |
| `DELETE /api/employee-onboarding/document-types/{id}` | حذف (اگه قبلاً کسی ثبت کرده باشه → `400`؛ به‌جاش `is_active=false` کنید) |
| `POST /api/employee-onboarding/document-types/upload-template` | آپلود فرم خام (مثلاً فرم افتتاح حساب بانکی، برای دانلود توسط کارمند) |
| `GET /api/employee-onboarding/monitoring` | وضعیت همه‌ی کارمندهای ثبت‌نام‌شده در مسیرهای Employee Onboarding |
| `GET /api/employee-onboarding/monitoring/{user_id}` | وضعیت کامل یک کارمند — همچنین برای بخش «مدارک» توی پروفایل کاربر توی پنل کاربران استفاده می‌شه |

`EmployeeDocumentTypeCreate`: `name، description، input_type (file | text — مثلاً «آپلود عکس کارت ملی» در برابر «شماره حساب بانکی»)، is_required، template_file_url (اختیاری، همون که از upload-template میاد)`.

**دسترسی واحدی (فیلد `target_dept_ids` روی مسیر):** یک مسیر `employee_onboarding` با `target_dept_ids` خالی برای **همه‌ی اعضای سازمان** در `GET /api/me/onboarding` قابل‌مشاهده‌ست (با `enrollment_id: null`, `is_enrolled: false`)؛ با لیست غیرخالی فقط اعضای اون واحدها. دیدن/گذراندن داوطلبانه هرگز کاربر رو از داشبورد قفل نمی‌کنه — **گیت** فقط وقتی فعال می‌شه که کاربر با تیک «کارمند جدید» فرم کاربر به مسیر اختصاص داده شده باشه (enrollment با `is_mandatory=true`). تب «پیشرفت کارکنان» فقط کسانی رو نشون می‌ده که ثبت‌نام واقعی دارن (حداقل یک مرحله رو باز/تکمیل کردن).

### بخش «مسیر ورود من» (هر کاربر فعال — این مسیرها از گیت Employee Onboarding معافن)

| متد و مسیر | کار |
|---|---|
| `GET /api/employee-onboarding/me/status` | وضعیت کامل من: مسیر(های) Employee Onboarding + چک‌لیست مدارک با وضعیت هرکدوم |
| `POST /api/employee-onboarding/me/document-types/{id}/upload-file` | آپلود یک مدرک (فقط برای `input_type=file`) |
| `POST /api/employee-onboarding/me/document-types/{id}/submit-text` | ثبت مقدار متنی یک مدرک (فقط برای `input_type=text`) |

هر دوی این‌ها **تأیید خودکار در همون لحظه** دارن — نیازی به تأیید دستی ادمین نیست. `POST .../upload-file`: `multipart file`. `POST .../submit-text`: body `{ "text_value": "..." }`.

**نکته‌ی مهم برای فرانت:** خودِ *مراحل محتوا/آزمون* داخل مسیر Employee Onboarding (نه مدارک) از همون endpoint های عمومی `/api/me/onboarding/...` (بخش [پرتال من](#آنبوردینگ-من)) دیده/تکمیل می‌شن — چون موتور مشترکیه با مسیرهای یادگیری معمولی. یعنی صفحه‌ی «ورود کارمند جدید» شما احتمالاً باید هم `GET /api/employee-onboarding/me/status` (برای چک‌لیست مدارک) رو صدا بزنه، هم `GET /api/me/onboarding` (برای مراحل محتوا/آزمون همون مسیر).

---

## تیکت‌ها (پنل مدیریت)
**پیشوند:** `/api/tickets` — این پنل صف بررسی تیکت‌های سازمانه (برای مدیر/پشتیبانی)، نه تیکت‌های خودِ کاربر (اون در [`/api/me/tickets`](#تیکتهای-من)).

| متد و مسیر | دسترسی | کار |
|---|---|---|
| `GET /api/ticket-categories` | هر کاربر فعال | لیست دسته‌بندی تیکت (برای dropdown) |
| `POST /api/ticket-categories` | super_admin | ساخت دسته‌بندی |
| `PATCH /api/ticket-categories/{id}` | super_admin | ویرایش |
| `DELETE /api/ticket-categories/{id}` | super_admin | حذف |
| `GET /api/tickets/access-grants` | super_admin | چه کسانی (غیر از org_admin) به تیکت‌های یک سازمان دسترسی دارن |
| `POST /api/tickets/access-grants` | super_admin | دادن دسترسی تیکت به یک نقش یا کاربر خاص |
| `DELETE /api/tickets/access-grants/{id}` | super_admin | لغو دسترسی |
| `GET /api/tickets` | هر کاربر فعال (با شرط دسترسی) | لیست تیکت‌های صف مدیریتی |
| `GET /api/tickets/{id}` | هر کاربر فعال (با شرط دسترسی) | جزئیات تیکت + کل مکالمه |
| `POST /api/tickets/{id}/messages` | هر کاربر فعال (با شرط دسترسی) | پاسخ کارشناس به تیکت |
| `POST /api/tickets/{id}/close` | هر کاربر فعال (با شرط دسترسی) | بستن اجباری تیکت (بدون امتیاز رضایت) |

نکته دسترسی: برای غیر-super_admin باید `org_id` داشته باشه **و** یا خودش `org_admin` سازمانش باشه یا از طریق `access-grants` دسترسی گرفته باشه، وگرنه `403`.

**ماشین وضعیت تیکت:**
```
open  --(اولین پاسخ کارشناس)-->  answered  --(بستن)-->  closed  --(بازکردن مجدد)-->  open
```
پس از `closed`، نمی‌شه پیام جدید فرستاد مگر دوباره باز بشه (reopen سمت کاربره، در `/api/me/tickets/{id}/reopen`).

`POST access-grants`: `{ "org_id": "...", "grant_type": "role"|"user", "role": "manager"|"employee", "user_id": "..." }` (بسته به `grant_type` یکی از `role`/`user_id` لازمه).

---

## امتیازات (پنل مدیریت)
**پیشوند:** `/api/points` — سیستم گیمیفیکیشن؛ دو لایه: «قوانین سراسری» (Event Rules) و «استثناهای دامنه‌دار» (Policy Rules) که با اولویت روی هم override می‌شن.

| متد و مسیر | دسترسی | کار |
|---|---|---|
| `GET /api/points/rules` | super_admin | لیست انواع رویداد امتیازی سراسری |
| `POST /api/points/rules` | super_admin | تعریف نوع رویداد جدید |
| `PATCH /api/points/rules/{id}` | super_admin | ویرایش برچسب/امتیاز/فعال‌بودن |
| `GET /api/points/policy-rules` | super_admin | لیست override های دامنه‌دار (سازمان/واحد/سمت/کاربر) |
| `POST /api/points/policy-rules` | super_admin | افزودن override |
| `PATCH /api/points/policy-rules/{id}` | super_admin | ویرایش override |
| `DELETE /api/points/policy-rules/{id}` | super_admin | حذف override |
| `POST /api/points/manual-transactions` | org_admin+ | امتیاز دستی (پاداش/تشویق/کسر/اصلاح) به یک کاربر |
| `GET /api/points/ledger` | org_admin+ | دفتر تراکنش‌های امتیازی کل سازمان |

`POST /manual-transactions`:
```json
{
  "user_id": "...",
  "transaction_type": "bonus",   // bonus | manual_adjustment | deduction | correction
  "points": 50,                  // همیشه مثبت وارد کنید — برای deduction هم مثبت بدید، خودش منفی می‌کنه
  "description": "پاداش عملکرد ماه"
}
```
نکات: برای `bonus` باید `points > 0` باشه. برای `deduction` هم باید مثبت وارد بشه (سرور خودش منفیش می‌کنه)؛ اگه موجودی کیف‌پول کافی نباشه `400`. همه‌چیز در audit log ثبت می‌شه.

`GET /ledger` هر ردیف: `transaction_number، transaction_type، event_type، points (علامت‌دار)، balance_before، balance_after، description، created_by_name، created_at`.

---

## جایزه‌ها (پنل مدیریت)
**پیشوند:** `/api/rewards` — کاتالوگ جایزه‌هایی که کارمند با امتیاز می‌تونه بگیره.

| متد و مسیر | دسترسی | کار |
|---|---|---|
| `GET /api/rewards` | org_admin+ | لیست جایزه‌ها (پنل مدیریت) |
| `POST /api/rewards` | org_admin+ | ساخت جایزه |
| `PATCH /api/rewards/{id}` | org_admin+ | ویرایش |
| `DELETE /api/rewards/{id}` | org_admin+ | آرشیو (soft — `status=archived` می‌شه، پاک نمی‌شه) |

`RewardCreate`:
```json
{
  "title": "پک هدیه فروشگاهی",
  "category": "gift_card",   // goods|gift_card|cash|course|benefit|special_access|leave|custom
  "cost_points": 500,        // الزامی، >۰
  "inventory_total": 20,     // خالی = نامحدود
  "start_date": "...", "end_date": "...",
  "status": "active"         // draft|active|inactive|archived
}
```
نکته: `org_id=null` یعنی جایزه‌ی سراسری/همه‌ی سازمان‌ها — فقط super_admin می‌تونه این کار رو بکنه؛ org_admin همیشه محدود به سازمان خودشه.

نمای کاربر عادی (فقط جایزه‌های «قابل‌دریافت»، با فیلتر امتیاز/موجودی) در [`/api/me/rewards`](#فروشگاه-جایزه-من) هست.

---

## درخواست‌های تبدیل امتیاز (پنل مدیریت)
**پیشوند:** `/api/redemptions` — صف بررسی درخواست‌های «تبدیل امتیاز به جایزه» که کارمند از `/api/me/redemptions` ثبت کرده.

| متد و مسیر | دسترسی | کار |
|---|---|---|
| `GET /api/redemptions` | org_admin+ | صف درخواست‌های سازمان (drafts نشون داده نمی‌شن) |
| `PATCH /api/redemptions/{id}/under-review` | org_admin+ | شروع بررسی |
| `PATCH /api/redemptions/{id}/approve` | org_admin+ | تأیید — امتیاز واقعاً کسر و موجودی جایزه واقعاً کم می‌شه |
| `PATCH /api/redemptions/{id}/reject` | org_admin+ | رد — هیچ امتیازی کسر نمی‌شه |
| `PATCH /api/redemptions/{id}/deliver` | org_admin+ | ثبت تحویل فیزیکی جایزه (فقط از حالت approved) |

همه‌ی این چهار endpoint یک body اختیاری `{ "admin_note": "..." }` می‌گیرن (به‌جز `deliver` که هیچ ورودی‌ای نداره).

**ماشین وضعیت درخواست تبدیل** (تلاش برای انتقال خارج از این جدول → `400`):
```
draft        → submitted, cancelled
submitted    → under_review, approved, rejected, cancelled
under_review → approved, rejected, cancelled
approved     → delivered
rejected / delivered / cancelled  → نهایی (پایان مسیر)
```
نکته‌های مهم برای UI:
- `approve` تنها لحظه‌ایه که واقعاً امتیاز از کیف‌پول کاربر کم و `inventory_remaining` جایزه کاهش پیدا می‌کنه. اگه موجودی جایزه یا موجودی امتیاز کاربر (که ممکنه از زمان درخواست تغییر کرده باشه) کافی نباشه → `400`، توصیه می‌شه `reject` کنید.
- `submitted`/`under_review` امتیاز رو «رزرو» (pending) می‌کنن ولی هنوز کسر نشده؛ با `reject` یا `cancel` این رزرو آزاد می‌شه بدون تغییر موجودی.
- `draft` و ثبت (`submit`)/لغو (`cancel`) توسط خودِ کارمند در [`/api/me/redemptions`](#درخواستهای-تبدیل-امتیاز-من) انجام می‌شه، نه اینجا.

---

## داشبورد و گزارش‌ها

### `GET /api/dashboard/super-admin`
دسترسی: فقط super_admin. یک بسته‌ی کامل داده برای داشبورد اصلی super admin — بدون ورودی. خروجی شامل:
```json
{
  "stats": { "active_users": 0, "total_orgs": 0, "content": {...}, "completion": {...}, "total_reward_points": 0 },
  "user_growth": [ { "label": "...", "count": 0 } ],   // ۱۲ هفته اخیر
  "top_users": [ { "user_id": "...", "full_name": "...", "quiz_score": 0 } ],
  "recent_tickets": [ { "id": "...", "subject": "...", "status": "...", "rating": 0 } ]
}
```

### گزارش‌ها — پیشوند `/api/reports` (دسترسی همه‌جا: org_admin+، با محدودیت سازمان خودشون)

| متد و مسیر | کار |
|---|---|
| `GET /api/reports/dashboard` | آمار کلی تجمیعی (تعداد محتوا، کاربر واجد شرایط/فعال، نرخ تکمیل، زمان تماشا) |
| `GET /api/reports/contents` | گزارش هر محتوا (فیلتر با واحد/سمت/کاربر/بازه‌ی تاریخ) |
| `GET /api/reports/contents/{id}` | ریز وضعیت هر کاربر روی یک محتوای مشخص |
| `GET /api/reports/organizations` | مقایسه‌ی سازمان‌ها با هم (فقط super_admin کاربردی‌ه) |
| `GET /api/reports/users` | گزارش پیشرفت یادگیری هر کاربر |

Query مشترک: `org_id (فقط super_admin)، dept_id، position_id، user_id، content_id، date_from، date_to` (همه اختیاری، هرکدوم که برای اون endpoint معنی داشته باشه).

---

## فایل‌ها
**پیشوند:** `/api/files` — چون MinIO خصوصیه، **تنها راه** دیدن هر فایل آپلودشده (کاور، PDF، ویدیو، آواتار، لوگو، مدرک...) عبور از این پراکسیه؛ هیچ‌جای دیگه‌ی برنامه لینک مستقیم و همیشگی MinIO برنمی‌گردونه.

| متد و مسیر | کار |
|---|---|
| `GET /api/files/playback-url/{object_path}` | یک لینک موقت (presigned) امضاشده می‌گیرید — از این برای پخش ویدیو استفاده کنید چون Range request (پرش توی ویدیو) رو ساپورت می‌کنه. با query param اختیاری `?download=<filename>` لینک برای دانلود (attachment با همون نام) امضا می‌شه، نه پخش inline — دانلود فایل حجیم (مثل ویدیو) هم باید از همین مسیر انجام بشه، نه از ردیف پایین، چون stream کردن کل فایل از پشت اپ برای فایل بزرگ می‌تونه به ERR_HTTP2_PROTOCOL_ERROR منجر بشه |
| `GET /api/files/{object_path}` | خودِ فایل رو مستقیم stream می‌کنه (fallback — برای عکس/PDF و هرچی نیاز به Range نداره خوبه) |

هر دو نیاز به `Authorization: Bearer` دارن و اگه فایل متعلق به سازمان دیگه‌ای باشه `403` می‌گیرید (به‌جز فایل‌های Public که برای همه آزادن). `object_path` همون چیزیه که در فیلدهایی مثل `thumbnail_url`, `media_url`, `file_url`, `avatar_url` ذخیره شده — یعنی این فیلدها رو مستقیم توی `<img src="">` نذارید، باید یا از `GET /api/files/{path}` عبورشون بدید یا (برای ویدیو) اول `playback-url` رو بگیرید و اون لینک موقت رو به `<video src="">` بدید.

---

## پرتال من
**پیشوند:** `/api/me` — همه‌چیزی که کاربر عادی (هر نقشی، ولی همیشه فقط داده‌های خودش) می‌بینه. برخلاف پنل‌های بالا، اینجا نقش کاربر مهم نیست — «محتواهای من»، «آزمون‌های من» و... برای super_admin هم همینه (چون این صفحات شخصیه، نه پنل مدیریت).

### محتوای من

| متد و مسیر | کار |
|---|---|
| `GET /api/me/contents` | فهرست محتواهای مجاز من (published + طبق قانون دیده‌شدن بالا) + وضعیت پیشرفتم |
| `GET /api/me/contents/{id}` | جزئیات محتوا + همه‌ی آیتم‌ها + کدوم قفله + پیشرفت من |
| `POST /api/me/contents/{id}/start` | ثبت شروع مشاهده (`started_at`) |
| `POST /api/me/contents/{id}/items/{item_id}/progress` | آپدیت پیشرفت یک آیتم مشخص |

هر آیتم توی `GET .../{id}` این‌ها رو داره: `my_status (not_started|in_progress|completed)، my_progress_pct، my_last_position، is_locked`. اگه محتوا `sequential_progress=true` باشه، آیتمی که آیتم قبلیش کامل نشده `is_locked=true` برمی‌گرده — همون‌جا `POST .../progress` هم روش `403` می‌ده.

`POST .../items/{item_id}/progress` body (`ItemProgressUpdate`) بسته به نوع آیتم فرق می‌کنه (مثلاً برای ویدیو `last_position` ثانیه‌ی فعلی، برای متن/PDF شاید فقط `status=completed`) — دقیق‌ترین مرجع فیلدهاش `schemas/progress.py` هست، چون بین انواع آیتم فرق می‌کنه.

### آزمون‌های من

| متد و مسیر | کار |
|---|---|
| `GET /api/me/quizzes/{id}` | سوالات برای شرکت — **بدون** پاسخ صحیح |
| `POST /api/me/quizzes/{id}/attempts` | ثبت پاسخ‌ها → نمره‌دهی خودکار فوری |
| `GET /api/me/quizzes/{id}/attempts` | تاریخچه‌ی تلاش‌های من |
| `GET /api/me/quizzes/{id}/attempts/{attempt_id}` | جزئیات یک تلاش، **این‌بار با** پاسخ صحیح/توضیح |

نکته: اگه آزمون از داخل یک آیتم `quiz_ref` محتوا باز شده، `content_id` و `item_id` رو به‌عنوان query param به هر دو endpoint اول بفرستید — سرور قفل ترتیبی محتوا رو هم چک می‌کنه (اگه آیتم قبلی کامل نشده، `403`).

`POST attempts` می‌تونه `400` بده اگه `max_attempts` پر شده یا `time_limit_min` گذشته باشه. هر attempt یک‌بار برای همیشه ثبت می‌شه، قابل ویرایش نیست.

### سازمان من (چارت و اسناد)

| متد و مسیر | کار |
|---|---|
| `GET /api/me/org` | معرفی سازمان (تاریخچه/ماموریت/چشم‌انداز/ارزش‌ها) |
| `GET /api/me/org-chart` | چارت سازمانی (فقط مشاهده، درختی) |
| `GET /api/me/documents/categories` | دسته‌بندی‌های اسناد قابل‌دیدن من |
| `GET /api/me/documents` | کتابخانه اسناد (طبق قانون دیده‌شدن OR بالا) |

### اطلاعیه‌های من (صفحه خانه)

`GET /api/me/announcements?limit=10` — اطلاعیه‌های فعال، در بازه‌ی نمایش، و طبق دسترسی واحد/نقش، جدیدترین اول.

### آنبوردینگ من

| متد و مسیر | کار |
|---|---|
| `GET /api/me/onboarding` | برنامه‌های آنبوردینگ من — هم اون‌هایی که توش ثبت‌نامم و هم مسیرهای `employee_onboarding` فعالی که طبق واحدم قابل‌مشاهده‌ان ولی هنوز ثبت‌نام نکردم. ترتیب: در حال انجام → ثبت‌نام‌نشده → تکمیل‌شده |
| `GET /api/me/onboarding/programs/{program_id}` | پیش‌مشاهده‌ی یک مسیر `employee_onboarding` که هنوز توش ثبت‌نام نکردم — همه‌ی مراحل با وضعیت `not_started` |
| `GET /api/me/onboarding/{enrollment_id}` | جزئیات یک برنامه + وضعیت من در هر مرحله |
| `POST /api/me/onboarding/steps/{step_id}/complete` | تیک‌زدن یک مرحله به‌عنوان انجام‌شده |
| `POST /api/me/onboarding/steps/{step_id}/skip` | رد کردن یک مرحله‌ی اختیاری (روی مرحله‌ی اجباری `400` می‌ده) |

هر آیتم `GET /api/me/onboarding`: `enrollment_id` (وقتی ثبت‌نام نکردم `null`)، `program_id`، `is_enrolled`، `is_mandatory` (یعنی ثبت‌نام «کارمند جدید» — گیت داره)، `progress_pct`، `steps_total`، `steps_completed`.

**ثبت‌نام تنبل:** فقط دیدن یک مسیر ثبت‌نام نمی‌سازه؛ اما اولین `complete`/`skip` روی یکی از مراحلش یک ثبت‌نام **داوطلبانه** (`is_mandatory=false`) می‌سازه که `enrollment_id` در پاسخ پر می‌شه و از اون پس در «پیشرفت کارکنان» پنل ادمین دیده می‌شه — ولی **هرگز کاربر رو قفل نمی‌کنه**.

هر مرحله در `GET .../{enrollment_id}` و `GET .../programs/{program_id}` این فیلدها رو داره: `type (content|quiz|document_upload|custom)، content_id + content_title (اگه content)، quiz_id + quiz_title (اگه quiz)، status، is_required`. برای مرحله‌ی نوع `content`، فرانت با همون `content_id` می‌ره سراغ `GET /api/me/contents/{content_id}` تا خودِ محتوا رو نشون بده؛ برای `quiz` هم مشابه با `GET /api/me/quizzes/{quiz_id}`.

### تیکت‌های من

| متد و مسیر | کار |
|---|---|
| `POST /api/me/tickets` | ثبت تیکت جدید |
| `GET /api/me/tickets` | لیست تیکت‌های من |
| `GET /api/me/tickets/{id}` | جزئیات + کل مکالمه |
| `POST /api/me/tickets/{id}/messages` | افزودن پیام به تیکت خودم |
| `POST /api/me/tickets/{id}/close` | بستن با امتیاز رضایت |
| `POST /api/me/tickets/{id}/reopen` | بازکردن دوباره‌ی تیکت بسته‌شده |

`POST /me/tickets` body (`TicketCreate`): `subject، body، category_id (اختیاری)، related_content_id (اختیاری — اگه تیکت درباره‌ی یک محتوای خاص باشه)`.
`POST .../close` body: `{ "satisfaction_rating": 1-5 }`.

### امتیازات من

| متد و مسیر | کار |
|---|---|
| `GET /api/me/points/summary` | مجموع امتیاز فعلی من |
| `GET /api/me/points/history` | تاریخچه‌ی تراکنش‌های امتیازی من |
| `GET /api/me/points/wallet` | کیف‌پول کامل (`total_earned، total_spent، total_expired، pending_points، redeemed_points`) |

### فروشگاه جایزه من

`GET /api/me/rewards` — کاتالوگ جایزه‌های *قابل‌دریافت* (فیلتر خودکار روی `status=active` + داخل بازه‌ی تاریخ + موجودی>۰ یا نامحدود)؛ Query: `page, page_size, search, category`.

### درخواست‌های تبدیل امتیاز من

| متد و مسیر | کار |
|---|---|
| `POST /api/me/redemptions` | ثبت درخواست جدید (به‌صورت draft) |
| `GET /api/me/redemptions` | لیست درخواست‌های من |
| `GET /api/me/redemptions/{id}` | جزئیات یک درخواست |
| `PATCH /api/me/redemptions/{id}/submit` | ارسال رسمی درخواست draft (می‌ره توی صف بررسی ادمین) |
| `PATCH /api/me/redemptions/{id}/cancel` | لغو توسط خودم |

`POST /me/redemptions` body: `{ "reward_id": "...", "quantity": 1, "user_note": "..." }`. جریان کامل: کاربر می‌سازه (draft) → `submit` می‌کنه → وارد صف پنل ادمین می‌شه ([بخش ۱۷](#درخواستهای-تبدیل-امتیاز-پنل-مدیریت)) → ادمین `approve`/`reject` می‌کنه.

---

## چند نکته‌ی عملی جمع‌بندی برای فرانت

- **همیشه** `401`، `428` و `403 employee_onboarding_required` رو در یک لایه‌ی مشترک (مثلاً interceptor فچ/axios) هندل کنید، نه در هر صفحه جداگانه — چون هر endpoint‌ای ممکنه این‌ها رو بده.
- برای نمایش هر عکس/ویدیو/فایل، مقدار خام فیلدهایی مثل `thumbnail_url`/`media_url`/`avatar_url` رو مستقیم استفاده نکنید؛ از `GET /api/files/{path}` (یا `playback-url` برای ویدیو) رد بشید.
- فیلدهای `targets` (توی محتوا/سند/اطلاعیه) در `PATCH` رفتار «جایگزینی کامل» دارن: نفرستادن = بدون تغییر، فرستادن `[]` = پاک‌کردن همه.
- برای پاک‌کردن رابطه‌های اختیاری کاربر (`dept_id`, `position_id`, `manager_id`) باید رشته‌ی خالی `""` بفرستید، نه `null` و نه حذف فیلد.
- نقش `manager` به بخش‌های مدیریت محتوا/آزمون/اسناد/آنبوردینگ (که `org_admin+` هستن) دسترسی *نداره* — فقط به بخش‌های کاربران/واحد/سمت/گزارش (که `manager+` هستن). این تمایز رو توی منوی پنل مدیریت رعایت کنید.
