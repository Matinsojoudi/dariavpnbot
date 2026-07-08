"""Shared traffic (bulk GB) logic for sellers and customers."""

import sqlite3
from env import settings

LOW_TRAFFIC_THRESHOLD_GB = 20.0

CUSTOMER_NO_TRAFFIC_MSG = (
    "⚙️ <b>سرویس‌های ما در حال آپدیت هستند.</b>\n\n"
    "لطفاً کمی بعد دوباره تلاش کنید."
)


def _conn():
    return sqlite3.connect(settings.database)


def get_seller_stats(seller_id):
    """Return (total_bulk_gb, used_bulk_gb, remaining_gb) or None."""
    with _conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT total_bulk_gb, used_bulk_gb FROM seller_configs WHERE seller_id = ?",
            (seller_id,),
        )
        row = c.fetchone()
    if not row:
        return None
    total, used = row[0] or 0.0, row[1] or 0.0
    return total, used, max(0.0, total - used)


def get_remaining_gb(seller_id):
    stats = get_seller_stats(seller_id)
    return stats[2] if stats else 0.0


def has_enough_traffic(seller_id, needed_gb):
    return get_remaining_gb(seller_id) >= float(needed_gb)


def deduct_traffic(seller_id, gb):
    """Atomically deduct used traffic. Returns True on success."""
    gb = float(gb)
    with _conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT total_bulk_gb, used_bulk_gb FROM seller_configs WHERE seller_id = ?",
            (seller_id,),
        )
        row = c.fetchone()
        if not row or (row[0] - row[1]) < gb:
            return False
        c.execute(
            "UPDATE seller_configs SET used_bulk_gb = used_bulk_gb + ? WHERE seller_id = ?",
            (gb, seller_id),
        )
        conn.commit()
    return True


def force_deduct_traffic(seller_id, gb):
    """Deduct traffic even if it goes below zero / exceeds total."""
    gb = float(gb)
    with _conn() as conn:
        c = conn.cursor()
        c.execute("SELECT seller_id FROM seller_configs WHERE seller_id = ?", (seller_id,))
        if not c.fetchone():
            c.execute("INSERT INTO seller_configs (seller_id, total_bulk_gb, used_bulk_gb) VALUES (?, 0.0, 0.0)", (seller_id,))
        c.execute(
            "UPDATE seller_configs SET used_bulk_gb = used_bulk_gb + ? WHERE seller_id = ?",
            (gb, seller_id),
        )
        conn.commit()


def refund_traffic(seller_id, gb):
    gb = float(gb)
    with _conn() as conn:
        c = conn.cursor()
        c.execute("SELECT used_bulk_gb FROM seller_configs WHERE seller_id = ?", (seller_id,))
        row = c.fetchone()
        if row:
            new_used = max(0.0, (row[0] or 0) - gb)
            c.execute(
                "UPDATE seller_configs SET used_bulk_gb = ? WHERE seller_id = ?",
                (new_used, seller_id),
            )
        conn.commit()


def add_traffic_to_seller(seller_id, gb):
    """Add purchased/allocated bulk GB to seller."""
    gb = float(gb)
    with _conn() as conn:
        c = conn.cursor()
        c.execute("SELECT total_bulk_gb FROM seller_configs WHERE seller_id = ?", (seller_id,))
        row = c.fetchone()
        if row:
            c.execute(
                "UPDATE seller_configs SET total_bulk_gb = total_bulk_gb + ? WHERE seller_id = ?",
                (gb, seller_id),
            )
        else:
            c.execute(
                "INSERT INTO seller_configs (seller_id, total_bulk_gb) VALUES (?, ?)",
                (seller_id, gb),
            )
        conn.commit()
    reset_alert_if_recovered(seller_id)


def reset_alert_if_recovered(seller_id):
    remaining = get_remaining_gb(seller_id)
    if remaining >= LOW_TRAFFIC_THRESHOLD_GB:
        with _conn() as conn:
            c = conn.cursor()
            c.execute(
                "UPDATE seller_configs SET low_traffic_alert_active = 0 WHERE seller_id = ?",
                (seller_id,),
            )
            conn.commit()


def _get_user_display(user_id):
    with _conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT first_name, last_name, user_name FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = c.fetchone()
    if not row:
        return str(user_id), "—", user_id
    first, last, username = row
    name = f"{first or ''} {last or ''}".strip() or "بدون نام"
    uname = f"@{username}" if username else "—"
    return name, uname, user_id


def block_customer_no_traffic(bot, customer_chat_id, seller_id, pkg_gb, pkg_name=None):
    """
    Notify customer with update message and alert seller about failed purchase attempt.
    Returns True (blocked).
    """
    bot.send_message(customer_chat_id, CUSTOMER_NO_TRAFFIC_MSG, parse_mode="HTML")

    name, uname, uid = _get_user_display(customer_chat_id)
    remaining = get_remaining_gb(seller_id)
    pkg_line = f"📦 بسته درخواستی: <b>{pkg_name}</b> ({pkg_gb} GB)\n" if pkg_name else f"📦 حجم درخواستی: <b>{pkg_gb} GB</b>\n"

    seller_msg = (
        "⚠️ <b>خرید انجام نشد — ترافیک ناکافی</b>\n\n"
        "یک خریدار تلاش کرد سرویس بخرد ولی به دلیل اتمام ترافیک شما، فروش انجام نشد.\n\n"
        f"👤 نام: <b>{name}</b>\n"
        f"🆔 آیدی: <code>{uid}</code>\n"
        f"📎 یوزرنیم: {uname}\n"
        f"{pkg_line}"
        f"🟢 ترافیک باقیمانده شما: <b>{remaining:.1f} GB</b>\n\n"
        "لطفاً از منوی فروشنده گزینه <b>🔄 تمدید / خرید ترافیک</b> را بزنید "
        "تا بتوانید خدمات را ادامه دهید."
    )
    try:
        bot.send_message(seller_id, seller_msg, parse_mode="HTML")
    except Exception:
        pass
    return True


def check_and_alert_low_traffic(bot, seller_id=None):
    """
    Send low-traffic warning to seller(s) when remaining < 20GB.
    If seller_id is given, only check that seller; otherwise check all sellers.
    """
    with _conn() as conn:
        c = conn.cursor()
        if seller_id is not None:
            c.execute(
                """SELECT seller_id, total_bulk_gb, used_bulk_gb, low_traffic_alert_active
                   FROM seller_configs WHERE seller_id = ?""",
                (seller_id,),
            )
        else:
            c.execute(
                """SELECT seller_id, total_bulk_gb, used_bulk_gb, low_traffic_alert_active
                   FROM seller_configs"""
            )
        rows = c.fetchall()

    for sid, total, used, alerted in rows:
        total = total or 0.0
        used = used or 0.0
        remaining = max(0.0, total - used)

        if remaining >= LOW_TRAFFIC_THRESHOLD_GB:
            if alerted:
                with _conn() as conn:
                    c = conn.cursor()
                    c.execute(
                        "UPDATE seller_configs SET low_traffic_alert_active = 0 WHERE seller_id = ?",
                        (sid,),
                    )
                    conn.commit()
            continue

        if alerted:
            continue

        msg = (
            "🔔 <b>هشدار کمبود ترافیک</b>\n\n"
            f"ترافیک باقیمانده شما: <b>{remaining:.1f} GB</b>\n"
            f"(کمتر از {int(LOW_TRAFFIC_THRESHOLD_GB)} گیگابایت)\n\n"
            "برای جلوگیری از قطع فروش به مشتریان، از منوی فروشنده "
            "گزینه <b>🔄 تمدید / خرید ترافیک</b> را انتخاب کنید."
        )
        try:
            bot.send_message(sid, msg, parse_mode="HTML")
            with _conn() as conn:
                c = conn.cursor()
                c.execute(
                    "UPDATE seller_configs SET low_traffic_alert_active = 1 WHERE seller_id = ?",
                    (sid,),
                )
                conn.commit()
        except Exception:
            pass


def _existing_columns(cursor, table):
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _ensure_columns(cursor, table, column_defs):
    """Add any missing columns to an existing table."""
    existing = _existing_columns(cursor, table)
    for col, typedef in column_defs.items():
        if col not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")


# Canonical column definitions used for upgrades (ALTER TABLE).
_TABLE_COLUMN_DEFS = {
    "users": {
        "user_id": "INTEGER",
        "phone_number": "TEXT",
        "verify": "TEXT",
        "first_name": "TEXT",
        "last_name": "TEXT",
        "user_name": "TEXT",
        "join_date": "TEXT",
        "role": "TEXT DEFAULT 'customer'",
        "parent_seller_id": "INTEGER",
        "balance": "INTEGER DEFAULT 0",
        "joined_at": "TEXT",
    },
    "seller_configs": {
        "bank_card": "TEXT",
        "card_owner": "TEXT",
        "crypto_wallet": "TEXT",
        "active_gateways": "TEXT DEFAULT 'card'",
        "approval_group_id": "INTEGER",
        "total_bulk_gb": "REAL DEFAULT 0",
        "used_bulk_gb": "REAL DEFAULT 0",
        "support_id": "TEXT",
        "channel_id": "TEXT",
        "instagram_id": "TEXT",
        "nickname": "TEXT",
        "username_prefix": "TEXT",
        "user_sequence": "INTEGER DEFAULT 1000",
        "show_card_for_traffic": "INTEGER DEFAULT 0",
        "low_traffic_alert_active": "INTEGER DEFAULT 0",
    },
    "packages": {
        "seller_id": "INTEGER",
        "name": "TEXT",
        "gb": "REAL",
        "days": "INTEGER",
        "price_toman": "INTEGER",
        "price_usd": "REAL DEFAULT 0",
    },
    "receipts": {
        "user_id": "INTEGER",
        "seller_id": "INTEGER",
        "type": "TEXT",
        "package_id": "INTEGER",
        "amount": "INTEGER",
        "photo_file_id": "TEXT",
        "service_uuid": "TEXT",
        "status": "TEXT DEFAULT 'pending'",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    },
    "invite_links": {
        "token": "TEXT",
        "seller_id": "INTEGER",
        "used": "INTEGER DEFAULT 0",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    },
    "admin_list": {
        "admin_id": "INTEGER",
        "admin_name": "TEXT",
    },
    "channels": {
        "button_name": "TEXT",
        "link": "TEXT",
        "channel_id": "TEXT",
    },
    "uploaded_files_new": {
        "title": "TEXT",
        "file_id": "TEXT",
        "file_type": "TEXT",
        "file_name": "TEXT",
        "file_size": "TEXT",
        "upload_date": "TEXT",
        "tracking_code": "TEXT",
        "download_count": "INTEGER DEFAULT 0",
    },
    "seller_packages": {
        "title": "TEXT",
        "volume_gb": "INTEGER",
        "price_usd": "REAL",
        "price_toman": "INTEGER DEFAULT 0",
    },
    "admin_wallets": {
        "network": "TEXT",
        "currency": "TEXT",
        "address": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
    },
    "charge_doc_channel": {
        "channel_id": "TEXT",
    },
}


def run_migrations():
    """Create all tables and ensure every required column exists."""
    with _conn() as conn:
        c = conn.cursor()

        c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                phone_number TEXT,
                verify TEXT,
                first_name TEXT,
                last_name TEXT,
                user_name TEXT,
                join_date TEXT,
                role TEXT DEFAULT 'customer',
                parent_seller_id INTEGER,
                balance INTEGER DEFAULT 0,
                joined_at TEXT
            );

            CREATE TABLE IF NOT EXISTS seller_configs (
                seller_id INTEGER PRIMARY KEY,
                bank_card TEXT,
                card_owner TEXT,
                crypto_wallet TEXT,
                active_gateways TEXT DEFAULT 'card',
                approval_group_id INTEGER,
                total_bulk_gb REAL DEFAULT 0,
                used_bulk_gb REAL DEFAULT 0,
                support_id TEXT,
                channel_id TEXT,
                instagram_id TEXT,
                nickname TEXT,
                username_prefix TEXT,
                user_sequence INTEGER DEFAULT 1000,
                show_card_for_traffic INTEGER DEFAULT 0,
                low_traffic_alert_active INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id INTEGER,
                name TEXT,
                gb REAL,
                days INTEGER,
                price_toman INTEGER,
                price_usd REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                seller_id INTEGER,
                type TEXT,
                package_id INTEGER,
                amount INTEGER,
                photo_file_id TEXT,
                service_uuid TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS invite_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE,
                seller_id INTEGER,
                used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS admin_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                admin_name TEXT
            );

            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                button_name TEXT,
                link TEXT,
                channel_id TEXT
            );

            CREATE TABLE IF NOT EXISTS block_list (
                chat_id INTEGER PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS uploaded_files_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                file_id TEXT,
                file_type TEXT,
                file_name TEXT,
                file_size TEXT,
                upload_date TEXT,
                tracking_code TEXT UNIQUE,
                download_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS seller_packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                volume_gb INTEGER,
                price_usd REAL,
                price_toman INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS admin_wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                network TEXT,
                currency TEXT,
                address TEXT,
                is_active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS charge_doc_channel (
                id INTEGER PRIMARY KEY,
                channel_id TEXT
            );
        """)

        for table, columns in _TABLE_COLUMN_DEFS.items():
            _ensure_columns(c, table, columns)

        conn.commit()


def verify_schema():
    """
    Run sanity checks on schema — returns list of error strings (empty if OK).
    Safe to call at startup.
    """
    errors = []
    critical_queries = [
        ("users", "SELECT role, parent_seller_id, balance, joined_at FROM users LIMIT 1"),
        ("seller_configs", "SELECT total_bulk_gb, used_bulk_gb, show_card_for_traffic, low_traffic_alert_active, username_prefix, user_sequence FROM seller_configs LIMIT 1"),
        ("packages", "SELECT id, name, gb, days, price_toman, price_usd FROM packages LIMIT 1"),
        ("receipts", "SELECT id, user_id, seller_id, type, package_id, amount, photo_file_id, service_uuid, status, created_at FROM receipts LIMIT 1"),
        ("seller_packages", "SELECT id, title, volume_gb, price_toman, price_usd FROM seller_packages LIMIT 1"),
        ("admin_wallets", "SELECT id, network, currency, address, is_active FROM admin_wallets LIMIT 1"),
        ("invite_links", "SELECT token, seller_id, used, created_at FROM invite_links LIMIT 1"),
        ("admin_list", "SELECT admin_id, admin_name FROM admin_list LIMIT 1"),
        ("channels", "SELECT button_name, link, channel_id FROM channels LIMIT 1"),
        ("bot_settings", "SELECT key, value FROM bot_settings LIMIT 1"),
        ("charge_doc_channel", "SELECT channel_id FROM charge_doc_channel LIMIT 1"),
    ]
    with _conn() as conn:
        c = conn.cursor()
        for table, query in critical_queries:
            try:
                c.execute(query)
            except sqlite3.OperationalError as e:
                errors.append(f"{table}: {e}")
    return errors
