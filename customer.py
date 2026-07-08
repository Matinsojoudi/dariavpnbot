import sqlite3
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from env import settings
from traffic_service import (
    has_enough_traffic,
    block_customer_no_traffic,
    deduct_traffic,
    force_deduct_traffic,
    refund_traffic,
    check_and_alert_low_traffic,
)


def _get_parent_seller_id(chat_id):
    with sqlite3.connect(settings.database) as conn:
        c = conn.cursor()
        c.execute("SELECT parent_seller_id, role FROM users WHERE user_id = ?", (chat_id,))
        row = c.fetchone()
    parent_id = row[0] if row and row[0] else None
    role = row[1] if row else "customer"
    if not parent_id and role == "seller":
        parent_id = chat_id
    return parent_id


def _should_check_traffic(seller_id):
    if not seller_id:
        return False
    if (int(seller_id) in settings.admin_list) or (int(seller_id) == int(settings.admin)):
        return False
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT role FROM users WHERE user_id = ?", (int(seller_id),))
            r = c.fetchone()
            if r and r[0] in ["admin", "superadmin"]:
                return False
    except:
        pass
    return True


def _parse_receipt_id(callback_data, prefix):
    """Extract receipt id from callback like confirm_receipt_123."""
    marker = f"{prefix}_"
    if not callback_data.startswith(marker):
        return None
    rid = callback_data[len(marker):]
    try:
        return int(rid)
    except ValueError:
        return None


def _update_receipt_photo(bot, call, receipt_id, status, reason=None, notify_text=None):
    """Update receipt caption, remove inline keyboard, answer callback."""
    new_cap = generate_receipt_caption(receipt_id, status, reason)
    try:
        bot.edit_message_caption(
            caption=new_cap,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(),
        )
    except Exception:
        try:
            bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=InlineKeyboardMarkup(),
            )
        except Exception:
            pass
    if notify_text:
        bot.answer_callback_query(call.id, notify_text, show_alert=notify_text.startswith("❌"))
    else:
        bot.answer_callback_query(call.id)


def register_customer_handlers(bot):

    @bot.message_handler(func=lambda message: message.text == "ورود به پنل خریدار 👤")
    def enter_customer_panel(message):
        chat_id = message.chat.id
        from buttons import customer_markup, get_customer_markup
        bot.send_message(chat_id, "👤 <b>به پنل کاربری خوش آمدید.</b>\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=get_customer_markup(chat_id), parse_mode="HTML")

    @bot.message_handler(func=lambda message: message.text in ["💰 شارژ کیف پول", "💰 افزایش اعتبار"])
    def add_balance(message):
        chat_id = message.chat.id
        from buttons import back_markup
        msg = bot.send_message(chat_id, "لطفاً مبلغی که می‌خواهید کیف پول خود را شارژ کنید به <b>تومان</b> وارد کنید:\n(مثلا: 50000)", parse_mode="HTML", reply_markup=back_markup)
        bot.register_next_step_handler(msg, process_charge_amount, bot)

    def process_charge_amount(message, bot):
        if message.text == "برگشت 🔙":
            from buttons import get_customer_markup
            bot.send_message(message.chat.id, "عملیات لغو شد. به منوی اصلی برگشتید.", reply_markup=get_customer_markup(message.chat.id))
            return
            
        try:
            amount = int(message.text)
            if amount < 10000:
                from buttons import get_customer_markup
                bot.send_message(message.chat.id, "❌ حداقل مبلغ شارژ 10,000 تومان است. عملیات لغو شد.", reply_markup=get_customer_markup(message.chat.id))
                return
            checkout_flow(message.chat.id, amount, 'charge', bot)
        except ValueError:
            from buttons import get_customer_markup
            bot.send_message(message.chat.id, "❌ مبلغ نامعتبر است. عملیات لغو شد.", reply_markup=get_customer_markup(message.chat.id))

    @bot.message_handler(func=lambda message: message.text in ["🛒 خرید سرویس (VPN)", "🛒 خرید سرویس (VPN)"])
    def buy_package(message):
        chat_id = message.chat.id
        # Need to find which seller this customer belongs to
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT parent_seller_id, role FROM users WHERE user_id = ?", (chat_id,))
            row = c.fetchone()
            
        parent_id = row[0] if row and row[0] else None
        role = row[1] if row else 'customer'
        if not parent_id and role == 'seller':
            parent_id = chat_id
            
        if not parent_id:
            bot.send_message(chat_id, "❌ شما از طریق لینک معرفی هیچ فروشنده‌ای وارد نشده‌اید. امکان خرید وجود ندارد.")
            return

        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT id, name, gb, days, price_toman FROM packages WHERE seller_id = ?", (parent_id,))
            packages = c.fetchall()
            
            c.execute("SELECT nickname FROM seller_configs WHERE seller_id = ?", (parent_id,))
            s_row = c.fetchone()
            seller_name = s_row[0] if s_row and s_row[0] else "فروشنده عزیز"
            
        if not packages:
            bot.send_message(chat_id, "فروشنده شما هنوز هیچ بسته‌ای برای فروش تعریف نکرده است.")
            return
            
        import uuid
        import os
        from utils.image_generator import generate_packages_image
        
        img_id = str(uuid.uuid4())
        img_path = f"temp_pkgs_{img_id}.png"
        
        try:
            generate_packages_image(packages, seller_name, img_path)
        except Exception as e:
            print("Error generating packages image:", e)
            
        markup = InlineKeyboardMarkup(row_width=2)
        msg_text = f"🛍 <b>سرویس‌های قابل خرید {seller_name}:</b>\n\n"
        msg_text += "🔸 لطفاً با توجه به نیاز خود، یکی از بسته‌های زیر را انتخاب کنید:"
        
        emojis = ["🚀", "💎", "⚡️", "🔥", "👑", "🌟"]
        
        buttons = []
        for i, p in enumerate(packages):
            pid, name, gb, days, price = p
            emo = emojis[i % len(emojis)]
            btn_text = f"{emo} {name}"
            buttons.append(InlineKeyboardButton(btn_text, callback_data=f"buy_pkg_{pid}"))
            
        markup.add(*buttons)
        
        try:
            with open(img_path, "rb") as photo:
                bot.send_photo(chat_id, photo, caption=msg_text, reply_markup=markup, parse_mode="HTML")
            if os.path.exists(img_path):
                os.remove(img_path)
        except Exception as e:
            bot.send_message(chat_id, msg_text, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("buy_pkg_"))
    def select_package(call):
        pkg_id = call.data.split("_")[2]
        chat_id = call.message.chat.id
        
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT price_toman, name, gb, days FROM packages WHERE id = ?", (pkg_id,))
            pkg = c.fetchone()
            
        if not pkg:
            bot.answer_callback_query(call.id, "بسته یافت نشد.")
            return
            
        price, name, gb, days = pkg

        parent_id = _get_parent_seller_id(chat_id)
        if _should_check_traffic(parent_id) and not has_enough_traffic(parent_id, gb):
            block_customer_no_traffic(bot, chat_id, parent_id, gb, name)
            bot.answer_callback_query(call.id)
            return
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("💳 خرید مستقیم", callback_data=f"checkout_direct_{pkg_id}"))
        markup.row(InlineKeyboardButton("💰 پرداخت از کیف پول", callback_data=f"checkout_wallet_{pkg_id}"))
        markup.row(InlineKeyboardButton("بازگشت به لیست بسته‌ها 🔙", callback_data="back_to_packages"))
        
        msg_text = f"💎 <b>مشخصات بسته انتخابی شما:</b>\n\n"
        msg_text += f"🏷 <b>نام بسته:</b> {name}\n"
        msg_text += f"🔋 <b>حجم اینترنت:</b> {gb} گیگابایت\n"
        msg_text += f"⏳ <b>اعتبار زمانی:</b> {days} روز\n"
        msg_text += f"💳 <b>مبلغ قابل پرداخت:</b> {price:,} تومان\n\n"
        msg_text += "لطفاً روش پرداخت خود را انتخاب کنید:"
        
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        
        bot.send_message(chat_id, msg_text, reply_markup=markup, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("checkout_wallet_"))
    def checkout_wallet(call):
        pkg_id = call.data.split("_")[2]
        chat_id = call.message.chat.id
        bot.answer_callback_query(call.id, "در حال بررسی موجودی...")
        
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT balance FROM users WHERE user_id = ?", (chat_id,))
            user_bal = c.fetchone()
            user_balance = user_bal[0] if user_bal else 0
            
            c.execute("SELECT price_toman, name, gb, days FROM packages WHERE id = ?", (pkg_id,))
            pkg = c.fetchone()
            
        if not pkg:
            bot.answer_callback_query(call.id, "بسته یافت نشد.", show_alert=True)
            return
            
        price, name, gb, days = pkg
        
        if user_balance < price:
            bot.answer_callback_query(call.id, "❌ موجودی ناکافی!")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("💳 شارژ کیف پول", callback_data="charge_wallet"))
            bot.send_message(chat_id, f"❌ <b>موجودی کیف پول شما کافی نیست!</b>\n\n💰 موجودی فعلی: <code>{user_balance:,}</code> تومان\n💳 مبلغ سرویس: <code>{price:,}</code> تومان\n\nبرای خرید این سرویس ابتدا کیف پول خود را شارژ کنید:", parse_mode="HTML", reply_markup=markup)
            return
            
        bot.answer_callback_query(call.id, "در حال ایجاد سرویس، لطفاً شکیبا باشید...")
        
        parent_id = _get_parent_seller_id(chat_id)
        if _should_check_traffic(parent_id) and not has_enough_traffic(parent_id, gb):
            block_customer_no_traffic(bot, chat_id, parent_id or 0, gb, name)
            return

        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, chat_id))
            
            c.execute("INSERT INTO receipts (user_id, seller_id, type, package_id, amount, status) VALUES (?, ?, ?, ?, ?, 'approved')",
                      (chat_id, parent_id, 'wallet', pkg_id, price))
            receipt_id = c.lastrowid
            
            if _should_check_traffic(parent_id):
                if not deduct_traffic(parent_id, gb):
                    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, chat_id))
                    c.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))
                    conn.commit()
                    block_customer_no_traffic(bot, chat_id, parent_id, gb, name)
                    return
            conn.commit()

        if _should_check_traffic(parent_id):
            check_and_alert_low_traffic(bot, parent_id)
            
        try:
            import uuid
            from hiddify.client import HiddifyClient
            client = HiddifyClient()
            client.reload_config()
            
            new_uuid = str(uuid.uuid4())
            user_name = f"User_{chat_id}_{receipt_id}"
            
            payload = {
                "name": user_name,
                "uuid": new_uuid,
                "usage_limit_GB": gb,
                "package_days": days,
                "comment": f"Sold by {parent_id}",
                "telegram_id": chat_id,
                "enable": True,
                "mode": "no_reset"
            }
            client.create_user(payload)
            
            sub_link = client.get_sub_link(new_uuid, user_name)
            
            with sqlite3.connect(settings.database) as conn:
                c = conn.cursor()
                c.execute("UPDATE receipts SET service_uuid = ? WHERE id = ?", (new_uuid, receipt_id))
                conn.commit()
            
            msg_text = f"✅ پرداخت شما از طریق کیف پول تأیید شد.\nسرویس <b>{name}</b> شما ایجاد گردید.\n\n🔗 لینک اشتراک شما:\n{sub_link}\n\nبه بخش '📦 سرویس‌های من' نیز می‌توانید مراجعه کنید."
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("🔗 اتصال سریع", url=sub_link))
            send_package_with_qr(bot, chat_id, msg_text, sub_link, markup)
        except Exception as e:
            # Revert the transaction if Hiddify API fails
            with sqlite3.connect(settings.database) as conn:
                c = conn.cursor()
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, chat_id))
                c.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))
                refund_traffic(parent_id, gb)
                conn.commit()
                
            bot.send_message(chat_id, "❌ متأسفانه در ارتباط با سرور برای ساخت سرویس مشکلی پیش آمد.\nمبلغ کسر شده به کیف پول شما بازگشت داده شد.\nلطفاً چند دقیقه دیگر مجدداً تلاش کنید.", parse_mode="HTML")
    @bot.callback_query_handler(func=lambda call: call.data.startswith("renew_pkg_"))
    def renew_package(call):
        parts = call.data.split("_")
        pkg_id = parts[2]
        p_uuid = parts[3]
        chat_id = call.message.chat.id
        
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT price_toman, name, gb, days FROM packages WHERE id = ?", (pkg_id,))
            pkg = c.fetchone()
            
        if not pkg:
            bot.answer_callback_query(call.id, "بسته اصلی یافت نشد. قابل تمدید نیست.")
            return
            
        price, name, gb, days = pkg
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("💳 پرداخت مستقیم", callback_data=f"renew_direct_{pkg_id}_{p_uuid}"))
        markup.row(InlineKeyboardButton("💰 پرداخت از کیف پول", callback_data=f"renew_wallet_{pkg_id}_{p_uuid}"))
        
        msg_text = f"🔄 <b>درخواست تمدید سرویس:</b>\n\n"
        msg_text += f"💎 <b>سرویس:</b> {name}\n"
        msg_text += f"💳 <b>مبلغ تمدید:</b> {price:,} تومان\n"
        msg_text += f"⚠️ توجه: با تمدید این سرویس، حجم مصرفی فعلی شما صفر شده و تنظیمات مجددا به ({gb} گیگابایت - {days} روز) تغییر می‌کند.\n\n"
        msg_text += "لطفاً روش پرداخت را انتخاب کنید:"
        
        bot.edit_message_text(msg_text, chat_id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("renew_direct_"))
    def renew_direct(call):
        parts = call.data.split("_")
        pkg_id = parts[2]
        p_uuid = parts[3]
        chat_id = call.message.chat.id
        
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT price_toman, name, gb FROM packages WHERE id = ?", (pkg_id,))
            row = c.fetchone()
        if not row:
            bot.answer_callback_query(call.id, "بسته یافت نشد.", show_alert=True)
            return
        price, name, gb = row
        parent_id = _get_parent_seller_id(chat_id)
        if _should_check_traffic(parent_id) and not has_enough_traffic(parent_id, gb):
            block_customer_no_traffic(bot, chat_id, parent_id, gb, name)
            bot.answer_callback_query(call.id)
            return
            
        checkout_flow(chat_id, price, 'renew', bot, pkg_id, renew_uuid=p_uuid)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("renew_wallet_"))
    def renew_wallet(call):
        parts = call.data.split("_")
        pkg_id = parts[2]
        p_uuid = parts[3]
        chat_id = call.message.chat.id
        bot.answer_callback_query(call.id, "در حال بررسی موجودی...")
        
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT balance FROM users WHERE user_id = ?", (chat_id,))
            user_bal = c.fetchone()
            user_balance = user_bal[0] if user_bal else 0
            
            c.execute("SELECT price_toman, name, gb, days FROM packages WHERE id = ?", (pkg_id,))
            pkg = c.fetchone()
            
        if not pkg:
            bot.answer_callback_query(call.id, "بسته یافت نشد.", show_alert=True)
            return
            
        price, name, gb, days = pkg
        
        if user_balance < price:
            bot.answer_callback_query(call.id, "❌ موجودی ناکافی!")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("💳 شارژ کیف پول", callback_data="charge_wallet"))
            bot.send_message(chat_id, f"❌ <b>موجودی کیف پول شما کافی نیست!</b>\n\n💰 موجودی فعلی: <code>{user_balance:,}</code> تومان\n💳 مبلغ سرویس: <code>{price:,}</code> تومان\n\nبرای تمدید این سرویس ابتدا کیف پول خود را شارژ کنید:", parse_mode="HTML", reply_markup=markup)
            return
            
        bot.answer_callback_query(call.id, "در حال تمدید سرویس، لطفاً شکیبا باشید...")
        
        parent_id = _get_parent_seller_id(chat_id)
        if _should_check_traffic(parent_id) and not has_enough_traffic(parent_id, gb):
            block_customer_no_traffic(bot, chat_id, parent_id or 0, gb, name)
            return

        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, chat_id))
            
            if _should_check_traffic(parent_id):
                if not deduct_traffic(parent_id, gb):
                    conn.commit()
                    block_customer_no_traffic(bot, chat_id, parent_id, gb, name)
                    return
            
            c.execute("INSERT INTO receipts (user_id, seller_id, type, package_id, amount, status, service_uuid) VALUES (?, ?, 'renew', ?, ?, 'approved', ?)",
                      (chat_id, parent_id, pkg_id, price, p_uuid))
            receipt_id = c.lastrowid
            conn.commit()

        if _should_check_traffic(parent_id):
            check_and_alert_low_traffic(bot, parent_id)
            
        try:
            from hiddify.client import HiddifyClient
            client = HiddifyClient()
            client.reload_config()
            
            # Fetch user to preserve name and other settings
            user_info = client.get_user(p_uuid)
            user_name = user_info.get("name", f"User_{chat_id}_{receipt_id}")
            
            client.update_user(p_uuid, {
                "name": user_name,
                "usage_limit_GB": gb,
                "package_days": days,
                "enable": True,
                "mode": "no_reset"
            })
            client.reset_user_usage(p_uuid)
            
            sub_link = client.get_sub_link(p_uuid, user_name)
            
            msg_text = f"✅ پرداخت شما از طریق کیف پول تأیید شد.\nسرویس <b>{name}</b> شما با موفقیت تمدید گردید.\n\n🔗 لینک اشتراک شما:\n{sub_link}\n\nبه بخش '📦 سرویس‌های من' نیز می‌توانید مراجعه کنید."
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("🔗 اتصال سریع", url=sub_link))
            send_package_with_qr(bot, chat_id, msg_text, sub_link, markup)
            bot.edit_message_caption(caption=f"✅ تمدید سرویس با موفقیت انجام شد.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        except Exception as e:
            with sqlite3.connect(settings.database) as conn:
                c = conn.cursor()
                c.execute("UPDATE receipts SET status = 'failed' WHERE id = ?", (receipt_id,))
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, chat_id))
                refund_traffic(parent_id, gb)
                conn.commit()
                
            bot.send_message(chat_id, "❌ متأسفانه در ارتباط با سرور برای تمدید سرویس مشکلی پیش آمد.\nمبلغ کسر شده به کیف پول شما بازگشت داده شد.\nلطفاً چند دقیقه دیگر مجدداً تلاش کنید.", parse_mode="HTML")
            print(f"Error in renew_wallet: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("checkout_direct_"))
    def checkout_direct(call):
        pkg_id = call.data.split("_")[2]
        chat_id = call.message.chat.id
        
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT price_toman, name, gb FROM packages WHERE id = ?", (pkg_id,))
            row = c.fetchone()
        if not row:
            bot.answer_callback_query(call.id, "بسته یافت نشد.", show_alert=True)
            return
        price, name, gb = row
        parent_id = _get_parent_seller_id(chat_id)
        if _should_check_traffic(parent_id) and not has_enough_traffic(parent_id, gb):
            block_customer_no_traffic(bot, chat_id, parent_id, gb, name)
            bot.answer_callback_query(call.id)
            return
            
        checkout_flow(chat_id, price, 'package', bot, pkg_id)
        bot.answer_callback_query(call.id)

    def checkout_flow(chat_id, amount, payment_type, bot, pkg_id=None, renew_uuid=None):
        parent_id = _get_parent_seller_id(chat_id)

        if payment_type in ("package", "renew") and pkg_id:
            with sqlite3.connect(settings.database) as conn:
                c = conn.cursor()
                c.execute("SELECT name, gb FROM packages WHERE id = ?", (pkg_id,))
                pkg_row = c.fetchone()
            if pkg_row:
                pname, pgb = pkg_row
                if _should_check_traffic(parent_id) and not has_enough_traffic(parent_id, pgb):
                    block_customer_no_traffic(bot, chat_id, parent_id, pgb, pname)
                    return

        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT parent_seller_id, role FROM users WHERE user_id = ?", (chat_id,))
            row = c.fetchone()
            parent_id = row[0] if row and row[0] else None
            role = row[1] if row else 'customer'
            
            if not parent_id and role == 'seller':
                parent_id = chat_id
            
            c.execute("SELECT bank_card, crypto_wallet, active_gateways FROM seller_configs WHERE seller_id = ?", (parent_id,))
            gw = c.fetchone()
            
        if not gw:
            bot.send_message(chat_id, "خطا: اطلاعات درگاه فروشنده یافت نشد.")
            return
            
        card, wallet, active = gw
        
        msg = f"مبلغ قابل پرداخت: <b>{amount} تومان</b>\n\n"
        if active in ['card', 'both']:
            msg += f"💳 شماره کارت جهت واریز:\n<code>{card}</code>\n\n"
        if active in ['crypto', 'both']:
            msg += f"💰 ولت ترون جهت واریز:\n<code>{wallet}</code>\n\n"
            
        msg += "پس از واریز، <b>عکس یا اسکرین‌شات رسید</b> خود را همینجا ارسال کنید:"
        
        # Save temporary state for next handler
        from buttons import back_markup
        bot.send_message(chat_id, msg, parse_mode="HTML", reply_markup=back_markup)
        bot.register_next_step_handler_by_chat_id(chat_id, receive_receipt, bot, amount, payment_type, pkg_id, parent_id, renew_uuid)

    def receive_receipt(message, bot, amount, payment_type, pkg_id, parent_id, renew_uuid=None):
        from buttons import get_customer_markup
        if message.text == "برگشت 🔙":
            bot.send_message(message.chat.id, "عملیات لغو شد. به منوی اصلی برگشتید.", reply_markup=get_customer_markup(message.chat.id))
            return
            
        if not message.photo:
            bot.send_message(message.chat.id, "شما باید عکس رسید را ارسال کنید. عملیات لغو شد.", reply_markup=get_customer_markup(message.chat.id))
            return
            
        photo_id = message.photo[-1].file_id
        chat_id = message.chat.id
        
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO receipts (user_id, seller_id, type, package_id, amount, photo_file_id, service_uuid) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (chat_id, parent_id, payment_type, pkg_id, amount, photo_id, renew_uuid))
            receipt_id = c.lastrowid
            conn.commit()

        group_id = None
        # 1. Try to get seller-specific group ID
        try:
            with sqlite3.connect(settings.database) as conn:
                c = conn.cursor()
                c.execute("SELECT approval_group_id FROM seller_configs WHERE seller_id = ?", (parent_id,))
                row = c.fetchone()
                if row and row[0]:
                    group_id = int(row[0])
        except Exception as e:
            print("Error retrieving seller approval_group_id:", e)

        # 2. Fallback to global group ID
        if not group_id:
            try:
                with sqlite3.connect(settings.database) as conn:
                    c = conn.cursor()
                    c.execute("SELECT value FROM bot_settings WHERE key = 'SELLER_RECEIPT_GROUP'")
                    row = c.fetchone()
                    if row and row[0]:
                        group_id = int(row[0])
            except Exception as e:
                print("Error retrieving global SELLER_RECEIPT_GROUP:", e)

        if not group_id:
            bot.send_message(
                chat_id,
                "❌ گروه پرداخت تنظیم نشده است. لطفاً با پشتیبانی تماس بگیرید.",
                reply_markup=get_customer_markup(chat_id),
            )
            return
            
        bot.send_message(chat_id, "✅ رسید شما دریافت شد و جهت بررسی برای فروشنده ارسال گردید. پس از تأیید، حساب یا سرویس شما فعال خواهد شد.", reply_markup=get_customer_markup(chat_id))
        
        # Send to approval group
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("✅ تأیید", callback_data=f"verify_receipt_{receipt_id}"),
            InlineKeyboardButton("❌ رد", callback_data=f"reject_receipt_{receipt_id}")
        )
        
        cap = generate_receipt_caption(receipt_id, "pending")
        
        try:
            bot.send_photo(group_id, photo_id, caption=cap, reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            bot.send_message(chat_id, "متاسفانه ارسال فیش به گروه ادمین با مشکل مواجه شد. لطفاً به پشتیبانی پیام دهید.")


    @bot.callback_query_handler(func=lambda call: call.data.startswith("verify_receipt_"))
    def verify_receipt(call):
        receipt_id = _parse_receipt_id(call.data, "verify_receipt")
        if not receipt_id:
            bot.answer_callback_query(call.id, "رسید نامعتبر است.")
            return
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("تأیید نهایی ✅", callback_data=f"confirm_receipt_{receipt_id}"))
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
            bot.answer_callback_query(call.id, "برای تأیید قطعی کلیک کنید")
        except Exception as e:
            bot.answer_callback_query(call.id, f"خطا در به‌روزرسانی دکمه: {e}", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("reject_receipt_"))
    def reject_receipt(call):
        receipt_id = _parse_receipt_id(call.data, "reject_receipt")
        if not receipt_id:
            bot.answer_callback_query(call.id, "رسید نامعتبر است.")
            return
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("مبلغ اشتباه", callback_data=f"do_reject_{receipt_id}_wrongamount"))
        markup.row(InlineKeyboardButton("فیش فیک", callback_data=f"do_reject_{receipt_id}_fake"))
        markup.row(InlineKeyboardButton("تکراری", callback_data=f"do_reject_{receipt_id}_duplicate"))
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
            bot.answer_callback_query(call.id, "دلیل رد را انتخاب کنید")
        except Exception as e:
            bot.answer_callback_query(call.id, f"خطا: {e}", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("do_reject_"))
    def do_reject_receipt(call):
        rest = call.data[len("do_reject_"):]
        if "_" not in rest:
            bot.answer_callback_query(call.id, "داده نامعتبر است.")
            return
        receipt_id_str, reason_code = rest.rsplit("_", 1)
        try:
            receipt_id = int(receipt_id_str)
        except ValueError:
            bot.answer_callback_query(call.id, "رسید نامعتبر است.")
            return
        reasons = {
            "wrongamount": "مبلغ واریزی اشتباه است.",
            "fake": "فیش جعلی تشخیص داده شد.",
            "duplicate": "این فیش قبلاً استفاده شده است.",
        }
        if reason_code not in reasons:
            bot.answer_callback_query(call.id, "دلیل نامعتبر است.")
            return

        try:
            with sqlite3.connect(settings.database) as conn:
                c = conn.cursor()
                c.execute("SELECT user_id, status FROM receipts WHERE id = ?", (receipt_id,))
                row = c.fetchone()
                if not row:
                    bot.answer_callback_query(call.id, "رسید یافت نشد.", show_alert=True)
                    return
                user_id, status = row
                if status != "pending":
                    bot.answer_callback_query(call.id, "این فیش قبلاً پردازش شده است.", show_alert=True)
                    return
                c.execute(
                    "UPDATE receipts SET status = 'rejected' WHERE id = ? AND status = 'pending'",
                    (receipt_id,),
                )
                if c.rowcount == 0:
                    bot.answer_callback_query(call.id, "این فیش قبلاً پردازش شده است.", show_alert=True)
                    return
                conn.commit()

            try:
                bot.send_message(
                    user_id,
                    f"❌ متأسفانه رسید شما تأیید نشد.\nدلیل: {reasons[reason_code]}",
                )
            except Exception:
                pass
            _update_receipt_photo(bot, call, receipt_id, "rejected", reasons[reason_code], "فیش رد شد.")
        except Exception as e:
            try:
                bot.send_message(call.message.chat.id, f"❌ خطا در رد فیش:\n{e}")
            except Exception:
                pass
            bot.answer_callback_query(call.id, "خطا در رد فیش. دوباره تلاش کنید.", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_receipt_"))
    def confirm_receipt(call):
        receipt_id = _parse_receipt_id(call.data, "confirm_receipt")
        if not receipt_id:
            bot.answer_callback_query(call.id, "رسید نامعتبر است.")
            return

        try:
            with sqlite3.connect(settings.database) as conn:
                c = conn.cursor()
                c.execute(
                    "SELECT user_id, seller_id, type, package_id, amount, status, service_uuid FROM receipts WHERE id = ?",
                    (receipt_id,),
                )
                row = c.fetchone()

                if not row or row[5] != "pending":
                    bot.answer_callback_query(call.id, "فیش پردازش شده یا نامعتبر است.", show_alert=True)
                    return

                user_id, seller_id, r_type, pkg_id, amount, status, renew_uuid = row

                if r_type == "charge":
                    c.execute("UPDATE receipts SET status = 'approved' WHERE id = ?", (receipt_id,))
                    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
                    conn.commit()
                    try:
                        bot.send_message(user_id, f"✅ حساب شما با موفقیت به مبلغ {amount} تومان شارژ شد.")
                    except Exception:
                        pass

                elif r_type == "package":
                    c.execute("SELECT name, gb, days FROM packages WHERE id = ?", (pkg_id,))
                    pkg = c.fetchone()
                    if not pkg:
                        bot.answer_callback_query(call.id, "بسته یافت نشد.", show_alert=True)
                        return

                    # Check if seller_id is admin
                    is_seller_admin = False
                    if (int(seller_id) in settings.admin_list) or (int(seller_id) == int(settings.admin)):
                        is_seller_admin = True
                    else:
                        c.execute("SELECT role FROM users WHERE user_id = ?", (int(seller_id),))
                        u_row = c.fetchone()
                        if u_row and u_row[0] in ["admin", "superadmin"]:
                            is_seller_admin = True

                    if not is_seller_admin:
                        force_deduct_traffic(seller_id, pkg[1])

                    c.execute("UPDATE receipts SET status = 'approved' WHERE id = ?", (receipt_id,))
                    conn.commit()

                    check_and_alert_low_traffic(bot, seller_id)

                    import uuid
                    from hiddify.client import HiddifyClient

                    client = HiddifyClient()
                    client.reload_config()
                    new_uuid = str(uuid.uuid4())

                    c.execute(
                        "SELECT username_prefix, user_sequence FROM seller_configs WHERE seller_id = ?",
                        (seller_id,),
                    )
                    seller_cfg = c.fetchone()
                    if seller_cfg and seller_cfg[0]:
                        prefix, seq = seller_cfg
                        user_name = f"{prefix}{seq}"
                        c.execute(
                            "UPDATE seller_configs SET user_sequence = user_sequence + 1 WHERE seller_id = ?",
                            (seller_id,),
                        )
                    else:
                        user_name = f"User_{user_id}_{receipt_id}"

                    client.create_user({
                        "name": user_name,
                        "uuid": new_uuid,
                        "usage_limit_GB": pkg[1],
                        "package_days": pkg[2],
                        "comment": f"Sold by {seller_id}",
                        "telegram_id": user_id,
                        "enable": True,
                        "mode": "no_reset",
                    })

                    sub_link = client.get_sub_link(new_uuid, user_name)
                    c.execute("UPDATE receipts SET service_uuid = ? WHERE id = ?", (new_uuid, receipt_id))
                    conn.commit()

                    msg_text = (
                        f"✅ پرداخت شما تأیید شد.\nسرویس <b>{pkg[0]}</b> شما ایجاد گردید.\n\n"
                        f"🔗 لینک اشتراک شما:\n{sub_link}"
                    )
                    markup = InlineKeyboardMarkup()
                    markup.row(InlineKeyboardButton("🔗 اتصال سریع", url=sub_link))
                    send_package_with_qr(bot, user_id, msg_text, sub_link, markup)

                elif r_type == "renew":
                    c.execute("SELECT name, gb, days FROM packages WHERE id = ?", (pkg_id,))
                    pkg = c.fetchone()
                    if not pkg:
                        bot.answer_callback_query(call.id, "بسته یافت نشد.", show_alert=True)
                        return

                    # Check if seller_id is admin
                    is_seller_admin = False
                    if (int(seller_id) in settings.admin_list) or (int(seller_id) == int(settings.admin)):
                        is_seller_admin = True
                    else:
                        c.execute("SELECT role FROM users WHERE user_id = ?", (int(seller_id),))
                        u_row = c.fetchone()
                        if u_row and u_row[0] in ["admin", "superadmin"]:
                            is_seller_admin = True

                    if not is_seller_admin:
                        force_deduct_traffic(seller_id, pkg[1])

                    c.execute("UPDATE receipts SET status = 'approved' WHERE id = ?", (receipt_id,))
                    conn.commit()
                    check_and_alert_low_traffic(bot, seller_id)

                    from hiddify.client import HiddifyClient

                    client = HiddifyClient()
                    client.reload_config()
                    user_info = client.get_user(renew_uuid)
                    user_name = user_info.get("name", f"User_{user_id}_{receipt_id}")
                    client.update_user(renew_uuid, {
                        "name": user_name,
                        "usage_limit_GB": pkg[1],
                        "package_days": pkg[2],
                        "enable": True,
                        "mode": "no_reset",
                    })
                    client.reset_user_usage(renew_uuid)
                    sub_link = client.get_sub_link(renew_uuid, user_name)
                    msg_text = (
                        f"✅ پرداخت شما تأیید شد.\nسرویس <b>{pkg[0]}</b> شما تمدید گردید.\n\n"
                        f"🔗 لینک اشتراک شما:\n{sub_link}"
                    )
                    markup = InlineKeyboardMarkup()
                    markup.row(InlineKeyboardButton("🔗 اتصال سریع", url=sub_link))
                    send_package_with_qr(bot, user_id, msg_text, sub_link, markup)

                else:
                    c.execute("UPDATE receipts SET status = 'approved' WHERE id = ?", (receipt_id,))
                    conn.commit()

            _update_receipt_photo(bot, call, receipt_id, "approved", notify_text="✅ فیش تأیید شد.")

        except Exception as e:
            try:
                with sqlite3.connect(settings.database) as conn:
                    c = conn.cursor()
                    c.execute(
                        "SELECT seller_id, type, package_id, status FROM receipts WHERE id = ?",
                        (receipt_id,),
                    )
                    err_row = c.fetchone()
                    if err_row:
                        err_seller, err_type, err_pkg_id, err_status = err_row
                        if err_status == "approved" and err_type in ("package", "renew") and err_pkg_id:
                            c.execute("SELECT gb FROM packages WHERE id = ?", (err_pkg_id,))
                            pkg_row = c.fetchone()
                            if pkg_row:
                                refund_traffic(err_seller, pkg_row[0])
                        c.execute(
                            "UPDATE receipts SET status = 'pending' WHERE id = ?",
                            (receipt_id,),
                        )
                        conn.commit()
            except Exception:
                pass
            try:
                bot.send_message(call.message.chat.id, f"❌ خطا در تأیید فیش:\n{e}")
            except Exception:
                pass
            bot.answer_callback_query(call.id, "خطا در تأیید فیش. دوباره تلاش کنید.", show_alert=True)


    @bot.message_handler(func=lambda message: message.text in ["📦 سرویس‌های من", "📦 بسته‌های من"])
    def my_packages(message):
        chat_id = message.chat.id
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT receipts.id, packages.name, receipts.service_uuid, packages.id FROM receipts JOIN packages ON receipts.package_id = packages.id WHERE receipts.user_id = ? AND receipts.status = 'approved' AND receipts.service_uuid IS NOT NULL", (chat_id,))
            pkgs = c.fetchall()
            
        if not pkgs:
            bot.send_message(chat_id, "شما هیچ بسته فعالی ندارید.")
            return
            
        from hiddify.client import HiddifyClient
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        client = HiddifyClient()
        client.reload_config()
        
        bot.send_message(chat_id, "📦 <b>لیست سرویس‌های شما:</b>", parse_mode="HTML")
        
        for r_id, p_name, p_uuid, pkg_id in pkgs:
            user_name = f"User_{chat_id}_{r_id}"
            sub_link = client.get_sub_link(p_uuid, user_name)
            
            msg = ""
            try:
                user_info = client.get_user(p_uuid)
                limit_gb = user_info.get("usage_limit_GB", 0)
                used_gb = user_info.get("current_usage_GB", 0)
                rem_gb = max(0, limit_gb - used_gb)
                
                pkg_days = user_info.get("package_days", 0)
                start_date_str = user_info.get("start_date")
                
                if not start_date_str:
                    status_text = f"⏳ شروع نشده ({pkg_days} روز اعتبار پس از اتصال)"
                else:
                    import datetime
                    start_date = datetime.datetime.strptime(start_date_str.replace("T", " ")[:19], "%Y-%m-%d %H:%M:%S")
                    end_date = start_date + datetime.timedelta(days=pkg_days)
                    rem_days = (end_date - datetime.datetime.now()).days
                    status_text = f"⏳ {rem_days} روز مانده" if rem_days > 0 else "❌ منقضی شده"
                    
                msg += f"💎 <b>{p_name}</b>\n"
                msg += f"📊 <b>حجم باقیمانده:</b> {rem_gb:.2f} از {limit_gb}GB\n"
                msg += f"🗓 <b>زمان باقیمانده:</b> {status_text}\n"
                msg += f"🔗 <b>لینک اشتراک:</b>\n{sub_link}"
            except Exception as e:
                print(f"Error fetching user stats for {p_uuid}: {e}")
                msg += f"💎 <b>{p_name}</b>\n🔗 <b>لینک اشتراک:</b>\n{sub_link}"
            
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("🔗 اتصال سریع", url=sub_link))
            markup.row(InlineKeyboardButton("🔄 تمدید سرویس", callback_data=f"renew_pkg_{pkg_id}_{p_uuid}"))
            
            send_package_with_qr(bot, chat_id, msg, sub_link, markup)

    @bot.callback_query_handler(func=lambda call: call.data == "history_purchases")
    def purchase_history(call):
        chat_id = call.message.chat.id
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT type, amount, status, created_at FROM receipts WHERE user_id = ? ORDER BY created_at DESC LIMIT 10", (chat_id,))
            history = c.fetchall()
            
        if not history:
            bot.send_message(chat_id, "شما هیچ تاریخچه‌ای ندارید.")
            return
            
        msg = "📜 <b>10 تراکنش اخیر شما:</b>\n\n"
        for t_type, amount, status, date in history:
            t_name = "خرید بسته" if t_type == "package" else "شارژ حساب" if t_type == "charge" else t_type
            s_name = "✅ تأیید شده" if status == "approved" else "⏳ در انتظار" if status == "pending" else "❌ رد شده"
            msg += f"🔸 نوع: {t_name} | مبلغ: {amount:,} تومان | وضعیت: {s_name}\n"
            
        bot.send_message(chat_id, msg, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    @bot.message_handler(func=lambda message: message.text in ["📚 راهنمای استفاده", "راهنما ❓"])
    def help_customer(message):
        chat_id = message.chat.id
        msg = "❓ <b>راهنمای جامع استفاده از ربات:</b>\n\n"
        msg += "🛒 <b>خرید سرویس (VPN):</b>\n"
        msg += "از این بخش می‌توانید لیست پکیج‌های اینترنت موجود را مشاهده کرده و سرویس مورد نظر خود را خریداری کنید. پس از انتخاب، می‌توانید هزینه را به‌صورت مستقیم (کارت یا رمزارز) پرداخت کرده و فیش واریزی را ارسال کنید، و یا مستقیماً از موجودی کیف پول خود خرید نمایید.\n\n"
        msg += "📦 <b>سرویس‌های من:</b>\n"
        msg += "سرویس‌های خریداری شده‌ی شما در این بخش قرار دارند. مشخصاتی نظیر حجم باقیمانده، مهلت اعتبار و دکمه‌ی اتصال سریع برای هرکدام نمایش داده می‌شود. همچنین از طریق دکمه‌ی «تمدید سرویس» می‌توانید سرویس خود را بدون تغییر لینک اشتراک، تمدید کنید.\n\n"
        msg += "💰 <b>شارژ کیف پول:</b>\n"
        msg += "با شارژ کردن کیف پول خود، می‌توانید بدون نیاز به ارسال فیش برای هر خرید و منتظر ماندن جهت تأیید، سرویس‌های جدید را در همان لحظه بخرید یا تمدید کنید.\n\n"
        msg += "👤 <b>پروفایل کاربری:</b>\n"
        msg += "اطلاعات حساب شما شامل موجودی فعلی کیف پول، تاریخ عضویت، تعداد سرویس‌های فعال و همچنین دکمه‌ای برای دسترسی به «تاریخچه پرداخت‌ها» در اینجا تعبیه شده است.\n\n"
        msg += "📞 <b>پشتیبانی:</b>\n"
        msg += "برای ارتباط با تیم پشتیبانی و دریافت شبکه‌های اجتماعی ما می‌توانید از این دکمه استفاده کنید."
        bot.send_message(chat_id, msg, parse_mode="HTML")

    @bot.message_handler(func=lambda message: message.text == "👤 پروفایل کاربری")
    def user_profile(message):
        chat_id = message.chat.id
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT balance, join_date FROM users WHERE user_id = ?", (chat_id,))
            user_data = c.fetchone()
            
            c.execute("SELECT COUNT(*) FROM receipts WHERE user_id = ? AND type = 'package' AND status = 'approved'", (chat_id,))
            services_count = c.fetchone()[0]
            
        if not user_data:
            bot.send_message(chat_id, "اطلاعات شما یافت نشد.")
            return
            
        balance, join_date = user_data
        
        msg = f"👤 <b>پروفایل کاربری شما</b>\n\n"
        msg += f"🆔 <b>آیدی عددی:</b> <code>{chat_id}</code>\n"
        if message.from_user.username:
            msg += f"🌐 <b>نام کاربری:</b> @{message.from_user.username}\n"
        msg += f"💰 <b>موجودی کیف پول:</b> {balance:,} تومان\n"
        msg += f"📦 <b>تعداد سرویس‌های فعال:</b> {services_count} عدد\n\n"
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📜 تاریخچه تراکنش‌ها", callback_data="history_purchases"))
        
        bot.send_message(chat_id, msg, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "back_to_packages")
    def back_to_packages(call):
        chat_id = call.message.chat.id
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        call.message.text = "🛒 خرید سرویس (VPN)"
        buy_package(call.message)
        bot.answer_callback_query(call.id)

def send_package_with_qr(bot, chat_id, msg_text, sub_link, markup):
    import os
    import uuid
    from utils.qr import link_to_qrcode, place_qr_on_template
    
    qr_id = str(uuid.uuid4())
    qr_path = f"temp_qr_{qr_id}.png"
    final_path = f"temp_final_{qr_id}.png"
    bg_path = "assets/qrcode_template.png"
    
    try:
        link_to_qrcode(sub_link, qr_path)
        place_qr_on_template(qr_path, bg_path, final_path, "sub_link", sub_link=sub_link)
        with open(final_path, "rb") as photo:
            bot.send_photo(chat_id, photo, caption=msg_text, reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        print(f"Error sending QR: {e}")
        bot.send_message(chat_id, msg_text, reply_markup=markup, parse_mode="HTML")
    finally:
        if os.path.exists(qr_path):
            os.remove(qr_path)
        if os.path.exists(final_path):
            os.remove(final_path)

def generate_receipt_caption(receipt_id, status="pending", reason=None):
    import sqlite3
    with sqlite3.connect(settings.database) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, type, amount FROM receipts WHERE id = ?", (receipt_id,))
        row = c.fetchone()
        if not row: return "رسید یافت نشد."
        user_id, r_type, amount = row
        
        c.execute("SELECT first_name, last_name, user_name, join_date, balance FROM users WHERE user_id = ?", (user_id,))
        user_info = c.fetchone()
        first_name, last_name, username, join_date, balance = user_info if user_info else ("Unknown", "", "", "Unknown", 0)
        
        c.execute("SELECT COUNT(*) FROM receipts WHERE user_id = ? AND status = 'approved'", (user_id,))
        purchases_count = c.fetchone()[0]
        
    full_name = f"{first_name} {last_name or ''}".strip()
    user_link = f"@{username}" if username else "ندارد"
    
    if status == "pending":
        cap = f"🧾 <b>رسید جدید</b> (کد #{receipt_id})\n\n"
    elif status == "approved":
        cap = f"✅ <b>رسید تأیید شده</b> (کد #{receipt_id})\n\n"
    elif status == "rejected":
        cap = f"❌ <b>رسید رد شده</b> (کد #{receipt_id})\n\n"
        
    cap += f"👤 <b>کاربر:</b> {full_name}\n"
    cap += f"🆔 <b>آیدی عددی:</b> <code>{user_id}</code>\n"
    cap += f"🔗 <b>یوزرنیم:</b> {user_link}\n"
    cap += f"📅 <b>تاریخ عضویت:</b> {join_date}\n"
    cap += f"🛍 <b>تعداد خریدهای موفق پیشین:</b> {purchases_count}\n"
    cap += f"💰 <b>موجودی فعلی کیف پول:</b> {balance:,} تومان\n\n"
    
    if r_type == "charge":
        cap += f"💳 <b>نوع تراکنش:</b> شارژ کیف پول\n"
    elif r_type == "package":
        cap += f"💳 <b>نوع تراکنش:</b> خرید سرویس جدید\n"
    elif r_type == "renew":
        cap += f"💳 <b>نوع تراکنش:</b> تمدید سرویس\n"
        
    cap += f"💵 <b>مبلغ پرداخت شده:</b> {amount:,} تومان"
    
    if status == "rejected" and reason:
        cap += f"\n\n💬 <b>دلیل رد:</b> {reason}"
        
    return cap
