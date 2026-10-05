import io
import json
import os
import time
import libsql
import logging
import threading
from contextlib import contextmanager
from datetime import datetime
from html import escape
from collections import defaultdict, deque
from flask import Flask
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ============================================================
# SECURE CONFIGURATION
# ============================================================
# IMPORTANT: never put the bot token in this file or GitHub.
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing. Add it to Render Environment Variables.")

CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@ECE_Latakia").strip()
ADMIN_IDS = {
    int(x.strip()) for x in os.environ.get("ADMIN_IDS", "7547218555").split(",")
    if x.strip().isdigit()
}
TURSO_URL = os.environ.get("TURSO_DATABASE_URL", "").strip()
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
if not TURSO_URL or not TURSO_AUTH_TOKEN:
    raise RuntimeError("TURSO_DATABASE_URL و TURSO_AUTH_TOKEN مطلوبين. أضفهما في Render Environment Variables.")
RATE_WINDOW = 10
RATE_LIMIT = 8
FEEDBACK_WINDOW = 3600
FEEDBACK_LIMIT = 3
SUB_CACHE_SECONDS = 60

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("student_bot")

bot = telebot.TeleBot(TOKEN, threaded=True)

# ============================================================
# IN-MEMORY STATE (short-lived only; persistent data stays in DB)
# ============================================================
user_states = {}
admin_states = {}
rate_buckets = defaultdict(deque)
feedback_buckets = defaultdict(deque)
subscription_cache = {}
last_seen_cache = {}
state_lock = threading.RLock()

app = Flask(__name__)

@app.route("/")
def home():
    return "OK", 200

def run_web():
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

threading.Thread(target=run_web, daemon=True, name="web-server").start()

# ============================================================
# DATABASE (Turso - سحابي دائم بدل ملف SQLite محلي بينمسح على Render)
# ============================================================
@contextmanager
def db_connect():
    """يفتح اتصال جديد بقاعدة Turso، وبيضمن إقفاله دايماً حتى لو صار خطأ
    (نفس أسلوب استخدام sqlite3 القديم بالكود ما تغير - with db_connect() as conn).
    فيها إعادة محاولة تلقائية لفتح الاتصال لو صار خطأ عابر (busy/idle stream)."""
    conn = None
    last_err = None
    for attempt in range(3):
        try:
            conn = libsql.connect(database=TURSO_URL, auth_token=TURSO_AUTH_TOKEN)
            break
        except Exception as e:
            last_err = e
            logger.warning("db_connect attempt %s failed: %s", attempt + 1, e)
            time.sleep(0.5 * (attempt + 1))
    if conn is None:
        raise last_err

    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()

def init_db():
    # نفذنا كل جملة CREATE لحالها (بدل executescript) لأن اتصال Turso البعيد
    # ما بيدعم بالضرورة تنفيذ عدة جمل SQL بضربة واحدة.
    statements = [
        """CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )""",
        """CREATE TABLE IF NOT EXISTS banned_users (
            user_id INTEGER PRIMARY KEY,
            banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type TEXT,
            text_content TEXT,
            file_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT NOT NULL,
            target TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            db_key TEXT NOT NULL,
            material_name TEXT NOT NULL,
            lecture_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER NOT NULL,
            db_key TEXT NOT NULL,
            material_name TEXT NOT NULL,
            lecture_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, db_key, material_name, lecture_name)
        )""",
        """CREATE TABLE IF NOT EXISTS recent_views (
            user_id INTEGER NOT NULL,
            db_key TEXT NOT NULL,
            material_name TEXT NOT NULL,
            lecture_name TEXT NOT NULL,
            viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, db_key, material_name, lecture_name)
        )""",
        """CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            first_name TEXT,
            message TEXT NOT NULL,
            admin_reply TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            replied_at TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS broadcast_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            total INTEGER DEFAULT 0,
            success INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP
        )""",
        """CREATE INDEX IF NOT EXISTS idx_downloads_user ON downloads(user_id)""",
        """CREATE INDEX IF NOT EXISTS idx_downloads_created ON downloads(created_at)""",
        """CREATE INDEX IF NOT EXISTS idx_recent_user ON recent_views(user_id, viewed_at)""",
        """CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback(user_id)""",
    ]
    with db_connect() as conn:
        for stmt in statements:
            conn.execute(stmt)

init_db()

# ============================================================
# HELPERS / SECURITY
# ============================================================
def is_admin(user_id):
    return user_id in ADMIN_IDS

def audit(admin_id, action, target="", details=""):
    try:
        with db_connect() as conn:
            conn.execute("INSERT INTO audit_logs (admin_id, action, target, details) VALUES (?, ?, ?, ?)",
                         (admin_id, action, str(target)[:200], str(details)[:1000]))
    except Exception:
        logger.exception("Audit log failed")

def is_user_banned(user_id):
    with db_connect() as conn:
        return conn.execute("SELECT 1 FROM banned_users WHERE user_id=?", (user_id,)).fetchone() is not None

def ban_user(user_id):
    with db_connect() as conn:
        conn.execute("INSERT OR IGNORE INTO banned_users(user_id) VALUES(?)", (user_id,))

def unban_user(user_id):
    with db_connect() as conn:
        conn.execute("DELETE FROM banned_users WHERE user_id=?", (user_id,))

LAST_SEEN_THROTTLE = 300  # ثواني - لتقليل الاتصال بقاعدة البيانات وتسريع رد البوت


def add_user(user_id, first_name):
    # كل رسالة كانت تفتح اتصال جديد بـ Turso فقط لتحديث "آخر ظهور" — وهاد
    # كان يبطّئ رد البوت بشكل ملموس. هلق نحدّثها بقاعدة البيانات كل 5 دقائق
    # بحد أقصى لكل مستخدم بدل كل رسالة، وهاد كافي جداً لهذا الاستخدام.
    now = time.monotonic()
    with state_lock:
        last = last_seen_cache.get(user_id)
        if last is not None and now - last < LAST_SEEN_THROTTLE:
            return
        last_seen_cache[user_id] = now

    with db_connect() as conn:
        conn.execute("""INSERT INTO users(user_id, first_name) VALUES(?, ?)
                       ON CONFLICT(user_id) DO UPDATE SET first_name=excluded.first_name,
                       last_seen=CURRENT_TIMESTAMP, is_active=1""", (user_id, first_name[:100]))

def mark_user_inactive(user_id):
    with db_connect() as conn:
        conn.execute("UPDATE users SET is_active=0 WHERE user_id=?", (user_id,))

def get_all_users():
    with db_connect() as conn:
        return [r[0] for r in conn.execute("SELECT user_id FROM users WHERE is_active=1 ORDER BY user_id").fetchall()]

def get_users_count():
    with db_connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

def rate_allowed(user_id):
    now = time.monotonic()
    with state_lock:
        q = rate_buckets[user_id]
        while q and now - q[0] > RATE_WINDOW:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            return False
        q.append(now)
        return True

def feedback_allowed(user_id):
    now = time.monotonic()
    with state_lock:
        q = feedback_buckets[user_id]
        while q and now - q[0] > FEEDBACK_WINDOW:
            q.popleft()
        if len(q) >= FEEDBACK_LIMIT:
            return False
        q.append(now)
        return True

def cleanup_states():
    while True:
        time.sleep(600)
        cutoff = time.monotonic() - 3600
        with state_lock:
            # States are timestamped as (state, updated_at).
            for store in (user_states, admin_states):
                for uid in list(store):
                    value = store[uid]
                    if isinstance(value, dict) and value.get("_updated", time.monotonic()) < cutoff:
                        store.pop(uid, None)
            for uid in list(subscription_cache):
                if subscription_cache[uid][1] < time.time():
                    subscription_cache.pop(uid, None)
            for uid in list(last_seen_cache):
                if time.monotonic() - last_seen_cache[uid] > LAST_SEEN_THROTTLE:
                    last_seen_cache.pop(uid, None)

threading.Thread(target=cleanup_states, daemon=True, name="state-cleaner").start()

def set_user_state(chat_id, **values):
    values["_updated"] = time.monotonic()
    with state_lock:
        user_states[chat_id] = values

def reset_user_state(chat_id):
    set_user_state(chat_id, year=None, sem=None, material=None)

def set_admin_state(user_id, **values):
    values["_updated"] = time.monotonic()
    with state_lock:
        admin_states[user_id] = values

def clear_admin_state(user_id):
    with state_lock:
        admin_states.pop(user_id, None)

def escape_md_text(text):
    return str(text).replace("\\", "\\\\").replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("`", "\\`")

# ============================================================
# STATIC COURSE CATALOG
# This remains the source of truth for lecture names + File IDs.
# To add/change/delete a lecture, edit the database below and redeploy.
# To obtain a File ID: use the admin button "📎 استخراج File ID" and send the file.
# ============================================================
database = {'year_1_sem_1': [{'name': 'رياضيات1 📐', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'فيزيا ⚡', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'تقانة 💻', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'خوارزميات 🧩', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'لغة1 🇬🇧', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'حماية بيئة 🌿', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'لغة عربية 📖', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}],
            'year_1_sem_2': [{'name': 'رياضيات2 📐', 'content': {' المقرر كامل 📄': 'BQACAgQAAxkBAAISyWqkBxNVP9FhULNWxsMd1JAZXaPaAAJXJwAC8KEgUf2QgCapkZOGPQQ', 'ملف التمارين الهام  📄': 'BQACAgQAAxkBAAITT2qo-qbacggOcG-van2oylXFXFeaAAKnJwAC8KEgUcLSED5ivsjCPQQ', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'ميكانيك ⚙️', 'content': {'مقرر كامل 📄': 'BQACAgQAAxkBAAIOtGqdKyBeezocYUtVXHhDULWaWzCPAAIgJQACyZjYUDRABVPmiW0iPQQ', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'برمجة 💻', 'content': {'برمجة نظري 📄': 'BQACAgQAAxkBAAIOsGqdKoTRvXpOkmdzyoXAfBKyWai8AAKUHwACWH24UMSW_RHmBGYLPQQ', 'برمجة عملي  📄': 'BQACAgQAAxkBAAIOsmqdKr_TnzATC2p-7k8Q3FK4gk9qAAKVHwACWH24UI3OBlPAzSO3PQQ', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'لغة2 🇬🇧', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAIKMmqTI84jkGbJC5fxdGfoHc4BQVpwAAIlHQACi-ohUs7uMgV_4xttPQQ', '📝 دورات سابقة': 'BQACAgQAAxkBAAIKNGqTI9eq2hpghJ4Hz6EUSOSXgj6WAAK8HAACIOEoUlA1QE3oHcC4PQQ'}}, 
                             {'name': 'اسس كهربا 🔌', 'content': {'تجارب المخبر 📄': 'BQACAgQAAxkBAAIOumqdLJNTOGfaF5wwywKJGiHvmGkGAAIwJQACyZjYUJ3pW6Tcx1HcPQQ', 'المقرر كامل 📄': 'BQACAgQAAxkBAAIOuGqdLHb4thNX8PAs74WqgxtVv8f5AAIuJQACyZjYUH7TU6EiFxwQPQQ'}},
                             {'name': 'صحة عامة 🏥', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAILBmqTtVV44UnTVNziyt5eGPEiS9MOAAI3GwACi-opUlPyu_XPA5P6PQQ', 'محاضرة 2 📄': 'BQACAgQAAxkBAAILCGqTtWCLZ-OZXbP0azVHlVqoqeKQAAI8GwACi-opUoL3FQEJSgdXPQQ', 'محاضرة 3 📄': 'BQACAgQAAxkBAAILCmqTtWpCoN1hl10jb6IFCp7h5-pqAAJhGwACi-opUi-rIxtCrslIPQQ', 'محاضرة 4 📄': 'BQACAgQAAxkBAAILDGqTtZE0qctHfdmmd0mohFhuBVLyAAI5GwACi-opUkf8n5XUbQWdPQQ', 'محاضرة 5 📄': 'BQACAgQAAxkBAAILDmqTtZsoAs_kCN2KwUHOZgZbCuH5AAI6GwACi-opUmHqmlpqR5JEPQQ', 'محاضرة 6 📄': 'BQACAgQAAxkBAAILEGqTtaL6wm_UNP3v9WbvxGUpdmCTAAI7GwACi-opUtsx3V-7tWYRPQQ', 'محاضرة 7 📄': 'BQACAgQAAxkBAAILCGqTtWCLZ-OZXbP0azVHlVqoqeKQAAI8GwACi-opUoL3FQEJSgdXPQQ', 'محاضرة 8 📄': 'BQACAgQAAxkBAAILE2qTtbi90VrAKzA8pocIPCfhDYm3AAI9GwACi-opUkh-wmkKxZzJPQQ', 'محاضرة 9 📄': 'BQACAgQAAxkBAAILFGqTtbgD6BEwSqY7OEZAK_UQ8a2IAAJiGwACi-opUiASFxjf4koBPQQ', 'محاضرة 10 📄': 'BQACAgQAAxkBAAILFWqTtbiXR5dgzJlaP35rZy3MfRmIAAK9HAACIOEoUty_CbP9uj8bPQQ', '📝 دورات سابقة': 'BQACAgQAAxkBAAILFWqTtbiXR5dgzJlaP35rZy3MfRmIAAK9HAACIOEoUty_CbP9uj8bPQQ'}}], 

            
             'year_2_sem_1': [{'name': 'رياضيات3 📐', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAJ112q_zNLpaH8YDish6H7zqq2wrtkCAAJnIwACA9MBUv5uGIalZSkSPQQ', 'محاضرة 2 📄': 'BQACAgQAAxkBAAJ12Wq_zOBR6CjhQ5i-fJW8Wydl4s2pAAJoIwACA9MBUqOk_56hUxr9PQQ', 'تمارين المحاضرة 1+2 📄': 'BQACAgQAAxkBAAJ122q_zOgSSErhMpphB7RrZCFdxtesAAJpIwACA9MBUvysHiUAAfBahT0E', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}, 
                             {'name': 'الكترون ⚡', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAKsUGrC3Xh8Ti5UpszrD1b1uiSr0lp8AAJIIAACho4YUuaCfxnSEZ_9PQQ', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}, 
                             {'name': 'oop 💻', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}, 
                             {'name': 'تصميم 🧩', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAJg1Gq-jeUTsx4B0U7yY09Aa_XQxsTXAAJhGwACbXjwUZBsqH7HT1IlPQQ', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'لغة3 🇬🇧', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'بني تحتية 🏥', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAKsT2rC3Xg_OzjLAR8Q7_mt5GTNHcXIAAJHIAACho4YUnowRQQZhn3QPQQ', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}, 
                             {'name': 'اسس دارات 🔌', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAJVOmq9g2-PZY-0InAobElriCvDjfQxAAL-HgACbXjoURIAAecYhPNj2T0E', 'محاضرة 2 📄': 'BQACAgQAAxkBAAJVOGq9g2dEGe4qJxJ4b7md6AgGzhgpAAL_HgACbXjoUWYR4AABvuxr4T0E' ,'محاضرة 3 📄': 'BQACAgQAAxkBAAKsU2rC3eV7mj_zKQMcBjGPj1fWHblsAAJnIQACXWoQUhqmmjzpy_U_PQQ', 'دورات 📄': 'BQACAgQAAxkBAAIW9mq46CfTJkVKDHrRd7qyGGD5gOXsAAIhGwACi5hoUxyXlftq04rPPQQ'}}],
         
            'year_2_sem_2': [{'name': 'رياضيات4 📐', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAITUWqo-vO5d4F_KioZ5depsFiunZrcAAKQHwAChhcpUYIVdo3aF7gJPQQ', 'محاضرة 2 📄': 'BQACAgQAAxkBAAITU2qo-wHdEBTF-V0oAgtJY4lK6tIyAAKRHwAChhcpUVTtg-2df6LTPQQ', 'محاضرة 3 📄': 'BQACAgQAAxkBAAITVWqo_Twpe2mAo7o5sOA7-LjCkm9zAAKSHwAChhcpUbwYTzPFaNqJPQQ', 'محاضرة 4 📄': 'BQACAgQAAxkBAAITV2qo_UtQwVo0dCQMjwdD_zHHizK5AAKTHwAChhcpUaX4ZEGy_0fUPQQ', 'محاضرة 5 📄': 'BQACAgQAAxkBAAITWWqo_V8UBi9zSAXXKQAB5jLVSypegAAClB8AAoYXKVHjjew-CLbH5z0E', 'محاضرة 6 📄': 'BQACAgQAAxkBAAITe2qo_72U-7ysM4VPlc7CYVCazHoPAAJgHgACduVJUSm-ilOlYJ-sPQQ', 'محاضرة 7 📄': 'BQACAgQAAxkBAAITW2qo_Zxg9gZbtIq1sln_AjlgD0CvAAKWHwAChhcpUQg1y6oTGHKNPQQ', 'محاضرة 8 📄': 'BQACAgQAAxkBAAITXWqo_a-vbxhDxGZ-zYWTnNhrSdsBAAKXHwAChhcpUcpKxU4MBBx0PQQ', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'تمثيلية ⚡', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAITX2qo_jlfKiHf9MOr5-mc8SuR9kBzAAKEHwAChhcpUT-h0vtJS8prPQQ', 'محاضرة 2 📄': 'BQACAgQAAxkBAAITYWqo_k5d--5C9P_OBPfxYLUy0OLwAAKFHwAChhcpUbGl5iAJlytnPQQ', 'محاضرة 3 📄': 'BQACAgQAAxkBAAITY2qo_mJXxDvt387XnaToY2LvwaXzAAKGHwAChhcpUanetCSMxGh6PQQ', 'محاضرة 4 📄': 'BQACAgQAAxkBAAITZWqo_nPEQ_YrcTAqAAERKegtovtxAwAChx8AAoYXKVEBIoZcLYOcAz0E', 'محاضرة 5 📄': 'BQACAgQAAxkBAAITZ2qo_oOYs69tKmg1G1GM2F0Rr0VFAAKIHwAChhcpUW1Fo1aGlQ2bPQQ', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}, 
                             {'name': 'اشارات 💻', 'content': {' المقرر كامل 📄': 'BQACAgQAAxkBAAITQGqo9CuuucVotC6-83v9x4WWH128AAKdHwAChhcpUYm-4_WDhjm5PQQ', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'انتشار 🧩', 'content': {' المقرر كامل 📄': 'BQACAgQAAxkBAAITTWqo-eP3rSoM19Ck1upqzvyhMIcjAAKeHwAChhcpUUHco3oqcpGwPQQ','📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'لغة4 🇬🇧', 'content': {' المقرر كامل 📄': 'BQACAgQAAxkBAAITjWqpAazm3Bh1RYAl1EGhUjHvvJu4AAJjHgACduVJUfX66-9dBENYPQQ',' نوطة 📄': 'BQACAgQAAxkBAAITzmqpAsjtzuAd2gFPYimigImWhLT4AAJmHgACduVJUcPBRDx9k3iNPQQ', '📝 دورات سابقة': 'BQACAgQAAxkBAAITi2qpAYiwq4jQSvmiJ1f7xEz4iBFBAAJiHgACduVJUWVAHTEcxYNWPQQ'}}, 
                             {'name': 'اقتصاد🌿', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAITaWqo_uGULKFDztz8NFkKRTDwHo6UAAKfHwAChhcpUYhdlwZlmhFzPQQ', 'محاضرة 2 📄': 'BQACAgQAAxkBAAITa2qo_yaDayBY2LQ42q9NAAHgdzeANgACoB8AAoYXKVEZC57VXjaIWT0E', 'محاضرة 3 📄': 'BQACAgQAAxkBAAITbWqo_zjQ5yx42Th-xRx-3jAtQtCFAAKhHwAChhcpUdAHYD_ZTqsEPQQ', 'محاضرة 4 📄': 'BQACAgQAAxkBAAITb2qo_0dNDrgEG8UP6c_p3fpeh9NdAAKiHwAChhcpUad9fMDINyeRPQQ', 'محاضرة 5 📄': 'BQACAgQAAxkBAAITcWqo_11YzC9q0cGWBlCM4lY6L0VCAAKjHwAChhcpUc0WvYIE95AkPQQ', 'محاضرة 6 📄': 'BQACAgQAAxkBAAITc2qo_2tvDAo6o8ruAQABbOJdPR3DTgACpB8AAoYXKVGoe7GDPVMg2T0E', 'محاضرة 7 📄': 'BQACAgQAAxkBAAITdWqo_38meBEVoHAcaOs1b4Uz3NZ1AAKlHwAChhcpUQvgpLIFTC3sPQQ', 'محاضرة 8 📄': 'BQACAgQAAxkBAAITd2qo_42mwrjb-motj420kpnrw2mdAAKmHwAChhcpUTpPfry7Lu-FPQQ', 'محاضرة 9 📄': 'BQACAgQAAxkBAAITeWqo_5uLTH9dGcyjGu_BiGnol8gPAAKnHwAChhcpUTG7GVX9c-k-PQQ','📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'مضخمات 🔌', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAITfWqo_9rMhdyctaAthLvkdxxx6GzTAAKJHwAChhcpUVCavaSgkTOOPQQ', 'محاضرة 2 📄': 'BQACAgQAAxkBAAITf2qo_-pJ6DT0oevWxgy61f9xcXsbAAKKHwAChhcpUROulKSvUkAUPQQ', 'محاضرة 3 📄': 'BQACAgQAAxkBAAITgWqo__rSeR1Kszaoe_6Nl8CHEum1AAKLHwAChhcpUckxkWYenxEPPQQ', 'محاضرة 4 📄': 'BQACAgQAAxkBAAITg2qpAAEHAVZ_xKjguwY8D5CVtpSV3QACjB8AAoYXKVGVg_oo23ZmGT0E', 'محاضرة 5 📄': 'BQACAgQAAxkBAAIThWqpAAEWGUVZFZLRI1WdUYr6KyweAQACjR8AAoYXKVF-mOFM7OkO_D0E', 'محاضرة 6 📄': 'BQACAgQAAxkBAAITh2qpAAEpTwlz7oEIsToIKtsmSRtxPwACjh8AAoYXKVFdar7Rm_AQhz0E', 'محاضرة 7 📄': 'BQACAgQAAxkBAAITiWqpAAE6Uh-NQIunoGraV0kM9NL7qgACjx8AAoYXKVGD3AIY70IICT0E', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}], 

            
            'year_3_sem_1': [{'name': 'قياسات 📏', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}, 
                             {'name': 'دارات منطقية 🔢', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'معالجة اشارة 📡', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAIZTGq7ajNPmpVic9HkPPQQQCsGXeH6AALRIQACu0XYUSI8m2M-AAEhkT0E', 'محاضرة 2 📄': 'BQACAgQAAxkBAAJVS2q9hElOoqzkb1DjvAcT24Q2mjqRAAKgHAACVC3oUQeIjxzUm7s7PQQ', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'نظرية الاحتمالات 🎲', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'بنية حاسب 💻', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'دارات خطية ولا خطية 📈', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'اتصالات رقمية 🔢', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAIZTmq7axqhry3X9bAo3HxWbErrlqBGAAJSIQACGUvZUaZx4C7i2OTwPQQ', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}], 
      
            'year_3_sem_2': [{'name': 'ترميز - نظم معلومات 🔐', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAIS82qkD1V4dkXJ_PyY1X8KVmHhuy-GAAJXHQACzUH4UNZDOBKgdYR4PQQ', 'محاضرة 2 📄': 'BQACAgQAAxkBAAIS9WqkD5CfrwNdWR4l_vOV4JGYfaNlAAJYHQACzUH4UIt6bjeaiAXzPQQ', 'محاضرة 3 📄': 'BQACAgQAAxkBAAIS92qkD6brXWkelE9Dp8_oKD-s0e7LAAJZHQACzUH4UBMjVjYUGBegPQQ', 'محاضرة 4 📄': 'BQACAgQAAxkBAAIS-WqkD8UDttyND_Uj7xNVKUEZMCe1AAJbHQACzUH4UJmFNy8wzIDsPQQ', 'محاضرة 5 📄': 'BQACAgQAAxkBAAIS-2qkD-xRAYIQPRqQJw2RXfyXIg9UAAJcHQACzUH4UBCdhQHTJCU1PQQ', 'محاضرة 6 📄': 'BQACAgQAAxkBAAIS_WqkD_yuwMPntJ3WbtY7W6M7EiplAAJdHQACzUH4UFLWVGTniaeGPQQ', 'محاضرة 7 📄': 'BQACAgQAAxkBAAIS_2qkEAu2GxX9cAS3Ig4THV-RsRN8AAJeHQACzUH4UMoQWwhTH39GPQQ', ' جلسة 1 عملي 📄': 'BQACAgQAAxkBAAITAWqkEKMR1zc_wc-bQWaERx5Y2-KPAAJfHQACzUH4UFvJX1DwdlNDPQQ', ' جلسة 2 عملي 📄': 'BQACAgQAAxkBAAITA2qkELCuxIWcpE0mRAjG3AZMCxfIAAJgHQACzUH4UPhOJ4GVL8OvPQQ', ' جلسة 3 عملي 📄': 'BQACAgQAAxkBAAITBWqkELwerZ_GVdZJEyaj03I_L1chAAJhHQACzUH4ULlGdIRuZdI2PQQ',  ' جلسة 4 عملي 📄': 'BQACAgQAAxkBAAITB2qkEM9Kc3i6ULl5o3oHB-UYYAYRAAJiHQACzUH4UI_wYcCWUmnjPQQ', ' جلسة 5 عملي 📄': 'BQACAgQAAxkBAAITCWqkEOQpBhe1G81Ha41MZsUIwWpgAAJjHQACzUH4UJj8PDVLtjvZPQQ', ' جلسة 6 عملي 📄': 'BQACAgQAAxkBAAITC2qkEPFqtZOOpDbsTtnquJw6Z_HTAAJkHQACzUH4UDElEcyll24ZPQQ',  ' جلسة 7 عملي 📄': 'BQACAgQAAxkBAAITDWqkEQABkrYMfKaIWc84t-yds_fQlgACZR0AAs1B-FB9utxI5DJ--z0E', ' جلسة 8 عملي 📄': 'BQACAgQAAxkBAAITD2qkEQ1ZTfLBx6K85RUUzYWqFGQYAAJmHQACzUH4UEEukQABYKaKYz0E', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}, 
                             {'name': 'تحكم الي 🤖', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAITEWqkFnJKop3CvJ_ER6uW4UQPHuMjAAJ8HwACzUEAAVGLkdEd-t56ZD0E', 'محاضرة 2 📄': 'BQACAgQAAxkBAAITE2qkFptuG74KTrKWqaMhAZcWf2vpAAJ9HwACzUEAAVFFWN062L0bNT0E', 'محاضرة 3 📄': 'BQACAgQAAxkBAAITFWqkFqiTrvLdBwYHebmDEh2Ru8jKAAJ_HwACzUEAAVGabC98XGvaIz0E', 'محاضرة 4 📄': 'BQACAgQAAxkBAAITF2qkFrR7tAmfxF1_vR4TPruXVRgXAAJ-HwACzUEAAVFzb20vZOZjGD0E', 'محاضرة 5 📄': 'BQACAgQAAxkBAAITGWqkFspxGYO8Q3cJRGpHT18jC5PgAAKAHwACzUEAAVFVoprBVE_Yjj0E', 'محاضرة 6 📄': 'BQACAgQAAxkBAAITG2qkFtXQQKMi9Ui7YE39TzqsmBgOAAKBHwACzUEAAVGR7TSRHZJ9fD0E', ' جلسة 1 عملي 📄': 'BQACAgQAAxkBAAITHWqkF2GX8rxLarpACMHg_BCnXXFWAAKNHwACzUEAAVHfsLmhobeb6j0E', ' جلسة 2 عملي  📄': 'BQACAgQAAxkBAAITH2qkF6VhXz9kdaAB5nPNyJLZYumQAAKMHwACzUEAAVHM_k-5LhP_sz0E', ' جلسة 3 عملي  📄': 'BQACAgQAAxkBAAITIWqkF7RQ9DXIZnKfnAqA1V9Y9O07AAKOHwACzUEAAVGhXHHmwWWUpT0E', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}, 
                             {'name': 'مكروية - هندسة امواج 🌊', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAIQD2qjL9BdAh-IS2bdXBtAkgrMHdWPAAJsHQACzUH4UAlUW0_suxlZPQQ', 'محاضرة 2 📄': 'BQACAgQAAxkBAAIQEWqjL-E5MeyNQOlEVb2hdeg4OshNAAJtHQACzUH4UL3prsn5TB6yPQQ', 'محاضرة 3 📄': 'BQACAgQAAxkBAAIQE2qjMBDmhX0xHX8SH-skseIIvASYAAJvHQACzUH4UOV0KcxiCbvfPQQ', 'محاضرة 4 📄': 'BQACAgQAAxkBAAIQFWqjMB_eVdTGbxco2yFNWHnq-HU_AAJwHQACzUH4UGfVvuiuT0h5PQQ', 'محاضرة 5 📄': 'BQACAgQAAxkBAAIQF2qjMDU0hyboYjBBGSz8aOuspBdeAAJxHQACzUH4UEoDlH_pnRpAPQQ', 'محاضرة 6 📄': 'BQACAgQAAxkBAAIQGWqjMEOWHS6jCwyIo1MQDqKKZNiLAAJyHQACzUH4UEmybKUFDYNaPQQ', 'محاضرة 7 📄': 'BQACAgQAAxkBAAIQG2qjMFJrxvOJ7mSPBwhRorvlhH7GAAJzHQACzUH4UKiu-26WZHWqPQQ', ' جلسة عملي 1 📄': 'BQACAgQAAxkBAAIRFmqjNnRwKNUfvpQyfF0feGm0cHUqAAJ2HQACzUH4UMoAAX9McK_Xdz0E', ' جلسة عملي 2 📄': 'BQACAgQAAxkBAAIRGGqjNrOcTIY7N1wAAeexSLpOnf54kAACdx0AAs1B-FB8Ysy79aS30D0E', ' جلسة عملي 3 📄': 'BQACAgQAAxkBAAIRGmqjNuOWcWg-ZpqKPyj95K5IVtVwAAJ4HQACzUH4UPnke6qI5zYdPQQ',  ' جلسة عملي 4 📄': 'BQACAgQAAxkBAAIRHGqjNxhqIngOXdkhKXOHmiUWrUSfAAJ5HQACzUH4UNzBikJX7e0dPQQ',  ' جلسة عملي 5+6 📄': 'BQACAgQAAxkBAAIQHWqjMUlxD_6IZg34FuqJe9TW7SZSAAJ7HQACzUH4UAVfM8hwegdiPQQ', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},     
                             {'name': 'دارات متكاملة 🔲', 'content': {'محاضرة 2+1 📄': 'BQACAgQAAxkBAAIPumqihZ9DAyGKcsGp1GK5wdMSAAHIYgAC2B4AAv2JGFHUODXIQZjO1z0E', 'محاضرة 3 📄': 'BQACAgQAAxkBAAIPvGqihg7yLSEYhfktQc21tdS50_jbAAI2HQACzUH4ULumym5ptRI3PQQ', 'محاضرة 4 📄': 'BQACAgQAAxkBAAIPvmqihhi4Q_E739mJXbwLawNX_FosAAI3HQACzUH4UAGHQbaRKThLPQQ', 'محاضرة 5 📄': 'BQACAgQAAxkBAAIPwGqihiHLCu4LIUDohkxeZgAB6h86WAACOB0AAs1B-FCcCjstU5bCtT0E', 'محاضرة 6 📄': 'BQACAgQAAxkBAAIPwmqihihS4dk_-N83NviilqDc-b5KAAI-HgAClLJwUkFStBL6iOHGPQQ', 'محاضرة 7 📄': 'BQACAgQAAxkBAAIPxGqihi7ymlHXdFGPARioGgABxtlPgwACLh4AAnf9SVITQzFTkFNS0z0E', 'محاضرة 8 📄': 'BQACAgQAAxkBAAIPxmqihjWYqWMxLV1GcptdB4Xk3Y1eAAIvHgACd_1JUgABqA3fjCEtqj0E', 'محاضرة 9 📄': 'BQACAgQAAxkBAAIPyGqihjqB3a4KnwIhIs3Zo8hCQ-hPAAIwHgACd_1JUny-7Jb30bMZPQQ', 'محاضرة 10 📄': 'BQACAgQAAxkBAAIPymqihj_2525DbZRs8nqNZPNixpARAAIxHgACd_1JUr5OoNs89qn0PQQ', ' ملف التمارين 📄': 'BQACAgQAAxkBAAIPzGqihkWii14uJv9khWb1H91NrkNDAAI5HQACzUH4UKOwzgaaoPGiPQQ', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},                             
                             {'name': 'معالجة ومتحكمات 🎛️', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAIQI2qjMjXEEPnU8gsUL8mmbjnHJbHRAAJUHgACzUH4UGRsL6lMKH6QPQQ', 'محاضرة 2 📄': 'BQACAgQAAxkBAAIQJWqjMk2f_dYlOJ12SKfBqOMPZDkrAAJWHgACzUH4UEOxrzykZyQSPQQ', 'محاضرة 3 📄': 'BQACAgQAAxkBAAIQJ2qjMmipGdBHLcnwFm6hJ7J37eAGAAJOHwACzUEAAVGIILr5NRVU0z0E', 'محاضرة 4 📄': 'BQACAgQAAxkBAAIQKWqjMnlBV1uTOnqtksHn6_XRvUEjAAJPHwACzUEAAVENPdw5J_2e0T0E', 'محاضرة 5 📄': 'BQACAgQAAxkBAAIQK2qjMo6VjjgO4A0jOwpFbYnKl5vrAAJQHwACzUEAAVF5yjHGNs96yz0E', 'محاضرة 6 📄': 'BQACAgQAAxkBAAIQLWqjMqPF_v8g_6a7fOvy1ASsY0pPAAJRHwACzUEAAVE4ls--6WPOBz0E', 'محاضرة 7 📄': 'BQACAgQAAxkBAAIQL2qjMrETk6RinkDNV6bwmYCpKrHgAAJSHwACzUEAAVEWB2gyfkUJ3D0E', 'محاضرة 8 📄': 'BQACAgQAAxkBAAIQMWqjMr99J6HFokVTwK1cqpBTvviNAAJTHwACzUEAAVHx0qV9-ctb_D0E' ,  ' جلسة عملي 1 📄': 'BQACAgQAAxkBAAIRIGqjOGbgTvM4ygMEqJhc9_6rW4e8AAJUHwACzUEAAVGgOUh5Ha8Hyz0E', ' جلسة عملي 2 📄': 'BQACAgQAAxkBAAIRImqjOIeWtypEkXSCmfxx4Nj6wTb4AAJVHwACzUEAAVH8VxDW0SuFPT0E',  ' جلسة عملي 3 📄': 'BQACAgQAAxkBAAIRJGqjOLyn19WIL9YO2JBCNB1gjT7yAAJXHwACzUEAAVH8zqyLS-Gnzj0E',  ' جلسة عملي 4 📄': 'BQACAgQAAxkBAAIRJmqjOMyobsNeBjTMppe2ZHBdFvIDAAJZHwACzUEAAVHAOiPHql96Ez0E', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},                         
                             {'name': 'تراسل معطيات 📲', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAITI2qkGRQS_zklxyxZUojP2ne60spqAAKCHwACzUEAAVGeYIU7DRUG3j0E', 'محاضرة 2 📄': 'BQACAgQAAxkBAAITJWqkGSIStJwnq0OO4hSUMPiZoamkAAKDHwACzUEAAVEdIygPITAliD0E', 'محاضرة 3 📄': 'BQACAgQAAxkBAAITJ2qkGS_lJppGI_3Rk36FD-mH-l1rAAKEHwACzUEAAVGIkpc3v_FOOT0E', 'محاضرة 4 📄': 'BQACAgQAAxkBAAITKWqkGVxsAsjotW-MFCuEtocENAocAAKFHwACzUEAAVFbdtz8ugSy8T0E', 'محاضرة 5 📄': 'BQACAgQAAxkBAAITK2qkGXBSOAk3G6nRGKA-1r1mihDoAAKGHwACzUEAAVGn6j1I4sgysT0E', 'محاضرة 6 📄': 'BQACAgQAAxkBAAITLWqkGYsProIX43HlZaSYTOxJ_R5mAAKHHwACzUEAAVHPWJQdDLoVLD0E', 'محاضرة 7 📄': 'BQACAgQAAxkBAAITL2qkGa7tiTiktSab3-zUIMQr2hOXAAKIHwACzUEAAVGyr-duddIAAf09BA', 'محاضرة 8 📄': 'BQACAgQAAxkBAAITMWqkGb3Gaix0HUAo6Nc3D5jFvQyZAAKJHwACzUEAAVGyIdlKG_HMGj0E', 'محاضرة 9 📄': 'BQACAgQAAxkBAAITM2qkGcvA8ND_Mozdc0Oi3OD8LGbdAAKKHwACzUEAAVHBjY3nwMlj5z0E', 'محاضرة 10 📄': 'BQACAgQAAxkBAAITNWqkGdpM4T-QPEX1T4BCWk-gvhPAAAKLHwACzUEAAVG8vn3CGweQ7D0E', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'الرسم باستخدام الحاسب 🎨', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAIP-2qjLcxAdQUBBU6eZk6eioXAZWeIAAI9HQACzUH4UFuopZBPJEP8PQQ', 'محاضرة 2 📄': 'BQACAgQAAxkBAAIP_WqjLdUbzMpdWKwoQ7evCF_2zL9IAAI-HQACzUH4UKR177Ilq0JMPQQ', 'محاضرة 3 📄': 'BQACAgQAAxkBAAIP_2qjLd5qjbD6zfXXVwlIq2wxAbBAAAI_HQACzUH4UIiXGkwK12oYPQQ', 'محاضرة 4 📄': 'BQACAgQAAxkBAAIQAWqjLjansUiJ9HgutYIojHqRuJ4wAAJAHQACzUH4UPo9r1kQ7aF8PQQ', 'محاضرة 5 📄': 'BQACAgQAAxkBAAIQA2qjLkh8J6Xl72WL3Can6MEVciOAAAJBHQACzUH4UNS16KGWCWvGPQQ', 'محاضرة 6 📄': 'BQACAgQAAxkBAAIQBWqjLljQeg3XNn8IQcnIzU6mQEolAAJCHQACzUH4UAMcpotXpkEzPQQ', 'محاضرة 7 📄': 'BQACAgQAAxkBAAIQCWqjLooAAWWYBEZiXWltZp7eP1UD_gACQx0AAs1B-FC6gMeKI8q6Jz0E', 'محاضرة 8 📄': 'BQACAgQAAxkBAAIQB2qjLmivPLYDOpavD6YHb75aHXscAAJEHQACzUH4UAWb5PUxX1H9PQQ',  ' جلسة عملي 1 📄': 'BQACAgQAAxkBAAIRNmqjOX7-AVxADXlkVosHvaWSzetSAAIPHwACxgthUW7dCfpjJxmzPQQ', ' جلسة عملي 2 📄': 'BQACAgQAAxkBAAIROGqjOcCIcz6w79ekijY2tZic6zhrAAIQHwACxgthUV9xTA81QzKGPQQ',  ' جلسة عملي 3 📄': 'BQACAgQAAxkBAAIROmqjOc_midjvDGD1ZOSmMOe61tMUAAIRHwACxgthUY4yLBNvYeRpPQQ',  ' جلسة عملي 4 📄': 'BQACAgQAAxkBAAIRPGqjOeh7JXhUfV7ZE2fBBJldkYcQAAISHwACxgthUXY_y-dpotbmPQQ', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}],
           
            
            'year_4_sem_1': [{'name': 'تلفزيون 📺', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAKxvWrDNMrseSRsKsqkl-ZJesxLJ929AAKKHwACAn8ZUlTjCSZCaRfWPQQ', 'محاضرة 2 📄': 'BQACAgQAAxkBAAKxv2rDNOcKDIHiomsxvShtsRl5kwABSQACix8AAgJ_GVLducJqq3OYAj0E', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}, 
                             {'name': 'رادار و سونار 🛰️', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAJVPGq9g8psKEyE0UZH6xp7GUL6FRcBAAIUIQAC977YUboUmrzCiYtkPQQ', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'شبكات 🌐', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'نمذجة 📊', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAALGImrDyGHu9DcGey135kKmrN88Gi8xAAJpIAACAn8ZUsnQuG408vrnPQQ', 'محاضرة 2 📄': 'BQACAgQAAxkBAALGI2rDyGGKzAhGJwveRiJ-vNb4Ywf-AAJqIAACAn8ZUhpDzg44qf3MPQQ', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}, 
                             {'name': 'هوائيات 📡', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAIZemq7p7KoCfbeu1KEci_OL1_X3_RkAAJbIAAC977YUYF2KIksNPEdPQQ', 'محاضرة 2 📄': 'BQACAgQAAxkBAAIZfGq7p8qugv_4QynoZY1AOIWt3fyjAAJeIAAC977YUcfAVfFG39mRPQQ', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'مقاسم 📞', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAIZeGq7p280IgHCks8No25aDEwYfoZ0AAJZIAAC977YUSZ1W9VAnAh7PQQ', 'محاضرة 2 📄': 'BQACAgQAAxkBAAKxwWrDNQQyzH0Z0ZPAf0IErEHtDdFuAAKNHwACAn8ZUgeYAAFRlS_ZKT0E', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}],

            'year_4_sem_2': [{'name': 'معالجة صورة 📶', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAIYC2q6oNvNz2U8yDnWMJVt9i-u8XGHAAKHHAAC3v3oUnFYOfwdt424PQQ', 'محاضرة 2 📄': 'BQACAgQAAxkBAAIYDGq6oNtjAS-4Yn85-CGJWfP3n75lAAKDHAAC3v3oUvzptoZ_6TL1PQQ', 'محاضرة 3 📄': 'BQACAgQAAxkBAAIYDWq6oNvND2LCkO5kGvcMjZaCI5d5AAL2IgAC3v3wUhwbWvCceLG4PQQ', 'محاضرة 4 📄': 'BQACAgQAAxkBAAIYDmq6oNvUjvZ4tSL5nJPRjNpq9nbUAAKrIgACkBApUzK6uf18QKVgPQQ', 'محاضرة 5 📄': 'BQACAgQAAxkBAAIYD2q6oNvcMHdOobAXZRzqjJCJGgnOAALuIQACqwhAUx1f8qEWjnbJPQQ', 'محاضرة 6 📄': 'BQACAgQAAxkBAAIYEGq6oNuXtWnbnpYaH9b-v0sM0iPCAAJFHwACzdCBU1EZA5rEes-4PQQ', 'محاضرة 7 📄': 'BQACAgQAAxkBAAIYEWq6oNtnCJKTnxiJpjWqMbSQ_bdxAAJGHwACzdCBU2KwJnLuT0fLPQQ', 'محاضرة 8 📄': 'BQACAgQAAxkBAAIYEmq6oNscc-0RPtvCB_OOLVKHzog7AAJRHAAC6KH5U6gghkjIboLUPQQ', 'محاضرة 9 📄': 'BQACAgQAAxkBAAIYE2q6oNuMbNQvQYcLzaHJkI6JM57oAAKYHwACwyoRUPwOfGELfwTCPQQ', 'محاضرة 10 📄': 'BQACAgQAAxkBAAIYFGq6oNsH-ox-KuvTCjdj--moGB6KAALSJAACeVVRUMiTl3WHbXVpPQQ', '📝 دورات سابقة': 'BQACAgQAAxkBAAIYH2q6orH3gwoEyZ6cdICTV1EwCPWRAAJSGwAC0eQQU_EPfBmTYMMuPQQ' , 'محاضرة 1 (قسم 2) 📄': 'BQACAgQAAxkBAAIYIWq6oszpcpJebCMkqOaZxzAoa-T-AAJ4IAACeLh4ULy9HwoUrnkdPQQ', 'محاضرة 2 (قسم 2) 📄': 'BQACAgQAAxkBAAIYImq6osx3ExoD8fwoohHIysDNV2oJAAJlHwACSaqRUEocHCCD1dmMPQQ', 'محاضرة 3 (قسم 2) 📄': 'BQACAgQAAxkBAAIYI2q6oswgraWc5JrGG97OQA7QyJgAAwEhAAISuqhQadCs0ZYgmjU9BA', 'محاضرة 4 (قسم 2) 📄': 'BQACAgQAAxkBAAIYJGq6osxTTqR1oKy8lMiV6BE-L0RHAALEHAACC3rhUDH1GJL0_JohPQQ', 'محاضرة 5 (قسم 2) 📄': 'BQACAgQAAxkBAAIYJWq6osyuI5rOwo3FqNTSvzMMCqTAAAKNIQAC3vsgUXYSejtxdPk-PQQ', 'محاضرة 6 (قسم 2) 📄': 'BQACAgQAAxkBAAIYJmq6osyqXApHXskXG6-4m1ajhJWrAAJrHAACXnAwUQ21hyFKpARyPQQ', 'جلسة 1 عملي 📄': 'BQACAgQAAxkBAAIYLWq6o1PaSXC79czJJOhC1e_hrRnDAAKFHAAC3v3oUnVbYj5JDPLwPQQ', 'جلسة 2 عملي 📄': 'BQACAgQAAxkBAAIYLmq6o1P5AAFd7QEouLey4nJzweYTIQACaSEAAqsIQFNgo2qTt3nHpD0E', 'جلسة 3 عملي  📄': 'BQACAgQAAxkBAAIYL2q6o1Mzbh1ruqKxGVsfxustI54HAAJqHAACVS8YUDqEG3zb3nL4PQQ', 'جلسة 4 عملي 📄': 'BQACAgQAAxkBAAIYMGq6o1M_YLt96UZtJwd4N0YQmZiKAAKuIgAC-w8BUXWBE_uZu4gBPQQ'}}, 
                             {'name': 'تقانة الانترنت 🌐', 'content': {'internet Technology 📄': 'BQACAgQAAxkBAAIX-Wq6mqCokQXQGl9IAAHhVAg5kD2bUgACPiAAAumhkFIHbQSmNzQDFD0E', 'ISDN 📄': 'BQACAgQAAxkBAAIX-2q6nM83jQbwwPFZZRDHlFhcTProAAI_IAAC6aGQUs4IH6oTLL-uPQQ', 'ATM 📄': 'BQACAgQAAxkBAAIX_Wq6nPSCvDJW-khS3__l4LpXTJZYAAJCIAAC6aGQUqREXsYk_06EPQQ', 'VOIP 📄': 'BQACAgQAAxkBAAIX_2q6nSZAGWrvjuxFu0LNFS41x5eXAAJBIAAC6aGQUnFB637HVmEFPQQ', 'MODEMS 📄': 'BQACAgQAAxkBAAIYAWq6nhaeQXtg5UqHBdYIDckPTnaeAAJDIAAC6aGQUh-j8QtLZuZmPQQ', 'X DSL 📄': 'BQACAgQAAxkBAAIYA2q6nmKFGiFa_m1ypLaQbAABUBlNkQACRCAAAumhkFKMEdeGwwmpCD0E', 'SONET 📄': 'BQACAgQAAxkBAAIYBWq6nqN5fP5aDrWLmJgES4xFBbL0AAKsIQACUoLJUVWfdf7FWr1dPQQ', ' دورات تقانة 📄': 'BQACAgQAAxkBAAIYB2q6nwxz0K6-pl0ggdeCQW_jPEcyAAKLIQACWPixUnm6hvqvqfaPPQQ', 'اخر دورة 📄': 'BQACAgQAAxkBAAIYCWq6n2OYDulQHP5cj4W8mbxx2S_ZAAKxHQAC4QfIUuCfF8GoGF2hPQQ'}},
                             {'name': 'بروتوكلات الانترنت 🔌', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAIYNWq6pOCTb8SUXGJQ-54CMkJEdTkyAAJFIAAC6aGQUtt0TdjdPoTQPQQ', 'محاضرة 2 📄': 'BQACAgQAAxkBAAIYNmq6pOChh5vyNOc8qIRMc-2hyBqNAAJGIAAC6aGQUkbUDIMe0OjAPQQ', 'محاضرة 3 📄': 'BQACAgQAAxkBAAIYN2q6pOAHGTK0sWzZx2DJB1-pRL-9AAIaIAACCJUBU1da8JARFC6QPQQ', 'محاضرة 4 📄': 'BQACAgQAAxkBAAIYOGq6pODyJQN3IsCdiXMRdqlpGG2ZAAKMGwACqwhIU15796rdI9c7PQQ', 'محاضرة 5 📄': 'BQACAgQAAxkBAAIYOWq6pODqxwxO7JDRuyDUYV7E8xJBAALGHwACwyoRUPMXTK8fJs5DPQQ', 'محاضرة 6 📄': 'BQACAgQAAxkBAAIYOmq6pODg9UKI3JawhLZ7w13IVVZBAAK3IwAClNhYUC5KzJIi00dxPQQ', '📝 دورات سابقة (ملف إضافي)': 'BQACAgQAAxkBAAIYQmq6pX8mDeNXt-2sYK1Oq9qQuJ6iAAJDHgACQ6EpUxKmc6wBwTJvPQQ', '📝 دورات سابقة': 'BQACAgQAAxkBAAIYQWq6pX_EJ5Fc0iA4qGSxEE7DoUD9AALvHAACr2QZU0PiOI0u2KogPQQ'}}, 
                             {'name': 'اتصالات ضوئية 💡', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAIYR2q6pwgd--JRMNfWt9Y3Z8HQ14b4AAKbHgACQUxBUIzTQVci66WGPQQ', 'محاضرة 2 📄': 'BQACAgQAAxkBAAIYSGq6pwhVxywvzA_8pnxezZxJ-mTFAAJNHwACSaqRUHlM9cen74QHPQQ', 'محاضرة 3 📄': 'BQACAgQAAxkBAAIYSWq6pwjkmaGVluq_BlrRbDMAAZ0YKwACTh8AAkmqkVCpmnO8jIm40z0E', 'محاضرة 4 📄': 'BQACAgQAAxkBAAIYSmq6pwhoSAABJb7gFL5ZE_4EVDcHNAACxhwAAgt64VDhH_bN8P8pgT0E', 'محاضرة 5 📄': 'BQACAgQAAxkBAAIYS2q6pwgE5tTBjwfl2q_lOqlc7PsrAAKMIgACNgx5Ub5WPmY-goFtPQQ', 'الفصل 3 📄': 'BQACAgQAAxkBAAIYUmq6p1coOAJ7WamdyDNUiWqsKrUTAAJjIQAC_k0QURrsQfutwVQjPQQ', 'الفصل 5 📄': 'BQACAgQAAxkBAAIYU2q6p1eA1SZ36zU6hLer6ZGKTf0CAAJJGgAChxfQUwFRPERkZuW2PQQ', 'الفصل 10 📄': 'BQACAgQAAxkBAAIYVGq6p1cx6dnY3rnDkXbv3r5M37rXAAIpHgACcYXJU7EH242sI25wPQQ', 'الفصل 12 📄': 'BQACAgQAAxkBAAIYVWq6p1ef-r85p0utOSZfumWR4cC4AAJzIAAC4MPZU6jvizJjlSvCPQQ', 'جلسة 1 عملي 📄': 'BQACAgQAAxkBAAIYWmq6p94IBMEx_lz1wUFG8X6yekT8AAJGHwACIlwwU_fyRMPKj-OzPQQ',  'جلسة 2 عملي 📄': 'BQACAgQAAxkBAAIYW2q6p97hsUQ229qWFYp4k-kiSdlzAAIfHgACcYXJU9PruM8HfdwBPQQ',  'جلسة 3 عملي 📄': 'BQACAgQAAxkBAAIYXGq6p966qwO-LXQ40e4NXmeZC_g5AAKDIAACeLh4UOGk5GQtV3CaPQQ',  'جلسة 4 عملي  📄': 'BQACAgQAAxkBAAIYXWq6p963SAQKMMXHfMc2-GShD008AALnIAAC61pQUdTGwZG6GA94PQQ', '📝 دورات سابقة': 'BQACAgQAAxkBAAIYRWq6piVfXuzvOQmHyE4waa1ssPpSAAJXHQACVp4oUg1xNzn07AEdPQQ'}},  
                             {'name': 'كهرصوت - تطبيقات امواج 🔊', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAIYYmq6qRkYf4jNPkhUsYbpSXbrJkv4AAI7IAAC6aGQUldFjokl-jtuPQQ', 'محاضرة 2 📄': 'BQACAgQAAxkBAAIYY2q6qRnpqqKjk11c3Jgff_Jear5qAAI9IAAC6aGQUg9aj2Tdce4BPQQ', 'محاضرة 3 📄': 'BQACAgQAAxkBAAIYZGq6qRkEh2AIlcW-shpfDKykQ6VMAAKXGwAC91DIUmxJd0pitI26PQQ', 'محاضرة 4 📄': 'BQACAgQAAxkBAAIYZWq6qRmZGnOCjEoJbjtdRmtjyVt5AAIYIAACCJUBU2vflHpu6hJsPQQ', 'محاضرة 5 📄': 'BQACAgQAAxkBAAIYZmq6qRmIIhzs8qxb4tuqByyMvZJ4AAJJGgACoCJRU3obCXlpCtpcPQQ', 'محاضرة 6 📄': 'BQACAgQAAxkBAAIYZ2q6qRm28vw53IQzh_3422q-0lxNAALjHgAC1lWQU5KZjA29qb9pPQQ', 'محاضرة 7 📄': 'BQACAgQAAxkBAAIYaGq6qRn3kiBwHl3lIsEjIKaEmXhXAALkHgAC1lWQU4mLA4U7oe1GPQQ', 'محاضرة 8 📄': 'BQACAgQAAxkBAAIYaWq6qRmCi5mycpGDpNDTNWBWyWvnAALIGwACVS8gUNaP8BYdOvu0PQQ', 'محاضرة 9 📄': 'BQACAgQAAxkBAAIYa2q6qRm6txZ_ipjky7TR_RcM8BCHAALKGwACVS8gULWGYvFfe54HPQQ', 'محاضرة 10 📄': 'BQACAgQAAxkBAAIYa2q6qRm6txZ_ipjky7TR_RcM8BCHAALKGwACVS8gULWGYvFfe54HPQQ', 'محاضرة 11 📄': 'BQACAgQAAxkBAAIYbGq6qRnX7PzapXNMtzHWLWmTjfjVAALLGwACVS8gUILDNkwsNdAxPQQ', 'محاضرة 12 📄': 'BQACAgQAAxkBAAIYbWq6qRlaYEUY7IvxVBIqjVqXpBAoAAJPIAACAYtwUIYLEnSORYfhPQQ', 'محاضرة 13 📄': 'BQACAgQAAxkBAAIYbmq6qRlDOnJxHovQmXhqKjqNohpeAALVGwAC-w8JURudGLtk9Oh9PQQ', '📝 دورات سابقة': 'BQACAgQAAxkBAAIYfGq6qdLiyXaqGYKqSRWqmim8NRFqAAJjHQACVp4oUsouEimbMdCWPQQ'}},
                             {'name': 'خليوي 1 📱', 'content': {'المقرر كامل 📄': 'BQACAgQAAxkBAAIYfmq6qlCkcmftiQIKrsW9qTdNk-ObAAJPHwACSaqRUC4OnAEJZj_2PQQ', 'جلسة عملي 1 📄': 'BQACAgQAAxkBAAIYgGq6qmN9gqZv45UAAdEbypgskQ_YcwACXx4AAgt66VDEWdYtF7mIDj0E', 'جلسة عملي 2 📄': 'BQACAgQAAxkBAAIYgmq6qqhp5YDHvmmBCXwKZu3eCUBOAAJXHgACC3rpUI79gImQAAG9lT0E', 'جلسة عملي 3 📄': 'BQACAgQAAxkBAAIYhGq6qxMLog7OueO3pzGdlwqo7AwUAAJbHgACC3rpUPRwXF2LDZl-PQQ', 'جلسة عملي 4 📄': 'BQACAgQAAxkBAAIYhmq6qxjvT6tbw17QO6U7nOIYVWyCAAJdHgACC3rpUJELhsVPyddtPQQ', 'جلسة عملي 5 📄': 'BQACAgQAAxkBAAIYiGq6qxqYPz4iZwpwkPA4lnGJJYK9AAJeHgACC3rpUJWozwthuGOlPQQ', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},  
                             {'name': 'تدريب ميداني 🛠️', 'content': {'معالجة الاشارة الهاتفية 📄': 'BQACAgQAAxkBAAIYimq6rZjmQkcrO_bx8cJ-fXibS1ggAAJHIAAC6aGQUtVig6sMbX6mPQQ', 'مقسم 1 📄': 'BQACAgQAAxkBAAIYjGq6reLKzPXvBlQappYCt_rUZNkxAAJIIAAC6aGQUncK7nB9kMg9PQQ', 'مقسم 2 📄': 'BQACAgQAAxkBAAIYjmq6rfSSgjKutztSjinBkBKmlwIDAAJLIAAC6aGQUoTjwNoBjNEvPQQ', 'التعرف مكونات الوصلة 📄': 'BQACAgQAAxkBAAIYkGq6rggW2xy36aVkBJqzUdK9xZqZAAJdJAAC3v3wUicN7pYrq14tPQQ', 'مكونات المحطة القاعدية 📄': 'BQACAgQAAxkBAAIYkmq6rk70366Bana5Hh06JP69K9wkAAI5HwACzdCBUx9QX-kLiIsUPQQ', 'انواع التجهيزات 📄': 'BQACAgQAAxkBAAIYlGq6rnOrhM5FfMN5FxpwbOn59NXiAAK7JAAC3v3wUs5CWhog8AucPQQ', 'انظام التيترا 📄': 'BQACAgQAAxkBAAIYlmq6rpk3qAJ1go_xN9bFcSaKeNiTAAI6HwACzdCBU_aBgcGmh5CAPQQ', ' محلل الطيف 📄': 'BQACAgQAAxkBAAIYmGq6rsB0cOznTmAyJ52xi0uEcpgcAAJrHAACVS8YUP1kGqA8YvJzPQQ', 'استخدام المكرر 📄': 'BQACAgQAAxkBAAIYmmq6rttqLFtEhtKNHh4Tl3CtYYzmAAJtHAACVS8YUAcnZCdoBLNaPQQ', ' تجهيزات المخبر 📄': 'BQACAgQAAxkBAAIYnGq6rt8BY85lhNgh9FiEX2Dd8ay7AAL9OgAC61pgUcEEqWVoTtTSPQQ', 'جلسة 1 عملي 📄': 'BQACAgQAAxkBAAIYnmq6r5MiE53iOqRSfB3XMbBQ3hQ_AAKOHAAC3v3oUqjD5gL8i4e0PQQ', 'جلسة 2 عملي 📄': 'BQACAgQAAxkBAAIYn2q6r5OX0NnT6NYy6JsgEEmV4nYnAAJOHwACIlwwU0gS5yUlrLjnPQQ', 'جلسة 3 عملي 📄': 'BQACAgQAAxkBAAIYoGq6r5NAx7KnD71QqMajLAMT7uFaAAIbHAACjt6JUVGbcP5wk8rKPQQ', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}], 

            
            'year_5_sem_1': [{'name': 'امن الشبكات 🛡️', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAAKxLmrDMWQ2zTCi8bMlhbOQPjo4idzEAAJgIwACBYMYUl-gtHZeghBOPQQ', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'دارات مكروية 🔬', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAALGVmrDyJlr9soTrhPd4iz7H9oQkXU3AAKBIAACHVYhUmG8bngklkdVPQQ', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}, 
                             {'name': 'نظم الاتصالات الخلوية 📱', 'content': {'محاضرة 1 📄': 'BAACAgQAAxkBAAKxXGrDMkPZIkXc52fuPlVpnudC6dvVAALtHwACuw4JUiznh7gpi-MqPQQ', 'تكملة المحاضرة 1 📄': 'BAACAgQAAxkBAAKxtWrDM-Nu8SsPlLi9XzOvqzdZtnFcAALvHwACuw4JUmFT6-JhEVxIPQQ', 'نهاية الاولى 📄': 'BAACAgQAAxkBAAKxu2rDM_6oBhtZB8ebfeRt7yidVte5AAL1HwACuw4JUoMVm6ZCwkjSPQQ', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'تصميم شبكات 📐', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}, 
                             {'name': 'تقانات نانونية ⚡', 'content': {'محاضرة 1 📄': 'BQACAgQAAxkBAALGOGrDyIJNmrRNPpS8YRe5C9Fz-1mcAAKAIAACHVYhUjhgN_EihptdPQQ', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'مخبر شبكات 💻', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}], 
            'year_5_sem_2': [{'name': 'حساسات - شبكات لاسلكية 📟', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}},
                             {'name': 'برمجة وادارة الشبكات ⚙️', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}, 
                             {'name': 'الوثوقية والمعايرة ⚖️', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}, 
                             {'name': 'ذكاء اصطناعي 🧠', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}, 
                             {'name': 'اتصالات فضائية 🚀', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}, 
                             {'name': 'تطبيقات برمجية 🖥️', 'content': {'محاضرة 1 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 2 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 3 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 4 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 5 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 6 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 7 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 8 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 9 📄': 'PASTE_FILE_ID_HERE', 'محاضرة 10 📄': 'PASTE_FILE_ID_HERE', '📝 دورات سابقة': 'PASTE_FILE_ID_HERE'}}]}

# ============================================================
# CATALOG HELPERS
# ============================================================
def catalog_materials(db_key):
    return database.get(db_key, [])

def find_material(db_key, material_name):
    return next((m for m in catalog_materials(db_key) if m["name"] == material_name), None)

def find_file_id(db_key, material_name, lecture_name):
    mat = find_material(db_key, material_name)
    if not mat:
        return None

    content = mat.get("content", {})
    # نبحث بالاسم كما هو أولاً، ثم نتجاهل المسافات الزائدة.
    value = content.get(lecture_name)
    if value is None:
        wanted = lecture_name.strip()
        for key, candidate in content.items():
            if key.strip() == wanted:
                value = candidate
                break

    if value in (None, "", "PASTE_FILE_ID_HERE", "ضع_هنا_file_id"):
        return None
    return value

def catalog_search(query, limit=15):
    q = query.casefold().strip()
    results = []
    for db_key, materials in database.items():
        for mat in materials:
            for lecture, file_id in mat.get("content", {}).items():
                if q in mat["name"].casefold() or q in lecture.casefold():
                    if file_id not in (None, "", "PASTE_FILE_ID_HERE", "ضع_هنا_file_id"):
                        results.append((db_key, mat["name"], lecture))
                        if len(results) >= limit:
                            return results
    return results

def code_snippet(db_key, material, lecture, file_id=None):
    value = file_id or "PASTE_FILE_ID_HERE"
    return f'"{lecture}": "{value}"'

def find_catalog_location(material_name, lecture_name):
    matches = []
    for db_key, materials in database.items():
        for mat in materials:
            if mat["name"] == material_name and lecture_name in mat.get("content", {}):
                matches.append(db_key)
    return matches

# ============================================================
# KEYBOARDS
# ============================================================
def get_years_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("السنة الأولى 1️⃣", "السنة الثانية 2️⃣")
    markup.row("السنة الثالثة 3️⃣", "السنة الرابعة 4️⃣")
    markup.row("السنة الخامسة 5️⃣")
    markup.row("💬 أرسل ملاحظة/استفسار", "📅 برنامج الاسبوع")
    return markup

def get_semesters_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("الفصل الأول 📘", "الفصل الثاني 📙")
    markup.row("🏠 العودة للرئيسية")
    return markup

def get_materials_keyboard(materials_list):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for item in materials_list:
        row.append(KeyboardButton(item["name"]))
        if len(row) == 2:
            markup.row(*row); row = []
    if row: markup.row(*row)
    markup.row("🔙 رجوع للفصول", "🏠 العودة للرئيسية")
    return markup

def get_content_keyboard(content_dict, db_key, material_name, user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for key, value in content_dict.items():
        if key == "📝 دورات سابقة":
            continue
        row.append(KeyboardButton(key))
        if len(row) == 2:
            markup.row(*row); row = []
    if row: markup.row(*row)
    if "📝 دورات سابقة" in content_dict:
        markup.row("📝 دورات سابقة")
    markup.row("🔙 رجوع للمواد", "🏠 العودة للرئيسية")
    return markup

def get_admin_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📊 إحصائيات البوت", "📢 إرسال إذاعة")
    markup.row("📎 استخراج File ID", "🧾 تجهيز سطر ملف")
    markup.row("🗑️ تجهيز حذف من الكود", "📸 برنامج الاسبوع")
    markup.row("📦 نسخة احتياطية", "🚫 حظر / إلغاء حظر مستخدم")
    markup.row("📜 سجل الإدارة", "🏠 العودة للرئيسية")
    return markup

def get_sub_inline_markup():
    markup = InlineKeyboardMarkup()
    clean_username = CHANNEL_USERNAME.lstrip("@")
    markup.add(InlineKeyboardButton("📢 رابط القناة", url=f"https://t.me/{clean_username}"))
    markup.add(InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_subscription"))
    return markup

def check_sub(user_id, force=False):
    now = time.time()
    cached = subscription_cache.get(user_id)
    if cached and not force and cached[1] > now:
        return cached[0]
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        ok = member.status in ["creator", "administrator", "member", "restricted"]
        subscription_cache[user_id] = (ok, now + SUB_CACHE_SECONDS)
        return ok
    except Exception:
        logger.exception("Subscription check failed")
        return False

def require_private(message):
    if message.chat.type != "private":
        try:
            bot.reply_to(message, "ℹ️ استخدم البوت في المحادثة الخاصة فقط.")
        except Exception:
            pass
        return False
    return True

# ============================================================
# PERSISTENT USER FEATURES
# ============================================================
def record_download(user_id, db_key, material, lecture):
    with db_connect() as conn:
        conn.execute("INSERT INTO downloads(user_id,db_key,material_name,lecture_name) VALUES(?,?,?,?)",
                     (user_id, db_key, material, lecture))
        conn.execute("""INSERT INTO recent_views(user_id,db_key,material_name,lecture_name)
                       VALUES(?,?,?,?) ON CONFLICT(user_id,db_key,material_name,lecture_name)
                       DO UPDATE SET viewed_at=CURRENT_TIMESTAMP""", (user_id, db_key, material, lecture))

def toggle_favorite(user_id, db_key, material, lecture):
    with db_connect() as conn:
        exists = conn.execute("SELECT 1 FROM favorites WHERE user_id=? AND db_key=? AND material_name=? AND lecture_name=?",
                              (user_id, db_key, material, lecture)).fetchone()
        if exists:
            conn.execute("DELETE FROM favorites WHERE user_id=? AND db_key=? AND material_name=? AND lecture_name=?",
                         (user_id, db_key, material, lecture))
            return False
        conn.execute("INSERT INTO favorites(user_id,db_key,material_name,lecture_name) VALUES(?,?,?,?)",
                     (user_id, db_key, material, lecture))
        return True

def get_favorites(user_id, limit=30):
    with db_connect() as conn:
        return conn.execute("SELECT db_key,material_name,lecture_name FROM favorites WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
                            (user_id, limit)).fetchall()

def get_recent(user_id, limit=10):
    with db_connect() as conn:
        return conn.execute("SELECT db_key,material_name,lecture_name FROM recent_views WHERE user_id=? ORDER BY viewed_at DESC LIMIT ?",
                            (user_id, limit)).fetchall()

def get_stats():
    with db_connect() as conn:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM users WHERE last_seen >= datetime('now','-7 day')").fetchone()[0]
        downloads = conn.execute("SELECT COUNT(*) FROM downloads").fetchone()[0]
        favs = conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0]
        banned = conn.execute("SELECT COUNT(*) FROM banned_users").fetchone()[0]
        top = conn.execute("""SELECT material_name, lecture_name, COUNT(*) c FROM downloads
                            GROUP BY material_name, lecture_name ORDER BY c DESC LIMIT 5""").fetchall()
        return users, active, downloads, favs, banned, top

# ============================================================
# ADMIN BROADCAST (persistent job + safe pacing)
# ============================================================
def run_broadcast(job_id, admin_id, text, users):
    success = failed = 0
    for uid in users:
        try:
            bot.send_message(uid, text)
            success += 1
        except Exception as exc:
            failed += 1
            msg = str(exc).lower()
            if "blocked" in msg or "forbidden" in msg or "chat not found" in msg:
                mark_user_inactive(uid)
        # Conservative pacing; do not try to bypass Telegram limits.
        time.sleep(0.08)
        if success % 50 == 0 and success:
            with db_connect() as conn:
                conn.execute("UPDATE broadcast_jobs SET success=?, failed=? WHERE id=?", (success, failed, job_id))
    with db_connect() as conn:
        conn.execute("UPDATE broadcast_jobs SET status='completed',success=?,failed=?,finished_at=CURRENT_TIMESTAMP WHERE id=?",
                     (success, failed, job_id))
    audit(admin_id, "broadcast_completed", job_id, f"success={success}, failed={failed}")
    try:
        bot.send_message(admin_id, f"✅ اكتملت الإذاعة\n• الإجمالي: {len(users)}\n• نجاح: {success}\n• فشل: {failed}")
    except Exception:
        pass

def start_broadcast(admin_id, text):
    users = get_all_users()
    with db_connect() as conn:
        conn.execute("INSERT INTO broadcast_jobs(admin_id,content,status,total) VALUES(?,?,?,?)",
                     (admin_id, text, "sending", len(users)))
        job_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    audit(admin_id, "broadcast_started", job_id, f"total={len(users)}")
    threading.Thread(target=run_broadcast, args=(job_id, admin_id, text, users), daemon=True).start()
    return len(users)

# ============================================================
# BACKUP
# ============================================================
BACKUP_TABLES = ["users", "banned_users", "settings", "audit_logs", "downloads",
                 "favorites", "recent_views", "feedback", "broadcast_jobs"]

def send_backup(chat_id):
    # ما في ملف SQLite محلي بعد الانتقال لـ Turso، فنبني نسخة JSON من كل
    # الجداول مباشرة من قاعدة البيانات السحابية ونرسلها كملف.
    try:
        backup = {}
        with db_connect() as conn:
            for table in BACKUP_TABLES:
                cur = conn.execute(f"SELECT * FROM {table}")
                cols = [d[0] for d in cur.description]
                backup[table] = [dict(zip(cols, row)) for row in cur.fetchall()]

        buf = io.BytesIO(json.dumps(backup, ensure_ascii=False, indent=2, default=str).encode("utf-8"))
        buf.name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        bot.send_document(chat_id, buf, caption=f"📦 نسخة احتياطية (JSON)\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\nℹ️ يمكنك أيضاً تنزيل نسخة SQLite كاملة مباشرة من لوحة Turso (زر Export Database).")
        audit(chat_id, "manual_backup")
    except Exception:
        logger.exception("Backup failed")
        bot.send_message(chat_id, "❌ فشل إنشاء النسخة الاحتياطية.")

# ============================================================
# MEDIA HANDLER — FILE ID EXTRACTION, NO DB COURSE MODIFICATION
# ============================================================
@bot.message_handler(content_types=["document", "photo", "video", "audio", "voice"])
def handle_media(message):
    if not require_private(message):
        return
    uid = message.from_user.id
    if not is_admin(uid):
        return
    state = admin_states.get(uid, {})
    file_id = None
    file_type = None
    if message.document:
        file_id, file_type = message.document.file_id, "document"
    elif message.photo:
        file_id, file_type = message.photo[-1].file_id, "photo"
    elif message.video:
        file_id, file_type = message.video.file_id, "video"
    elif message.audio:
        file_id, file_type = message.audio.file_id, "audio"
    elif message.voice:
        file_id, file_type = message.voice.file_id, "voice"
    if not file_id:
        bot.reply_to(message, "❌ لم أستطع استخراج File ID.")
        return
    if state.get("action") == "exam_schedule":
        with db_connect() as conn:
            conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('exam_schedule_file_id',?)", (file_id,))
        clear_admin_state(uid)
        audit(uid, "exam_schedule_updated", "", f"type={file_type}")
        bot.reply_to(message, "✅ تم حفظ ملف برنامج الاسبوع.")
        return
    if state.get("action") == "get_file_id":
        clear_admin_state(uid)
        audit(uid, "file_id_extracted", "", f"type={file_type}")
        bot.reply_to(message, f"🔑 File ID:\n\n<code>{escape(file_id)}</code>\n\n📌 النوع: {file_type}\n\nانسخه وضعه بجانب اسم المحاضرة داخل <code>database</code> في الكود.", parse_mode="HTML")
        return
    # Safe default: any admin media gives the ID, but never edits course data automatically.
    bot.reply_to(message, f"🔑 File ID:\n\n<code>{escape(file_id)}</code>\n\n📌 النوع: {file_type}", parse_mode="HTML")

# ============================================================
# TEXT HANDLER
# ============================================================
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    if not require_private(message):
        return
    uid = message.from_user.id
    chat_id = message.chat.id
    text = (message.text or "").strip()
    first_name = (message.from_user.first_name or "المهندس")[:100]

    if is_user_banned(uid) and not is_admin(uid):
        bot.send_message(chat_id, "🚫 تم حظرك من استخدام هذا البوت.")
        return
    if not rate_allowed(uid) and not is_admin(uid):
        bot.send_message(chat_id, "شوي شوي يا مهندس 👨🏻‍💼 كبسة كبسة ليش مستعجل 🙂")
        return

    add_user(uid, first_name)

    try:
        # ---------------- ADMIN ----------------
        if is_admin(uid):
            state = admin_states.get(uid, {})

            if text == "/admin":
                clear_admin_state(uid)
                bot.send_message(chat_id, "🔧 <b>لوحة تحكم الأدمن</b>", reply_markup=get_admin_keyboard(), parse_mode="HTML")
                return

            if text == "📊 إحصائيات البوت":
                users, active, downloads, favs, banned, top = get_stats()
                msg = [f"📊 <b>إحصائيات البوت</b>", f"👥 المستخدمون: <code>{users}</code>", f"🟢 نشطون خلال 7 أيام: <code>{active}</code>",
                       f"📥 التحميلات: <code>{downloads}</code>", f"⭐ المفضلة: <code>{favs}</code>", f"🚫 المحظورون: <code>{banned}</code>"]
                if top:
                    msg.append("\n🏆 <b>الأكثر طلبًا:</b>")
                    msg += [f"• {escape(m)} — {escape(l)}: {c}" for m,l,c in top]
                bot.send_message(chat_id, "\n".join(msg), parse_mode="HTML")
                return

            if text == "📎 استخراج File ID":
                set_admin_state(uid, action="get_file_id")
                bot.send_message(chat_id, "📎 أرسل الآن الملف/الصورة/الفيديو. سأعطيك File ID فقط ولن أغيّر الكود تلقائيًا.")
                return

            if text == "📸 برنامج الاسبوع":
                set_admin_state(uid, action="exam_schedule")
                bot.send_message(chat_id, "📸 أرسل صورة/ملف برنامج الاسبوع. سيُحفظ في قاعدة الإعدادات.")
                return

            if text == "📢 إرسال إذاعة":
                set_admin_state(uid, action="broadcast")
                bot.send_message(chat_id, "📢 أرسل نص الإذاعة الآن. ستعمل كـ Job مستقل مع تسجيل النجاح والفشل.\n\n❌ للإلغاء: اكتب /cancel")
                return

            if text == "📦 نسخة احتياطية":
                send_backup(chat_id); return

            if text == "🚫 حظر / إلغاء حظر مستخدم":
                set_admin_state(uid, action="ban")
                bot.send_message(chat_id, "أرسل User ID رقمي. إذا كان محظورًا سأفك الحظر، وإلا سأحظره.\n\n❌ /cancel")
                return

            if text == "📜 سجل الإدارة":
                with db_connect() as conn:
                    rows = conn.execute("SELECT action,target,created_at FROM audit_logs ORDER BY id DESC LIMIT 15").fetchall()
                if not rows:
                    bot.send_message(chat_id, "لا يوجد سجل بعد.")
                else:
                    bot.send_message(chat_id, "📜 <b>آخر عمليات الإدارة:</b>\n" + "\n".join(
                        f"• {escape(a)} | {escape(str(t))} | {escape(str(d))}" for a,t,d in rows), parse_mode="HTML")
                return

            if text == "🧾 تجهيز سطر ملف":
                set_admin_state(uid, action="code_line", step="year")
                bot.send_message(chat_id, "أرسل السنة: 1 أو 2 أو 3 أو 4 أو 5.\n❌ /cancel")
                return

            if text == "🗑️ تجهيز حذف من الكود":
                set_admin_state(uid, action="code_delete", step="year")
                bot.send_message(chat_id, "أرسل السنة: 1 أو 2 أو 3 أو 4 أو 5.\n❌ /cancel")
                return

            if text == "🏠 العودة للرئيسية":
                clear_admin_state(uid)
                reset_user_state(chat_id)
                bot.send_message(chat_id, "صلي على النبي ", reply_markup=get_years_keyboard())
                return

            # Persistent admin workflows.
            if state.get("action") in ("broadcast", "ban", "code_line", "code_delete"):
                if text == "/cancel":
                    clear_admin_state(uid); bot.send_message(chat_id, "✅ تم إلغاء العملية."); return

                if state["action"] == "broadcast":
                    clear_admin_state(uid)
                    total = start_broadcast(uid, text)
                    bot.send_message(chat_id, f"🚀 بدأت الإذاعة كعملية مستقلة. عدد المستلمين: <code>{total}</code>", parse_mode="HTML")
                    return

                if state["action"] == "ban":
                    clear_admin_state(uid)
                    try:
                        target = int(text)
                        if target == uid:
                            bot.send_message(chat_id, "❌ لا يمكنك حظر نفسك."); return
                        if is_user_banned(target):
                            unban_user(target); audit(uid,"unban_user",target); bot.send_message(chat_id, "✅ تم إلغاء الحظر.")
                        else:
                            ban_user(target); audit(uid,"ban_user",target); bot.send_message(chat_id, "🚫 تم الحظر.")
                    except ValueError:
                        bot.send_message(chat_id, "❌ User ID يجب أن يكون رقمًا.")
                    return

                action = state["action"]
                step = state.get("step")
                if step == "year":
                    if text not in {"1","2","3","4","5"}:
                        bot.send_message(chat_id, "❌ أرسل رقم السنة من 1 إلى 5."); return
                    set_admin_state(uid, action=action, step="sem", year=int(text))
                    bot.send_message(chat_id, "أرسل الفصل: 1 أو 2")
                    return
                if step == "sem":
                    if text not in {"1","2"}:
                        bot.send_message(chat_id, "❌ أرسل 1 أو 2."); return
                    set_admin_state(uid, action=action, step="material", year=state["year"], sem=int(text))
                    mats = catalog_materials(f"year_{state['year']}_sem_{int(text)}")
                    bot.send_message(chat_id, "اختر/اكتب اسم المادة حرفيًا:\n\n" + "\n".join(f"• {m['name']}" for m in mats))
                    return
                if step == "material":
                    db_key = f"year_{state['year']}_sem_{state['sem']}"
                    mat = find_material(db_key, text)
                    if not mat:
                        bot.send_message(chat_id, "❌ اسم المادة غير موجود. انسخه كما يظهر في القائمة."); return
                    set_admin_state(uid, action=action, step="lecture", year=state["year"], sem=state["sem"], material=text)
                    bot.send_message(chat_id, "أرسل اسم المحاضرة حرفيًا، مثل: محاضرة 1 📄")
                    return
                if step == "lecture":
                    db_key = f"year_{state['year']}_sem_{state['sem']}"
                    mat = find_material(db_key, state["material"])
                    if not mat or text not in mat.get("content", {}):
                        bot.send_message(chat_id, "❌ اسم المحاضرة غير موجود داخل المادة."); return
                    clear_admin_state(uid)
                    if action == "code_line":
                        current = mat["content"].get(text)
                        bot.send_message(chat_id, f"🧾 <b>السطر الجاهز:</b>\n\n<code>{escape(code_snippet(db_key, state['material'], text, current if current not in ('PASTE_FILE_ID_HERE','ضع_هنا_file_id') else None))}</code>\n\n📌 إذا أردت تحديثه: أرسل الملف أولًا عبر 📎 استخراج File ID ثم ضع الـ ID مكان القيمة.", parse_mode="HTML")
                        audit(uid,"code_line_generated",f"{db_key}/{state['material']}/{text}")
                    else:
                        snippet = code_snippet(db_key, state["material"], text, "PASTE_FILE_ID_HERE")
                        bot.send_message(chat_id, f"🗑️ <b>لحذف الملف من الكود:</b> استبدل السطر الحالي بهذا السطر، ثم احذف السطر بالكامل إذا أردت إزالة زر المحاضرة أيضًا:\n\n<code>{escape(snippet)}</code>\n\nثم ارفع التعديل إلى GitHub.", parse_mode="HTML")
                        audit(uid,"delete_snippet_generated",f"{db_key}/{state['material']}/{text}")
                    return

        # ---------------- COMMON / USER ----------------
        if text in ("/cancel",):
            with state_lock:
                user_states.pop(chat_id, None)
            bot.send_message(chat_id, "✅ تم الإلغاء.")
            return

        if text == "/start" or text == "ابدأ من جديد 🔄" or text == "🏠 العودة للرئيسية":
            reset_user_state(chat_id)

            # عند الضغط على Start: افحص الاشتراك أولاً.
            # إذا لم يكن مشتركاً، لا تظهر رسالة الترحيب ولا السنوات.
            if not check_sub(uid, force=True):
                bot.send_message(
                    chat_id,
                    f"⚠️ <b>يجب عليك الاشتراك في القناة أولاً لاستخدام البوت.</b>\n\n"
                    f"📢 القناة: {escape(CHANNEL_USERNAME)}\n\n"
                    f"👇 اشترك بالقناة ثم اضغط «تحقق من الاشتراك»." ,
                    reply_markup=get_sub_inline_markup(),
                    parse_mode="HTML"
                )
                return

            # إذا كان مشتركاً، تظهر رسالة الترحيب الكاملة وتظهر السنوات تحتها.
            welcome = (
                f"👋 <b>أهلاً بك يا {escape(first_name)}!</b>\n"
                f"🎓 مرحباً بك في بوت الاتصالات المساعد.\n"
                f"📚 يمكنك الوصول لجميع المحاضرات والمقررات بسهولة.\n\n"
                f"🎓 صنع هذا البوت @Youssef_Sabra.\n"
                f"👇 <b>يرجى اختيار السنة الدراسية للبدء:</b>"
            )
            bot.send_message(
                chat_id,
                welcome,
                reply_markup=get_years_keyboard(),
                parse_mode="HTML"
            )
            return

        if not check_sub(uid):
            bot.send_message(chat_id, f"⚠️ يجب عليك الاشتراك في القناة أولاً لاستخدام البوت:\n{escape(CHANNEL_USERNAME)}",
                             reply_markup=get_sub_inline_markup(), parse_mode="HTML")
            return

        # Exam schedule
        if text == "📅 برنامج الاسبوع":
            with db_connect() as conn:
                row = conn.execute("SELECT value FROM settings WHERE key='exam_schedule_file_id'").fetchone()
            if not row:
                bot.send_message(chat_id, "ℹ️ لم يتم رفع برنامج الاسببوع بعد.")
            else:
                try:
                    bot.send_photo(chat_id, row[0], caption="📅 برنامج الاسبوع الرسمي:")
                except Exception:
                    bot.send_document(chat_id, row[0], caption="📅 برنامج الاسبوع الرسمي:")
            return

        # Feedback
        if text == "💬 أرسل ملاحظة/استفسار":
            if not feedback_allowed(uid):
                bot.send_message(chat_id, "⏳ وصلت للحد المسموح للملاحظات حاليًا. حاول لاحقًا.")
                return
            set_user_state(chat_id, feedback=True)
            bot.send_message(chat_id, "✍️ اكتب رسالتك الآن. /cancel للإلغاء.")
            return
        state = user_states.get(chat_id, {})
        if state.get("feedback"):
            if text == "/cancel":
                reset_user_state(chat_id); bot.send_message(chat_id,"✅ تم الإلغاء."); return
            reset_user_state(chat_id)
            with db_connect() as conn:
                conn.execute("INSERT INTO feedback(user_id,first_name,message) VALUES(?,?,?)", (uid, first_name, text[:4000]))
                fid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            safe = escape(text[:4000])
            for admin_id in ADMIN_IDS:
                try:
                    bot.send_message(admin_id,
                                     f"📩 <b>ملاحظة #{fid}</b>\nمن: {escape(first_name)}\nID: <code>{uid}</code>\n\n{safe}\n\nللرد: استخدم Reply على هذه الرسالة ثم اكتب الرد.", parse_mode="HTML")
                except Exception:
                    logger.exception("Failed to notify admin %s about feedback", admin_id)
            bot.send_message(chat_id, "✅ تم إرسال ملاحظتك للإدارة. شكرًا لك!")
            return

        # Search
        if text == "🔎 بحث":
            set_user_state(chat_id, search=True)
            bot.send_message(chat_id, "🔎 اكتب اسم المادة أو المحاضرة للبحث. /cancel للإلغاء.")
            return
        if state.get("search"):
            if text == "/cancel":
                reset_user_state(chat_id); bot.send_message(chat_id,"✅ تم الإلغاء."); return
            reset_user_state(chat_id)
            results = catalog_search(text)
            if not results:
                bot.send_message(chat_id, "❌ لم أجد نتائج."); return
            lines = ["🔎 <b>نتائج البحث:</b>"]
            for db_key, mat, lec in results:
                lines.append(f"• <b>{escape(mat)}</b> — {escape(lec)}\n  <code>{db_key}</code>")
            bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")
            return

        # Navigation
        years_map = {"السنة الأولى 1️⃣":1, "السنة الثانية 2️⃣":2, "السنة الثالثة 3️⃣":3, "السنة الرابعة 4️⃣":4, "السنة الخامسة 5️⃣":5}
        if text in years_map:
            set_user_state(chat_id, year=years_map[text], sem=None, material=None)
            bot.send_message(chat_id, "اختر الفصل الدراسي:", reply_markup=get_semesters_keyboard())
            return

        sems_map = {"الفصل الأول 📘":1, "الفصل الثاني 📙":2}
        if text in sems_map:
            year = state.get("year")
            if not year:
                bot.send_message(chat_id, "اختر السنة الدراسية أولاً.", reply_markup=get_years_keyboard()); return
            sem = sems_map[text]
            db_key = f"year_{year}_sem_{sem}"
            set_user_state(chat_id, year=year, sem=sem, material=None)
            bot.send_message(chat_id, f"إليك مواد السنة {year} - الفصل {sem}:", reply_markup=get_materials_keyboard(catalog_materials(db_key)))
            return

        if text == "🔙 رجوع للفصول":
            year = state.get("year")
            if year:
                set_user_state(chat_id, year=year, sem=None, material=None)
                bot.send_message(chat_id, "اختر الفصل الدراسي:", reply_markup=get_semesters_keyboard())
            else:
                bot.send_message(chat_id, "اختر السنة الدراسية:", reply_markup=get_years_keyboard())
            return

        if text == "🔙 رجوع للمواد":
            year, sem = state.get("year"), state.get("sem")
            if year and sem:
                set_user_state(chat_id, year=year, sem=sem, material=None)
                bot.send_message(chat_id, "اختر المادة:", reply_markup=get_materials_keyboard(catalog_materials(f"year_{year}_sem_{sem}")))
            else:
                bot.send_message(chat_id, "اختر السنة الدراسية:", reply_markup=get_years_keyboard())
            return

        year, sem = state.get("year"), state.get("sem")
        if year and sem:
            db_key = f"year_{year}_sem_{sem}"
            mat = find_material(db_key, text)
            if mat:
                set_user_state(chat_id, year=year, sem=sem, material=text)
                bot.send_message(chat_id, f"📚 اختر المحاضرة المتاحة لمادة {escape(text)}:",
                                 reply_markup=get_content_keyboard(mat.get("content", {}), db_key, text, uid), parse_mode="HTML")
                return

       

            material = state.get("material")
            if material:
                mat = find_material(db_key, material)
                if mat:
                    # Telegram قد يعيد النص مع مسافات مختلفة؛ نطابق الاسم بعد strip.
                    content_key = next((k for k in mat.get("content", {}) if k.strip() == text.strip()), None)
                    if content_key is not None:
                        file_id = find_file_id(db_key, material, content_key)
                        if not file_id:
                            bot.send_message(chat_id, "⏳ هذه المحاضرة لم تُرفع بعد.")
                            return
                        try:
                            bot.send_chat_action(chat_id, "upload_document")
                            bot.send_document(
                                chat_id,
                                file_id,
                                caption=f"📌 المادة: {material}\n📑 المحتوى: {content_key}\n\n"
                            )
                            record_download(uid, db_key, material, content_key)
                        except Exception as exc:
                            logger.exception("Document send failed for %s / %s", material, content_key)
                            bot.send_message(chat_id, "✨ بالتوفيق والنجاح!")
                        return

    except Exception:
        logger.exception("Unhandled message error")
        try:
            bot.send_message(chat_id, "⚠️ حدث خطأ مؤقت. حاول مرة أخرى لاحقًا.")
        except Exception:
            pass

# ============================================================
# CALLBACKS — always authorize callback user
# ============================================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        uid = call.from_user.id
        if call.data == "check_subscription":
            ok = check_sub(uid, force=True)
            if ok:
                bot.answer_callback_query(call.id, "✅ تم التحقق من الاشتراك!")
                try: bot.delete_message(call.message.chat.id, call.message.message_id)
                except Exception: pass
                reset_user_state(call.message.chat.id)
                first_name = (call.from_user.first_name or "المهندس")[:100]
                welcome = (
                    f"👋 <b>أهلاً بك يا {escape(first_name)}!</b>\n"
                    f"🎓 مرحباً بك في بوت الاتصالات المساعد.\n"
                    f"📚 يمكنك الوصول لجميع المحاضرات والمقررات بسهولة.\n"
                    f"🎓 صنع هذا البوت @Youssef_Sabra.\n\n"
                    f"👇 <b>يرجى اختيار السنة الدراسية للبدء:</b>"
                )
                bot.send_message(
                    call.message.chat.id,
                    welcome,
                    reply_markup=get_years_keyboard(),
                    parse_mode="HTML"
                )
            else:
                bot.answer_callback_query(call.id, "❌ لم يتم العثور على اشتراكك.", show_alert=True)
        else:
            # Future admin callbacks must pass this gate.
            if not is_admin(uid):
                bot.answer_callback_query(call.id, "❌ غير مصرح.", show_alert=True)
                return
            bot.answer_callback_query(call.id, "تم")
    except Exception:
        logger.exception("Callback error")

# ============================================================
# SAFE STARTUP
# ============================================================
if __name__ == "__main__":
    logger.info("Student bot started")
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10, allowed_updates=None)
        except Exception:
            # لو صار خطأ عابر (متل انقطاع لحظي بالاتصال مع Turso أو تيليجرام)،
            # ما نخلي البرنامج كله يطيح ويستنى Render يلاحظ ويعيد تشغيله (دقائق) -
            # بنسجل الخطأ ونعيد المحاولة مباشرة بعد ثواني قليلة.
            logger.exception("Polling stopped unexpectedly, restarting in 5s")
            time.sleep(5)
