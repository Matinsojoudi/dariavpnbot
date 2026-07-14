from telebot.types import ReplyKeyboardMarkup
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from env import settings

back_markup = ReplyKeyboardMarkup(resize_keyboard=True)
back_markup.row("برگشت 🔙")

super_admin_markup = ReplyKeyboardMarkup(resize_keyboard=True)
super_admin_markup.row("📢 پیام همگانی", "📊 آمار ربات")
super_admin_markup.row("👤 تنظیم فروشنده", "👥 تنظیم گروه رسیدها")
super_admin_markup.row("📶 مدیریت حجم فروشنده", "📦 مدیریت بسته‌های حجمی")
super_admin_markup.row("⚙️ تنظیمات پنل X-UI", "🛠 مدیریت سرویس‌ها (X-UI)")
super_admin_markup.row("➕ افزودن کانال", "🗑️ حذف کانال")
super_admin_markup.row("➕ افزودن ادمین", "❌ حذف ادمین")
super_admin_markup.row("⚙️ تنظیمات پروکسی ساکس", "💳 تنظیمات پرداخت")
super_admin_markup.row("ورود به پنل فروشنده 🛒")

def get_seller_markup(chat_id=None):
    from env import settings
    import sqlite3
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("⚙️ تنظیمات پرداخت و فیش", "🛠 تنظیمات پروفایل من")
    markup.row("📦 مدیریت بسته‌های من", "📊 آمار فروش و درآمد")
    markup.row("➕ ساخت کانفیگ دستی", "📋 کانفیگ‌های دستی من")
    security_mode = '0'
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM bot_settings WHERE key = 'SECURITY_MODE'")
            row = c.fetchone()
            if row and row[0]:
                security_mode = row[0]
    except:
        pass
        
    markup.row("🔄 تمدید / خرید ترافیک")
    if security_mode == '1':
        markup.row("🛡️ حالت امنیت: فعال", "✉️ ایجاد لینک دعوت")
    else:
        markup.row("🛡️ حالت امنیت: غیرفعال")
    markup.row("ورود به پنل خریدار 👤")
    
    is_admin = False
    if chat_id is not None:
        try:
            if int(chat_id) in settings.admin_list:
                is_admin = True
            else:
                with sqlite3.connect(settings.database) as conn:
                    c = conn.cursor()
                    c.execute("SELECT admin_id FROM admin_list WHERE admin_id = ?", (int(chat_id),))
                    if c.fetchone():
                        is_admin = True
        except:
            pass
            
    if is_admin:
        markup.row("برگشت به پنل سوپر ادمین 🔙")
    return markup

seller_markup = get_seller_markup()


customer_markup = ReplyKeyboardMarkup(resize_keyboard=True)
customer_markup.row("🛒 خرید سرویس (VPN)")
customer_markup.row("📦 سرویس‌های من", "👤 پروفایل کاربری")
customer_markup.row("💰 شارژ کیف پول", "📚 راهنمای استفاده")
customer_markup.row("🌐 ارتباط با ما", "☎️ پشتیبانی")

connect_with_us_markup = InlineKeyboardMarkup()
connect_with_us_markup.add(InlineKeyboardButton("📸 اینستاگرام ما", url="https://www.instagram.com/YourVpnStore"))
connect_with_us_markup.add(InlineKeyboardButton("🌟 کانال فروشگاه", url="https://t.me/YourVpnStore"))
connect_with_us_markup.add(InlineKeyboardButton("🛎️ پشتیبانی مجموعه", url="https://t.me/YourSupportID"))

connect_poshtibani_markup = InlineKeyboardMarkup()
connect_poshtibani_markup.add(InlineKeyboardButton("🛎️ پشتیبانی مجموعه", url="https://t.me/YourSupportID"))

def get_customer_markup(chat_id=None):
    if chat_id is None:
        return customer_markup
        
    import sqlite3
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT role FROM users WHERE user_id = ?", (chat_id,))
            row = c.fetchone()
            if row and row[0] == "seller":
                customer_seller_markup = ReplyKeyboardMarkup(resize_keyboard=True)
                customer_seller_markup.row("🛒 خرید سرویس (VPN)")
                customer_seller_markup.row("📦 سرویس‌های من", "👤 پروفایل کاربری")
                customer_seller_markup.row("💰 شارژ کیف پول", "📚 راهنمای استفاده")
                customer_seller_markup.row("🌐 ارتباط با ما", "☎️ پشتیبانی")
                customer_seller_markup.row("برگشت به پنل فروشنده 🔙")
                return customer_seller_markup
    except Exception as e:
        pass
    
    return customer_markup
