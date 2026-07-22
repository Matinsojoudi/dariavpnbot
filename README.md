# Daria VPN Bot

ربات فروشگاه VPN با سه پنل: **سوپر ادمین**، **فروشنده**، **خریدار**.

پنل فعال: **X-UI (Sanaei)** از طریق `hiddify/client.py` (نام ماژول تاریخی است).

## معماری نقش‌ها

| نقش | خرید از | فروش به |
|-----|---------|---------|
| سوپر ادمین | — | بسته‌های حجمی (GB) به فروشنده |
| فروشنده | ترافیک عمده از سوپر ادمین | پکیج VPN به خریدار |
| خریدار | سرویس VPN از فروشنده | — |

- موجودی فروشنده: `seller_configs.total_bulk_gb` / `used_bulk_gb`
- پکیج‌های عمده: جدول `seller_packages`
- پکیج‌های فروش به مشتری: جدول `packages`
- اتصال مشتری به فروشنده: `users.parent_seller_id` (از `SINGLE_SELLER_ID` یا لینک دعوت)

## راه‌اندازی

### پیش‌نیازها

```bash
cd "/root/VPN Bots/dariavpnbot"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # سپس مقادیر را پر کنید
```

### متغیرهای `.env`

| متغیر | توضیح |
|--------|--------|
| `TOKEN` | توکن ربات از BotFather |
| `BOT_ID` | یوزرنیم ربات |
| `BOT_LINK` | لینک ربات |
| `ADMIN_LIST` | آیدی‌های سوپر ادمین (با کاما) |
| `ADMIN` | آیدی فروشنده پیش‌فرض / ادمین اصلی |
| `MATIN` | آیدی دریافت خطاها |
| `DATABASE` | مسیر فایل SQLite |
| `SOCKS_PROXY` | پروکسی اختیاری تلگرام |

تنظیمات پنل X-UI در جدول `bot_settings` ذخیره می‌شود (از منوی سوپر ادمین → ⚙️ تنظیمات پنل X-UI):
`XUI_PANEL_URL`, `XUI_USERNAME`, `XUI_PASSWORD`, `XUI_INBOUND_ID`, `SUB_BASE_URL`

### پنل X-UI پیش‌فرض سرور (mongol / سنایی)

| کلید | مقدار |
|------|--------|
| `XUI_PANEL_URL` | `https://mongol.62.60.184.127.nip.io/mango_banana_4Ever/` |
| `XUI_USERNAME` | `Matthew` |
| `XUI_INBOUND_ID` | `1` (Germany) |
| `SUB_BASE_URL` | `https://sus.62.60.184.127.nip.io/sus` |

رمز عبور پنل در `/root/x-ui-mongol-install-credentials.txt` روی سرور نگهداری می‌شود.

اعمال/بازنشانی تنظیمات روی دیتابیس:

```bash
python3 "/root/VPN Bots/scripts/apply-xui-panel-settings.py" dariavpnbot.db
```

### اجرا با tmux

```bash
./scripts/start-tmux.sh
# یا:
tmux new-session -d -s dariavpnbot -c "/root/VPN Bots/dariavpnbot"
tmux send-keys -t dariavpnbot 'source venv/bin/activate && python3 main.py' Enter
```

توقف: `./scripts/stop-tmux.sh`

## جریان‌های اصلی

### فروشنده → سوپر ادمین (خرید ترافیک)

1. فروشنده: 🔄 تمدید / خرید ترافیک
2. انتخاب بسته + ارسال فیش
3. سوپر ادمین در گروه/`SELLER_RECEIPT_GROUP` تأیید می‌کند
4. `add_traffic_to_seller` حجم را اضافه می‌کند

### خریدار → فروشنده (خرید VPN)

1. خریدار: 🛒 خرید سرویس
2. پرداخت کیف‌پول یا کارت‌به‌کارت + فیش
3. بررسی ترافیک فروشنده؛ در صورت کمبود → پیام «در حال آپدیت»
4. تأیید فیش فقط توسط **فروشنده مالک** یا **سوپر ادمین**
5. ساخت کاربر روی X-UI + ارسال لینک ساب و QR

## پنل‌ها

### سوپر ادمین

- پیام همگانی، آمار، تنظیم فروشنده تکی، گروه رسیدها
- **📶 مدیریت حجم فروشنده**: افزایش/کاهش دستی حجم `SINGLE_SELLER_ID` + اطلاع‌رسانی به فروشنده
- بسته‌های حجمی، تنظیمات/مدیریت X-UI
- کانال‌ها، ادمین‌ها، پروکسی، تنظیمات پرداخت
- ورود به پنل فروشنده

### فروشنده

- تنظیمات پرداخت و فیش، پروفایل
- مدیریت بسته‌های فروش، آمار درآمد
- ساخت کانفیگ دستی، خرید ترافیک
- حالت امنیت + لینک دعوت یک‌بارمصرف

### خریدار

- خرید سرویس، سرویس‌های من، شارژ کیف پول
- تمدید سرویس (کیف پول / مستقیم)
- پروفایل، راهنما، پشتیبانی

## امنیت و صحت منطق (مهم)

- ورود به پنل فروشنده فقط برای `role=seller` یا سوپر ادمین
- تأیید/رد فیش مشتری فقط برای فروشنده همان رسید یا سوپر ادمین
- کسر ترافیک فروشنده با `deduct_traffic` (نه force)؛ در کمبود ترافیک فیش تأیید نمی‌شود
- در تمدید کیف‌پول اگر کسر ترافیک شکست بخورد، موجودی برمی‌گردد
- لینک دعوت، خریدار را به `seller_id` دعوت‌کننده وصل می‌کند
- ستون `invite_links.used_by` برای حالت امنیت الزامی است

## دیتابیس و migration

`traffic_service.run_migrations()` در استارت اجرا می‌شود و `verify_schema()` صحت را چک می‌کند.

جداول: `users`, `seller_configs`, `packages`, `receipts`, `invite_links`, `admin_list`, `channels`, `block_list`, `uploaded_files_new`, `bot_settings`, `seller_packages`, `admin_wallets`, `charge_doc_channel`

کلیدهای مهم `bot_settings`: `SINGLE_SELLER_ID`, `SELLER_RECEIPT_GROUP`, `SECURITY_MODE`, `SUPER_ADMIN_BANK_CARD`, `PAYMENT_CARD_STATUS`, `PAYMENT_CRYPTO_STATUS`, `XUI_*`, `SUB_BASE_URL`

## ساختار فایل‌ها

```
main.py                 # هسته + پنل سوپر ادمین + استارت
customer.py             # پنل خریدار (خرید/کیف پول/فیش/تمدید)
seller.py               # ورود و تنظیمات فروشنده
seller_packages.py      # CRUD بسته‌های فروش
seller_earnings.py      # آمار درآمد
seller_traffic.py       # خرید ترافیک + تأیید سوپر ادمین
seller_manual_config.py # کانفیگ دستی
traffic_service.py      # ترافیک مشترک + migration
hiddify/client.py       # پل X-UI
buttons.py              # کیبوردها
scripts/test_logic.py   # تست منطق ترافیک/احراز هویت
scripts/start-tmux.sh
scripts/stop-tmux.sh
```

## تست

```bash
source venv/bin/activate
python3 scripts/test_logic.py
```

## چک‌لیست استقرار پس از آپدیت

1. `git pull`
2. `python3 scripts/test_logic.py`
3. ری‌استارت: `./scripts/stop-tmux.sh && ./scripts/start-tmux.sh`
4. در سوپر ادمین: تنظیم X-UI، کارت بانکی، گروه رسید، فروشنده تکی
5. فروشنده: کارت/گروه فیش + ساخت حداقل یک پکیج
6. یک خرید تستی کیف‌پول و یک خرید فیش مستقیم

## تاریخچه رفع باگ‌های منطقی (۲۰۲۶-۰۷)

- رفع نمایش پنل فروشنده در `/start` برای فروشنده تنظیم‌شده و دارای `seller_configs`
- رفع دکمه «تمدید سرویس» در پیام‌های QR (ویرایش caption به‌جای text)
- رفع `database is locked` در ساخت کانفیگ دستی (کسر ترافیک و ثبت receipt در تراکنش‌های جدا)
- گزارش خطای شفاف هنگام شکست ساخت روی پنل X-UI + بازگشت ترافیک
- پنل فروشنده دیگر برای همه کاربران باز نیست
- تأیید فیش بدون احراز هویت بسته شد
- باگ برگشت‌ندادن موجودی در `renew_wallet` هنگام کمبود ترافیک
- دعوت‌نامه فروشنده دعوت‌کننده را به‌عنوان `parent_seller_id` ست می‌کند
- حذف ثبت تکراری handlerهای ترافیک و X-UI
- تعریف `send_welcome` برای لغو تخصیص حجم
- اصلاح شرط fallback پیام «متوجه نشدم»
- دکمه callback `charge_wallet` به جریان شارژ وصل شد
- جلوگیری از تأیید دوبل فیش (atomic update)
- seed اولیه `SINGLE_SELLER_ID` و وضعیت پرداخت در استارت
