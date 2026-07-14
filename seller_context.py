"""Resolve which seller account the current actor should operate as."""

import sqlite3
from env import settings


def _is_super_admin(actor_id):
    try:
        uid = int(actor_id)
    except (TypeError, ValueError):
        return False
    if uid in settings.admin_list:
        return True
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM admin_list WHERE admin_id = ?", (uid,))
            if c.fetchone():
                return True
    except Exception:
        pass
    return False


def get_single_seller_id():
    """Return configured SINGLE_SELLER_ID or fallback ADMIN env."""
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM bot_settings WHERE key = 'SINGLE_SELLER_ID'")
            row = c.fetchone()
            if row and row[0]:
                return int(row[0])
    except Exception:
        pass
    if settings.admin:
        try:
            return int(settings.admin)
        except (TypeError, ValueError):
            pass
    return None


def get_effective_seller_id(actor_id):
    """
    Seller panel context:
    - Normal seller → own id
    - Super admin → configured SINGLE_SELLER_ID (impersonate that seller)
    """
    try:
        actor = int(actor_id)
    except (TypeError, ValueError):
        return actor_id

    if _is_super_admin(actor):
        target = get_single_seller_id()
        if target:
            return target
    return actor


def can_access_seller_panel(actor_id):
    """True if actor is a seller or super-admin."""
    try:
        actor = int(actor_id)
    except (TypeError, ValueError):
        return False
    if _is_super_admin(actor):
        return True
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT role FROM users WHERE user_id = ?", (actor,))
            row = c.fetchone()
            if row and row[0] == "seller":
                return True
            # Configured single seller may use panel even before role sync
            single = get_single_seller_id()
            if single and actor == single:
                return True
    except Exception:
        pass
    return False
