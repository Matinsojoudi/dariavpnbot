#!/usr/bin/env python3
"""Logic tests for kingvpnstorebot (traffic, auth, wallet refund paths)."""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Use an isolated temp DB before importing modules that touch settings.database
_fd, _TEST_DB = tempfile.mkstemp(prefix="kingvpn_test_", suffix=".db")
os.close(_fd)
os.environ["DATABASE"] = _TEST_DB
os.environ.setdefault("ADMIN_LIST", "111,222")
os.environ.setdefault("ADMIN", "111")
os.environ.setdefault("TOKEN", "test-token")
os.environ.setdefault("BOT_ID", "@test")
os.environ.setdefault("BOT_LINK", "https://t.me/test")
os.environ.setdefault("MATIN", "111")

# Force reload env with test DB
import importlib
import env as env_mod

importlib.reload(env_mod)
env_mod.settings.database = _TEST_DB
env_mod.settings.admin_list = [111, 222]
env_mod.settings.admin = "111"

import traffic_service as ts
importlib.reload(ts)
ts.settings = env_mod.settings

from traffic_service import (
    run_migrations,
    verify_schema,
    has_enough_traffic,
    deduct_traffic,
    refund_traffic,
    add_traffic_to_seller,
    get_remaining_gb,
    force_deduct_traffic,
)

import customer as customer_mod
importlib.reload(customer_mod)
customer_mod.settings = env_mod.settings


def setup_db():
    if os.path.exists(_TEST_DB):
        os.remove(_TEST_DB)
    run_migrations()
    issues = verify_schema()
    assert not issues, f"schema issues: {issues}"
    with sqlite3.connect(_TEST_DB) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO users (chat_id, user_id, role, parent_seller_id, balance) VALUES (?,?,?,?,?)",
            (1001, 1001, "seller", 1001, 0),
        )
        c.execute(
            "INSERT INTO users (chat_id, user_id, role, parent_seller_id, balance) VALUES (?,?,?,?,?)",
            (2002, 2002, "customer", 1001, 500000),
        )
        c.execute(
            "INSERT INTO seller_configs (seller_id, total_bulk_gb, used_bulk_gb, bank_card, active_gateways, show_card_for_traffic) VALUES (?,?,?,?,?,?)",
            (1001, 100.0, 0.0, "6219860000000000", "card", 1),
        )
        c.execute(
            "INSERT INTO packages (seller_id, name, gb, days, price_toman) VALUES (?,?,?,?,?)",
            (1001, "Test 30G", 30.0, 30, 100000),
        )
        c.execute(
            "INSERT INTO invite_links (token, seller_id, used) VALUES (?,?,0)",
            ("abcd1234", 1001),
        )
        c.execute(
            "INSERT INTO receipts (user_id, seller_id, type, package_id, amount, status) VALUES (?,?,?,?,?,?)",
            (2002, 1001, "package", 1, 100000, "pending"),
        )
        conn.commit()


def test_traffic_ops():
    assert has_enough_traffic(1001, 30) is True
    assert deduct_traffic(1001, 30) is True
    assert abs(get_remaining_gb(1001) - 70.0) < 0.01
    assert deduct_traffic(1001, 80) is False  # insufficient
    assert abs(get_remaining_gb(1001) - 70.0) < 0.01
    refund_traffic(1001, 30)
    assert abs(get_remaining_gb(1001) - 100.0) < 0.01
    add_traffic_to_seller(1001, 50)
    assert abs(get_remaining_gb(1001) - 150.0) < 0.01
    # force deduct can exceed but we no longer use it for customer sales
    force_deduct_traffic(1001, 200)
    rem = get_remaining_gb(1001)
    assert rem == 0.0
    print("OK traffic_ops")


def test_receipt_auth():
    assert customer_mod._can_manage_receipt(1001, 1001) is True  # owner seller
    assert customer_mod._can_manage_receipt(111, 1001) is True  # super admin
    assert customer_mod._can_manage_receipt(9999, 1001) is False  # stranger
    assert customer_mod._can_manage_receipt(2002, 1001) is False  # customer
    print("OK receipt_auth")


def test_should_check_traffic():
    # Non-admin seller must be checked
    assert customer_mod._should_check_traffic(1001) is True
    # Admin seller bypasses
    assert customer_mod._should_check_traffic(111) is False
    print("OK should_check_traffic")


def test_parent_seller():
    assert customer_mod._get_parent_seller_id(2002) == 1001
    assert customer_mod._get_parent_seller_id(1001) == 1001
    print("OK parent_seller")


def test_invite_schema_and_assign():
    with sqlite3.connect(_TEST_DB) as conn:
        c = conn.cursor()
        c.execute("SELECT used_by FROM invite_links WHERE token = ?", ("abcd1234",))
        assert c.fetchone()[0] is None
        c.execute(
            "UPDATE invite_links SET used = 1, used_by = ? WHERE token = ?",
            (2002, "abcd1234"),
        )
        conn.commit()
        c.execute("SELECT used, used_by, seller_id FROM invite_links WHERE token = ?", ("abcd1234",))
        used, used_by, seller_id = c.fetchone()
        assert used == 1 and used_by == 2002 and seller_id == 1001
    print("OK invite_schema")


def test_wallet_renew_refund_logic():
    """Simulate renew_wallet deduct failure path: balance must be restored."""
    with sqlite3.connect(_TEST_DB) as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET balance = 200000 WHERE user_id = 2002")
        c.execute("UPDATE seller_configs SET total_bulk_gb = 10, used_bulk_gb = 0 WHERE seller_id = 1001")
        conn.commit()

    price, gb = 100000, 30
    parent_id = 1001
    chat_id = 2002

    with sqlite3.connect(_TEST_DB) as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, chat_id))
        if not deduct_traffic(parent_id, gb):
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, chat_id))
            conn.commit()
        else:
            raise AssertionError("deduct should fail")

    with sqlite3.connect(_TEST_DB) as conn:
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (chat_id,))
        bal = c.fetchone()[0]
    assert bal == 200000, f"balance not restored: {bal}"
    print("OK wallet_renew_refund")


def test_atomic_receipt_claim():
    with sqlite3.connect(_TEST_DB) as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE receipts SET status = 'approved' WHERE id = 1 AND status = 'pending'"
        )
        assert c.rowcount == 1
        c.execute(
            "UPDATE receipts SET status = 'approved' WHERE id = 1 AND status = 'pending'"
        )
        assert c.rowcount == 0
        conn.commit()
    print("OK atomic_receipt_claim")


def main():
    setup_db()
    test_traffic_ops()
    setup_db()  # reset after force_deduct
    test_receipt_auth()
    test_should_check_traffic()
    test_parent_seller()
    test_invite_schema_and_assign()
    test_wallet_renew_refund_logic()
    test_atomic_receipt_claim()
    print("\nALL TESTS PASSED")
    try:
        os.remove(_TEST_DB)
    except OSError:
        pass


if __name__ == "__main__":
    main()
