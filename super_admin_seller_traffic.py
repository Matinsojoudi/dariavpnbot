"""Super-admin manual increase/decrease of the configured seller's bulk traffic."""

import sqlite3
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from env import settings
from traffic_service import get_seller_stats, adjust_seller_total_gb, check_and_alert_low_traffic
from seller_context import get_single_seller_id


def _is_super_admin(chat_id):
    main = __import__("main")
    return (int(chat_id) in settings.admin_list) or (int(chat_id) in main.get_admin_ids())


def _seller_label(seller_id):
    with sqlite3.connect(settings.database) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT nickname, username_prefix FROM seller_configs WHERE seller_id = ?",
            (seller_id,),
        )
        row = c.fetchone()
        c.execute("SELECT value FROM bot_settings WHERE key = 'SINGLE_SELLER_PREFIX'")
        prefix_row = c.fetchone()
    nickname = (row[0] if row and row[0] else None) or "فروشنده"
    prefix = (row[1] if row and row[1] else None) or (prefix_row[0] if prefix_row else "—")
    return nickname, prefix


def _dashboard_text(seller_id):
    stats = get_seller_stats(seller_id)
    nickname, prefix = _seller_label(seller_id)
    if not stats:
        total = used = rem = 0.0
    else:
        total, used, rem = stats
    return (
        "📶 <b>مدیریت حجم فروشنده</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 فروشنده: <b>{nickname}</b>\n"
        f"🆔 آیدی: <code>{seller_id}</code>\n"
        f"🏷 پیشوند: <code>{prefix}</code>\n\n"
        f"📦 کل حجم: <b>{total:g} GB</b>\n"
        f"📉 مصرف‌شده: <b>{used:g} GB</b>\n"
        f"🟢 مانده: <b>{rem:g} GB</b>\n\n"
        "از دکمه‌های زیر برای افزایش یا کاهش دستی حجم استفاده کنید."
    )


def _dashboard_markup():
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("➕ افزایش حجم", callback_data="sa_traffic_inc"),
        InlineKeyboardButton("➖ کاهش حجم", callback_data="sa_traffic_dec"),
    )
    markup.row(InlineKeyboardButton("🔄 بروزرسانی", callback_data="sa_traffic_refresh"))
    return markup


def register_super_admin_seller_traffic_handlers(bot):

    @bot.message_handler(func=lambda m: m.text == "📶 مدیریت حجم فروشنده")
    def seller_traffic_admin_menu(message):
        chat_id = message.chat.id
        if not _is_super_admin(chat_id):
            return
        seller_id = get_single_seller_id()
        if not seller_id:
            bot.send_message(
                chat_id,
                "❌ هنوز فروشنده‌ای تنظیم نشده است.\n"
                "ابتدا از منوی <b>👤 تنظیم فروشنده</b> فروشنده را تعریف کنید.",
                parse_mode="HTML",
                reply_markup=__import__("buttons").super_admin_markup,
            )
            return
        bot.send_message(
            chat_id,
            _dashboard_text(seller_id),
            reply_markup=_dashboard_markup(),
            parse_mode="HTML",
        )

    @bot.callback_query_handler(func=lambda c: c.data == "sa_traffic_refresh")
    def sa_traffic_refresh(call):
        if not _is_super_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
            return
        seller_id = get_single_seller_id()
        if not seller_id:
            bot.answer_callback_query(call.id, "فروشنده تنظیم نشده.", show_alert=True)
            return
        try:
            bot.edit_message_text(
                _dashboard_text(seller_id),
                call.message.chat.id,
                call.message.message_id,
                reply_markup=_dashboard_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        bot.answer_callback_query(call.id, "بروزرسانی شد")

    @bot.callback_query_handler(func=lambda c: c.data in ("sa_traffic_inc", "sa_traffic_dec"))
    def sa_traffic_ask_amount(call):
        if not _is_super_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
            return
        seller_id = get_single_seller_id()
        if not seller_id:
            bot.answer_callback_query(call.id, "فروشنده تنظیم نشده.", show_alert=True)
            return

        action = "inc" if call.data == "sa_traffic_inc" else "dec"
        action_fa = "افزایش" if action == "inc" else "کاهش"
        from buttons import back_markup

        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            call.message.chat.id,
            f"📶 <b>{action_fa} حجم فروشنده</b>\n"
            f"فروشنده: <code>{seller_id}</code>\n\n"
            "مقدار را به <b>گیگابایت</b> وارد کنید (مثلاً <code>50</code> یا <code>100.5</code>):",
            parse_mode="HTML",
            reply_markup=back_markup,
        )
        bot.register_next_step_handler(msg, _apply_traffic_change, bot, seller_id, action)

    def _apply_traffic_change(message, bot, seller_id, action):
        from buttons import super_admin_markup

        chat_id = message.chat.id
        if not _is_super_admin(chat_id):
            return
        if message.text == "برگشت 🔙":
            bot.send_message(chat_id, "عملیات لغو شد.", reply_markup=super_admin_markup)
            return

        try:
            amount = float(str(message.text).strip().replace(",", ""))
            if amount <= 0:
                raise ValueError("non-positive")
        except (TypeError, ValueError):
            bot.send_message(
                chat_id,
                "❌ مقدار نامعتبر است. یک عدد مثبت وارد کنید.",
                reply_markup=super_admin_markup,
            )
            return

        delta = amount if action == "inc" else -amount
        result = adjust_seller_total_gb(seller_id, delta)
        if not result["ok"]:
            if result["error"] == "cannot_decrease_below_used":
                bot.send_message(
                    chat_id,
                    "❌ امکان کاهش بیشتر وجود ندارد.\n"
                    f"حجم مصرف‌شده فروشنده <b>{result['used']:g} GB</b> است و "
                    "کل حجم نمی‌تواند از این مقدار کمتر شود.",
                    parse_mode="HTML",
                    reply_markup=super_admin_markup,
                )
            elif result["error"] == "seller_not_found":
                bot.send_message(
                    chat_id,
                    "❌ فروشنده یافت نشد. ابتدا فروشنده را تنظیم کنید.",
                    reply_markup=super_admin_markup,
                )
            else:
                bot.send_message(chat_id, "❌ عملیات ناموفق بود.", reply_markup=super_admin_markup)
            return

        applied = result["delta_applied"]
        if action == "inc":
            admin_msg = (
                f"✅ <b>{applied:g} GB</b> به حجم فروشنده اضافه شد.\n\n"
                f"👤 فروشنده: <code>{seller_id}</code>\n"
                f"📦 قبل: <b>{result['old_total']:g} GB</b> → بعد: <b>{result['new_total']:g} GB</b>\n"
                f"🟢 مانده فعلی: <b>{result['remaining']:g} GB</b>"
            )
            seller_msg = (
                "🎉 <b>افزایش حجم توسط مدیریت</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"➕ مقدار اضافه‌شده: <b>{applied:g} GB</b>\n"
                f"📦 کل حجم جدید: <b>{result['new_total']:g} GB</b>\n"
                f"🟢 مانده شما: <b>{result['remaining']:g} GB</b>\n\n"
                "حجم جدید روی حساب فروشندگی شما اعمال شد."
            )
        else:
            reduced = abs(applied)
            admin_msg = (
                f"✅ <b>{reduced:g} GB</b> از حجم فروشنده کسر شد.\n\n"
                f"👤 فروشنده: <code>{seller_id}</code>\n"
                f"📦 قبل: <b>{result['old_total']:g} GB</b> → بعد: <b>{result['new_total']:g} GB</b>\n"
                f"🟢 مانده فعلی: <b>{result['remaining']:g} GB</b>"
            )
            seller_msg = (
                "⚠️ <b>کاهش حجم توسط مدیریت</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"➖ مقدار کسرشده: <b>{reduced:g} GB</b>\n"
                f"📦 کل حجم جدید: <b>{result['new_total']:g} GB</b>\n"
                f"🟢 مانده شما: <b>{result['remaining']:g} GB</b>\n\n"
                "در صورت نیاز با پشتیبانی هماهنگ کنید."
            )

        bot.send_message(chat_id, admin_msg, parse_mode="HTML", reply_markup=super_admin_markup)
        try:
            bot.send_message(seller_id, seller_msg, parse_mode="HTML")
        except Exception:
            bot.send_message(
                chat_id,
                "⚠️ تغییر حجم اعمال شد، اما ارسال پیام به فروشنده ممکن نشد "
                "(احتمالاً هنوز ربات را استارت نکرده).",
            )

        try:
            check_and_alert_low_traffic(bot, seller_id)
        except Exception:
            pass
