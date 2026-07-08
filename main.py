import os, re, time
import random
import telebot
import sqlite3
from hiddify.client import HiddifyClient

from utils.qr import link_to_qrcode, place_qr_on_template

import uuid
import string
import traceback
import threading
from confings import *
from threading import Timer
from buttons import *
from env import settings
from telebot import types
from telebot import apihelper
from urllib.parse import urlparse, parse_qs

def parse_proxy_url(proxy_url):
    if not proxy_url:
        return None
    proxy_url = proxy_url.strip()
    if proxy_url.startswith("tg://socks"):
        try:
            parsed = urlparse(proxy_url)
            query = parse_qs(parsed.query)
            server = query.get('server', [''])[0]
            port = query.get('port', [''])[0]
            user = query.get('user', [''])[0]
            password = query.get('pass', [''])[0]
            if server and port:
                if user and password:
                    return f"socks5h://{user}:{password}@{server}:{port}"
                else:
                    return f"socks5h://{server}:{port}"
        except Exception:
            return None
    elif proxy_url.startswith("socks5://") or proxy_url.startswith("socks5h://"):
        return proxy_url
    elif ":" in proxy_url and not "://" in proxy_url:
        return f"socks5h://{proxy_url}"
    return None

def apply_proxy():
    try:
        proxy_val = None
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bot_settings'")
            if c.fetchone():
                c.execute("SELECT value FROM bot_settings WHERE key = 'SOCKS_PROXY'")
                row = c.fetchone()
                if row and row[0]:
                    proxy_val = row[0]
                    
        if not proxy_val and hasattr(settings, 'socks_proxy') and settings.socks_proxy:
            proxy_val = settings.socks_proxy
            
        if proxy_val:
            parsed = parse_proxy_url(proxy_val)
            if parsed:
                apihelper.proxy = {'https': parsed, 'http': parsed}
                print(f"SOCKS Proxy applied: {parsed}")
                return
        apihelper.proxy = None
    except Exception as e:
        print("Error applying proxy:", e)

apply_proxy()

from jdatetime import datetime as jdatetime
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from collections import defaultdict
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import requests
import schedule
from typing import Union, Iterable
from typing import Optional, Dict, Any, Tuple

stop_event = threading.Event()

temp_data = {}
admin_states = {}
delete_states = {}
user_states = {}
keyboards = {}
contents = {}
user_data = {}
current_pages = {}
temp_offer = {}
user_last_message = {}
charge_doc_channel_id = "-1001913448637"
bot = telebot.TeleBot(settings.token)

REMINDER_CHANNEL = "-1002933818552"

SEND_PAUSE = 1    # بعد از هر 20 پیام چند ثانیه وقفه
SEND_EVERY = 20   # هر چند نفر یکبار وقفه

IPPANEL_TOKEN = "OWZlYzVmOWQtYjg5NC00ZGMxLWE1YWUtZDhhZjQzMzkxOGU3ZjVjMTMxNjRhOTMzNDE3MDY1ZTFhNDRmZGZiNjFmYmU="   
IPPANEL_FROM_NUMBER = "+983000505"       
IPPANEL_FROM_NUMBER2 = "+985000125475"       
IPPANEL_FROM_NUMBER3 = "+9810004223"
IPPANEL_FROM_NUMBER4 = "+985000404223"



# def update_sms_patterns_by_ids(db_path, patterns, ids):
#     """
#     بروزرسانی sms_pattern_id ها برای رکوردهای مشخص
#     :param db_path: مسیر دیتابیس sqlite
#     :param patterns: لیست پترن‌های جدید به ترتیب
#     :param ids: لیست id رکوردهایی که باید تغییر کنن
#     """
#     conn = sqlite3.connect(db_path)
#     cursor = conn.cursor()

#     for i, course_id in enumerate(ids):
#         if i < len(patterns):
#             new_pattern = patterns[i]
#             cursor.execute(
#                 "UPDATE courses_enhanced SET sms_pattern_id = ? WHERE id = ?",
#                 (new_pattern, course_id)
#             )

#     conn.commit()
#     conn.close()
#     print("✅ رکوردهای انتخاب‌شده بروزرسانی شدند.")


# # --------- استفاده ----------
# db_file = settings.database

# # پترن‌های جدید به ترتیب
# new_patterns = [
#     "i0j132oq33lyzl8",
#     "fqwse5izxu65zth",
#     "je74s0fsohxvov9"
# ]

# # فقط رکوردهای id=3,4,5
# ids_to_update = [3, 4, 5]

# update_sms_patterns_by_ids(db_file, new_patterns, ids_to_update)



def save_info(user_id, first_name, last_name, chat_id, user_name):
    try:
        update_block_list(chat_id, "delete")
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS users (
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
                         )''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS seller_configs (
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
                            user_sequence INTEGER DEFAULT 1000
                         )''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS packages (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            seller_id INTEGER,
                            name TEXT,
                            gb REAL,
                            days INTEGER,
                            price_toman INTEGER,
                            price_usd REAL DEFAULT 0,
                            FOREIGN KEY (seller_id) REFERENCES seller_configs(seller_id)
                         )''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS receipts (
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
                         )''')

            c.execute('''CREATE TABLE IF NOT EXISTS invite_links (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            token TEXT UNIQUE,
                            seller_id INTEGER,
                            used INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                         )''')
            try:
                c.execute("ALTER TABLE invite_links ADD COLUMN used_by INTEGER")
            except sqlite3.OperationalError:
                pass
            
            c.execute("SELECT * FROM users WHERE chat_id=?", (chat_id,))
            existing_user = c.fetchone()

            if existing_user:
                c.execute("""UPDATE users SET first_name=?, last_name=?, user_name=?, user_id=? WHERE chat_id=?""",
                          (first_name, last_name, user_name, user_id, chat_id))
#                 bot.send_message(settings.customers_starts_2, 
#     text=f"""
# 🔔Activation NEWS

# <b>👤Name: </b> {first_name} {last_name}
# <b>👤Chat: </b> <code>{chat_id}</code>
# <b>👤User Name: </b> @{user_name}
# <b>☎️User's chat ID: </b> <code>{user_id}</code>
# """,
#     parse_mode="HTML"
# )

            else:
                join_date = str(get_current_timestamp())
                c.execute("INSERT INTO users (chat_id, user_id, phone_number, verify, first_name, last_name, user_name, join_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                          (chat_id, user_id, None, None, first_name, last_name, user_name, join_date))
                # bot.send_message(
#                     settings.customers_starts_2, 
#     text=f"""
# 🔔Activation NEWS

# <b>👤Name: </b> {first_name} {last_name}
# <b>👤Chat: </b> <code>{chat_id}</code>
# <b>👤User Name: </b> @{user_name}
# <b>☎️User's chat ID: </b> <code>{user_id}</code>
# """,
#     parse_mode="HTML"
# )

            conn.commit()
    except sqlite3.Error as e:
        send_error_to_admin(traceback.format_exc())


def save_new_admin(admin_id, message):
    if admin_id == "برگشت 🔙":
        bot.send_message(message.chat.id, "به منوی ادمین برگشتید.", reply_markup=super_admin_markup)
    else:
        try:
            with sqlite3.connect(settings.database) as conn:
                c = conn.cursor()
                c.execute("BEGIN TRANSACTION")
                c.execute('''CREATE TABLE IF NOT EXISTS admin_list (
                                id INTEGER PRIMARY KEY,
                                admin_id INTEGER
                             )''')
                c.execute("INSERT INTO admin_list (admin_id) VALUES (?)", (admin_id,))
                conn.commit()
                bot.send_message(message.chat.id, "ادمین مورد نظر با موفقیت افزوده شد.", reply_markup=super_admin_markup)
        except Exception as e:
            bot.send_message(settings.matin, f"Error in save_new_admin: {e}")
            bot.send_message(message.chat.id, f"Error in save_new_admin: {e}")


def is_member_in_all_channels(chat_id):
    all_channels = get_all_channels()
    for channel_id in all_channels:
        member = bot.get_chat_member(channel_id, chat_id)
        if member.status not in ['member', 'administrator', 'creator']:
            return False
    return True


def get_all_channels():
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT channel_id FROM channels")
            channels = [channel[0] for channel in c.fetchall() if channel[0] and str(channel[0]).startswith("-100")]
            return channels
    except Exception as e:
        send_error_to_admin(traceback.format_exc())
        return []


def delete_channel_by_id(channel_id):
    conn = sqlite3.connect(settings.database)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM channels WHERE id=?", (channel_id,))
        conn.commit()
        bot.send_message(settings.matin, f"Channel with id {channel_id} deleted successfully.")
    except Exception as e:
        conn.rollback()
        send_error_to_admin(traceback.format_exc())
    finally:
        conn.close()

def make_delete_channel_id_keyboard():
    try:
        conn = sqlite3.connect(settings.database)
        c = conn.cursor()

        c.execute("SELECT * FROM channels ORDER BY id")
        channel_info = c.fetchall()

        keyboard = []
        for channel in channel_info:
            channel_id, button_name, link_type, link, channel_chat_id = channel
            keyboard.append([InlineKeyboardButton(button_name, callback_data=f"delete_row_{channel_id}")])

        keyboard.append([InlineKeyboardButton("❌ خروج از منوی حذف کانال", callback_data=f"delete_button_1")])

        conn.close()
        return InlineKeyboardMarkup(keyboard)
    except Exception as e:
        send_error_to_admin(traceback.format_exc())
        return None


def get_current_timestamp():
    try:
        from jdatetime import datetime as jdt
        return jdt.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_current_date():
    from jdatetime import datetime as jdt
    return jdt.now().strftime("%Y_%m_%d")


def search_all_users():
    conn = sqlite3.connect(settings.database)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_count = c.fetchone()[0]
    conn.close()
    return total_count


def make_delete_admin_list_keyboard():
    try:
        conn = sqlite3.connect(settings.database)
        c = conn.cursor()

        c.execute("SELECT * FROM admin_list ORDER BY id")
        latest_news = c.fetchall()

        keyboard = []
        for news in latest_news:
            news_id, post_title = news
            keyboard.append([InlineKeyboardButton(post_title, callback_data=f"delete_row_admin_{news_id}")])

        keyboard.append([InlineKeyboardButton("❌ خروج از منوی حذف ادمین", callback_data=f"delete_button_1")])

        conn.close()
        return InlineKeyboardMarkup(keyboard)
    except Exception as e:
        bot.send_message(settings.matin, f"Error in creating make_delete_admin_list_keyboard: {e}")
        return None


def check_admin_id_exists(admin_id):
    conn = sqlite3.connect(settings.database)  
    c = conn.cursor()
    
    c.execute('SELECT 1 FROM crush_admin_info WHERE admin_id = ?', (admin_id,))
    result = c.fetchone()    
    conn.close()
    return result is not None



def is_member_channel(chat_id, channel_id):
    member = bot.get_chat_member(channel_id, chat_id)
    if member.status not in ['member', 'administrator', 'creator']:
        return False
    return True


def get_button_name(message):
    if check_return_2(message):
        return
    
    chat_id = message.chat.id
    name = message.text.strip()
    if len(name) > 40:
        msg = bot.send_message(chat_id, "نام دکمه نباید بیشتر از ۴۰ کاراکتر باشد. لطفاً مجدداً ارسال کنید:", reply_markup=back_markup)
        bot.register_next_step_handler(msg, get_button_name)
        return
    temp_data[chat_id]['button_name'] = name
    msg = bot.send_message(chat_id, "لینک شما برای تلگرام است یا سایر موارد؟", reply_markup=create_selection_markup())
    bot.register_next_step_handler(msg, handle_link_type)
    

def handle_link_type(message):
    if check_return_2(message):
        return
    
    chat_id = message.chat.id
    selection = message.text.strip()
    temp_data[chat_id]["link_type"] = selection
    
    if selection == "تلگرام":
        msg = bot.send_message(chat_id, "باشه! پس اول لینک یا آیدی اون کانال یا گروه تلگرامی رو برام بفرست و حواست باشه ربات رو توی اون کانال یا گروه ادمین کرده باشی.", reply_markup=back_markup)
        bot.register_next_step_handler(msg, get_telegram_link)
    elif selection == "سایر موارد":
        msg = bot.send_message(chat_id, "لینک سایت، ربات، اینستاگرام، یا هر لینک دیگری که مدنظرتون هست رو ارسال کنید:", reply_markup=back_markup)
        bot.register_next_step_handler(msg, get_other_link)

def get_telegram_link(message):
    if check_return_2(message):
        return

    chat_id = message.chat.id
    link = message.text.strip()
    if link.startswith("@"): 
        link = f"https://t.me/{link[1:]}"
    elif not re.match(r"^https://t.me/\S+$", link):
        msg = bot.send_message(chat_id, "لینک یا آیدی معتبر ارسال کنید:", reply_markup=back_markup)
        bot.register_next_step_handler(msg, get_telegram_link)
        return
    temp_data[chat_id]['link'] = link
    msg = bot.send_message(chat_id, "یک پیام از آن کانال به من فوروارد کن یا آیدی عددی آن را بفرست (باید با -100 شروع شود):", reply_markup=back_markup)
    bot.register_next_step_handler(msg, get_telegram_id)

def get_telegram_id(message):
    if check_return_2(message):
        return
    
    chat_id = message.chat.id
    if message.forward_from_chat:
        temp_data[chat_id]["channel_id"] = message.forward_from_chat.id
    elif message.text.startswith("-100"):
        temp_data[chat_id]["channel_id"] = message.text.strip()
    else:
        msg = bot.send_message(chat_id, "آیدی عددی باید با -100 شروع شود. لطفاً مجدداً ارسال کنید:", reply_markup=back_markup)
        bot.register_next_step_handler(msg, get_telegram_id)
        return
    save_data(chat_id)

def get_other_link(message):
    if check_return_2(message):
        return
    
    chat_id = message.chat.id
    temp_data[chat_id]["link"] = message.text.strip()
    save_data(chat_id)

def save_data(chat_id):
    try:
        data = temp_data.get(chat_id, {})
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("BEGIN TRANSACTION")
            c.execute('''CREATE TABLE IF NOT EXISTS channels (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            button_name TEXT NOT NULL,
                            link_type TEXT NOT NULL,
                            link TEXT NOT NULL,
                            channel_id TEXT
                         )''')
            c.execute("INSERT INTO channels (button_name, link_type, link, channel_id) VALUES (?, ?, ?, ?)",
                      (data.get("button_name"), data.get("link_type"), data.get("link"), data.get("channel_id")))
            conn.commit()
        bot.send_message(chat_id, "✅ اطلاعات با موفقیت ذخیره شد.", reply_markup=super_admin_markup)
        del temp_data[chat_id]
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطا در ذخیره اطلاعات", reply_markup=super_admin_markup)
        bot.send_message(settings.matin, f"❌ خطا در ذخیره اطلاعات: {e}", reply_markup=super_admin_markup)

def create_selection_markup():
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.row("تلگرام", "سایر موارد")
    markup.row("برگشت 🔙")
    return markup


def delete_admin_by_id(admin_id):
    conn = sqlite3.connect(settings.database)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM admin_list WHERE id=?", (admin_id,))
        conn.commit()
        bot.send_message(settings.matin, f"Channel with id {admin_id} deleted successfully.")
    except Exception as e:
        conn.rollback()
        bot.send_message(settings.matin, f"Error in delete_channel_by_id: {e}")
    finally:
        conn.close()

def get_admin_ids():
    return get_ids_from_db("admin_list", "admin_id")

def get_ids_from_db(table_name, column_name):
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute(f"SELECT {column_name} FROM {table_name}")
            ids = [row[0] for row in c.fetchall()]
            return ids
    except Exception as e:
        bot.send_message(settings.matin, f"Error in get_ids_from_db: {e}")
        return []



def create_block_list_table():
    with sqlite3.connect(settings.database) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS block_list (
                chat_id INTEGER PRIMARY KEY
            )
        """)
        conn.commit()
    
create_block_list_table()

def update_block_list(chat_id, operation):
    with sqlite3.connect(settings.database) as conn:
        c = conn.cursor()
        if operation.lower() == "add":
            c.execute("SELECT chat_id FROM block_list WHERE chat_id = ?", (chat_id,))
            result = c.fetchone()
            if not result:
                c.execute("INSERT INTO block_list (chat_id) VALUES (?)", (chat_id,))
                conn.commit()
                return True
            
        elif operation.lower() == "delete":
            c.execute("SELECT chat_id FROM block_list WHERE chat_id = ?", (chat_id,))
            result = c.fetchone()
            if result:
                c.execute("DELETE FROM block_list WHERE chat_id = ?", (chat_id,))
                conn.commit()
                return True

        else:
            return False
        

def confirm_send_all_users(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(types.KeyboardButton("✔ مطمئن هستم"))
    keyboard.add(types.KeyboardButton("❌ انصراف از ارسال"))
    
    msg = bot.send_message(message.chat.id, "آیا مطمئن هستید که می‌خواهید این پیام را همگانی ارسال کنید؟", reply_markup=keyboard)
    bot.register_next_step_handler(msg, lambda response: process_confirmation_send_all_users(response, message))


def process_confirmation_send_all_users(user_response, original_message):
    if user_response.text == "✔ مطمئن هستم":
        send_all_users(original_message)
    else:
        bot.send_message(user_response.chat.id, "❌ ارسال پیام همگانی لغو شد.", reply_markup=super_admin_markup)
    

def send_admin_public_msg(message):
    chat_id = message.chat.id
    if message.content_type == 'text':
        bot.send_message(chat_id, message.text, reply_markup=get_customer_markup(chat_id))
    elif message.content_type == 'photo':
        caption = message.caption if message.caption else " "
        bot.send_photo(chat_id, message.photo[-1].file_id, caption=caption, reply_markup=get_customer_markup(chat_id))
    elif message.content_type == 'video':
        caption = message.caption if message.caption else " "
        bot.send_video(chat_id, message.video.file_id, caption=caption, reply_markup=get_customer_markup(chat_id))
    elif message.content_type == 'audio':
        caption = message.caption if message.caption else " "
        bot.send_audio(chat_id, message.audio.file_id, caption=caption, reply_markup=get_customer_markup(chat_id))
    elif message.content_type == 'document':
        caption = message.caption if message.caption else " "
        bot.send_document(chat_id, message.document.file_id, caption=caption, reply_markup=get_customer_markup(chat_id))
    elif message.content_type == 'sticker':
        bot.send_sticker(chat_id, message.sticker.file_id, reply_markup=get_customer_markup(chat_id))
    elif message.content_type == 'voice':
        caption = message.caption if message.caption else " "
        bot.send_voice(chat_id, message.voice.file_id, caption=caption, reply_markup=get_customer_markup(chat_id))
    elif message.content_type == 'animation':
        caption = message.caption if message.caption else " "
        bot.send_animation(chat_id, message.animation.file_id, caption=caption, reply_markup=get_customer_markup(chat_id))
    elif message.content_type == 'video_note':
        bot.send_video_note(chat_id, message.video_note.file_id, reply_markup=get_customer_markup(chat_id))



def send_all_users(message):
    global stop_event
    stop_event.clear()
    
    if check_return_2(message):
        return

    with sqlite3.connect(settings.database) as conn:
        c = conn.cursor()
        try:
            c.execute("SELECT COUNT(chat_id) FROM users WHERE chat_id NOT IN (SELECT chat_id FROM block_list)")
            total_users = c.fetchone()[0]

            groups_of_29 = total_users // 20
            remainder = total_users % 20
            send_time = groups_of_29 * 1.5  
            if remainder > 0:
                send_time += 1.5

            estimated_time = round(send_time / 60, 2)  

            start_message = (
                f"🚀 عملیات ارسال پیام همگانی آغاز شد!\n\n"
                f"👥 تعداد کل کاربران فعال: {total_users}\n"
                f"⏳ زمان تقریبی اتمام ارسال: {estimated_time} دقیقه."
            )

            bot.send_message(message.chat.id, start_message, reply_markup=super_admin_markup)
            bot.send_message(settings.matin, start_message, reply_markup=super_admin_markup)

            emergency_markup = InlineKeyboardMarkup()
            emergency_markup.add(InlineKeyboardButton("⛔ توقف اضطراری", callback_data="confirm_stop_broadcast"))
            send_admin_public_msg(message)
            bot.send_message(message.chat.id , "⚠ جهت توقف اضطراری دکمه زیر را کلیک کنید:", reply_markup=emergency_markup)

        except Exception as e:
            bot.send_message(settings.matin, text=f"❌ Error during calculating total users:\n{e}")
            return

    def send_messages():
        global stop_event
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            try:
                c.execute("SELECT chat_id FROM users WHERE chat_id NOT IN (SELECT chat_id FROM block_list)")
                all_chat_ids = c.fetchall()
                not_send = 0  
                count_29 = 0  
                progress_counter = 0  

                for idx, chat_id in enumerate(all_chat_ids):
                    if stop_event.is_set():  # بررسی توقف اضطراری
                        bot.send_message(message.chat.id, "⛔ عملیات ارسال پیام متوقف شد!")
                        bot.send_message(message.chat.id, f"🔴 ارسال پیام متوقف شد! تعداد ارسال‌شده: {progress_counter} نفر")

                        bot.send_message(settings.matin, "⛔ عملیات ارسال پیام متوقف شد!")
                        bot.send_message(settings.matin, f"🔴 ارسال پیام متوقف شد! تعداد ارسال‌شده: {progress_counter} نفر")
                        
                        return

                    try:
                        if message.content_type == 'text':
                            bot.send_message(chat_id[0], message.text, reply_markup=get_customer_markup(chat_id[0]))
                        elif message.content_type == 'photo':
                            caption = message.caption if message.caption else " "
                            bot.send_photo(chat_id[0], message.photo[-1].file_id, caption=caption, reply_markup=get_customer_markup(chat_id[0]))
                        elif message.content_type == 'video':
                            caption = message.caption if message.caption else " "
                            bot.send_video(chat_id[0], message.video.file_id, caption=caption, reply_markup=get_customer_markup(chat_id[0]))
                        elif message.content_type == 'audio':
                            caption = message.caption if message.caption else " "
                            bot.send_audio(chat_id[0], message.audio.file_id, caption=caption, reply_markup=get_customer_markup(chat_id[0]))
                        elif message.content_type == 'document':
                            caption = message.caption if message.caption else " "
                            bot.send_document(chat_id[0], message.document.file_id, caption=caption, reply_markup=get_customer_markup(chat_id[0]))
                        elif message.content_type == 'sticker':
                            bot.send_sticker(chat_id[0], message.sticker.file_id, reply_markup=get_customer_markup(chat_id[0]))
                        elif message.content_type == 'voice':
                            caption = message.caption if message.caption else " "
                            bot.send_voice(chat_id[0], message.voice.file_id, caption=caption, reply_markup=get_customer_markup(chat_id[0]))
                        elif message.content_type == 'animation':
                            caption = message.caption if message.caption else " "
                            bot.send_animation(chat_id[0], message.animation.file_id, caption=caption, reply_markup=get_customer_markup(chat_id[0]))
                        elif message.content_type == 'video_note':
                            bot.send_video_note(chat_id[0], message.video_note.file_id, reply_markup=get_customer_markup(chat_id[0]))

                        count_29 += 1
                        progress_counter += 1

                        if count_29 == 20:
                            time.sleep(1.5)
                            count_29 = 0

                        if progress_counter % 1000 == 0:
                            progress_message = f"✅ گزارش پیشرفت: تاکنون پیام به {progress_counter} نفر ارسال شد."
                            bot.send_message(settings.matin, text=progress_message)
                            bot.send_message(settings.admin, text=progress_message)

                    except Exception as e:
                        not_send += 1
                        update_block_list(chat_id[0], "add")
                        continue
                    
                sent = total_users - not_send
                final_message = (
                    f"🎉 عملیات ارسال پیام تکمیل شد!\n\n"
                    f"✅ پیام شما به {sent} نفر از کل {total_users} کاربر ارسال شد."
                )
                bot.send_message(message.chat.id, text=final_message, reply_markup=super_admin_markup)
                bot.send_message(settings.matin, text=final_message, reply_markup=super_admin_markup)

            except Exception as e:
                bot.send_message(settings.matin, text=f"❌ Error during sending messages:\n{e}")

    threading.Thread(target=send_messages).start()
    

def check_return(message):
    if message.text == "برگشت 🔙":
        return True
    return False


def check_return_2(message):
    if message.text == "برگشت 🔙":
        bot.send_message(message.chat.id, "به منوی ادمین برگشتید.", reply_markup=super_admin_markup)
        return True
    else:
        return False
    

def get_file_from_db(tracking_code):
    try:
        with sqlite3.connect(settings.database) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT file_id, file_type, caption
                FROM uploaded_files_new
                WHERE tracking_code = ?
            """, (tracking_code,))
            result = cursor.fetchone()
            return result  # (file_id, file_type, caption) یا None
    except sqlite3.Error as e:
        send_error_to_admin(traceback.format_exc())
        return None
    

def send_file_by_type(chat_id, file_id, file_type, caption):
    if caption is None or caption.lower() == "none":
        caption = " " 

    try:
        if file_type == "photo":
            bot.send_photo(chat_id, file_id, caption=caption, reply_markup=get_customer_markup(chat_id))
        elif file_type == "video":
            bot.send_video(chat_id, file_id, caption=caption, reply_markup=get_customer_markup(chat_id))
        elif file_type == "audio":
            bot.send_audio(chat_id, file_id, caption=caption, reply_markup=get_customer_markup(chat_id))
        elif file_type == "document":
            bot.send_document(chat_id, file_id, caption=caption, reply_markup=get_customer_markup(chat_id))
        elif file_type == "audio":
            bot.send_audio(chat_id, file_id, caption=caption, reply_markup=get_customer_markup(chat_id))
        elif file_type == "video_note":
            bot.send_video_note(chat_id, file_id, reply_markup=get_customer_markup(chat_id))
        elif file_type == "voice":
            bot.send_voice(chat_id, file_id, caption=caption, reply_markup=get_customer_markup(chat_id))
        elif file_type == "text":
            bot.send_message(chat_id, caption or "متن ذخیره شده بدون کپشن است.", reply_markup=get_customer_markup(chat_id))
        else:
            bot.send_message(chat_id, "نوع فایل پشتیبانی نمی‌شود.", reply_markup=get_customer_markup(chat_id))
            
    except Exception as e:
        send_error_to_admin(traceback.format_exc())


def handel_hidden_start_msgs(start_msg, chat_id, message):
    first_name = message.from_user.first_name if message.from_user.first_name else "کاربر"
    must_join_keyboard = make_channel_id_keyboard_invited_link(start_msg)
    
    if start_msg.startswith("upload_"):
        if is_member_in_all_channels(chat_id):
            tracking_code = start_msg.split("upload_")[1]  
            file_info = get_file_from_db(tracking_code)
            
            if file_info:
                file_id, file_type, caption = file_info
                send_file_by_type(chat_id, file_id, file_type, caption)
                increment_download_count(tracking_code)
            else:
                bot.reply_to(message, "فایلی با این کد پیگیری پیدا نشد.", reply_markup=get_customer_markup(message.chat.id))
        else: 
            bot.send_message(chat_id, text=f"""
سلام {first_name} عزیز خیلی خوش اومدید ❤️
فقط کافیه کانال تلگرامی ما رو داشته باشی تا هم دیگه رو گم نکنیم 
سپس روی دکمه‌ی عضو هستم کلیک کنید 😊❤️
""", reply_markup=must_join_keyboard, parse_mode="HTML")
            
    elif start_msg.startswith("free_webinar_money"):
        handle_free_registration(message)    
        
    else:
        if is_member_in_all_channels(chat_id):
            bot.send_message(chat_id, text=welcome_msg, reply_markup=get_customer_markup(chat_id) ,parse_mode="HTML")
        else: 
            bot.send_message(chat_id, text=f"""
سلام {first_name} عزیز خیلی خوش اومدید ❤️
فقط کافیه کانال تلگرامی ما رو داشته باشی تا هم دیگه رو گم نکنیم 
سپس روی دکمه‌ی عضو هستم کلیک کنید 😊❤️
""", reply_markup=must_join_keyboard, parse_mode="HTML")
            

def handle_content(message):
    if check_return_2(message):
        return
    
    chat_id = message.chat.id
    content_type = message.content_type

    if content_type in ["text", "photo", "video"]:
        # بررسی وجود کپشن
        caption = message.caption if hasattr(message, 'caption') else "  "  # اگر کپشن نداشت دو فاصله ذخیره می‌شود

        # ذخیره محتوای دریافت شده به همراه کپشن
        contents[chat_id] = {"type": content_type, "data": message.json, "caption": caption}
        
        bot.send_message(chat_id, "محتوا دریافت شد. حالا لطفاً عنوان کلید شیشه‌ای را وارد کنید (حداکثر 50 کاراکتر).", reply_markup=back_markup)
        bot.register_next_step_handler(message, handle_title)
    else:
        msg = bot.send_message(chat_id, "فقط متن، تصویر یا ویدیو مجاز است. لطفاً دوباره تلاش کنید.", reply_markup=back_markup)
        bot.register_next_step_handler(msg, handle_content)

def handle_title(message):
    if check_return_2(message):
        return
    
    chat_id = message.chat.id
    title = message.text

    if len(title) > 50:
        msg = bot.send_message(chat_id, "عنوان نمی‌تواند بیش از 50 کاراکتر باشد. لطفاً دوباره تلاش کنید.", reply_markup=back_markup)
        bot.register_next_step_handler(msg, handle_title)
    else:
        # ذخیره عنوان موقتاً در کلیدها
        bot.send_message(chat_id, "عنوان دریافت شد. حالا لطفاً لینک مربوط به کلید شیشه‌ای را ارسال کنید.", reply_markup=back_markup)
        bot.register_next_step_handler(message, handle_link, title)

def handle_link(message, title):
    if check_return_2(message):
        return
    
    chat_id = message.chat.id
    link = message.text

    if link.startswith("http://") or link.startswith("https://"):
        # ذخیره لینک و عنوان در لیست کلیدها
        content = contents.get(chat_id)  # تغییر به get برای جلوگیری از خطا در صورت عدم وجود محتوا
        if content:
            keyboards[chat_id].append({"title": title, "link": link, "content": content})

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add("اتمام و انتخاب آیدی", "عنوان بعدی")
        bot.send_message(chat_id, "لینک دریافت شد. جهت اتمام ایجاد کلید شیشه‌ای، دکمه 'اتمام و انتخاب آیدی' را انتخاب کنید یا برای ایجاد عنوان جدید، 'عنوان بعدی' را انتخاب کنید.", reply_markup=markup)
        bot.register_next_step_handler(message, handle_finish_or_next)
    else:
        msg = bot.send_message(chat_id, "لینک وارد شده معتبر نیست. لطفاً دوباره تلاش کنید.", reply_markup=back_markup)
        bot.register_next_step_handler(msg, handle_link, title)

def handle_finish_or_next(message):
    if check_return_2(message):
        return
    
    chat_id = message.chat.id
    text = message.text

    if text == "اتمام و انتخاب آیدی":
        msg = bot.send_message(chat_id, "لطفاً یک پیام از گروه یا کانالی که می‌خواهید کلید شیشه‌ای به آن ارسال شود، به ربات فوروارد کنید یا آیدی عددی آن را وارد کنید. توجه داشته باشید که ربات باید در گروه یا کانال ادمین باشد.", reply_markup=back_markup)
        bot.register_next_step_handler(msg, process_forwarded_message)
    elif text == "عنوان بعدی":
        msg = bot.send_message(chat_id, "لطفاً عنوان بعدی کلید شیشه‌ای را وارد کنید (حداکثر 50 کاراکتر).", reply_markup=back_markup)
        bot.register_next_step_handler(msg, handle_title)
    else:
        msg = bot.send_message(chat_id, "گزینه معتبر نیست. لطفاً دوباره تلاش کنید.")
        bot.register_next_step_handler(msg, handle_finish_or_next)

def process_forwarded_message(message):
    if check_return_2(message):
        return
    
    chat_id = message.chat.id
    if message.forward_from_chat:
        destination_id = message.forward_from_chat.id
        send_keyboard(chat_id, destination_id)
    else:
        try:
            destination_id = int(message.text)
            send_keyboard(chat_id, destination_id)
        except ValueError:
            msg = bot.send_message(chat_id, "آیدی وارد شده معتبر نیست. لطفاً یک پیام را فوروارد کنید یا آیدی عددی معتبر وارد کنید.")
            bot.register_next_step_handler(msg, process_forwarded_message)

def send_keyboard(chat_id, destination_id):
    try:
        # ایجاد و ارسال کلیدهای شیشه‌ای
        markup = types.InlineKeyboardMarkup()
        for button in keyboards.get(chat_id, []):
            markup.add(types.InlineKeyboardButton(text=button["title"], url=button["link"]))
        
        content = button.get("content")
        if content:
            if content["type"] == "photo":
                bot.send_photo(destination_id, content["data"]["photo"][0]["file_id"], caption=content["caption"], reply_markup=markup)
            elif content["type"] == "video":
                bot.send_video(destination_id, content["data"]["video"]["file_id"], caption=content["caption"], reply_markup=markup)
            else:
                bot.send_message(destination_id, content["data"]["text"], reply_markup=markup)
                
        bot.send_message(chat_id, "کلیدهای شیشه‌ای ارسال شد.", reply_markup=super_admin_markup)
    except Exception as e:
        bot.send_message(chat_id, "خطا در ارسال کلیدها", reply_markup=super_admin_markup)
        bot.send_message(settings.matin, f"خطا در ارسال کلیدها: {str(e)}", reply_markup=super_admin_markup)

def send_error_to_admin(error_message):
    admin_chat_id = settings.matin
    # bot.send_message(admin_chat_id, f"⚠️ خطا رخ داده است:\n{error_message}")
    log_error_to_file(error_message)

def log_error_to_file(error_message):
    with open("errors.txt", "a", encoding="utf-8") as f:
        timestamp = get_current_timestamp()
        f.write(f"{timestamp} - ERROR - {error_message}\n")
        


def stop_broadcast_handler(call):
    global stop_broadcast, stop_event
    stop_broadcast = True 
    stop_event.set()  
    bot.answer_callback_query(call.id, "⛔ ارسال پیام متوقف شد!")
    bot.send_message(settings.matin, "🛑 توقف اضطراری فعال شد! ارسال پیام‌ها متوقف گردید.", reply_markup=super_admin_markup)
    bot.edit_message_text("⛔ ارسال پیام متوقف شد.", call.message.chat.id, call.message.message_id)

def cancel_stop_handler(call):
    stop_keyboard = types.InlineKeyboardMarkup()
    stop_button = types.InlineKeyboardButton("🛑 توقف اضطراری", callback_data="confirm_stop_broadcast")
    stop_keyboard.add(stop_button)

    bot.edit_message_text("✅ ارسال پیام ادامه دارد!", call.message.chat.id, call.message.message_id, reply_markup=stop_keyboard)

def confirm_stop_broadcast(call):
    confirm_keyboard = types.InlineKeyboardMarkup()
    confirm_keyboard.add(types.InlineKeyboardButton("✔ مطمئن هستم", callback_data="stop_broadcast"))
    confirm_keyboard.add(types.InlineKeyboardButton("❌ انصراف از توقف", callback_data="cancel_stop"))

    bot.edit_message_text("⚠ آیا مطمئن هستید که می‌خواهید ارسال پیام را متوقف کنید؟", 
                          call.message.chat.id, call.message.message_id, 
                          reply_markup=confirm_keyboard)

def make_channel_id_keyboard_invited_link(inviter_link):
    try:
        keyboard = []
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT button_name, link FROM channels ORDER BY id DESC LIMIT 10")
            latest_channels = c.fetchall()
            
        for name, link in latest_channels:
            keyboard.append([types.InlineKeyboardButton(name, url=link)])

        keyboard.append([InlineKeyboardButton(f"✅ عضو شدم!", url=f"{settings.bot_link}?start={inviter_link}")])
        return types.InlineKeyboardMarkup(keyboard)
    
    except Exception as e:
        send_error_to_admin(traceback.format_exc())
        return None


def make_channel_id_keyboard():
    try:
        keyboard = []
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT button_name, link FROM channels ORDER BY id DESC LIMIT 10")
            latest_channels = c.fetchall()

        for name, link in latest_channels:
            keyboard.append([types.InlineKeyboardButton(name, url=link)])

        keyboard.append([types.InlineKeyboardButton("✅ عضو شدم!", url=f"{settings.bot_link}?start=invite_{settings.matin}")])

        return types.InlineKeyboardMarkup(keyboard)
    
    except Exception as e:
        send_error_to_admin(traceback.format_exc())
        return None


def handle_file(message):
    if check_return_2(message):
        return
    
    file_type = None
    file_id = None

    # بررسی کپشن و جایگزینی "None" با رشته خالی
    caption = message.caption if hasattr(message, 'caption') else None
    if caption is None or caption.lower() == "none":
        caption = ""

    # شناسایی نوع فایل
    if message.content_type == 'photo':
        file_type = 'photo'
        file_id = message.photo[-1].file_id  # بالاترین کیفیت عکس
    elif message.content_type == 'video':
        file_type = 'video'
        file_id = message.video.file_id
    elif message.content_type == 'audio':
        file_type = 'audio'
        file_id = message.audio.file_id
    elif message.content_type == 'document':
        file_type = 'document'
        file_id = message.document.file_id
    elif message.content_type == 'audio':
        file_type = 'audio'
        file_id = message.audio.file_id
    elif message.content_type == 'video_note':
        file_type = 'video_note'
        file_id = message.video_note.file_id
    elif message.content_type == 'voice':
        file_type = 'voice'
        file_id = message.voice.file_id
    elif message.content_type == 'text':
        file_type = 'text'
        file_id = "none"
        caption = message.text

    else:
        bot.send_message(message.chat.id, "نوع پیام ارسالی پشتیبانی نمیشود." , reply_markup=super_admin_markup)
        return


    tracking_code = generate_tracking_code()

    # ذخیره فایل در دیتابیس
    save_file_to_db(file_id, file_type, caption, tracking_code)

    # ارسال پیام موفقیت و کد پیگیری
    bot.reply_to(message, f"""
✅ فایل شما با موفقیت ذخیره شد.
{settings.bot_link}?start=upload_{tracking_code}                          
""", reply_markup=super_admin_markup)

def generate_tracking_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
  
def create_uploaded_files_table():
    try:
        with sqlite3.connect(settings.database) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS uploaded_files_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    caption TEXT,
                    count INTEGER,
                    tracking_code TEXT NOT NULL UNIQUE
                )
            """)
            conn.commit()  # عملیات ذخیره‌سازی تغییرات
    except sqlite3.Error as e:
        send_error_to_admin(traceback.format_exc())


def save_file_to_db(file_id, file_type, caption, tracking_code):
    create_uploaded_files_table()
    try:
        with sqlite3.connect(settings.database) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO uploaded_files_new (file_id, file_type, caption, count,tracking_code)
                VALUES (?, ?, ?, ?, ?)
            """, (file_id, file_type, caption,0, tracking_code))
            conn.commit()
    except sqlite3.Error as e:
        send_error_to_admin(traceback.format_exc())



def handle_delete_request(message):
    if check_return_2(message):
        return
    
    link = message.text

    # بررسی و استخراج کد پیگیری از لینک
    tracking_code = extract_tracking_code(link)
    if not tracking_code:
        bot.reply_to(message, "لینک معتبر نیست یا کد پیگیری در آن وجود ندارد. لطفاً دوباره امتحان کنید.", reply_markup=super_admin_markup)
        return

    deleted = delete_file_by_tracking_code(tracking_code)
    if deleted:
        bot.reply_to(message, f"✅ فایل با کد پیگیری {tracking_code} با موفقیت حذف شد.", reply_markup=super_admin_markup)
    else:
        bot.reply_to(message, f"❌ فایل با کد پیگیری {tracking_code} پیدا نشد یا قبلاً حذف شده است.", reply_markup=super_admin_markup)


def extract_tracking_code(link):
    if not link.startswith(settings.bot_link):
        return None
    try:
        return link.split("upload_")[1]
    except IndexError:
        return None


def delete_file_by_tracking_code(tracking_code):
    try:
        with sqlite3.connect(settings.database) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM uploaded_files_new WHERE tracking_code = ?", (tracking_code,))
            conn.commit()
            return cursor.rowcount > 0  
    except sqlite3.Error as e:
        send_error_to_admin(traceback.format_exc())
        return False


    
def get_upload_count_from_link(message):
    if check_return_2(message):
        return
    
    try:
        link = message.text.strip()
        if "?start=upload_" in link:
            tracking_code = link.split("?start=upload_")[-1]
        else:
            bot.send_message(message.chat.id, "لینک نامعتبر است. لطفاً لینک صحیح را ارسال کنید.")
            return
        
        with sqlite3.connect(settings.database) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count FROM uploaded_files_new WHERE tracking_code = ?", (tracking_code,))
            result = cursor.fetchone()
            
            if result:
                bot.send_message(message.chat.id, f"تعداد دانلود ویدیو: {result[0]}", reply_markup=super_admin_markup)
            else:
                bot.send_message(message.chat.id, "کد پیگیری یافت نشد.", reply_markup=super_admin_markup)
    except Exception as e:
        bot.send_message(message.chat.id, "خطایی رخ داد. لطفاً دوباره تلاش کنید.", reply_markup=super_admin_markup)
        send_error_to_admin(traceback.format_exc())

def increment_download_count(tracking_code):
    try:
        with sqlite3.connect(settings.database) as conn:
            cursor = conn.cursor()
            # افزایش تعداد دانلود به اندازه ۱
            cursor.execute("UPDATE uploaded_files_new SET count = count + 1 WHERE tracking_code = ?", (tracking_code,))
            conn.commit()
    except sqlite3.Error:
        send_error_to_admin(traceback.format_exc())
        return None

def save_admin_username(message):
    global admin_username
    if check_return_2(message):
        return
    chat_id = message.chat.id
    username = message.text.strip()
    if not username.startswith("@"):
        msg = bot.send_message(chat_id, "آیدی باید با @ شروع شود. لطفاً مجدداً ارسال کنید:", reply_markup=back_markup)
        bot.register_next_step_handler(msg, save_admin_username)
        return
    admin_username = username
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            c.execute("""
                INSERT INTO bot_settings (key, value) VALUES ('admin_username', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """, (username,))
            conn.commit()
        bot.send_message(chat_id, f"آیدی پشتیبانی با موفقیت به {username} تغییر یافت.", reply_markup=super_admin_markup)
    except Exception as e:
        bot.send_message(settings.matin, f"خطا در ذخیره آیدی پشتیبانی: {e}")

def load_admin_username():
    global admin_username
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            c.execute("SELECT value FROM bot_settings WHERE key='admin_username'")
            result = c.fetchone()
            if result:
                admin_username = result[0]
    except Exception as e:
        pass

load_admin_username()




# ------------------- تنظیم کانال مدرک شارژ توسط ادمین -------------------

def init_charge_doc_channel_db():
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS charge_doc_channel (
                    id INTEGER PRIMARY KEY,
                    channel_id TEXT
                )
            """)
            conn.commit()
    except Exception as e:
        send_error_to_admin(traceback.format_exc())

def save_charge_doc_channel_id(channel_id):
    init_charge_doc_channel_db()
    global charge_doc_channel_id
    charge_doc_channel_id = channel_id
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO charge_doc_channel (id, channel_id) VALUES (1, ?)
                ON CONFLICT(id) DO UPDATE SET channel_id=excluded.channel_id
            """, (str(channel_id),))
            conn.commit()
    except Exception as e:
        send_error_to_admin(traceback.format_exc())

def load_charge_doc_channel_id():
    global charge_doc_channel_id
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT channel_id FROM charge_doc_channel WHERE id=1")
            result = c.fetchone()
            if result and result[0]:
                charge_doc_channel_id = result[0]
    except Exception as e:
        pass

load_charge_doc_channel_id()


def handle_forwarded_charge_doc_channel(message):
    if check_return_2(message):
        return
    chat_id = message.chat.id
    if not message.forward_from_chat:
        msg = bot.send_message(
            chat_id,
            "⚠️ <b>لطفاً حتماً یک پیام از کانال را به ربات فوروارد کنید.</b>\n\n"
            "🔹 <b>قبل از فوروارد کردن پیام، باید ربات را به عنوان <u>ادمین</u> در آن کانال اضافه کنید.</b>\n"
            "در غیر این صورت ربات نمی‌تواند کانال را شناسایی کند و عملیات انجام نمی‌شود.\n\n"
            "✅ <b>مراحل انجام کار:</b>\n"
            "۱️⃣ ابتدا ربات را به کانال مورد نظر اضافه و به عنوان <b>ادمین</b> انتخاب کنید.\n"
            "۲️⃣ سپس یک پیام از همان کانال را به ربات <b>فوروارد</b> نمایید.\n\n"
            "⛔️ <i>در صورتی که ربات ادمین نباشد، امکان ثبت کانال وجود ندارد.</i>",
            reply_markup=back_markup,
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, handle_forwarded_charge_doc_channel)
        return
    channel_id = message.forward_from_chat.id
    try:
        bot.send_message(channel_id, "✅ ربات با موفقیت در این کانال تنظیم شد.")
        save_charge_doc_channel_id(channel_id)
        bot.send_message(chat_id, f"کانال با موفقیت تنظیم شد.\nChat ID: <code>{channel_id}</code>", parse_mode="HTML", reply_markup=super_admin_markup)
    except Exception as e:
        bot.send_message(chat_id, "❌ ربات باید ادمین کانال باشد وگرنه نمی‌تواند پیام ارسال کند.\nعملیات متوقف شد و به منوی ادمین برگشتید.", reply_markup=super_admin_markup)
        send_error_to_admin(traceback.format_exc())

############ MAIN PART ############################################################



##############################################
# شروع فعال یا غیرفعال کردن ثبت‌نام در دوره
REGISTRATION_ENABLED = True

# ---------- 1) ایجاد جدول تنظیمات ----------
def is_user_blocked_by_security(chat_id, text=None):
    # Allow group/supergroup chats
    if int(chat_id) < 0:
        return False
        
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        return False
        
    security_mode = '0'
    try:
        import sqlite3
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM bot_settings WHERE key = 'SECURITY_MODE'")
            row = c.fetchone()
            if row and row[0]:
                security_mode = row[0]
    except:
        pass
        
    if security_mode != '1':
        return False
        
    if text and text.startswith("/start inv_"):
        return False
        
    # Check database status
    try:
        import sqlite3
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT role FROM users WHERE user_id = ?", (int(chat_id),))
            row = c.fetchone()
            if row:
                if row[0] == "seller":
                    return False
                    
            # Check if user has ever used a valid invite link
            c.execute("SELECT 1 FROM invite_links WHERE used_by = ?", (int(chat_id),))
            if c.fetchone():
                return False
    except:
        pass
        
    return True


@bot.callback_query_handler(func=lambda call: is_user_blocked_by_security(call.from_user.id))
def handle_blocked_callback_query(call):
    bot.answer_callback_query(call.id, "🔐 جهت استفاده از ربات باید دعوت شده باشید.", show_alert=True)


@bot.message_handler(func=lambda message: is_user_blocked_by_security(message.chat.id, message.text))
def handle_blocked_user(message):
    msg = (
        "🔐 <b>ورود محدود | حالت امنیت فعال است</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ <b>کاربر گرامی، جهت استفاده از خدمات این ربات، شما حتماً باید از طرف فروشنده مجاز دعوت شده باشید.</b>\n\n"
        "✉️ اگر لینک دعوت معتبر دارید، لطفاً ربات را از طریق همان لینک شروع (Start) کنید.\n\n"
        "🔗 در غیر این صورت، برای دریافت دعوت‌نامه با فروشنده یا پشتیبانی ربات هماهنگ کنید."
    )
    bot.send_message(
        message.chat.id,
        msg,
        parse_mode="HTML"
    )


@bot.message_handler(commands=['start'])
def handle_start(message):
    must_join_keyboard = make_channel_id_keyboard()
    Chat = message.chat.id
    Chat_id = message.from_user.id
    first_name = message.from_user.first_name if message.from_user.first_name else " "
    last_name = message.from_user.last_name if message.from_user.last_name else " "
    username = message.from_user.username if message.from_user.username else " "

    try:
        import sqlite3
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            
            # Extract invite token if any
            args = message.text.split()
            invite_token = None
            if len(args) > 1 and args[1].startswith("inv_"):
                invite_token = args[1].split("inv_")[1]
                
            c.execute("SELECT role, parent_seller_id FROM users WHERE user_id = ?", (Chat_id,))
            row = c.fetchone()
            
            user_role = row[0] if row else "customer"
            parent_seller_id = row[1] if row else None
            is_new = not row
            
            c.execute("SELECT value FROM bot_settings WHERE key = 'SINGLE_SELLER_ID'")
            s_row = c.fetchone()
            target_seller_id = int(s_row[0]) if s_row and s_row[0] else int(settings.admin)
            
            # If invite token is supplied, validate it!
            if invite_token:
                c.execute("SELECT used, seller_id FROM invite_links WHERE token = ?", (invite_token,))
                inv_row = c.fetchone()
                if not inv_row:
                    bot.send_message(Chat, "❌ این لینک دعوت نامعتبر است.")
                    return
                used, inv_seller_id = inv_row
                if used == 1:
                    bot.send_message(Chat, "❌ این لینک دعوت قبلاً استفاده شده است.")
                    return
                    
                # Mark link as used
                c.execute("UPDATE invite_links SET used = 1, used_by = ? WHERE token = ?", (Chat_id, invite_token))
                
                # Notify seller
                seller_msg = (
                    "👤 <b>کاربر جدید دعوت شده به ربات پیوست!</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"• نام: {first_name} {last_name}\n"
                    f"• یوزرنیم: @{username}\n"
                    f"• آیدی عددی: <code>{Chat_id}</code>\n"
                    f"• کد دعوت استفاده شده: <code>{invite_token}</code>"
                )
                try:
                    bot.send_message(target_seller_id, seller_msg, parse_mode="HTML")
                except Exception as ex:
                    print("Error notifying seller of invite:", ex)
                    
            if is_new:
                c.execute("INSERT INTO users (chat_id, user_id, parent_seller_id) VALUES (?, ?, ?)", (Chat, Chat_id, target_seller_id))
                conn.commit()
                parent_seller_id = target_seller_id
            elif not parent_seller_id:
                c.execute("UPDATE users SET parent_seller_id = ? WHERE user_id = ?", (target_seller_id, Chat_id))
                conn.commit()
                parent_seller_id = target_seller_id

        # Admin Logic
        if (int(Chat_id) in settings.admin_list) or (int(Chat_id) in get_admin_ids()):
            save_info(Chat, first_name, last_name, Chat_id, username)
            bot.send_message(message.chat.id, text=f"Welcome {first_name}, you are Admin 🦾", reply_markup=super_admin_markup)
            return
            
        # Seller Logic
        if user_role == "seller":
            save_info(Chat, first_name, last_name, Chat_id, username)
            bot.send_message(Chat_id, text=f"سلام {first_name} عزیز، به پنل فروشندگی خود خوش آمدید! 🛍", reply_markup=get_seller_markup(Chat_id))
            return

        if parent_seller_id:
            if is_member_in_all_channels(Chat_id):
                save_info(Chat, first_name, last_name, Chat_id, username)
                bot.send_message(Chat_id, text=welcome_msg, reply_markup=get_customer_markup(Chat_id), parse_mode="HTML")
            else:
                save_info(Chat, first_name, last_name, Chat_id, username)
                bot.send_message(Chat_id, text=f"""سلام {first_name} عزیز خیلی خوش اومدید ❤️
فقط کافیه کانال تلگرامی ما رو داشته باشی تا هم دیگه رو گم نکنیم 
سپس روی دکمه‌ی عضو هستم کلیک کنید 😊❤️""", reply_markup=must_join_keyboard, parse_mode="HTML")

    except Exception as e:
        send_error_to_admin(traceback.format_exc())




# --- استارت جریان حذف


def get_back_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔙 بازگشت به منوی اصلی")
    return markup




def random_string(length=6):
    import random
    import string
    letters = string.ascii_letters + string.digits
    return ''.join(random.choice(letters) for i in range(length))




@bot.message_handler(func=lambda message: message.text == "🔙 بازگشت به منوی اصلی")
def handle_back_to_main(message):
    bot.send_message(
        message.chat.id,
        "🏠 <b>به منوی اصلی بازگشتید.</b>\n\n"
        "از گزینه‌های زیر استفاده کنید 👇",
        parse_mode='HTML',
        reply_markup=get_customer_markup(message.chat.id)
    )
    # پاکسازی state اگر نیاز بود:
    user_id = message.from_user.id
    temp_data.pop(user_id, None)


@bot.message_handler(func=lambda message: message.text == "✅ تنظیم کانال اطلاع رسانی")
def set_charge_doc_channel(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        msg = bot.send_message(chat_id, "لطفاً یک پیام از کانال را به ربات فوروارد کنید (ربات باید ادمین کانال باشد).", reply_markup=back_markup)
        bot.register_next_step_handler(msg, handle_forwarded_charge_doc_channel)
    else:
        bot.send_message(chat_id, "شما دسترسی لازم برای این عملیات را ندارید.", reply_markup=get_customer_markup(chat_id))


@bot.message_handler(func=lambda message: message.text in ["برگشت 🔙"])
def process_consent(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "به منوی اصلی برگشتید!", reply_markup=get_customer_markup(chat_id))


@bot.message_handler(func=lambda message: message.text in ["☎️ پشتیبانی", "☎️ ارتباط با پشتیبانی"])
def handle_poshtibani(message):
    chat_id = message.chat.id
    import sqlite3
    from env import settings
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT parent_seller_id FROM users WHERE user_id = ?", (chat_id,))
            row = c.fetchone()
            parent_id = row[0] if row else None
            
            if parent_id:
                c.execute("SELECT support_id FROM seller_configs WHERE seller_id = ?", (parent_id,))
                seller_row = c.fetchone()
                if seller_row and seller_row[0]:
                    markup = InlineKeyboardMarkup()
                    support_link = seller_row[0]
                    if not support_link.startswith("http") and not support_link.startswith("@"):
                        support_link = "https://t.me/" + support_link
                    elif support_link.startswith("@"):
                        support_link = "https://t.me/" + support_link[1:]
                    markup.add(InlineKeyboardButton("🛎️ پشتیبانی فروشنده", url=support_link))
                    bot.send_message(chat_id, "☎️ برای ارتباط با پشتیبانی، پیام خود را به آیدی زیر ارسال کنید:", reply_markup=markup)
                    return
    except Exception as e:
        print("Error in poshtibani:", e)

    bot.send_message(chat_id, text=poshtibani_msg, reply_markup=connect_poshtibani_markup)

@bot.message_handler(func=lambda message: message.text in ["🌐 ارتباط با ما", "🌐شبکه های اجتماعی ما"])
def handle_ertebat(message):
    chat_id = message.chat.id
    import sqlite3
    from env import settings
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT parent_seller_id FROM users WHERE user_id = ?", (chat_id,))
            row = c.fetchone()
            parent_id = row[0] if row else None
            
            if parent_id:
                c.execute("SELECT support_id, channel_id, instagram_id FROM seller_configs WHERE seller_id = ?", (parent_id,))
                seller_row = c.fetchone()
                if seller_row and any(seller_row):
                    markup = InlineKeyboardMarkup()
                    support_id, channel_id, instagram_id = seller_row
                    
                    if instagram_id:
                        link = instagram_id if instagram_id.startswith("http") else "https://instagram.com/" + instagram_id.replace("@", "")
                        markup.add(InlineKeyboardButton("📸 اینستاگرام فروشنده", url=link))
                    if channel_id:
                        link = channel_id if channel_id.startswith("http") else "https://t.me/" + channel_id.replace("@", "")
                        markup.add(InlineKeyboardButton("🌟 کانال فروشگاه", url=link))
                    if support_id:
                        link = support_id if support_id.startswith("http") else "https://t.me/" + support_id.replace("@", "")
                        markup.add(InlineKeyboardButton("🛎️ پشتیبانی فروشنده", url=link))
                    
                    bot.send_message(chat_id, "برای ارتباط با ما و دریافت پشتیبانی، می‌توانید از شبکه‌های اجتماعی زیر استفاده کنید:", reply_markup=markup)
                    return
    except Exception as e:
        print("Error in ertebat:", e)

    bot.send_message(chat_id, text=connect_with_us, reply_markup=connect_with_us_markup)
    
    
@bot.message_handler(func=lambda message: message.text == "بررسی وضعیت لینک آپلود")
def ask_for_link(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        bot.send_message(message.chat.id, "لطفاً لینک مربوطه را ارسال نمایید:", reply_markup=back_markup)
        bot.register_next_step_handler(message, get_upload_count_from_link)


@bot.message_handler(func=lambda message: message.text == "ایجاد کلید شیشه ای")
def ask_for_content(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        keyboards[chat_id] = []  # ایجاد لیست جدید برای ذخیره کلیدها
        msg = bot.send_message(chat_id, "لطفاً محتوایی که می‌خواهید به کلید شیشه‌ای متصل کنید (متن، تصویر، ویدیو یا کپشن) را ارسال کنید.", reply_markup=back_markup)
        bot.register_next_step_handler(msg, handle_content)
    else:
        bot.send_message(chat_id, "شما دسترسی لازم برای این عملیات را ندارید.", reply_markup=get_customer_markup(chat_id))


@bot.message_handler(func=lambda message: message.text and message.text.strip() == "پنل")
def handle_panel_word(message):
    chat_id = message.chat.id
    
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        bot.send_message(chat_id, "به پنل سوپر ادمین خوش آمدید:", reply_markup=super_admin_markup)
        return
    
    import sqlite3
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT role FROM users WHERE user_id = ?", (chat_id,))
            row = c.fetchone()
            if row and row[0] == 'seller':
                bot.send_message(chat_id, "به پنل فروشندگی خود خوش آمدید! 🛍", reply_markup=get_seller_markup(chat_id))
                return
    except:
        pass


@bot.message_handler(func=lambda message: message.text == "🔙 برگشت به پنل ادمین")
def new_Aghahi(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        bot.send_message(message.chat.id, text=f"به پنل ادمین متصل شدید", reply_markup=super_admin_markup)

        
@bot.message_handler(func=lambda message: message.text == "➰ منوی کاربر عادی")
def back(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        bot.send_message(message.chat.id,
                         "به منوی کاربری عادی متصل شدید\n(جهت برگشتن به منوی ادمین مجددا /start را بزنید.)",
                         reply_markup=get_customer_markup(message.chat.id))


@bot.message_handler(func=lambda message: message.text == "🗑️ حذف کانال")
def new_Aghahi(message):
    chat_id = message.chat.id
    keyboard = make_delete_channel_id_keyboard()
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        bot.send_message(message.chat.id, "جهت حذف، بر روی آیدی کانال مورد نظر کلیک کنید.", reply_markup=keyboard)


@bot.message_handler(func=lambda message: message.text == "➕ افزودن کانال")
def admin_keyboard_set_tablighat(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        temp_data[chat_id] = {}
        msg = bot.send_message(chat_id, "لطفاً یک نام کوتاه برای دکمه شیشه‌ای (حداکثر ۴۰ کاراکتر) ارسال کنید:", reply_markup=back_markup)
        bot.register_next_step_handler(msg, get_button_name)


@bot.message_handler(func=lambda message: message.text == "📊 آمار ربات")
def button(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        all_user_num = search_all_users()
        bot.send_message(message.chat.id, f"""
آمار ربات

تعداد کل کاربران ربات: {all_user_num}

🆔 {settings.bot_id}
""")


@bot.message_handler(func=lambda message: message.text == "📢 پیام همگانی")
def admin_keyboard_set_tablighat(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        msg = bot.send_message(message.chat.id, "فایل یا پیام خود را جهت ارسال همگانی ارسال نمایید.",
                               reply_markup=back_markup)
        bot.register_next_step_handler(msg, lambda user_message: confirm_send_all_users(user_message))


@bot.message_handler(func=lambda message: message.text == "دیتا")
def new_Aghahi(message):
    if str(message.chat.id) == settings.matin:
        try:
            with open(settings.database, "rb") as f:
                bot.send_document(settings.matin, f)

            with open("errors.txt", "rb") as f:
                bot.send_document(settings.matin, f)
                
            bot.send_message(message.chat.id, text="آخرین اطلاعات آپدیت شد.", reply_markup=super_admin_markup)
        except Exception as e:
            send_error_to_admin(traceback.format_exc())


@bot.message_handler(func=lambda message: message.text == "➕ افزودن ادمین")
def admin_keyboard_set_tablighat(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list):
        msg = bot.send_message(message.chat.id, "آیدی عددی ادمین را ارسال نمایید.", reply_markup=back_markup)
        bot.register_next_step_handler(msg, lambda user_message: save_new_admin(user_message.text, user_message))


@bot.message_handler(func=lambda message: message.text == "❌ حذف ادمین")
def new_Aghahi(message):
    chat_id = message.chat.id
    keyboard = make_delete_admin_list_keyboard()
    if (int(chat_id) in settings.admin_list):
        bot.send_message(message.chat.id, "جهت حذف، بر روی آیدی عددی ادمین مورد نظر کلیک کنید.", reply_markup=keyboard)


@bot.message_handler(func=lambda message: message.text == "🚫 حذف لینک آپلودر"and message.chat.type == "private")
def request_tracking_code(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        
        bot.reply_to(message, "لطفاً لینک مربوط به فایل آپلود شده را ارسال کنید.", reply_markup=back_markup)
        bot.register_next_step_handler(message, handle_delete_request)
        
    
@bot.message_handler(func=lambda message: message.text == "📤 آپلود فایل جدید"and message.chat.type == "private")
def request_file(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        bot.reply_to(message, "فایل مورد نظر خود را جهت تبدیل به لینک ارسال کنید:", reply_markup=back_markup)
        bot.register_next_step_handler(message, handle_file)
        
        
@bot.message_handler(func=lambda message: message.text == "👤 تنظیم آیدی پشتیبانی")
def set_admin_username(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        msg = bot.send_message(chat_id, "لطفاً آیدی جدید پشتیبانی (مثلاً @username) را ارسال کنید:", reply_markup=back_markup)
        bot.register_next_step_handler(msg, save_admin_username)
    else:
        bot.send_message(chat_id, "شما دسترسی لازم برای این عملیات را ندارید.", reply_markup=get_customer_markup(chat_id))






def init_base_db():
    """Delegate all schema setup to centralized migrations."""
    from traffic_service import run_migrations, verify_schema
    run_migrations()
    issues = verify_schema()
    if issues:
        print("Schema verification warnings:")
        for issue in issues:
            print(" -", issue)
            
    # Auto-insert/update the single seller config for the main admin
    try:
        import sqlite3
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            admin_id = int(settings.admin)
            # Check if admin is in users as a seller
            c.execute("SELECT role FROM users WHERE user_id = ?", (admin_id,))
            row = c.fetchone()
            if not row:
                c.execute("INSERT INTO users (chat_id, user_id, role, parent_seller_id) VALUES (?, ?, 'seller', ?)", (admin_id, admin_id, admin_id))
            else:
                c.execute("UPDATE users SET role = 'seller', parent_seller_id = ? WHERE user_id = ?", (admin_id, admin_id))
                
            # Check if admin is in seller_configs
            c.execute("SELECT seller_id FROM seller_configs WHERE seller_id = ?", (admin_id,))
            if not c.fetchone():
                c.execute("INSERT INTO seller_configs (seller_id, total_bulk_gb, used_bulk_gb, nickname) VALUES (?, 999999.0, 0.0, 'مدیریت')", (admin_id,))
            conn.commit()
    except Exception as e:
        print("Error initializing single seller database settings:", e)

init_base_db()

from traffic_service import check_and_alert_low_traffic

# ========================================================================================================
# Wallet Management Handlers
# ========================================================================================================

@bot.message_handler(func=lambda message: message.text in ["💳 تنظیمات پرداخت", "💳 مدیریت ولت‌ها"])
def manage_wallets_menu(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        show_payment_settings_view(chat_id)

def show_payment_settings_view(chat_id, edit_message_id=None):
    with sqlite3.connect(settings.database) as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM bot_settings WHERE key = 'PAYMENT_CARD_STATUS'")
        card_status_row = c.fetchone()
        c.execute("SELECT value FROM bot_settings WHERE key = 'PAYMENT_CRYPTO_STATUS'")
        crypto_status_row = c.fetchone()
        c.execute("SELECT value FROM bot_settings WHERE key = 'SUPER_ADMIN_BANK_CARD'")
        card_row = c.fetchone()
        c.execute("SELECT value FROM bot_settings WHERE key = 'SUPER_ADMIN_CARD_OWNER'")
        owner_row = c.fetchone()
        c.execute("SELECT id, network, currency, address FROM admin_wallets")
        wallets = c.fetchall()

    card_status = card_status_row[0] if card_status_row and card_status_row[0] else '1'
    crypto_status = crypto_status_row[0] if crypto_status_row and crypto_status_row[0] else '1'

    card_status_text = "🟢 فعال" if card_status == '1' else "🔴 غیرفعال"
    crypto_status_text = "🟢 فعال" if crypto_status == '1' else "🔴 غیرفعال"

    card_display = card_row[0] if card_row and card_row[0] else "تنظیم نشده"
    owner_display = owner_row[0] if owner_row and owner_row[0] else "—"

    msg = (
        "💳 <b>تنظیمات روش‌های پرداخت سوپر ادمین</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>۱. کارت به کارت:</b> {card_status_text}\n"
        f"📥 شماره کارت: <code>{card_display}</code>\n"
        f"👤 به نام: <b>{owner_display}</b>\n\n"
        f"<b>۲. ارز دیجیتال:</b> {crypto_status_text}\n"
    )

    if not wallets:
        msg += "📥 هیچ ولتی ثبت نشده است."
    else:
        msg += "لیست ولت‌های ثبت شده:\n\n"
        for w in wallets:
            msg += f"• ID: {w[0]} | {w[1]} ({w[2]}): <code>{w[3]}</code>\n"

    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("💳 تغییر وضعیت کارت", callback_data="toggle_pay_card"),
        InlineKeyboardButton("🌐 تنظیم کارت بانکی", callback_data="set_admin_bank_card")
    )
    markup.row(
        InlineKeyboardButton("🪙 تغییر وضعیت ولت", callback_data="toggle_pay_crypto"),
        InlineKeyboardButton("➕ افزودن ولت جدید", callback_data="add_new_wallet")
    )
    
    if wallets:
        for w in wallets:
            markup.row(InlineKeyboardButton(f"❌ حذف ولت {w[0]} - {w[1]}", callback_data=f"del_wallet_{w[0]}"))

    if edit_message_id:
        try:
            bot.edit_message_text(msg, chat_id, edit_message_id, reply_markup=markup, parse_mode="HTML")
        except:
            bot.send_message(chat_id, msg, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(chat_id, msg, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data in ["toggle_pay_card", "toggle_pay_crypto"])
def toggle_payment_status(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        key = "PAYMENT_CARD_STATUS" if call.data == "toggle_pay_card" else "PAYMENT_CRYPTO_STATUS"
        
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
            row = c.fetchone()
            curr = row[0] if row and row[0] else '1'
            new_val = '0' if curr == '1' else '1'
            c.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)", (key, new_val))
            conn.commit()
            
        bot.answer_callback_query(call.id, "وضعیت پرداخت تغییر کرد.")
        show_payment_settings_view(chat_id, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data == "set_admin_bank_card")
def set_admin_bank_card_start(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        msg = bot.send_message(chat_id, "لطفاً شماره کارت بانکی را وارد کنید:")
        bot.register_next_step_handler(msg, set_admin_bank_card_step2)
    bot.answer_callback_query(call.id)

def set_admin_bank_card_step2(message):
    card = message.text.strip()
    msg = bot.send_message(message.chat.id, "لطفاً نام صاحب کارت را وارد کنید:")
    bot.register_next_step_handler(msg, save_admin_bank_card, card)

def save_admin_bank_card(message, card):
    owner = message.text.strip()
    with sqlite3.connect(settings.database) as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('SUPER_ADMIN_BANK_CARD', ?)", (card,))
        c.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('SUPER_ADMIN_CARD_OWNER', ?)", (owner,))
        conn.commit()
    bot.send_message(message.chat.id, "✅ اطلاعات کارت بانکی ذخیره شد.")
    show_payment_settings_view(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_wallet_"))
def del_wallet_callback(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        wallet_id = call.data.split("_")[2]
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM admin_wallets WHERE id = ?", (wallet_id,))
            conn.commit()
        bot.answer_callback_query(call.id, "ولت با موفقیت حذف شد.")
        show_payment_settings_view(chat_id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "add_new_wallet")
def add_wallet_step1(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        msg = bot.send_message(chat_id, "لطفاً شبکه ولت را وارد کنید (مثلاً TRC20):")
        bot.register_next_step_handler(msg, add_wallet_step2)

def add_wallet_step2(message):
    network = message.text
    msg = bot.send_message(message.chat.id, f"شبکه: {network}\nلطفاً نوع ارز را وارد کنید (مثلاً USDT):")
    bot.register_next_step_handler(msg, add_wallet_step3, network)

def add_wallet_step3(message, network):
    currency = message.text
    msg = bot.send_message(message.chat.id, f"شبکه: {network}\nارز: {currency}\nلطفاً آدرس ولت را وارد کنید:")
    bot.register_next_step_handler(msg, save_new_wallet, network, currency)

def save_new_wallet(message, network, currency):
    address = message.text
    with sqlite3.connect(settings.database) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO admin_wallets (network, currency, address) VALUES (?, ?, ?)", (network, currency, address))
        conn.commit()
    bot.send_message(message.chat.id, "ولت با موفقیت ثبت شد ✅")


# ========================================================================================================
# Package Management Handlers
# ========================================================================================================

@bot.message_handler(func=lambda message: message.text == "👤 تنظیم فروشنده")
def set_single_seller_start(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM bot_settings WHERE key = 'SINGLE_SELLER_ID'")
            s_row = c.fetchone()
            c.execute("SELECT value FROM bot_settings WHERE key = 'SINGLE_SELLER_PREFIX'")
            p_row = c.fetchone()
            
            curr_id = s_row[0] if s_row else "تنظیم نشده"
            curr_prefix = p_row[0] if p_row else "تنظیم نشده"
            
        msg = (
            f"👤 <b>تنظیم فروشنده واحد ربات</b>\n\n"
            f"فروشنده فعلی: <code>{curr_id}</code>\n"
            f"پیش‌وند کاربری: <code>{curr_prefix}</code>\n\n"
            f"لطفاً آیدی عددی تلگرام فروشنده جدید را وارد کنید (فقط عدد):"
        )
        msg_obj = bot.send_message(chat_id, msg, parse_mode="HTML", reply_markup=back_markup)
        bot.register_next_step_handler(msg_obj, save_single_seller_step1)

def save_single_seller_step1(message):
    chat_id = message.chat.id
    if message.text == "برگشت 🔙":
        bot.send_message(chat_id, "عملیات لغو شد.", reply_markup=super_admin_markup)
        return
    try:
        seller_id = int(message.text.strip())
        msg = bot.send_message(chat_id, f"آیدی فروشنده: {seller_id}\nلطفاً پیش‌وند نام کاربری کانفیگ‌های این فروشنده را وارد کنید (مثلاً SM - یا اگر نمی‌خواهید پیش‌وند بگذارید فقط '-' بنویسید):", reply_markup=back_markup)
        bot.register_next_step_handler(msg, save_single_seller_step2, seller_id)
    except ValueError:
        bot.send_message(chat_id, "❌ خطا: لطفاً فقط آیدی عددی تلگرام را وارد کنید. عملیات لغو شد.", reply_markup=super_admin_markup)

def save_single_seller_step2(message, seller_id):
    chat_id = message.chat.id
    if message.text == "برگشت 🔙":
        bot.send_message(chat_id, "عملیات لغو شد.", reply_markup=super_admin_markup)
        return
        
    prefix = message.text.strip()
    if prefix == "-":
        prefix = ""
        
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            # 1. Update bot_settings
            c.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('SINGLE_SELLER_ID', ?)", (str(seller_id),))
            c.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('SINGLE_SELLER_PREFIX', ?)", (prefix,))
            
            # 2. Update users role to seller for the user
            c.execute("SELECT role FROM users WHERE user_id = ?", (seller_id,))
            row = c.fetchone()
            if not row:
                c.execute("INSERT INTO users (chat_id, user_id, role, parent_seller_id) VALUES (?, ?, 'seller', ?)", (seller_id, seller_id, seller_id))
            else:
                c.execute("UPDATE users SET role = 'seller', parent_seller_id = ? WHERE user_id = ?", (seller_id, seller_id))
                
            # 3. Insert or update seller_configs
            c.execute("SELECT seller_id FROM seller_configs WHERE seller_id = ?", (seller_id,))
            if not c.fetchone():
                c.execute("INSERT INTO seller_configs (seller_id, total_bulk_gb, used_bulk_gb, nickname, username_prefix) VALUES (?, 0.0, 0.0, 'فروشنده', ?)", (seller_id, prefix))
            else:
                c.execute("UPDATE seller_configs SET username_prefix = ? WHERE seller_id = ?", (prefix, seller_id))
                
            # 4. Automatically re-bind ALL customers to this new single seller ID
            c.execute("UPDATE users SET parent_seller_id = ? WHERE role = 'customer' AND user_id != ?", (seller_id, seller_id))
            conn.commit()
            
        bot.send_message(chat_id, f"✅ فروشنده با موفقیت تنظیم شد!\nآیدی: <code>{seller_id}</code>\nپیش‌وند: <code>{prefix}</code>\nتمامی مشتریان موجود به این فروشنده متصل شدند.", parse_mode="HTML", reply_markup=super_admin_markup)
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطا در ثبت اطلاعات دیتابیس:\n{e}", reply_markup=super_admin_markup)

@bot.message_handler(func=lambda message: message.text == "👥 تنظیم گروه رسیدها")
def set_receipt_group_start(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM bot_settings WHERE key = 'SELLER_RECEIPT_GROUP'")
            g_row = c.fetchone()
            curr_group = g_row[0] if g_row else "تنظیم نشده"
            
        msg = (
            f"👥 <b>تنظیم گروه رسیدهای پرداختی فروشندگان</b>\n\n"
            f"گروه فعلی: <code>{curr_group}</code>\n\n"
            f"لطفاً آیدی عددی گروه تلگرام رسیدهای پرداخت را وارد کنید (باید با - یا -100 شروع شود):"
        )
        msg_obj = bot.send_message(chat_id, msg, parse_mode="HTML", reply_markup=back_markup)
        bot.register_next_step_handler(msg_obj, save_receipt_group)

def save_receipt_group(message):
    chat_id = message.chat.id
    if message.text == "برگشت 🔙":
        bot.send_message(chat_id, "عملیات لغو شد.", reply_markup=super_admin_markup)
        return
    try:
        group_id = int(message.text.strip())
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('SELLER_RECEIPT_GROUP', ?)", (str(group_id),))
            conn.commit()
        bot.send_message(chat_id, f"✅ گروه رسیدها با موفقیت تنظیم شد:\n<code>{group_id}</code>", parse_mode="HTML", reply_markup=super_admin_markup)
    except ValueError:
        bot.send_message(chat_id, "❌ خطا: لطفاً فقط آیدی عددی صحیح گروه (مثال: -100123456789) را وارد کنید.", reply_markup=super_admin_markup)

@bot.message_handler(func=lambda message: message.text == "📦 مدیریت بسته‌های حجمی")
def manage_packages_menu(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("➕ افزودن بسته جدید", callback_data="add_new_package"))
        
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT id, title, volume_gb, price_toman, price_usd FROM seller_packages")
            packages = c.fetchall()
            
            if not packages:
                msg = "هیچ بسته‌ای تعریف نشده است."
            else:
                msg = "لیست بسته‌های تعریف شده:\n\n"
                for p in packages:
                    pt = p[3] or 0
                    pu = p[4] or 0
                    msg += f"🆔 ID: {p[0]}\n🏷 عنوان: {p[1]}\n📦 حجم: {p[2]} گیگابایت\n💵 قیمت: {pt:,} تومان\n💲 قیمت: {pu} دلار\n"
                    markup.add(InlineKeyboardButton(f"❌ حذف بسته {p[0]}", callback_data=f"del_package_{p[0]}"))
        
        bot.send_message(chat_id, msg, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_package_"))
def del_package_callback(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        package_id = call.data.split("_")[2]
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM seller_packages WHERE id = ?", (package_id,))
            conn.commit()
        bot.answer_callback_query(call.id, "بسته با موفقیت حذف شد.")
        bot.delete_message(chat_id, call.message.message_id)
        manage_packages_menu(call.message)

@bot.callback_query_handler(func=lambda call: call.data == "add_new_package")
def add_package_step1(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        msg = bot.send_message(chat_id, "لطفاً عنوان بسته را وارد کنید (مثلاً ۱ ترابایت طلایی):")
        bot.register_next_step_handler(msg, add_package_step2)

def add_package_step2(message):
    title = message.text
    msg = bot.send_message(message.chat.id, f"عنوان: {title}\nلطفاً حجم بسته را به گیگابایت (فقط عدد) وارد کنید (مثلاً 1024):")
    bot.register_next_step_handler(msg, add_package_step3, title)

def add_package_step3(message, title):
    try:
        volume = int(message.text)
        msg = bot.send_message(message.chat.id, f"عنوان: {title}\nحجم: {volume} GB\nلطفاً قیمت بسته را به <b>تومان</b> (عدد) وارد کنید:", parse_mode="HTML")
        bot.register_next_step_handler(msg, add_package_step4, title, volume)
    except ValueError:
        bot.send_message(message.chat.id, "لطفاً فقط عدد انگلیسی وارد کنید. عملیات لغو شد.")

def add_package_step4(message, title, volume):
    try:
        price_toman = int(message.text)
        msg = bot.send_message(message.chat.id, f"عنوان: {title}\nحجم: {volume} GB\nقیمت: {price_toman:,} تومان\nلطفاً قیمت بسته را به <b>دلار</b> (عدد) وارد کنید:", parse_mode="HTML")
        bot.register_next_step_handler(msg, save_new_package, title, volume, price_toman)
    except ValueError:
        bot.send_message(message.chat.id, "لطفاً فقط عدد انگلیسی وارد کنید. عملیات لغو شد.")

def save_new_package(message, title, volume, price_toman):
    try:
        price_usd = float(message.text)
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO seller_packages (title, volume_gb, price_toman, price_usd) VALUES (?, ?, ?, ?)", (title, volume, price_toman, price_usd))
            conn.commit()
        bot.send_message(message.chat.id, "بسته با موفقیت ثبت شد ✅")
    except ValueError:
        bot.send_message(message.chat.id, "لطفاً فقط عدد انگلیسی وارد کنید. عملیات لغو شد.")

@bot.message_handler(func=lambda message: message.text == "ورود به پنل فروشنده 🛒")
def to_seller_panel(message):
    bot.send_message(message.chat.id, "وارد پنل فروشنده شدید:", reply_markup=get_seller_markup(message.chat.id))


@bot.message_handler(func=lambda message: message.text in ["🛡️ حالت امنیت: فعال", "🛡️ حالت امنیت: غیرفعال"])
def handle_toggle_security_mode(message):
    chat_id = message.chat.id
    # Check if authorized
    is_authorized = False
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        is_authorized = True
    else:
        try:
            with sqlite3.connect(settings.database) as conn:
                c = conn.cursor()
                c.execute("SELECT value FROM bot_settings WHERE key = 'SINGLE_SELLER_ID'")
                row = c.fetchone()
                if row and row[0] and int(row[0]) == int(chat_id):
                    is_authorized = True
        except:
            pass

    if not is_authorized:
        return

    new_val = '1' if message.text == "🛡️ حالت امنیت: غیرفعال" else '0'
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('SECURITY_MODE', ?)", (new_val,))
            conn.commit()
        
        status_text = "فعال" if new_val == '1' else "غیرفعال"
        bot.send_message(
            chat_id, 
            f"🛡️ حالت امنیت با موفقیت <b>{status_text}</b> شد.", 
            parse_mode="HTML", 
            reply_markup=get_seller_markup(chat_id)
        )
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطا در تغییر وضعیت امنیت:\n{str(e)}")


@bot.message_handler(func=lambda message: message.text == "✉️ ایجاد لینک دعوت")
def handle_create_invite_link(message):
    chat_id = message.chat.id
    # Check if authorized
    is_authorized = False
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        is_authorized = True
    else:
        try:
            with sqlite3.connect(settings.database) as conn:
                c = conn.cursor()
                c.execute("SELECT value FROM bot_settings WHERE key = 'SINGLE_SELLER_ID'")
                row = c.fetchone()
                if row and row[0] and int(row[0]) == int(chat_id):
                    is_authorized = True
        except:
            pass

    if not is_authorized:
        return

    import uuid
    token = str(uuid.uuid4())[:8]
    
    try:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO invite_links (token, seller_id, used) VALUES (?, ?, 0)", (token, chat_id))
            conn.commit()
            
        bot_info = bot.get_me()
        bot_username = bot_info.username
        invite_url = f"https://t.me/{bot_username}?start=inv_{token}"
        
        msg = (
            "✉️ <b>لینک دعوت یکبار مصرف ایجاد شد:</b>\n\n"
            f"<code>{invite_url}</code>\n\n"
            "⚠️ این لینک فقط برای عضویت یک کاربر معتبر است و پس از اولین استارت باطل خواهد شد."
        )
        bot.send_message(chat_id, msg, parse_mode="HTML")
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطا در ایجاد لینک دعوت:\n{str(e)}")

@bot.message_handler(func=lambda message: message.text == "ورود به پنل خریدار 👤")
def to_customer_panel(message):
    bot.send_message(message.chat.id, "وارد پنل خریدار شدید:", reply_markup=get_customer_markup(message.chat.id))

@bot.message_handler(func=lambda message: message.text == "برگشت به پنل سوپر ادمین 🔙")
def to_super_admin_panel(message):
    bot.send_message(message.chat.id, "وارد پنل سوپر ادمین شدید:", reply_markup=super_admin_markup)

@bot.message_handler(func=lambda message: message.text == "➰ منوی کاربر عادی")
def handle_normal_menu(message):
    bot.send_message(message.chat.id, "وارد منوی خریدار شدید.", reply_markup=get_customer_markup(message.chat.id))


# ========================================================================================================
# Hiddify Panel Settings Handlers
# ========================================================================================================

@bot.message_handler(func=lambda message: message.text == "⚙️ تنظیمات پنل X-UI")
def xui_settings_menu(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        show_xui_settings_view(chat_id)

def show_xui_settings_view(chat_id, edit_message_id=None):
    with sqlite3.connect(settings.database) as conn:
        c = conn.cursor()
        c.execute("SELECT key, value FROM bot_settings WHERE key IN ('XUI_PANEL_URL', 'XUI_USERNAME', 'XUI_PASSWORD', 'XUI_INBOUND_ID', 'SUB_BASE_URL')")
        rows = dict(c.fetchall())
    
    panel_url = rows.get('XUI_PANEL_URL', 'تنظیم نشده')
    username = rows.get('XUI_USERNAME', 'تنظیم نشده')
    password = rows.get('XUI_PASSWORD', 'تنظیم نشده')
    inbound_id = rows.get('XUI_INBOUND_ID', 'تنظیم نشده')
    sub_base_url = rows.get('SUB_BASE_URL', 'https://sus.ananasino.icu/sus')
    
    masked_pass = f"{password[:2]}***{password[-2:]}" if password != 'تنظیم نشده' and len(password) > 4 else password
    
    msg = f"🔧 <b>تنظیمات اتصال به پنل X-UI (سنایی)</b>\n\n"
    msg += f"🌐 آدرس پنل: <code>{panel_url}</code>\n"
    msg += f"👤 نام کاربری: <code>{username}</code>\n"
    msg += f"🔑 رمز عبور: <code>{masked_pass}</code>\n"
    msg += f"🔌 آیدی اینباندها: <code>{inbound_id}</code>\n"
    msg += f"🔗 آدرس پایه ساب: <code>{sub_base_url}</code>\n\n"
    msg += "برای ویرایش هر بخش روی دکمه مربوطه کلیک کنید 👇"
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🌐 ویرایش آدرس پنل", callback_data="edit_xui_url"))
    markup.row(InlineKeyboardButton("👤 ویرایش نام کاربری", callback_data="edit_xui_user"))
    markup.row(InlineKeyboardButton("🔑 ویرایش رمز عبور", callback_data="edit_xui_pass"))
    markup.row(InlineKeyboardButton("🔌 ویرایش آیدی اینباندها", callback_data="edit_xui_inbound"))
    markup.row(InlineKeyboardButton("🔗 ویرایش آدرس پایه ساب", callback_data="edit_xui_sub_base"))
    
    if edit_message_id:
        try:
            bot.edit_message_text(msg, chat_id, edit_message_id, reply_markup=markup, parse_mode="HTML")
        except:
            bot.send_message(chat_id, msg, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(chat_id, msg, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data in ["edit_xui_url", "edit_xui_user", "edit_xui_pass", "edit_xui_inbound", "edit_xui_sub_base"])
def handle_edit_xui_field(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        field = call.data
        bot.answer_callback_query(call.id)
        
        if field == "edit_xui_url":
            msg_text = "لطفاً <b>آدرس جدید پنل</b> (با پورت و بدون اسلش آخر) را وارد کنید:\n(مثال: <code>http://12.34.56.78:2087</code>)"
        elif field == "edit_xui_user":
            msg_text = "لطفاً <b>نام کاربری جدید</b> پنل X-UI را وارد کنید:"
        elif field == "edit_xui_pass":
            msg_text = "لطفاً <b>رمز عبور جدید</b> پنل X-UI را وارد کنید:"
        elif field == "edit_xui_inbound":
            msg_text = "لطفاً <b>آیدی جدید اینباندها</b> را به صورت عددی وارد کنید (مثلا <code>1</code> یا برای چند اینباند به صورت کاما جدا شده <code>1,2</code>):"
        elif field == "edit_xui_sub_base":
            msg_text = "لطفاً <b>آدرس پایه ساب جدید</b> را وارد کنید:\n(مثال: <code>https://sus.ananasino.icu/sus</code>)"
            
        msg = bot.send_message(chat_id, msg_text, parse_mode="HTML")
        bot.register_next_step_handler(msg, save_xui_single_field, field)

def save_xui_single_field(message, field):
    chat_id = message.chat.id
    new_val = message.text.strip()
    
    db_key = None
    field_name = None
    if field == "edit_xui_url":
        db_key = "XUI_PANEL_URL"
        field_name = "آدرس پنل"
    elif field == "edit_xui_user":
        db_key = "XUI_USERNAME"
        field_name = "نام کاربری"
    elif field == "edit_xui_pass":
        db_key = "XUI_PASSWORD"
        field_name = "رمز عبور"
    elif field == "edit_xui_inbound":
        db_key = "XUI_INBOUND_ID"
        field_name = "آیدی اینباندها"
    elif field == "edit_xui_sub_base":
        db_key = "SUB_BASE_URL"
        field_name = "آدرس پایه ساب"
        
    if db_key:
        try:
            with sqlite3.connect(settings.database) as conn:
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)", (db_key, new_val))
                conn.commit()
            bot.send_message(chat_id, f"✅ فیلد <b>{field_name}</b> با موفقیت به مقدار جدید به‌روزرسانی شد.", parse_mode="HTML")
            show_xui_settings_view(chat_id)
        except Exception as e:
            bot.send_message(chat_id, f"❌ خطا در ذخیره‌سازی:\n{str(e)}")


# ========================================================================================================
# SOCKS Proxy Settings Handlers
# ========================================================================================================

@bot.message_handler(func=lambda message: message.text == "⚙️ تنظیمات پروکسی ساکس")
def socks_proxy_settings_menu(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM bot_settings WHERE key = 'SOCKS_PROXY'")
            row = c.fetchone()
        
        current_proxy = row[0] if row else 'تنظیم نشده'
        
        msg = "⚙️ <b>تنظیمات پروکسی ساکس (SOCKS5 Proxy)</b>\n\n"
        msg += f"🔗 پروکسی فعلی: <code>{current_proxy}</code>\n\n"
        msg += "از پروکسی برای عبور ربات از سد فیلترینگ تلگرام استفاده می‌شود.\n"
        msg += "شما می‌توانید آدرس استاندارد (مثل <code>socks5h://user:pass@host:port</code>) یا لینک تلگرام (مثل <code>tg://socks?server=...</code>) وارد کنید."
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✏️ تنظیم پروکسی جدید", callback_data="edit_socks_proxy"))
        if current_proxy != 'تنظیم نشده':
            markup.add(InlineKeyboardButton("❌ حذف پروکسی فعلی", callback_data="delete_socks_proxy"))
            
        bot.send_message(chat_id, msg, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "edit_socks_proxy")
def edit_socks_proxy_step1(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        msg = bot.send_message(chat_id, "لطفاً لینک پروکسی خود را ارسال کنید:\n\n"
                                        "نمونه لینک تلگرام:\n<code>tg://socks?server=87.236.208.195&port=2020&user=matin&pass=matin</code>\n\n"
                                        "نمونه آدرس استاندارد:\n<code>socks5h://matin:matin@87.236.208.195:2020</code>", parse_mode="HTML")
        bot.register_next_step_handler(msg, save_socks_proxy)

@bot.callback_query_handler(func=lambda call: call.data == "delete_socks_proxy")
def delete_socks_proxy(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM bot_settings WHERE key = 'SOCKS_PROXY'")
            conn.commit()
        apply_proxy()
        bot.send_message(chat_id, "✅ پروکسی با موفقیت حذف شد و ارتباط مستقیم فعال گردید.")

def save_socks_proxy(message):
    chat_id = message.chat.id
    proxy_val = message.text.strip()
    
    parsed = parse_proxy_url(proxy_val)
    if not parsed:
        bot.send_message(chat_id, "❌ فرمت پروکسی ارسال شده نامعتبر است. عملیات لغو شد.")
        return
        
    bot.send_message(chat_id, "⏳ در حال تست اتصال پروکسی...")
    
    try:
        proxies = {
            'http': parsed,
            'https': parsed
        }
        response = requests.get("https://api.telegram.org", proxies=proxies, timeout=5)
        is_working = (response.status_code == 200)
        error_msg = ""
    except Exception as e:
        is_working = False
        error_msg = str(e)
        
    if is_working:
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('SOCKS_PROXY', ?)", (proxy_val,))
            conn.commit()
        apply_proxy()
        bot.send_message(chat_id, "✅ پروکسی تست شد و با موفقیت ذخیره گردید!")
    else:
        markup = InlineKeyboardMarkup()
        temp_data[f"pending_proxy_{chat_id}"] = proxy_val
        
        markup.add(
            InlineKeyboardButton("💾 ذخیره به هر حال", callback_data="force_save_proxy"),
            InlineKeyboardButton("❌ لغو", callback_data="cancel_save_proxy")
        )
        bot.send_message(chat_id, f"⚠️ تست اتصال پروکسی با خطا مواجه شد:\n<code>{error_msg}</code>\n\nآیا با این حال می‌خواهید آن را ذخیره کنید؟", reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data in ["force_save_proxy", "cancel_save_proxy"])
def handle_force_save_proxy_callback(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        if call.data == "force_save_proxy":
            proxy_val = temp_data.get(f"pending_proxy_{chat_id}")
            if proxy_val:
                with sqlite3.connect(settings.database) as conn:
                    c = conn.cursor()
                    c.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('SOCKS_PROXY', ?)", (proxy_val,))
                    conn.commit()
                apply_proxy()
                bot.send_message(chat_id, "✅ پروکسی با موفقیت ذخیره و اعمال شد (هرچند تست اتصال آن ناموفق بود).")
                temp_data.pop(f"pending_proxy_{chat_id}", None)
            else:
                bot.send_message(chat_id, "❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.")
        elif call.data == "cancel_save_proxy":
            temp_data.pop(f"pending_proxy_{chat_id}", None)
            bot.send_message(chat_id, "❌ عملیات تنظیم پروکسی لغو شد.")

    





# ========================================================================================================
# Hiddify VPN Management (Super Admin)
# ========================================================================================================

@bot.message_handler(func=lambda message: message.text == "🛠 مدیریت سرویس‌ها (X-UI)")
def hiddify_management_menu(message):
    chat_id = message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("📊 آمار سرور", callback_data="hiddify_server_stats")
        )
        markup.add(
            InlineKeyboardButton("👥 لیست کاربران", callback_data="hiddify_list_users_page_1"),
            InlineKeyboardButton("➕ ایجاد کاربر جدید", callback_data="hiddify_create_user")
        )
        markup.add(InlineKeyboardButton("🔎 جستجوی کاربر", callback_data="hiddify_search_user"))
        
        bot.send_message(chat_id, "بخش مدیریت مستقیم پنل X-UI (سنایی):\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "hiddify_server_stats")
def handle_server_stats(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        client = HiddifyClient()
        client.reload_config()
        try:
            raw = client.get_stats()
            bot.answer_callback_query(call.id)

            def fmt_gb(val_bytes):
                try:
                    return f"{float(val_bytes) / 1024**3:.2f} GB"
                except:
                    return str(val_bytes)

            def fmt_mb(val_bytes):
                try:
                    return f"{float(val_bytes) / 1024**2:.1f} MB"
                except:
                    return str(val_bytes)

            def pct(used, total):
                try:
                    return f"{used / total * 100:.0f}%"
                except:
                    return "—"

            if isinstance(raw, dict):
                sys  = raw.get("stats", {}).get("system", {})
                top5 = raw.get("stats", {}).get("top5", {})
                hist = raw.get("usage_history", {})

                # ── سیستم ──────────────────────────────
                ram_used  = sys.get("ram_used",  0)
                ram_total = sys.get("ram_total", 1)
                disk_used = sys.get("disk_used", 0)
                disk_total= sys.get("disk_total",1)

                msg  = "🖥 <b>آمار سرور X-UI</b>\n"
                msg += "━━━━━━━━━━━━━━━━━━\n\n"

                msg += "⚙️ <b>سیستم</b>\n"
                msg += f"🔲 CPU: <b>{sys.get('cpu_percent', '—')}%</b>  (<b>{sys.get('num_cpus', '—')}</b> هسته)\n"
                msg += f"💾 RAM: <b>{ram_used:.2f} / {ram_total:.2f} GB</b>  (<b>{pct(ram_used, ram_total)}</b>)\n"
                msg += f"💿 دیسک: <b>{disk_used:.2f} / {disk_total:.2f} GB</b>  (<b>{pct(disk_used, disk_total)}</b>)\n"
                msg += f"📦 Xray: <b>{sys.get('hiddify_used', 0):.2f} GB</b>\n"
                load1  = sys.get('load_avg_1min',  '—')
                load5  = sys.get('load_avg_5min',  '—')
                load15 = sys.get('load_avg_15min', '—')
                msg += f"📊 بار CPU: <b>{load1} / {load5} / {load15}</b>  (۱ / ۵ / ۱۵ دقیقه)\n\n"

                # ── شبکه ──────────────────────────────
                msg += "🌐 <b>شبکه</b>\n"
                msg += f"⬇️ دریافت: <b>{fmt_gb(sys.get('bytes_recv', 0))}</b>\n"
                msg += f"⬆️ ارسال: <b>{fmt_gb(sys.get('bytes_sent', 0))}</b>\n"
                msg += f"📶 کل مصرف تجمعی: <b>{sys.get('net_total_cumulative_GB', 0):.2f} GB</b>\n"
                msg += f"🔗 اتصال فعال: <b>{sys.get('total_connections', '—')}</b>  |  IP منحصر: <b>{sys.get('total_unique_ips', '—')}</b>\n\n"

                # ── آمار کاربران ───────────────────────
                today     = hist.get("today",        {})
                yesterday = hist.get("yesterday",    {})
                h24       = hist.get("h24",          {})
                last30    = hist.get("last_30_days", {})
                total     = hist.get("total",        {})

                msg += "👥 <b>آمار کاربران</b>\n"
                msg += f"⏱ امروز: آنلاین <b>{today.get('online','—')}</b>  |  مصرف <b>{fmt_mb(today.get('usage', 0))}</b>\n"
                msg += f"📅 دیروز: آنلاین <b>{yesterday.get('online','—')}</b>  |  مصرف <b>{fmt_mb(yesterday.get('usage', 0))}</b>\n"
                msg += f"🕐 ۲۴ ساعت: آنلاین <b>{h24.get('online','—')}</b>  |  مصرف <b>{fmt_mb(h24.get('usage', 0))}</b>\n"
                msg += f"📆 ۳۰ روز: آنلاین <b>{last30.get('online','—')}</b>  |  مصرف <b>{fmt_gb(last30.get('usage', 0))}</b>\n"
                msg += f"🗄 مجموع: کاربران <b>{total.get('users','—')}</b>  |  مصرف کل <b>{fmt_gb(total.get('usage', 0))}</b>\n\n"

                # ── Top 5 CPU ──────────────────────────
                cpu_top = top5.get("cpu", [])
                if cpu_top:
                    msg += "🔥 <b>پرمصرف‌ترین CPU</b>\n"
                    for rank, (proc, val) in enumerate(cpu_top[:5], 1):
                        msg += f"  {rank}. {proc}: <b>{val:.2f}%</b>\n"
                    msg += "\n"

                # ── Top 5 RAM ──────────────────────────
                ram_top = top5.get("ram", top5.get("memory", []))
                if ram_top:
                    msg += "🧠 <b>پرمصرف‌ترین RAM</b>\n"
                    for rank, (proc, val) in enumerate(ram_top[:5], 1):
                        msg += f"  {rank}. {proc}: <b>{val:.0f} MB</b>\n"

            else:
                msg = f"📊 آمار سرور:\n{str(raw)}"

            bot.send_message(chat_id, msg, parse_mode="HTML")
        except Exception as e:
            bot.answer_callback_query(call.id, "خطا!")
            bot.send_message(chat_id, f"❌ خطا در آمار سرور:\n{str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("hiddify_list_users_page_"))
def handle_list_users(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        page = int(call.data.split("_")[-1])
        client = HiddifyClient()
        client.reload_config()
        try:
            users = client.list_users()
            if not users:
                bot.answer_callback_query(call.id, "هیچ کاربری در پنل وجود ندارد.")
                return
            
            per_page = 5
            total_pages = (len(users) + per_page - 1) // per_page
            if page > total_pages: page = total_pages
            if page < 1: page = 1
            
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_users = users[start_idx:end_idx]
            
            markup = InlineKeyboardMarkup()
            for u in page_users:
                markup.add(InlineKeyboardButton(f"👤 {u.get('name', 'Unknown')}", callback_data=f"hiddify_user_info_{u.get('uuid')}"))
                
            nav_buttons = []
            if page > 1:
                nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"hiddify_list_users_page_{page-1}"))
            if page < total_pages:
                nav_buttons.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"hiddify_list_users_page_{page+1}"))
            if nav_buttons:
                markup.row(*nav_buttons)
                
            bot.edit_message_text(f"👥 لیست کاربران (صفحه {page} از {total_pages})", chat_id, call.message.message_id, reply_markup=markup)
        except Exception as e:
            bot.answer_callback_query(call.id, "خطا!")
            bot.send_message(chat_id, f"❌ خطا در لیست کاربران:\n{str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "hiddify_create_user")
def create_user_step1(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        msg = bot.send_message(chat_id, "لطفاً نام کاربر جدید را وارد کنید (بدون فاصله، فقط انگلیسی):")
        bot.register_next_step_handler(msg, create_user_step2)

def create_user_step2(message):
    name = message.text
    msg = bot.send_message(message.chat.id, f"نام: {name}\nلطفاً حجم ترافیک (به گیگابایت) را وارد کنید:")
    bot.register_next_step_handler(msg, create_user_step3, name)

def create_user_step3(message, name):
    try:
        usage = int(message.text)
        msg = bot.send_message(message.chat.id, f"نام: {name}\nحجم: {usage} GB\nلطفاً تعداد روز اعتبار را وارد کنید:")
        bot.register_next_step_handler(msg, create_user_finish, name, usage)
    except ValueError:
        bot.send_message(message.chat.id, "مقدار باید عددی باشد. عملیات لغو شد.")

def create_user_finish(message, name, usage):
    try:
        days = int(message.text)
        client = HiddifyClient()
        client.reload_config()
        
        user_uuid = str(uuid.uuid4())
        payload = {
            "name": name,
            "uuid": user_uuid,
            "usage_limit_GB": usage,
            "package_days": days,
            "mode": "no_reset",
            "enable": True
        }
        client.create_user(payload)
        
        # Get subscription link
        sub_link = client.get_sub_link(user_uuid, name)
        
        msg = f"✅ کاربر با موفقیت ساخته شد.\n\n"
        msg += f"👤 نام: {name}\n"
        msg += f"📦 حجم: {usage} GB\n"
        msg += f"⏳ زمان: {days} روز\n\n"
        msg += f"🔗 لینک ساب:\n<code>{sub_link}</code>"
        
        qr_path = f"temp_qr_{user_uuid}.png"
        final_path = f"temp_final_{user_uuid}.png"
        bg_path = "assets/qrcode_template.png"
        
        try:
            link_to_qrcode(sub_link, qr_path)
            place_qr_on_template(qr_path, bg_path, final_path, "sub_link", sub_link=sub_link)
            
            with open(final_path, "rb") as photo:
                bot.send_photo(message.chat.id, photo, caption=msg, parse_mode="HTML")
        except Exception as e:
            bot.send_message(message.chat.id, msg, parse_mode="HTML")
            print("QR Error:", e)
        finally:
            if os.path.exists(qr_path): os.remove(qr_path)
            if os.path.exists(final_path): os.remove(final_path)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا در ایجاد کاربر:\n{str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "hiddify_search_user")
def search_user_step1(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        msg = bot.send_message(chat_id, "لطفاً UUID کاربر را وارد کنید:")
        bot.register_next_step_handler(msg, search_user_step2)

def search_user_step2(message):
    uuid_str = message.text.strip()
    show_user_info(message.chat.id, uuid_str)

@bot.callback_query_handler(func=lambda call: call.data.startswith("hiddify_user_info_"))
def handle_user_info_callback(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        user_uuid = call.data.split("hiddify_user_info_")[1]
        show_user_info(chat_id, user_uuid)
        bot.answer_callback_query(call.id)

def show_user_info(chat_id, user_uuid):
    client = HiddifyClient()
    client.reload_config()
    try:
        user = client.get_user(user_uuid)
        if not user:
            bot.send_message(chat_id, "کاربر یافت نشد.")
            return
            
        try:
            usage_info = client.get_user_usage(user_uuid)
        except Exception:
            usage_info = None
        
        msg = f"👤 <b>اطلاعات کاربر</b>\n"
        msg += f"👤 نام: {user.get('name')}\n"
        msg += f"📦 حجم کل: {user.get('usage_limit_GB')} GB\n"
        msg += f"⏳ اعتبار: {user.get('package_days')} روز\n"
        
        current_usage = user.get('current_usage_GB', None)
        if current_usage is not None:
            msg += f"📉 مصرف شده: {current_usage} GB\n"
        elif usage_info and isinstance(usage_info, dict):
            msg += f"📉 مصرف شده: {usage_info.get('usage', 'N/A')} GB\n"
            
        link = client.get_sub_link(user_uuid, user.get("name", ""))
        msg += f"\n🔗 لینک ساب:\n<code>{link}</code>\n"

        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🔗 دریافت مجدد لینک", callback_data=f"hiddify_get_link_{user_uuid}"))
        
        status_text = "🔴 غیرفعال کردن کاربر" if user.get('enable') else "🟢 فعال کردن کاربر"
        markup.row(InlineKeyboardButton(status_text, callback_data=f"hiddify_toggle_status_{user_uuid}"))
        
        markup.row(
            InlineKeyboardButton("📊 تغییر ترافیک (GB)", callback_data=f"hiddify_edit_traffic_{user_uuid}"),
            InlineKeyboardButton("⏳ تغییر زمان (روز)", callback_data=f"hiddify_edit_days_{user_uuid}")
        )
        
        markup.row(
            InlineKeyboardButton("🔄 ریست حجم", callback_data=f"hiddify_reset_usage_{user_uuid}"),
            InlineKeyboardButton("🗑 حذف کاربر", callback_data=f"hiddify_delete_user_{user_uuid}")
        )
        
        qr_path = f"temp_qr_{user_uuid}.png"
        final_path = f"temp_final_{user_uuid}.png"
        bg_path = "assets/qrcode_template.png"
        
        import os
        from utils.qr import link_to_qrcode, place_qr_on_template
        
        try:
            link_to_qrcode(link, qr_path)
            place_qr_on_template(qr_path, bg_path, final_path, "sub_link", sub_link=sub_link)
            with open(final_path, "rb") as photo:
                bot.send_photo(chat_id, photo, caption=msg, reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            bot.send_message(chat_id, msg, reply_markup=markup, parse_mode="HTML")
            print("QR Error:", e)
        finally:
            if os.path.exists(qr_path): os.remove(qr_path)
            if os.path.exists(final_path): os.remove(final_path)
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطا در اطلاعات کاربر:\n{str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("hiddify_get_link_"))
def handle_get_sub_link(call):
    user_uuid = call.data.split("hiddify_get_link_")[1]
    client = HiddifyClient()
    client.reload_config()
    try:
        user = client.get_user(user_uuid)
        link = client.get_sub_link(user_uuid, user.get("name", ""))
        msg = f"🔗 لینک اشتراک:\n<code>{link}</code>"
        
        qr_path = f"temp_qr_{user_uuid}.png"
        final_path = f"temp_final_{user_uuid}.png"
        bg_path = "assets/qrcode_template.png"
        
        try:
            link_to_qrcode(link, qr_path)
            place_qr_on_template(qr_path, bg_path, final_path, "sub_link", sub_link=sub_link)
            
            with open(final_path, "rb") as photo:
                bot.send_photo(call.message.chat.id, photo, caption=msg, parse_mode="HTML")
            bot.answer_callback_query(call.id)
        except Exception as e:
            bot.send_message(call.message.chat.id, msg, parse_mode="HTML")
            bot.answer_callback_query(call.id)
            print("QR Error:", e)
        finally:
            if os.path.exists(qr_path): os.remove(qr_path)
            if os.path.exists(final_path): os.remove(final_path)
    except Exception as e:
        bot.answer_callback_query(call.id, "خطا!")
        bot.send_message(call.message.chat.id, f"❌ خطا در دریافت لینک:\n{str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("hiddify_reset_usage_"))
def handle_reset_usage(call):
    user_uuid = call.data.split("hiddify_reset_usage_")[1]
    client = HiddifyClient()
    client.reload_config()
    try:
        client.reset_user_usage(user_uuid)
        bot.answer_callback_query(call.id, "✅ حجم کاربر ریست شد.")
    except Exception as e:
        bot.answer_callback_query(call.id, "خطا!")
        bot.send_message(call.message.chat.id, f"❌ خطا در ریست حجم:\n{str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("hiddify_delete_user_"))
def handle_delete_user(call):
    user_uuid = call.data.split("hiddify_delete_user_")[1]
    client = HiddifyClient()
    client.reload_config()
    try:
        client.delete_user(user_uuid)
        bot.answer_callback_query(call.id, "🗑 کاربر حذف شد.")
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        bot.answer_callback_query(call.id, "خطا!")
        bot.send_message(call.message.chat.id, f"❌ خطا در حذف کاربر:\n{str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("hiddify_toggle_status_"))
def handle_toggle_status(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        user_uuid = call.data.split("hiddify_toggle_status_")[1]
        client = HiddifyClient()
        client.reload_config()
        try:
            user = client.get_user(user_uuid)
            if not user:
                bot.answer_callback_query(call.id, "کاربر یافت نشد!")
                return
            new_enable = not user.get("enable", True)
            client.update_user(user_uuid, {"enable": new_enable})
            bot.answer_callback_query(call.id, f"وضعیت کاربر به {'فعال' if new_enable else 'غیرفعال'} تغییر یافت.")
            # Refresh user info
            bot.delete_message(chat_id, call.message.message_id)
            show_user_info(chat_id, user_uuid)
        except Exception as e:
            bot.answer_callback_query(call.id, "خطا!")
            bot.send_message(chat_id, f"❌ خطا در تغییر وضعیت کاربر:\n{str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("hiddify_edit_traffic_"))
def handle_edit_traffic(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        user_uuid = call.data.split("hiddify_edit_traffic_")[1]
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            chat_id,
            "لطفاً حجم جدید کاربر را به گیگابایت وارد کنید (مثلاً 50) یا با استفاده از علامت‌های + و - حجم فعلی را تغییر دهید (مثلاً +10 یا -5):"
        )
        bot.register_next_step_handler(msg, process_edit_traffic, user_uuid)


def process_edit_traffic(message, user_uuid):
    chat_id = message.chat.id
    input_text = message.text.strip()
    client = HiddifyClient()
    client.reload_config()
    try:
        user = client.get_user(user_uuid)
        if not user:
            bot.send_message(chat_id, "کاربر یافت نشد.")
            return
            
        current_gb = user.get("usage_limit_GB", 0)
        
        # Parse absolute or relative
        if input_text.startswith("+"):
            val = float(input_text[1:].strip())
            new_gb = current_gb + val
        elif input_text.startswith("-"):
            val = float(input_text[1:].strip())
            new_gb = max(0.0, current_gb - val)
        else:
            new_gb = float(input_text)
            
        client.update_user(user_uuid, {"usage_limit_GB": new_gb})
        bot.send_message(chat_id, f"✅ حجم کاربر به {new_gb:g} GB تغییر یافت.")
        show_user_info(chat_id, user_uuid)
    except ValueError:
        bot.send_message(chat_id, "❌ مقدار وارد شده نامعتبر است. لطفاً عدد وارد کنید.")
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطا در تغییر حجم کاربر:\n{str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("hiddify_edit_days_"))
def handle_edit_days(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        user_uuid = call.data.split("hiddify_edit_days_")[1]
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            chat_id,
            "لطفاً تعداد روزهای جدید اعتبار کاربر را وارد کنید (مثلاً 30) یا با استفاده از علامت‌های + و - اعتبار فعلی را تغییر دهید (مثلاً +30 یا -10):"
        )
        bot.register_next_step_handler(msg, process_edit_days, user_uuid)


def process_edit_days(message, user_uuid):
    chat_id = message.chat.id
    input_text = message.text.strip()
    client = HiddifyClient()
    client.reload_config()
    try:
        user = client.get_user(user_uuid)
        if not user:
            bot.send_message(chat_id, "کاربر یافت نشد.")
            return
            
        current_days = user.get("package_days", 0)
        
        # Parse absolute or relative
        if input_text.startswith("+"):
            val = int(input_text[1:].strip())
            new_days = current_days + val
        elif input_text.startswith("-"):
            val = int(input_text[1:].strip())
            new_days = max(0, current_days - val)
        else:
            new_days = int(input_text)
            
        client.update_user(user_uuid, {"package_days": new_days})
        bot.send_message(chat_id, f"✅ اعتبار کاربر به {new_days} روز تغییر یافت.")
        show_user_info(chat_id, user_uuid)
    except ValueError:
        bot.send_message(chat_id, "❌ مقدار وارد شده نامعتبر است. لطفاً عدد وارد کنید.")
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطا در تغییر زمان کاربر:\n{str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("hiddify_toggle_status_"))
def handle_toggle_status(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        user_uuid = call.data.split("hiddify_toggle_status_")[1]
        client = HiddifyClient()
        client.reload_config()
        try:
            user = client.get_user(user_uuid)
            if not user:
                bot.answer_callback_query(call.id, "کاربر یافت نشد!")
                return
            new_enable = not user.get("enable", True)
            client.update_user(user_uuid, {"enable": new_enable})
            bot.answer_callback_query(call.id, f"وضعیت کاربر به {'فعال' if new_enable else 'غیرفعال'} تغییر یافت.")
            # Refresh user info
            bot.delete_message(chat_id, call.message.message_id)
            show_user_info(chat_id, user_uuid)
        except Exception as e:
            bot.answer_callback_query(call.id, "خطا!")
            bot.send_message(chat_id, f"❌ خطا در تغییر وضعیت کاربر:\n{str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("hiddify_edit_traffic_"))
def handle_edit_traffic(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        user_uuid = call.data.split("hiddify_edit_traffic_")[1]
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            chat_id,
            "لطفاً حجم جدید کاربر را به گیگابایت وارد کنید (مثلاً 50) یا با استفاده از علامت‌های + و - حجم فعلی را تغییر دهید (مثلاً +10 یا -5):"
        )
        bot.register_next_step_handler(msg, process_edit_traffic, user_uuid)


def process_edit_traffic(message, user_uuid):
    chat_id = message.chat.id
    input_text = message.text.strip()
    client = HiddifyClient()
    client.reload_config()
    try:
        user = client.get_user(user_uuid)
        if not user:
            bot.send_message(chat_id, "کاربر یافت نشد.")
            return
            
        current_gb = user.get("usage_limit_GB", 0)
        
        # Parse absolute or relative
        if input_text.startswith("+"):
            val = float(input_text[1:].strip())
            new_gb = current_gb + val
        elif input_text.startswith("-"):
            val = float(input_text[1:].strip())
            new_gb = max(0.0, current_gb - val)
        else:
            new_gb = float(input_text)
            
        client.update_user(user_uuid, {"usage_limit_GB": new_gb})
        bot.send_message(chat_id, f"✅ حجم کاربر به {new_gb:g} GB تغییر یافت.")
        show_user_info(chat_id, user_uuid)
    except ValueError:
        bot.send_message(chat_id, "❌ مقدار وارد شده نامعتبر است. لطفاً عدد وارد کنید.")
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطا در تغییر حجم کاربر:\n{str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("hiddify_edit_days_"))
def handle_edit_days(call):
    chat_id = call.message.chat.id
    if (int(chat_id) in settings.admin_list) or (int(chat_id) in get_admin_ids()):
        user_uuid = call.data.split("hiddify_edit_days_")[1]
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            chat_id,
            "لطفاً تعداد روزهای جدید اعتبار کاربر را وارد کنید (مثلاً 30) یا با استفاده از علامت‌های + و - اعتبار فعلی را تغییر دهید (مثلاً +30 یا -10):"
        )
        bot.register_next_step_handler(msg, process_edit_days, user_uuid)


def process_edit_days(message, user_uuid):
    chat_id = message.chat.id
    input_text = message.text.strip()
    client = HiddifyClient()
    client.reload_config()
    try:
        user = client.get_user(user_uuid)
        if not user:
            bot.send_message(chat_id, "کاربر یافت نشد.")
            return
            
        current_days = user.get("package_days", 0)
        
        # Parse absolute or relative
        if input_text.startswith("+"):
            val = int(input_text[1:].strip())
            new_days = current_days + val
        elif input_text.startswith("-"):
            val = int(input_text[1:].strip())
            new_days = max(0, current_days - val)
        else:
            new_days = int(input_text)
            
        client.update_user(user_uuid, {"package_days": new_days})
        bot.send_message(chat_id, f"✅ اعتبار کاربر به {new_days} روز تغییر یافت.")
        show_user_info(chat_id, user_uuid)
    except ValueError:
        bot.send_message(chat_id, "❌ مقدار وارد شده نامعتبر است. لطفاً عدد وارد کنید.")
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطا در تغییر زمان کاربر:\n{str(e)}")





# =========================================================
# EXTERNAL MODULES (Seller, Customer, Super Admin Sellers)
# =========================================================
from seller import register_seller_handlers
register_seller_handlers(bot)

from seller_packages import register_seller_package_handlers
register_seller_package_handlers(bot)

from seller_earnings import register_seller_earnings_handlers
register_seller_earnings_handlers(bot)

from customer import register_customer_handlers
register_customer_handlers(bot)

from seller_manual_config import register_seller_manual_config_handlers
register_seller_manual_config_handlers(bot)

from seller_traffic import register_seller_traffic_handlers
register_seller_traffic_handlers(bot)

from seller_traffic import register_seller_traffic_handlers
register_seller_traffic_handlers(bot)

def _is_catchall_callback(data):
    return (
        data.startswith("delete_button_")
        or data.startswith("delete_row_admin_")
        or data.startswith("delete_row_")
        or data in ("confirm_stop_broadcast", "stop_broadcast", "cancel_stop")
        or data.startswith("joined_channels")
    )


@bot.callback_query_handler(func=lambda call: _is_catchall_callback(call.data))
def call(call):
    Chat_id = call.message.chat.id
    User_id = call.from_user.id
    Msg_id = call.message.message_id
    try:            
        if call.data.startswith('delete_button_1'):
            bot.delete_message(chat_id=Chat_id, message_id=Msg_id - 1)
            bot.delete_message(chat_id=Chat_id, message_id=Msg_id)

        elif call.data.startswith('delete_button_'):
            bot.delete_message(chat_id=Chat_id, message_id=Msg_id)

        elif call.data.startswith('delete_row_admin_'):
            news_id = call.data.split('delete_row_admin_')[1]
            delete_admin_by_id(news_id)
            delete_list_question_keyboard = make_delete_admin_list_keyboard()
            bot.edit_message_reply_markup(chat_id=Chat_id, message_id=Msg_id,
                                          reply_markup=delete_list_question_keyboard)

        elif call.data.startswith('delete_row_'):
            news_id = call.data.split('delete_row_')[1]
            delete_channel_by_id(news_id)
            delete_list_question_keyboard = make_delete_channel_id_keyboard()
            bot.edit_message_reply_markup(chat_id=Chat_id, message_id=Msg_id, reply_markup=delete_list_question_keyboard)

        elif call.data == "confirm_stop_broadcast":
            confirm_stop_broadcast(call)
            
        elif call.data == "stop_broadcast":
            stop_broadcast_handler(call)
            
        elif call.data == "cancel_stop":
            cancel_stop_handler(call)
            
        elif call.data.startswith("joined_channels"):
            handle_joined_channels_callback(call)
            
            
    except Exception as e:
        pass
        # bot.send_message(call.message.chat.id, "خطایی رخ داد. لطفا دوباره تلاش کنید.")
        # bot.send_message(settings.matin, str(e))


@bot.message_handler(func=lambda message: message.chat.type == 'private', 
                     content_types=['text','audio', 'document', 'photo', 'sticker', 
                                    'video', 'video_note', 'voice','location', 
                                    'contact', 'venue', 'animation'])
def fallback_non_text(message):
    chat_id = message.chat.id
    if (int(chat_id) not in settings.admin_list) or (int(chat_id) not in get_admin_ids()):
        bot.send_message(
            message.chat.id,
            text=f"""
<b>✨ دوست عزیز، متوجه منظورت نشدم!</b>
این بات طراحی شده تا کار مشخصی رو انجام بده. اگر کاری داری یا سوالی داری:

به پشتیبانی مجموعه پیام ارسال کنید؛ در خدمتتون هستیم ❤️⬇️: 
👉 {admin_username}
""",
        parse_mode="HTML",
        reply_markup=get_customer_markup(message.chat.id),
        disable_web_page_preview=True)



# =========================================================
# ALLOCATE BULK VOLUME (SUPER ADMIN)
# =========================================================
@bot.message_handler(func=lambda message: message.text == "🗂 تخصیص حجم به فروشنده")
def allocate_volume_start(message):
    if (int(message.chat.id) in settings.admin_list) or (int(message.chat.id) in get_admin_ids()):
        msg = bot.send_message(message.chat.id, "لطفاً **آیدی عددی تلگرام** فروشنده را وارد کنید:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, allocate_volume_step2)

def allocate_volume_step2(message):
    if message.text == "برگشت 🔙":
        return send_welcome(message)
        
    try:
        seller_id = int(message.text)
        msg = bot.send_message(message.chat.id, f"آیدی فروشنده: {seller_id}\nلطفاً **حجم به گیگابایت (GB)** که می‌خواهید به این فروشنده اختصاص دهید را وارد کنید:\n(مثلا: 500)")
        bot.register_next_step_handler(msg, allocate_volume_step3, seller_id)
    except ValueError:
        bot.send_message(message.chat.id, "❌ آیدی نامعتبر است. لطفاً یک عدد صحیح وارد کنید.")

def allocate_volume_step3(message, seller_id):
    if message.text == "برگشت 🔙":
        return send_welcome(message)
        
    try:
        gb_amount = float(message.text)
        with sqlite3.connect(settings.database) as conn:
            c = conn.cursor()
            
            # Make sure seller exists in seller_configs
            c.execute("SELECT total_bulk_gb FROM seller_configs WHERE seller_id = ?", (seller_id,))
            row = c.fetchone()
            
            if row:
                new_total = row[0] + gb_amount
                c.execute("UPDATE seller_configs SET total_bulk_gb = ? WHERE seller_id = ?", (new_total, seller_id))
            else:
                c.execute("INSERT INTO seller_configs (seller_id, total_bulk_gb) VALUES (?, ?)", (seller_id, gb_amount))
                
            # Update role to seller in users table
            c.execute("SELECT role FROM users WHERE user_id = ?", (seller_id,))
            if not c.fetchone():
                c.execute("INSERT INTO users (chat_id, user_id, role) VALUES (?, ?, 'seller')", (seller_id, seller_id))
            else:
                c.execute("UPDATE users SET role = 'seller' WHERE user_id = ?", (seller_id,))
                
            conn.commit()
            
        bot.send_message(message.chat.id, f"✅ با موفقیت مقدار {gb_amount} گیگابایت به فروشنده {seller_id} اختصاص یافت.")
        
        # Notify the seller if possible
        try:
            bot.send_message(seller_id, f"🎉 تبریک! مقدار {gb_amount} گیگابایت حجم عمده توسط مدیریت به حساب فروشندگی شما اختصاص یافت.")
        except Exception:
            pass
            
    except ValueError:
        bot.send_message(message.chat.id, "❌ حجم نامعتبر است. لطفاً یک عدد وارد کنید.")


if __name__ == '__main__':
    def _traffic_alert_loop():
        while True:
            try:
                check_and_alert_low_traffic(bot)
            except Exception as e:
                print("Traffic alert loop error:", e)
            time.sleep(3600)

    threading.Thread(target=_traffic_alert_loop, daemon=True).start()
    bot.infinity_polling()
