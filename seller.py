import sqlite3
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from env import settings
from seller_context import get_effective_seller_id, can_access_seller_panel
import traceback

def register_seller_handlers(bot):

    def _require_seller(chat_id):
        return can_access_seller_panel(chat_id)
    
    @bot.message_handler(func=lambda message: message.text == "ورود به پنل فروشنده 🛒")
    def enter_seller_panel(message):
        chat_id = message.chat.id
        if _require_seller(chat_id):
            from buttons import get_seller_markup
            seller_id = get_effective_seller_id(chat_id)
            note = f"\n👤 فروشنده فعال: <code>{seller_id}</code>" if int(seller_id) != int(chat_id) else ""
            bot.send_message(
                chat_id,
                f"🛒 <b>به پنل فروشندگان خوش آمدید.</b>{note}\nلطفاً از منوی زیر استفاده کنید:",
                reply_markup=get_seller_markup(chat_id),
                parse_mode="HTML",
            )
        else:
            bot.send_message(chat_id, "❌ شما دسترسی فروشنده ندارید.")


    @bot.message_handler(func=lambda message: message.text == "⚙️ تنظیمات پرداخت و فیش")
    def seller_payment_settings(message):
        chat_id = message.chat.id
        if not _require_seller(chat_id):
            bot.send_message(chat_id, "❌ شما دسترسی فروشنده ندارید.")
            return
        
        seller_id = get_effective_seller_id(chat_id)
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT bank_card, crypto_wallet, approval_group_id, active_gateways FROM seller_configs WHERE seller_id = ?", (seller_id,))
            row = c.fetchone()
            
        if not row:
            row = ('تنظیم نشده', 'تنظیم نشده', 'تنظیم نشده', 'card')
            
        card, wallet, group, active = row
        
        msg = f"⚙️ <b>تنظیمات درگاه‌های پرداخت شما:</b>\n"
        if int(seller_id) != int(chat_id):
            msg += f"👤 فروشنده فعال: <code>{seller_id}</code>\n"
        msg += "\n"
        msg += f"💳 شماره کارت: <code>{card}</code>\n"
        msg += f"💰 کیف پول تتر/ترون: <code>{wallet}</code>\n"
        msg += f"👥 آیدی گروه تأیید فیش: <code>{group}</code>\n"
        msg += f"🟢 درگاه فعال فعلی: <code>{active}</code>\n\n"
        msg += "برای ویرایش روی گزینه‌های زیر کلیک کنید:"
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("💳 ویرایش کارت", callback_data="seller_edit_card"), InlineKeyboardButton("💰 ویرایش ولت", callback_data="seller_edit_wallet"))
        markup.row(InlineKeyboardButton("👥 تغییر گروه فیش", callback_data="seller_edit_group"), InlineKeyboardButton("تغییر درگاه فعال 🔄", callback_data="seller_toggle_active"))
        
        bot.send_message(chat_id, msg, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "seller_edit_card")
    def edit_card_start(call):
        msg = bot.send_message(call.message.chat.id, "لطفاً شماره کارت 16 رقمی خود را وارد کنید:")
        bot.register_next_step_handler(msg, save_seller_card, bot)
        bot.answer_callback_query(call.id)
        
    def save_seller_card(message, bot):
        seller_id = get_effective_seller_id(message.chat.id)
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO seller_configs (seller_id) VALUES (?)", (seller_id,))
            c.execute("UPDATE seller_configs SET bank_card = ? WHERE seller_id = ?", (message.text, seller_id))
            conn.commit()
        bot.send_message(message.chat.id, "✅ شماره کارت با موفقیت ذخیره شد.")

    @bot.callback_query_handler(func=lambda call: call.data == "seller_edit_wallet")
    def edit_wallet_start(call):
        msg = bot.send_message(call.message.chat.id, "لطفاً آدرس ولت تتر (TRC20) یا ترون خود را وارد کنید:")
        bot.register_next_step_handler(msg, save_seller_wallet, bot)
        bot.answer_callback_query(call.id)
        
    def save_seller_wallet(message, bot):
        seller_id = get_effective_seller_id(message.chat.id)
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO seller_configs (seller_id) VALUES (?)", (seller_id,))
            c.execute("UPDATE seller_configs SET crypto_wallet = ? WHERE seller_id = ?", (message.text, seller_id))
            conn.commit()
        bot.send_message(message.chat.id, "✅ آدرس ولت با موفقیت ذخیره شد.")

    @bot.callback_query_handler(func=lambda call: call.data == "seller_edit_group")
    def edit_group_start(call):
        msg = bot.send_message(call.message.chat.id, "لطفاً آیدی عددی گروه خود (همراه با منفی) را وارد کنید:\nربات باید در این گروه ادمین باشد!")
        bot.register_next_step_handler(msg, save_seller_group, bot)
        bot.answer_callback_query(call.id)
        
    def save_seller_group(message, bot):
        try:
            gid = int(message.text)
            seller_id = get_effective_seller_id(message.chat.id)
            with sqlite3.connect(settings.database) as conn:
                c = conn.cursor()
                c.execute("INSERT OR IGNORE INTO seller_configs (seller_id) VALUES (?)", (seller_id,))
                c.execute("UPDATE seller_configs SET approval_group_id = ? WHERE seller_id = ?", (gid, seller_id))
                conn.commit()
            bot.send_message(message.chat.id, "✅ آیدی گروه با موفقیت ثبت شد.")
        except ValueError:
            bot.send_message(message.chat.id, "❌ آیدی نامعتبر است.")

    @bot.callback_query_handler(func=lambda call: call.data == "seller_toggle_active")
    def toggle_active_gateway(call):
        chat_id = call.message.chat.id
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("کارت به کارت", callback_data="seller_set_gateway_card"))
        markup.row(InlineKeyboardButton("ولت کریپتو", callback_data="seller_set_gateway_crypto"))
        markup.row(InlineKeyboardButton("هر دو", callback_data="seller_set_gateway_both"))
        bot.send_message(chat_id, "کدام درگاه برای مشتریان شما فعال باشد؟", reply_markup=markup)
        bot.answer_callback_query(call.id)
        
    @bot.callback_query_handler(func=lambda call: call.data.startswith("seller_set_gateway_"))
    def set_active_gateway(call):
        chat_id = call.message.chat.id
        seller_id = get_effective_seller_id(call.from_user.id)
        gw = call.data.replace("seller_set_gateway_", "")
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO seller_configs (seller_id) VALUES (?)", (seller_id,))
            c.execute("UPDATE seller_configs SET active_gateways = ? WHERE seller_id = ?", (gw, seller_id))
            conn.commit()
        bot.send_message(chat_id, f"✅ درگاه فعال به {gw} تغییر یافت.")
        bot.answer_callback_query(call.id, "آپدیت شد.")

    @bot.message_handler(func=lambda message: message.text == "برگشت به پنل فروشنده 🔙")
    def back_to_seller_panel(message):
        chat_id = message.chat.id
        if can_access_seller_panel(chat_id):
            from buttons import get_seller_markup
            seller_id = get_effective_seller_id(chat_id)
            note = f" (فروشنده <code>{seller_id}</code>)" if int(seller_id) != int(chat_id) else ""
            bot.send_message(chat_id, f"به پنل فروشنده برگشتید{note}:", reply_markup=get_seller_markup(chat_id), parse_mode="HTML")
        else:
            bot.send_message(chat_id, "شما دسترسی فروشنده ندارید.")

    @bot.message_handler(func=lambda message: message.text == "🛠 تنظیمات پروفایل من")
    def seller_profile_settings(message):
        chat_id = message.chat.id
        if not _require_seller(chat_id):
            bot.send_message(chat_id, "❌ شما دسترسی فروشنده ندارید.")
            return
        seller_id = get_effective_seller_id(chat_id)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📝 تنظیم لقب فروشگاه", callback_data="seller_prof_nickname"))
        markup.add(InlineKeyboardButton("👤 تنظیم آیدی پشتیبانی", callback_data="seller_prof_support"))
        markup.add(InlineKeyboardButton("📢 تنظیم لینک کانال", callback_data="seller_prof_channel"))
        markup.add(InlineKeyboardButton("📸 تنظیم لینک اینستاگرام", callback_data="seller_prof_instagram"))
        note = f"\n👤 فروشنده فعال: <code>{seller_id}</code>" if int(seller_id) != int(chat_id) else ""
        bot.send_message(
            chat_id,
            f"🛠 <b>تنظیمات پروفایل شما:</b>{note}\nاز طریق این منو می‌توانید اطلاعاتی که به کاربرانتان نمایش داده می‌شود را سفارشی‌سازی کنید.",
            reply_markup=markup,
            parse_mode="HTML",
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("seller_prof_"))
    def edit_seller_profile(call):
        action = call.data.split("_")[2]
        chat_id = call.message.chat.id
        
        from buttons import back_markup
        
        if action == "nickname":
            msg = bot.send_message(chat_id, "لطفاً لقب جدید فروشگاه خود را ارسال کنید (مثلاً: فروشگاه وی‌پی‌ان علی):", reply_markup=back_markup)
            bot.register_next_step_handler(msg, process_seller_profile, "nickname")
        elif action == "support":
            msg = bot.send_message(chat_id, "لطفاً آیدی پشتیبانی خود را ارسال کنید (مثلاً: @YourSupport):", reply_markup=back_markup)
            bot.register_next_step_handler(msg, process_seller_profile, "support_id")
        elif action == "channel":
            msg = bot.send_message(chat_id, "لطفاً لینک کانال تلگرام خود را ارسال کنید (مثلاً: https://t.me/YourChannel):", reply_markup=back_markup)
            bot.register_next_step_handler(msg, process_seller_profile, "channel_id")
        elif action == "instagram":
            msg = bot.send_message(chat_id, "لطفاً لینک اینستاگرام خود را ارسال کنید:", reply_markup=back_markup)
            bot.register_next_step_handler(msg, process_seller_profile, "instagram_id")

    def process_seller_profile(message, field):
        from buttons import get_seller_markup
        chat_id = message.chat.id
        if message.text == "برگشت 🔙":
            bot.send_message(chat_id, "عملیات لغو شد.", reply_markup=get_seller_markup(chat_id))
            return
            
        val = message.text
        seller_id = get_effective_seller_id(chat_id)
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO seller_configs (seller_id) VALUES (?)", (seller_id,))
            query = f"UPDATE seller_configs SET {field} = ? WHERE seller_id = ?"
            c.execute(query, (val, seller_id))
            conn.commit()
            
        bot.send_message(chat_id, "✅ اطلاعات با موفقیت بروزرسانی شد.", reply_markup=get_seller_markup(chat_id))
