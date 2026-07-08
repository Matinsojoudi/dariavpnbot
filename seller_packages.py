"""Seller package management — create, edit, delete customer-facing VPN packages."""

import sqlite3
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from env import settings

_pending_edit = {}  # chat_id -> {"pkg_id": int, "field": str} or {"create": True, "step": str}


def _cancel_create_flow(bot, chat_id):
    state = _pending_edit.get(chat_id)
    if not state or not state.get("create"):
        return False
    _pending_edit.pop(chat_id, None)
    from buttons import get_seller_markup
    bot.send_message(
        chat_id,
        "❌ ایجاد بسته لغو شد.\nبه پنل فروشنده برگشتید.",
        reply_markup=get_seller_markup(chat_id),
    )
    return True


def _send_create_prompt(bot, chat_id, text):
    from buttons import back_markup
    footer = (
        "\n\n━━━━━━━━━━━━━━━━━━\n"
        "👇 برای لغو کامل و خروج از مراحل، دکمه <b>برگشت 🔙</b> پایین صفحه را بزنید."
    )
    bot.send_message(chat_id, text + footer, parse_mode="HTML", reply_markup=back_markup)


def _is_seller(chat_id):
    if int(chat_id) in settings.admin_list:
        return True
    with sqlite3.connect(settings.database) as conn:
        c = conn.cursor()
        c.execute("SELECT role FROM users WHERE user_id = ?", (chat_id,))
        row = c.fetchone()
    return bool(row and row[0] == "seller")


def _get_seller_packages(seller_id):
    with sqlite3.connect(settings.database) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, name, gb, days, price_toman FROM packages WHERE seller_id = ? ORDER BY id DESC",
            (seller_id,),
        )
        return c.fetchall()


def _get_package(pkg_id, seller_id):
    with sqlite3.connect(settings.database) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, name, gb, days, price_toman FROM packages WHERE id = ? AND seller_id = ?",
            (pkg_id, seller_id),
        )
        return c.fetchone()


def _format_package_card(pkg, index=None):
    pid, name, gb, days, price = pkg
    prefix = f"{index}. " if index else ""
    gb_txt = f"{gb:g}" if float(gb) == int(gb) else f"{gb:.1f}"
    return (
        f"{prefix}<b>{name}</b>\n"
        f"   📊 {gb_txt} GB  |  ⏳ {days} روز  |  💰 {price:,} تومان"
    )


def _detail_message(pkg):
    _, name, gb, days, price = pkg
    gb_txt = f"{gb:g}" if float(gb) == int(gb) else f"{gb:.1f}"
    return (
        "📦 <b>جزئیات بسته</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🏷 <b>نام:</b> {name}\n"
        f"📊 <b>حجم:</b> {gb_txt} گیگابایت\n"
        f"⏳ <b>مدت:</b> {days} روز\n"
        f"💰 <b>قیمت:</b> {price:,} تومان\n\n"
        "برای ویرایش، یکی از گزینه‌های زیر را انتخاب کنید:"
    )


def _list_message(packages):
    msg = "📦 <b>مدیریت بسته‌های فروش</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━\n\n"
    if not packages:
        msg += "هنوز بسته‌ای تعریف نکرده‌اید.\n"
        msg += "با دکمه <b>➕ بسته جدید</b> اولین بسته را بسازید."
    else:
        msg += f"📋 تعداد بسته‌ها: <b>{len(packages)}</b>\n\n"
        for i, pkg in enumerate(packages, 1):
            msg += _format_package_card(pkg, i) + "\n\n"
        msg += "روی نام هر بسته بزنید تا ویرایش یا حذف کنید."
    return msg


def _list_markup(packages):
    markup = InlineKeyboardMarkup()
    for pkg in packages:
        pid, name, gb, days, price = pkg
        gb_short = f"{gb:g}" if float(gb) == int(gb) else f"{gb:.1f}"
        label = f"✏️ {name[:18]} | {gb_short}GB"
        markup.add(InlineKeyboardButton(label, callback_data=f"spkg_view_{pid}"))
    markup.row(
        InlineKeyboardButton("➕ بسته جدید", callback_data="spkg_new"),
        InlineKeyboardButton("🔄 بروزرسانی", callback_data="spkg_list"),
    )
    return markup


def _detail_markup(pkg_id):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("🏷 نام", callback_data=f"spkg_edit_{pkg_id}_name"),
        InlineKeyboardButton("📊 حجم", callback_data=f"spkg_edit_{pkg_id}_gb"),
    )
    markup.row(
        InlineKeyboardButton("⏳ مدت", callback_data=f"spkg_edit_{pkg_id}_days"),
        InlineKeyboardButton("💰 قیمت", callback_data=f"spkg_edit_{pkg_id}_price"),
    )
    markup.row(InlineKeyboardButton("🗑 حذف بسته", callback_data=f"spkg_del_{pkg_id}"))
    markup.row(InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="spkg_list"))
    return markup


def _delete_confirm_markup(pkg_id):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("✅ بله، حذف شود", callback_data=f"spkg_delok_{pkg_id}"),
        InlineKeyboardButton("❌ انصراف", callback_data=f"spkg_view_{pkg_id}"),
    )
    return markup


def _show_list(bot, chat_id, message_id=None):
    packages = _get_seller_packages(chat_id)
    text = _list_message(packages)
    markup = _list_markup(packages)
    if message_id:
        try:
            bot.edit_message_text(
                text, chat_id, message_id, reply_markup=markup, parse_mode="HTML"
            )
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")


def _show_detail(bot, call, pkg_id):
    pkg = _get_package(pkg_id, call.message.chat.id)
    if not pkg:
        bot.answer_callback_query(call.id, "بسته یافت نشد.", show_alert=True)
        return
    try:
        bot.edit_message_text(
            _detail_message(pkg),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=_detail_markup(pkg_id),
            parse_mode="HTML",
        )
    except Exception:
        bot.send_message(
            call.message.chat.id,
            _detail_message(pkg),
            reply_markup=_detail_markup(pkg_id),
            parse_mode="HTML",
        )
    bot.answer_callback_query(call.id)


def register_seller_package_handlers(bot):

    @bot.message_handler(
        func=lambda m: m.text == "برگشت 🔙"
        and m.chat.id in _pending_edit
        and _pending_edit[m.chat.id].get("create")
    )
    def spkg_abort_create_keyboard(message):
        """Cancel package creation from reply keyboard back button."""
        _cancel_create_flow(bot, message.chat.id)

    @bot.message_handler(func=lambda m: m.text == "📦 مدیریت بسته‌های من")
    def seller_packages_menu(message):
        chat_id = message.chat.id
        if not _is_seller(chat_id):
            bot.send_message(chat_id, "❌ این بخش فقط برای فروشندگان است.")
            return
        _show_list(bot, chat_id)

    @bot.callback_query_handler(func=lambda c: c.data == "spkg_list")
    def spkg_list(call):
        if not _is_seller(call.message.chat.id):
            bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
            return
        _show_list(bot, call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("spkg_view_"))
    def spkg_view(call):
        if not _is_seller(call.message.chat.id):
            bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
            return
        pkg_id = int(call.data.split("_")[2])
        _show_detail(bot, call, pkg_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("spkg_del_") and not c.data.startswith("spkg_delok_"))
    def spkg_delete_confirm(call):
        if not _is_seller(call.message.chat.id):
            bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
            return
        pkg_id = int(call.data.split("_")[2])
        pkg = _get_package(pkg_id, call.message.chat.id)
        if not pkg:
            bot.answer_callback_query(call.id, "بسته یافت نشد.", show_alert=True)
            return
        name = pkg[1]
        try:
            bot.edit_message_text(
                f"⚠️ <b>حذف بسته</b>\n\n"
                f"آیا از حذف بسته <b>{name}</b> مطمئن هستید؟\n\n"
                "این عمل قابل بازگشت نیست.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=_delete_confirm_markup(pkg_id),
                parse_mode="HTML",
            )
        except Exception:
            pass
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("spkg_delok_"))
    def spkg_delete(call):
        if not _is_seller(call.message.chat.id):
            bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
            return
        pkg_id = int(call.data.split("_")[2])
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute(
                "DELETE FROM packages WHERE id = ? AND seller_id = ?",
                (pkg_id, call.message.chat.id),
            )
            deleted = c.rowcount
            conn.commit()
        if not deleted:
            bot.answer_callback_query(call.id, "بسته یافت نشد.", show_alert=True)
            return
        bot.answer_callback_query(call.id, "✅ بسته حذف شد.")
        _show_list(bot, call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("spkg_edit_"))
    def spkg_edit_start(call):
        if not _is_seller(call.message.chat.id):
            bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
            return
        parts = call.data.split("_")
        pkg_id = int(parts[2])
        field = parts[3]
        pkg = _get_package(pkg_id, call.message.chat.id)
        if not pkg:
            bot.answer_callback_query(call.id, "بسته یافت نشد.", show_alert=True)
            return

        prompts = {
            "name": ("🏷 <b>ویرایش نام بسته</b>\n\nنام فعلی: <b>{}</b>\n\nنام جدید را ارسال کنید:", pkg[1]),
            "gb": ("📊 <b>ویرایش حجم</b>\n\nحجم فعلی: <b>{} GB</b>\n\nحجم جدید (گیگابایت) را ارسال کنید:", pkg[2]),
            "days": ("⏳ <b>ویرایش مدت</b>\n\nمدت فعلی: <b>{} روز</b>\n\nتعداد روز جدید را ارسال کنید:", pkg[3]),
            "price": ("💰 <b>ویرایش قیمت</b>\n\nقیمت فعلی: <b>{:,} تومان</b>\n\nقیمت جدید (تومان) را ارسال کنید:", pkg[4]),
        }
        if field not in prompts:
            bot.answer_callback_query(call.id, "فیلد نامعتبر.", show_alert=True)
            return

        chat_id = call.message.chat.id
        _pending_edit[chat_id] = {"pkg_id": pkg_id, "field": field}
        from buttons import back_markup
        tpl, current = prompts[field]
        if field == "price":
            prompt = tpl.format(current)
        elif field == "gb":
            gb_txt = f"{current:g}" if float(current) == int(current) else f"{current:.1f}"
            prompt = tpl.format(gb_txt)
        else:
            prompt = tpl.format(current)

        bot.send_message(chat_id, prompt, parse_mode="HTML", reply_markup=back_markup)
        bot.register_next_step_handler_by_chat_id(chat_id, spkg_edit_save, bot)
        bot.answer_callback_query(call.id)

    def spkg_edit_save(message, bot):
        from buttons import get_seller_markup
        chat_id = message.chat.id
        pending = _pending_edit.pop(chat_id, None)
        if not pending:
            return
        if message.text == "برگشت 🔙":
            bot.send_message(chat_id, "ویرایش لغو شد.", reply_markup=get_seller_markup(chat_id))
            pkg = _get_package(pending["pkg_id"], chat_id)
            if pkg:
                bot.send_message(
                    chat_id,
                    _detail_message(pkg),
                    reply_markup=_detail_markup(pending["pkg_id"]),
                    parse_mode="HTML",
                )
            return

        pkg_id = pending["pkg_id"]
        field = pending["field"]
        col_map = {"name": "name", "gb": "gb", "days": "days", "price": "price_toman"}
        db_col = col_map[field]

        try:
            if field == "name":
                val = message.text.strip()
                if not val or len(val) > 60:
                    bot.send_message(chat_id, "❌ نام باید بین ۱ تا ۶۰ کاراکتر باشد.")
                    _pending_edit[chat_id] = pending
                    bot.register_next_step_handler_by_chat_id(chat_id, spkg_edit_save, bot)
                    return
            elif field == "gb":
                val = float(message.text.strip())
                if val <= 0:
                    raise ValueError
            elif field == "days":
                val = int(message.text.strip())
                if val <= 0:
                    raise ValueError
            elif field == "price":
                val = int(message.text.strip().replace(",", "").replace("،", ""))
                if val <= 0:
                    raise ValueError
            else:
                return
        except ValueError:
            bot.send_message(chat_id, "❌ مقدار نامعتبر است. دوباره تلاش کنید.")
            _pending_edit[chat_id] = pending
            bot.register_next_step_handler_by_chat_id(chat_id, spkg_edit_save, bot)
            return

        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute(
                f"UPDATE packages SET {db_col} = ? WHERE id = ? AND seller_id = ?",
                (val, pkg_id, chat_id),
            )
            if c.rowcount == 0:
                bot.send_message(chat_id, "❌ بسته یافت نشد.", reply_markup=get_seller_markup(chat_id))
                return
            conn.commit()

        pkg = _get_package(pkg_id, chat_id)
        field_labels = {"name": "نام", "gb": "حجم", "days": "مدت", "price": "قیمت"}
        bot.send_message(
            chat_id,
            f"✅ {field_labels[field]} بسته با موفقیت به‌روزرسانی شد.",
            reply_markup=get_seller_markup(chat_id),
        )
        if pkg:
            bot.send_message(
                chat_id,
                _detail_message(pkg),
                reply_markup=_detail_markup(pkg_id),
                parse_mode="HTML",
            )

    @bot.callback_query_handler(func=lambda c: c.data == "spkg_new")
    def spkg_new_start(call):
        if not _is_seller(call.message.chat.id):
            bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
            return
        chat_id = call.message.chat.id
        _pending_edit[chat_id] = {"create": True, "step": "name"}
        _send_create_prompt(
            bot,
            chat_id,
            "➕ <b>ایجاد بسته جدید</b>\n\n"
            "مرحله ۱ از ۴\n"
            "🏷 نام بسته را وارد کنید:\n"
            "<i>مثال: استاندارد یک ماهه</i>",
        )
        bot.register_next_step_handler_by_chat_id(chat_id, spkg_create_step, bot)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data == "spkg_cancel_create")
    def spkg_cancel_create(call):
        if _cancel_create_flow(bot, call.message.chat.id):
            bot.answer_callback_query(call.id, "ایجاد بسته لغو شد.")
        else:
            bot.answer_callback_query(call.id)

    def spkg_create_step(message, bot):
        from buttons import get_seller_markup
        chat_id = message.chat.id
        state = _pending_edit.get(chat_id)
        if not state or not state.get("create"):
            return

        if message.text == "برگشت 🔙":
            _cancel_create_flow(bot, chat_id)
            return

        step = state["step"]
        try:
            if step == "name":
                name = message.text.strip()
                if not name or len(name) > 60:
                    _send_create_prompt(
                        bot,
                        chat_id,
                        "❌ نام باید بین ۱ تا ۶۰ کاراکتر باشد.\n\n"
                        "مرحله ۱ از ۴\n🏷 نام بسته را دوباره وارد کنید:",
                    )
                    bot.register_next_step_handler_by_chat_id(chat_id, spkg_create_step, bot)
                    return
                state["name"] = name
                state["step"] = "gb"
                _send_create_prompt(
                    bot,
                    chat_id,
                    "مرحله ۲ از ۴\n📊 حجم بسته (گیگابایت):\n<i>مثال: 30</i>",
                )
            elif step == "gb":
                gb = float(message.text.strip())
                if gb <= 0:
                    raise ValueError
                state["gb"] = gb
                state["step"] = "days"
                _send_create_prompt(
                    bot,
                    chat_id,
                    "مرحله ۳ از ۴\n⏳ مدت بسته (روز):\n<i>مثال: 30</i>",
                )
            elif step == "days":
                days = int(message.text.strip())
                if days <= 0:
                    raise ValueError
                state["days"] = days
                state["step"] = "price"
                _send_create_prompt(
                    bot,
                    chat_id,
                    "مرحله ۴ از ۴\n💰 قیمت (تومان):\n<i>مثال: 150000</i>",
                )
            elif step == "price":
                price = int(message.text.strip().replace(",", "").replace("،", ""))
                if price <= 0:
                    raise ValueError
                with sqlite3.connect(settings.database) as conn:
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO packages (seller_id, name, gb, days, price_toman, price_usd) VALUES (?, ?, ?, ?, ?, ?)",
                        (chat_id, state["name"], state["gb"], state["days"], price, 0.0),
                    )
                    new_id = c.lastrowid
                    conn.commit()
                _pending_edit.pop(chat_id, None)
                pkg = _get_package(new_id, chat_id)
                bot.send_message(
                    chat_id,
                    f"✅ بسته <b>{state['name']}</b> با موفقیت ساخته شد!",
                    parse_mode="HTML",
                    reply_markup=get_seller_markup(chat_id),
                )
                if pkg:
                    bot.send_message(
                        chat_id,
                        _detail_message(pkg),
                        reply_markup=_detail_markup(new_id),
                        parse_mode="HTML",
                    )
                return
        except ValueError:
            step_labels = {
                "name": "۱ — نام",
                "gb": "۲ — حجم",
                "days": "۳ — مدت",
                "price": "۴ — قیمت",
            }
            _send_create_prompt(
                bot,
                chat_id,
                f"❌ مقدار نامعتبر است.\n\n"
                f"مرحله {step_labels.get(step, step)} را دوباره وارد کنید:",
            )
        bot.register_next_step_handler_by_chat_id(chat_id, spkg_create_step, bot)

    # Legacy callbacks — redirect to new UI
    @bot.callback_query_handler(func=lambda c: c.data == "seller_new_package")
    def legacy_new_package(call):
        spkg_new_start(call)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("seller_del_pkg_"))
    def legacy_del_package(call):
        if not _is_seller(call.message.chat.id):
            bot.answer_callback_query(call.id, "دسترسی ندارید.", show_alert=True)
            return
        pkg_id = int(call.data.split("_")[3])
        pkg = _get_package(pkg_id, call.message.chat.id)
        if not pkg:
            bot.answer_callback_query(call.id, "بسته یافت نشد.", show_alert=True)
            return
        try:
            bot.edit_message_text(
                f"⚠️ <b>حذف بسته</b>\n\nآیا از حذف <b>{pkg[1]}</b> مطمئن هستید؟",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=_delete_confirm_markup(pkg_id),
                parse_mode="HTML",
            )
        except Exception:
            bot.send_message(
                call.message.chat.id,
                f"⚠️ آیا از حذف <b>{pkg[1]}</b> مطمئن هستید؟",
                reply_markup=_delete_confirm_markup(pkg_id),
                parse_mode="HTML",
            )
        bot.answer_callback_query(call.id)
