"""Seller traffic purchase flow and super-admin receipt approval (group chat support)."""

import sqlite3
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from env import settings
from traffic_service import add_traffic_to_seller, check_and_alert_low_traffic


def _is_super_admin(chat_id):
    main = __import__("main")
    return (int(chat_id) in settings.admin_list) or (int(chat_id) in main.get_admin_ids())


def _get_bot_setting(key, default=""):
    with sqlite3.connect(settings.database) as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
        row = c.fetchone()
    return row[0] if row else default


def _get_admin_wallets():
    with sqlite3.connect(settings.database) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT network, currency, address FROM admin_wallets WHERE is_active = 1 OR is_active IS NULL"
        )
        return c.fetchall()


def _notify_super_admins(bot, photo_id, caption, receipt_id):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("✅ تأیید ترافیک", callback_data=f"confirm_traffic_{receipt_id}"),
        InlineKeyboardButton("❌ رد", callback_data=f"reject_traffic_{receipt_id}"),
    )
    
    # Try sending to configured group first
    group_id_str = _get_bot_setting("SELLER_RECEIPT_GROUP")
    if group_id_str:
        try:
            bot.send_photo(int(group_id_str), photo_id, caption=caption, reply_markup=markup, parse_mode="HTML")
            return
        except Exception as e:
            print("Failed to send receipt to group chat, falling back to private chats:", e)

    # Fallback to sending privately to all admins
    admin_ids = set(settings.admin_list)
    if settings.matin:
        try:
            admin_ids.add(int(settings.matin))
        except (TypeError, ValueError):
            pass
    if settings.admin:
        try:
            admin_ids.add(int(settings.admin))
        except (TypeError, ValueError):
            pass

    for aid in admin_ids:
        try:
            bot.send_photo(aid, photo_id, caption=caption, reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass


def register_seller_traffic_handlers(bot):

    @bot.message_handler(func=lambda m: m.text == "🔄 تمدید / خرید ترافیک")
    def seller_traffic_menu(message):
        chat_id = message.chat.id
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT role FROM users WHERE user_id = ?", (chat_id,))
            row = c.fetchone()
        role = row[0] if row else "customer"
        if role != "seller" and chat_id not in settings.admin_list:
            bot.send_message(chat_id, "❌ این بخش فقط برای فروشندگان است.")
            return

        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute(
                "SELECT id, title, volume_gb, price_toman, price_usd FROM seller_packages ORDER BY volume_gb"
            )
            packages = c.fetchall()

        if not packages:
            bot.send_message(
                chat_id,
                "📭 هنوز بسته ترافیکی توسط مدیریت تعریف نشده است.\n"
                "لطفاً با پشتیبانی تماس بگیرید.",
            )
            return

        markup = InlineKeyboardMarkup(row_width=1)
        msg = "📡 <b>بسته‌های ترافیک قابل خرید:</b>\n\n"
        for pid, title, vol, pt, pu in packages:
            pt = pt or 0
            pu = pu or 0
            msg += f"🔹 <b>{title}</b> — {vol} GB\n"
            msg += f"   💵 {pt:,} تومان | 💲 {pu} دلار\n\n"
            markup.add(
                InlineKeyboardButton(
                    f"🛒 {title} ({vol}GB)",
                    callback_data=f"buy_traffic_{pid}",
                )
            )
        bot.send_message(chat_id, msg, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy_traffic_"))
    def buy_traffic_select(call):
        pkg_id = int(call.data.split("_")[2])
        chat_id = call.message.chat.id

        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute(
                "SELECT title, volume_gb, price_toman, price_usd FROM seller_packages WHERE id = ?",
                (pkg_id,),
            )
            pkg = c.fetchone()
            c.execute(
                "SELECT show_card_for_traffic FROM seller_configs WHERE seller_id = ?",
                (chat_id,),
            )
            cfg = c.fetchone()

        if not pkg:
            bot.answer_callback_query(call.id, "بسته یافت نشد.", show_alert=True)
            return

        title, vol, pt, pu = pkg
        card_status = _get_bot_setting("PAYMENT_CARD_STATUS") or "1"
        crypto_status = _get_bot_setting("PAYMENT_CRYPTO_STATUS") or "1"

        # Per-seller override: show_card_for_traffic=0 hides admin card for this seller
        seller_show_card = 1
        if cfg is not None and cfg[0] is not None:
            try:
                seller_show_card = int(cfg[0])
            except (TypeError, ValueError):
                seller_show_card = 1

        show_card = (card_status == "1") and (seller_show_card != 0)
        show_crypto = crypto_status == "1"
        pt = pt or 0
        pu = pu or 0

        msg = (
            f"📦 <b>{title}</b>\n"
            f"📊 حجم: <b>{vol} GB</b>\n"
            f"💵 قیمت: <b>{pt:,}</b> تومان\n"
            f"💲 قیمت: <b>{pu}</b> دلار\n\n"
            "روش پرداخت:\n"
        )

        has_method = False

        if show_card:
            card = _get_bot_setting("SUPER_ADMIN_BANK_CARD")
            owner = _get_bot_setting("SUPER_ADMIN_CARD_OWNER")
            if card:
                msg += f"\n💳 <b>پرداخت کارت به کارت:</b>\nشماره کارت:\n<code>{card}</code>\n"
                if owner:
                    msg += f"👤 به نام: <b>{owner}</b>\n"
                has_method = True

        if show_crypto:
            wallets = _get_admin_wallets()
            if wallets:
                msg += "\n🪙 <b>پرداخت با ارز دیجیتال:</b>\n"
                for net, cur, addr in wallets:
                    msg += f"🌐 {net} ({cur}):\n<code>{addr}</code>\n"
                has_method = True

        if not has_method:
            msg += "\n⚠️ اطلاعات پرداخت هنوز توسط مدیریت تنظیم نشده یا غیرفعال است. لطفاً با پشتیبانی تماس بگیرید.\n"

        msg += "\nپس از واریز، <b>عکس رسید</b> را همینجا ارسال کنید:"

        from buttons import back_markup
        bot.send_message(chat_id, msg, parse_mode="HTML", reply_markup=back_markup)
        bot.register_next_step_handler_by_chat_id(
            chat_id, receive_traffic_receipt, bot, pkg_id, title, vol, pt
        )
        bot.answer_callback_query(call.id)

    def receive_traffic_receipt(message, bot, pkg_id, title, vol, amount_toman):
        from buttons import get_seller_markup
        chat_id = message.chat.id

        if message.text == "برگشت 🔙":
            bot.send_message(
                chat_id,
                "عملیات لغو شد.",
                reply_markup=get_seller_markup(chat_id),
            )
            return

        if not message.photo:
            bot.send_message(
                chat_id,
                "❌ لطفاً عکس رسید را ارسال کنید.",
                reply_markup=get_seller_markup(chat_id),
            )
            return

        photo_id = message.photo[-1].file_id

        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute(
                """INSERT INTO receipts (user_id, seller_id, type, package_id, amount, photo_file_id, status)
                   VALUES (?, 0, 'traffic_purchase', ?, ?, ?, 'pending')""",
                (chat_id, pkg_id, amount_toman or 0, photo_id),
            )
            receipt_id = c.lastrowid
            conn.commit()

        bot.send_message(
            chat_id,
            "✅ رسید شما ثبت شد و برای تأیید مدیریت ارسال گردید.\n"
            "پس از تأیید، ترافیک به حساب شما اضافه می‌شود.",
            reply_markup=get_seller_markup(chat_id),
        )

        cap = (
            f"📡 <b>درخواست خرید ترافیک</b>\n\n"
            f"👤 فروشنده: <code>{chat_id}</code>\n"
            f"📦 بسته: <b>{title}</b> ({vol} GB)\n"
            f"💵 مبلغ: {amount_toman:,} تومان\n"
            f"🆔 رسید: #{receipt_id}"
        )
        _notify_super_admins(bot, photo_id, cap, receipt_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_traffic_"))
    def confirm_traffic_receipt(call):
        if not _is_super_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
            return

        receipt_id = int(call.data.split("_")[2])

        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute(
                "SELECT user_id, package_id, status FROM receipts WHERE id = ? AND type = 'traffic_purchase'",
                (receipt_id,),
            )
            row = c.fetchone()
            if not row or row[2] != "pending":
                bot.answer_callback_query(call.id, "رسید نامعتبر یا پردازش شده.", show_alert=True)
                return

            seller_id, pkg_id, _ = row
            c.execute("SELECT title, volume_gb FROM seller_packages WHERE id = ?", (pkg_id,))
            pkg = c.fetchone()
            if not pkg:
                bot.answer_callback_query(call.id, "بسته ترافیک یافت نشد.", show_alert=True)
                return

            title, vol = pkg
            c.execute("UPDATE receipts SET status = 'approved' WHERE id = ?", (receipt_id,))
            conn.commit()

        add_traffic_to_seller(seller_id, vol)
        check_and_alert_low_traffic(bot, seller_id)

        try:
            bot.send_message(
                seller_id,
                f"✅ خرید ترافیک تأیید شد!\n\n"
                f"📦 بسته: <b>{title}</b>\n"
                f"➕ {vol} GB به حساب شما اضافه شد.",
                parse_mode="HTML",
            )
        except Exception:
            pass

        try:
            bot.edit_message_caption(
                caption=f"✅ تأیید شد — {vol}GB به فروشنده {seller_id} اضافه شد.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
            )
        except Exception:
            pass
        bot.answer_callback_query(call.id, "ترافیک اضافه شد.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("reject_traffic_"))
    def reject_traffic_receipt(call):
        if not _is_super_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
            return

        try:
            receipt_id = int(call.data.rsplit("_", 1)[-1])
        except ValueError:
            bot.answer_callback_query(call.id, "رسید نامعتبر است.", show_alert=True)
            return

        try:
            with sqlite3.connect(settings.database) as conn:
                c = conn.cursor()
                c.execute(
                    "SELECT user_id, status FROM receipts WHERE id = ? AND type = 'traffic_purchase'",
                    (receipt_id,),
                )
                row = c.fetchone()
                if not row or row[1] != "pending":
                    bot.answer_callback_query(call.id, "رسید نامعتبر یا قبلاً پردازش شده.", show_alert=True)
                    return
                seller_id = row[0]
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
                    seller_id,
                    "❌ رسید خرید ترافیک شما تأیید نشد.\n"
                    "در صورت نیاز با پشتیبانی تماس بگیرید.",
                )
            except Exception:
                pass

            try:
                bot.edit_message_caption(
                    caption="❌ رسید خرید ترافیک رد شد.",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
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
            bot.answer_callback_query(call.id, "فیش رد شد.")
        except Exception as e:
            bot.answer_callback_query(call.id, "خطا در رد فیش.", show_alert=True)
            try:
                bot.send_message(call.message.chat.id, f"❌ خطا در رد فیش ترافیک:\n{e}")
            except Exception:
                pass
