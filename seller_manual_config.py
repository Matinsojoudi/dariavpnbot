"""Seller manual VPN config creation (deducts from seller traffic quota)."""

import uuid
import sqlite3
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from env import settings
from seller_context import get_effective_seller_id, can_access_seller_panel
from traffic_service import (
    get_remaining_gb,
    has_enough_traffic,
    deduct_traffic,
    refund_traffic,
    check_and_alert_low_traffic,
)

_pending_manual = {}


def _is_seller(chat_id):
    return can_access_seller_panel(chat_id)


def _next_username(seller_id):
    with sqlite3.connect(settings.database, timeout=30) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT username_prefix, user_sequence FROM seller_configs WHERE seller_id = ?",
            (seller_id,),
        )
        row = c.fetchone()
        if row and row[0]:
            prefix, seq = row[0], row[1] or 1000
            name = f"{prefix}{seq}"
            c.execute(
                "UPDATE seller_configs SET user_sequence = user_sequence + 1 WHERE seller_id = ?",
                (seller_id,),
            )
            conn.commit()
            return name
    return f"Seller{seller_id}_{uuid.uuid4().hex[:6]}"


def _list_manual_configs(seller_id, limit=15):
    with sqlite3.connect(settings.database, timeout=30) as conn:
        c = conn.cursor()
        c.execute(
            """SELECT id, service_uuid, created_at FROM receipts
               WHERE seller_id = ? AND type = 'seller_manual' AND status = 'approved'
               ORDER BY id DESC LIMIT ?""",
            (seller_id, limit),
        )
        return c.fetchall()


def register_seller_manual_config_handlers(bot):

    @bot.message_handler(func=lambda m: m.text == "➕ ساخت کانفیگ دستی")
    def manual_config_start(message):
        chat_id = message.chat.id
        if not _is_seller(chat_id):
            bot.send_message(chat_id, "❌ این بخش فقط برای فروشندگان است.")
            return

        remaining = get_remaining_gb(get_effective_seller_id(chat_id))
        if remaining <= 0:
            bot.send_message(
                chat_id,
                "❌ <b>ترافیک شما تمام شده است.</b>\n\n"
                "برای ساخت کانفیگ جدید، ابتدا از منوی "
                "<b>🔄 تمدید / خرید ترافیک</b> حجم خریداری کنید.",
                parse_mode="HTML",
            )
            return

        from buttons import back_markup
        msg = (
            f"➕ <b>ساخت کانفیگ دستی</b>\n\n"
            f"🟢 ترافیک باقیمانده شما: <b>{remaining:.1f} GB</b>\n\n"
            "لطفاً <b>نام کاربر</b> را وارد کنید (انگلیسی، بدون فاصله)\n"
            "یا برای نام‌گذاری خودکار عبارت <code>-</code> را بفرستید:"
        )
        sent = bot.send_message(chat_id, msg, parse_mode="HTML", reply_markup=back_markup)
        bot.register_next_step_handler(sent, manual_config_step_gb, bot)

    def manual_config_step_gb(message, bot):
        from buttons import get_seller_markup
        chat_id = message.chat.id

        if message.text == "برگشت 🔙":
            bot.send_message(chat_id, "عملیات لغو شد.", reply_markup=get_seller_markup(chat_id))
            return

        name = None if message.text.strip() == "-" else message.text.strip()
        if name and (" " in name or len(name) < 2):
            bot.send_message(chat_id, "❌ نام نامعتبر است. فقط حروف/اعداد انگلیسی بدون فاصله.")
            return

        from buttons import back_markup
        msg = bot.send_message(
            chat_id,
            "لطفاً <b>حجم کانفیگ</b> را به گیگابایت وارد کنید:\n(مثلا: 30)",
            parse_mode="HTML",
            reply_markup=back_markup,
        )
        bot.register_next_step_handler(msg, manual_config_step_days, bot, name)

    def manual_config_step_days(message, bot, name):
        from buttons import get_seller_markup
        chat_id = message.chat.id

        if message.text == "برگشت 🔙":
            bot.send_message(chat_id, "عملیات لغو شد.", reply_markup=get_seller_markup(chat_id))
            return

        try:
            gb = float(message.text)
            if gb <= 0:
                raise ValueError()
        except ValueError:
            bot.send_message(chat_id, "❌ حجم نامعتبر است.")
            return

        remaining = get_remaining_gb(get_effective_seller_id(chat_id))
        if not has_enough_traffic(get_effective_seller_id(chat_id), gb):
            bot.send_message(
                chat_id,
                f"❌ ترافیک کافی ندارید.\nباقیمانده: <b>{remaining:.1f} GB</b> — درخواستی: <b>{gb} GB</b>",
                parse_mode="HTML",
                reply_markup=get_seller_markup(chat_id),
            )
            return

        from buttons import back_markup
        msg = bot.send_message(
            chat_id,
            f"حجم: <b>{gb} GB</b>\n\nلطفاً <b>مدت اعتبار</b> را به روز وارد کنید:\n(مثلا: 30)",
            parse_mode="HTML",
            reply_markup=back_markup,
        )
        bot.register_next_step_handler(msg, manual_config_confirm, bot, name, gb)

    def manual_config_confirm(message, bot, name, gb):
        from buttons import get_seller_markup
        chat_id = message.chat.id

        if message.text == "برگشت 🔙":
            bot.send_message(chat_id, "عملیات لغو شد.", reply_markup=get_seller_markup(chat_id))
            return

        try:
            days = int(message.text)
            if days <= 0:
                raise ValueError()
        except ValueError:
            bot.send_message(chat_id, "❌ تعداد روز نامعتبر است.")
            return

        display_name = name if name else "(نام خودکار با پیش‌وند شما)"
        remaining = get_remaining_gb(get_effective_seller_id(chat_id))

        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("✅ تأیید و ساخت", callback_data="seller_manual_confirm"),
            InlineKeyboardButton("❌ لغو", callback_data="seller_manual_cancel"),
        )

        bot.send_message(
            chat_id,
            f"📋 <b>خلاصه کانفیگ</b>\n\n"
            f"👤 نام: <code>{display_name}</code>\n"
            f"📦 حجم: <b>{gb} GB</b>\n"
            f"⏳ اعتبار: <b>{days} روز</b>\n"
            f"🟢 ترافیک پس از ساخت: <b>{remaining - gb:.1f} GB</b>\n\n"
            "آیا تأیید می‌کنید؟",
            parse_mode="HTML",
            reply_markup=markup,
        )

        _pending_manual[chat_id] = {"name": name, "gb": gb, "days": days}

    @bot.message_handler(func=lambda m: m.text == "📋 کانفیگ‌های دستی من")
    def list_manual_configs(message):
        chat_id = message.chat.id
        if not _is_seller(chat_id):
            bot.send_message(chat_id, "❌ این بخش فقط برای فروشندگان است.")
            return

        rows = _list_manual_configs(get_effective_seller_id(chat_id))
        if not rows:
            bot.send_message(chat_id, "شما هنوز کانفیگ دستی نساخته‌اید.")
            return

        from hiddify.client import HiddifyClient
        client = HiddifyClient()
        client.reload_config()

        bot.send_message(chat_id, f"📋 <b>آخرین {len(rows)} کانفیگ دستی شما:</b>", parse_mode="HTML")
        for rid, svc_uuid, created in rows:
            if not svc_uuid:
                continue
            try:
                info = client.get_user(svc_uuid)
                uname = info.get("name", "—")
                limit_gb = info.get("usage_limit_GB", 0)
                pkg_days = info.get("package_days", 0)
                sub_link = client.get_sub_link(svc_uuid, uname)
                msg = (
                    f"🆔 #{rid} | 📅 {created}\n"
                    f"👤 <code>{uname}</code> | 📦 {limit_gb}GB | ⏳ {pkg_days}روز\n"
                    f"🔗 {sub_link}"
                )
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("🔗 اتصال", url=sub_link))
                bot.send_message(
                    chat_id, msg, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True
                )
            except Exception:
                bot.send_message(chat_id, f"🆔 #{rid} — UUID: <code>{svc_uuid}</code>", parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "seller_manual_cancel")
    def manual_config_cancel(call):
        from buttons import get_seller_markup
        _pending_manual.pop(call.message.chat.id, None)
        bot.edit_message_text(
            "❌ ساخت کانفیگ لغو شد.",
            call.message.chat.id,
            call.message.message_id,
        )
        bot.send_message(
            call.message.chat.id,
            "به پنل فروشنده برگشتید.",
            reply_markup=get_seller_markup(call.message.chat.id),
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data == "seller_manual_confirm")
    def manual_config_create(call):
        from buttons import get_seller_markup
        from customer import send_package_with_qr
        from hiddify.client import HiddifyClient
        from hiddify.exceptions import HiddifyAPIError

        chat_id = call.message.chat.id
        if not _is_seller(chat_id):
            bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
            return

        pending = _pending_manual.pop(chat_id, None)
        if not pending:
            bot.answer_callback_query(call.id, "درخواست منقضی شده. دوباره شروع کنید.", show_alert=True)
            return

        gb = pending["gb"]
        days = pending["days"]
        seller_id = get_effective_seller_id(chat_id)
        user_name = pending["name"] or _next_username(seller_id)

        if not has_enough_traffic(seller_id, gb):
            remaining = get_remaining_gb(seller_id)
            bot.answer_callback_query(call.id, "ترافیک کافی نیست!", show_alert=True)
            bot.send_message(
                chat_id,
                f"❌ ترافیک کافی ندارید.\nباقیمانده: {remaining:.1f} GB",
                reply_markup=get_seller_markup(chat_id),
            )
            return

        bot.answer_callback_query(call.id, "در حال ساخت کانفیگ...")

        receipt_id = None
        traffic_deducted = False

        def _fail_user(message_text):
            try:
                bot.edit_message_text(
                    "❌ ساخت کانفیگ ناموفق بود.",
                    chat_id,
                    call.message.message_id,
                )
            except Exception:
                pass
            bot.send_message(
                chat_id,
                message_text,
                parse_mode="HTML",
                reply_markup=get_seller_markup(chat_id),
            )

        try:
            if not deduct_traffic(seller_id, gb):
                _fail_user("❌ ترافیک کافی نیست یا خطا در کسر حجم رخ داد.")
                return
            traffic_deducted = True

            with sqlite3.connect(settings.database, timeout=30) as conn:
                c = conn.cursor()
                c.execute(
                    """INSERT INTO receipts (user_id, seller_id, type, amount, status)
                       VALUES (?, ?, 'seller_manual', 0, 'approved')""",
                    (chat_id, seller_id),
                )
                receipt_id = c.lastrowid
                conn.commit()

            client = HiddifyClient()
            client.reload_config()
            new_uuid = str(uuid.uuid4())

            client.create_user({
                "name": user_name,
                "uuid": new_uuid,
                "usage_limit_GB": gb,
                "package_days": days,
                "comment": f"Manual by seller {seller_id}",
                "enable": True,
                "mode": "no_reset",
            })

            user_info = client.get_user(new_uuid)
            if not user_info or not user_info.get("uuid"):
                raise HiddifyAPIError("کاربر روی پنل ساخته نشد یا قابل بازیابی نیست")

            sub_link = client.get_sub_link(new_uuid, user_name)

            with sqlite3.connect(settings.database, timeout=30) as conn:
                c = conn.cursor()
                c.execute(
                    "UPDATE receipts SET service_uuid = ? WHERE id = ?",
                    (new_uuid, receipt_id),
                )
                conn.commit()

            remaining = get_remaining_gb(seller_id)
            msg_text = (
                f"✅ <b>کانفیگ با موفقیت ساخته شد!</b>\n\n"
                f"👤 نام: <code>{user_name}</code>\n"
                f"📦 حجم: <b>{gb} GB</b>\n"
                f"⏳ اعتبار: <b>{days} روز</b>\n"
                f"🟢 ترافیک باقیمانده: <b>{remaining:.1f} GB</b>\n\n"
                f"🔗 لینک ساب:\n{sub_link}"
            )
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("🔗 اتصال سریع", url=sub_link))

            try:
                bot.delete_message(chat_id, call.message.message_id)
            except Exception:
                pass
            bot.send_message(
                chat_id,
                "✅ کانفیگ ساخته شد — در پیام بعدی ارسال می‌شود.",
                reply_markup=get_seller_markup(chat_id),
            )
            send_package_with_qr(bot, chat_id, msg_text, sub_link, markup)
            check_and_alert_low_traffic(bot, chat_id)

        except sqlite3.OperationalError as e:
            if traffic_deducted:
                refund_traffic(seller_id, gb)
            if receipt_id:
                with sqlite3.connect(settings.database, timeout=30) as conn:
                    c = conn.cursor()
                    c.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))
                    conn.commit()
            _fail_user(
                "❌ خطا در دسترسی به دیتابیس.\n"
                f"<code>{e}</code>\n"
                "ترافیک به حساب شما بازگردانده شد. لطفاً چند ثانیه بعد دوباره تلاش کنید."
            )
        except Exception as e:
            if traffic_deducted:
                refund_traffic(seller_id, gb)
            if receipt_id:
                with sqlite3.connect(settings.database, timeout=30) as conn:
                    c = conn.cursor()
                    c.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))
                    conn.commit()
            _fail_user(
                f"❌ خطا در ساخت کانفیگ:\n<code>{e}</code>\n"
                "ترافیک به حساب شما بازگردانده شد."
            )
