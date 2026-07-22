#!/usr/bin/env python3
"""Apply shared X-UI (Sanaei / mongol) panel settings to a bot SQLite database."""

import os
import sqlite3
import sys

PANEL_SETTINGS = {
    "XUI_PANEL_URL": "https://mongol.62.60.184.127.nip.io/mango_banana_4Ever/",
    "XUI_USERNAME": "Matthew",
    "XUI_PASSWORD": "Matinisthebest4Ever",
    "XUI_INBOUND_ID": "1",
    "SUB_BASE_URL": "https://sus.62.60.184.127.nip.io/sus",
}


def apply(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute(
            "CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, value TEXT)"
        )
        for key, value in PANEL_SETTINGS.items():
            c.execute(
                "INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        conn.commit()
    print(f"Applied X-UI settings to {db_path}")


def main() -> int:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path-to-bot.db>")
        return 1
    db_path = sys.argv[1]
    if not os.path.isfile(db_path):
        print(f"Database not found: {db_path}")
        return 1
    apply(db_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
