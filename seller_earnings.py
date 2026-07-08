"""Seller sales earnings tracking and reporting."""

import sqlite3
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from env import settings

# Receipt types that count as seller revenue from customers
SALE_TYPES = ("package", "renew", "wallet", "charge")

TYPE_LABELS = {
    "package": "💳 خرید مستقیم",
    "wallet": "💰 خرید از کیف پول",
    "renew": "🔄 تمدید سرویس",
    "charge": "🔋 شارژ کیف پول مشتری",
}


def get_seller_earnings(seller_id):
    """Return earnings summary dict for a seller."""
    with sqlite3.connect(settings.database) as conn:
        c = conn.cursor()

        placeholders = ",".join("?" * len(SALE_TYPES))

        c.execute(
            f"""SELECT COALESCE(SUM(amount), 0), COUNT(*)
                FROM receipts
                WHERE seller_id = ? AND status = 'approved' AND type IN ({placeholders})""",
            (seller_id, *SALE_TYPES),
        )
        total_revenue, approved_count = c.fetchone()

        c.execute(
            f"""SELECT COALESCE(SUM(amount), 0), COUNT(*)
                FROM receipts
                WHERE seller_id = ? AND status = 'pending' AND type IN ({placeholders})""",
            (seller_id, *SALE_TYPES),
        )
        pending_amount, pending_count = c.fetchone()

        c.execute(
            f"""SELECT type, COUNT(*), COALESCE(SUM(amount), 0)
                FROM receipts
                WHERE seller_id = ? AND status = 'approved' AND type IN ({placeholders})
                GROUP BY type""",
            (seller_id, *SALE_TYPES),
        )
        by_type = {row[0]: (row[1], row[2]) for row in c.fetchall()}

        c.execute(
            f"""SELECT p.name, COUNT(*), COALESCE(SUM(r.amount), 0)
                FROM receipts r
                LEFT JOIN packages p ON p.id = r.package_id
                WHERE r.seller_id = ? AND r.status = 'approved'
                  AND r.type IN ('package', 'renew', 'wallet')
                  AND r.package_id IS NOT NULL
                GROUP BY r.package_id
                ORDER BY SUM(r.amount) DESC""",
            (seller_id,),
        )
        by_package = c.fetchall()

        c.execute(
            f"""SELECT r.id, r.type, r.amount, r.created_at, COALESCE(p.name, '—'), r.user_id
                FROM receipts r
                LEFT JOIN packages p ON p.id = r.package_id
                WHERE r.seller_id = ? AND r.status = 'approved' AND type IN ({placeholders})
                ORDER BY r.created_at DESC
                LIMIT 8""",
            (seller_id, *SALE_TYPES),
        )
        recent = c.fetchall()

        c.execute(
            "SELECT total_bulk_gb, used_bulk_gb FROM seller_configs WHERE seller_id = ?",
            (seller_id,),
        )
        traffic = c.fetchone()

        c.execute(
            "SELECT COUNT(*) FROM users WHERE parent_seller_id = ?",
            (seller_id,),
        )
        customers = c.fetchone()[0]

    total_revenue = total_revenue or 0
    approved_count = approved_count or 0
    pending_amount = pending_amount or 0
    pending_count = pending_count or 0

    return {
        "total_revenue": total_revenue,
        "approved_count": approved_count,
        "pending_amount": pending_amount,
        "pending_count": pending_count,
        "by_type": by_type,
        "by_package": by_package,
        "recent": recent,
        "traffic": traffic,
        "customers": customers or 0,
    }


def format_earnings_dashboard(seller_id):
    data = get_seller_earnings(seller_id)
    msg = "📊 <b>آمار فروش و درآمد شما</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━\n\n"

    msg += "💰 <b>درآمد کل:</b> "
    msg += f"<code>{data['total_revenue']:,}</code> تومان\n"
    msg += f"🛒 <b>فروش موفق:</b> {data['approved_count']} تراکنش\n"
    msg += f"👥 <b>مشتریان:</b> {data['customers']} نفر\n"

    if data["pending_count"]:
        msg += (
            f"⏳ <b>در انتظار تأیید:</b> {data['pending_count']} فیش "
            f"({data['pending_amount']:,} تومان)\n"
        )

    if data["by_type"]:
        msg += "\n📋 <b>تفکیک درآمد:</b>\n"
        for rtype in ("package", "wallet", "renew", "charge"):
            if rtype in data["by_type"]:
                cnt, amt = data["by_type"][rtype]
                label = TYPE_LABELS.get(rtype, rtype)
                msg += f"   {label}: <b>{cnt}</b> — <b>{amt:,}</b> ت\n"

    traffic = data["traffic"]
    if traffic:
        total_gb, used_gb = traffic
        rem = max(0.0, (total_gb or 0) - (used_gb or 0))
        msg += "\n📦 <b>ترافیک:</b>\n"
        msg += f"   کل: <code>{total_gb or 0:g} GB</code> | "
        msg += f"مصرف: <code>{used_gb or 0:g} GB</code> | "
        msg += f"مانده: <code>{rem:g} GB</code>\n"

    msg += "\nبرای جزئیات بیشتر از دکمه‌های زیر استفاده کنید."
    return msg


def format_recent_sales(seller_id):
    data = get_seller_earnings(seller_id)
    msg = "📋 <b>آخرین فروش‌های موفق</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━\n\n"
    if not data["recent"]:
        msg += "هنوز فروش ثبت‌شده‌ای ندارید."
        return msg

    for rid, rtype, amount, created, pkg_name, user_id in data["recent"]:
        label = TYPE_LABELS.get(rtype, rtype)
        date_txt = (created or "—")[:16]
        msg += f"🧾 #{rid} | {label}\n"
        msg += f"   📦 {pkg_name} | 💵 {amount:,} ت\n"
        msg += f"   👤 مشتری: <code>{user_id}</code> | 📅 {date_txt}\n\n"
    return msg


def format_package_breakdown(seller_id):
    data = get_seller_earnings(seller_id)
    msg = "📦 <b>درآمد به تفکیک بسته</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━\n\n"
    if not data["by_package"]:
        msg += "فروش بسته‌ای ثبت نشده است."
        return msg

    for name, cnt, amt in data["by_package"]:
        msg += f"🔹 <b>{name}</b>\n"
        msg += f"   {cnt} فروش — <b>{amt:,}</b> تومان\n\n"
    return msg


def _dashboard_markup():
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("📋 آخرین فروش‌ها", callback_data="earn_recent"),
        InlineKeyboardButton("📦 تفکیک بسته‌ها", callback_data="earn_packages"),
    )
    markup.row(InlineKeyboardButton("🔄 بروزرسانی", callback_data="earn_refresh"))
    return markup


def register_seller_earnings_handlers(bot):

    def _send_dashboard(chat_id, message_id=None):
        text = format_earnings_dashboard(chat_id)
        markup = _dashboard_markup()
        if message_id:
            try:
                bot.edit_message_text(
                    text, chat_id, message_id, reply_markup=markup, parse_mode="HTML"
                )
                return
            except Exception:
                pass
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(
        func=lambda m: m.text in ("📊 آمار فروش و درآمد", "📊 آمار فروش و حجم")
    )
    def seller_earnings_menu(message):
        chat_id = message.chat.id
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT role FROM users WHERE user_id = ?", (chat_id,))
            row = c.fetchone()
        if not row or row[0] != "seller":
            if int(chat_id) not in settings.admin_list:
                bot.send_message(chat_id, "❌ این بخش فقط برای فروشندگان است.")
                return
        _send_dashboard(chat_id)

    @bot.callback_query_handler(func=lambda c: c.data == "earn_refresh")
    def earn_refresh(call):
        _send_dashboard(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "بروزرسانی شد")

    @bot.callback_query_handler(func=lambda c: c.data == "earn_recent")
    def earn_recent(call):
        chat_id = call.message.chat.id
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🔙 بازگشت", callback_data="earn_refresh"))
        bot.edit_message_text(
            format_recent_sales(chat_id),
            chat_id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML",
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data == "earn_packages")
    def earn_packages(call):
        chat_id = call.message.chat.id
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🔙 بازگشت", callback_data="earn_refresh"))
        bot.edit_message_text(
            format_package_breakdown(chat_id),
            chat_id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML",
        )
        bot.answer_callback_query(call.id)
