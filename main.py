# -*- coding: utf-8 -*-
"""
بوت طلبات إعادة العملي — النسخة v2
- عدة أدمن يردّون من داخل البوت نفسه (بدون غروب)
- رسوم ثابتة للطلب مهما كان عدد المواد
- تفاصيل الدفع قابلة للنسخ بلمسة واحدة (<code>)
- قاعدة بيانات Turso (HTTP) أو SQLite محلي للتجربة
"""
import os
import io
import re
import csv
import json
import time
import html
import sqlite3
import logging
import threading
from collections import namedtuple
from datetime import datetime, timezone, timedelta

import requests
import telebot
from telebot import util
from telebot.apihelper import ApiTelegramException
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommand, BotCommandScopeChat,
)
from flask import Flask

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("lab-bot")

# ════════════════════════════ الإعدادات ════════════════════════════
TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not TOKEN:
    raise SystemExit("❌ BOT_TOKEN غير موجود في متغيرات البيئة")


def _parse_ids(raw):
    return [int(x) for x in re.split(r"[,\s]+", raw.strip()) if x.strip().lstrip("-").isdigit()]


# قائمة الأدمن: ADMIN_IDS=111,222,333  (يدعم الاسم القديم ADMIN_USER_ID)
ADMIN_IDS = _parse_ids(os.getenv("ADMIN_IDS") or os.getenv("ADMIN_USER_ID") or "")
if not ADMIN_IDS:
    raise SystemExit("❌ ADMIN_IDS غير موجود (مثال: 111111,222222)")

DEFAULT_PRICE = int(os.getenv("PRICE", "100"))        # سعر الطلب الثابت
CURRENCY = os.getenv("CURRENCY", "ل.س")
BANNER = os.getenv("BANNER_FILE_ID") or os.getenv("BANNER_URL") or ""
DEV_TAG = os.getenv("DEV_TAG", "@nono")


def _icon(emoji_id, fallback):
    """إيموجي مخصص (يحتاج Premium لصاحب البوت) إذا حُدد رقمه، وإلا الإيموجي العادي."""
    emoji_id = (emoji_id or "").strip()
    if emoji_id.isdigit():
        return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
    return fallback


SYRIATEL_ICON = _icon(os.getenv("SYRIATEL_EMOJI_ID"), "📱")
SHAM_ICON = _icon(os.getenv("SHAM_EMOJI_ID"), "💠")

# ملصقات تليجرام (file_id). كل واحد اختياري: إذا تُرك فارغاً لا يُرسل شيء.
# طريقة جلب file_id: أرسل أي ملصق للبوت من حساب أدمن فيرد عليك بالـ file_id.
# أو ضع رقم إيموجي مخصص (أرقام فقط) فيظهر كبير ومتحرك كأنه ملصق (يحتاج Premium لصاحب البوت).
STICKERS = {k: os.getenv(f"STICKER_{k}", "").strip()
            for k in ("WELCOME", "SYRIATEL", "SHAM", "RECEIVED", "APPROVED", "REJECTED")}

# ============================================================
# ✨ أيقونات متحركة على الأزرار (يحتاج Premium على حساب صاحب البوت)
# ============================================================
# كيف تجيب الرقم؟ أرسل الإيموجي المتحرك للبوت من حساب أدمن فيرد برقمه، وضعه بين علامتي التنصيص
# (أو من Render بالاسم EMOJI_ + اسم المفتاح بحروف كبيرة، مثل EMOJI_BRANCH_POWER).
# إذا تركته فاضي: يظهر الإيموجي العادي (ولا يتعطل شيء).
EMOJI_IDS = {
    # أيقونة لكل فرع — بنفس ترتيب القائمة: من الاتصالات إلى الطبية
    "branch_communications": "",   # ← قسم هندسة الاتصالات
    "branch_electronics": "",      # ← قسم الطاقة الكهربائية
    "branch_power": "",            # ← قسم القوى
    "branch_computers": "",        # ← قسم الحاسبات والتحكم الآلي
    "branch_mechanical_1": "",     # ← قسم الإنتاج والتصميم
    "branch_mechanical_2": "",     # ← قسم البحرية
    "branch_Mechatronics": "",     # ← قسم الميكاترونيك
    "branch_general_prep": "",     # ← قسم الطبية
    # أزرار المواد
    "selected": "",        # ← علامة ✅ المتحركة لما الطالب يختار مادة (والزر يصير أزرق)
    "continue": "",        # ← زر المتابعة (اختياري)
    "change_branch": "",   # ← زر تغيير الفرع (اختياري)
}
for _k in EMOJI_IDS:
    EMOJI_IDS[_k] = os.environ.get("EMOJI_" + _k.upper(), EMOJI_IDS[_k]).strip()

# مكان الأيقونة: "left" يسار الكلمة ، "right" يمينها (إذا ما تغير المكان عندك جرّب right)
ICON_SIDE = os.environ.get("ICON_SIDE", "left").strip().lower()

# تأثيرات الرسائل (حركة تظهر لما توصل الرسالة بالمحادثة الخاصة): 🎉 قصاصات ، 👍
# اتركها فاضية من Render لتعطيلها. إذا ما اشتغل التأثير يُرسل الرسالة عادي.
EFFECTS = {
    "approved": os.environ.get("EFFECT_APPROVED", "5046509860389126442").strip(),
    "received": os.environ.get("EFFECT_RECEIVED", "5107584321108051014").strip(),
}
for _k, _v in EFFECTS.items():          # للتعطيل من Render: EFFECT_APPROVED=off
    if _v.lower() in ("off", "no", "none", "0", "false"):
        EFFECTS[_k] = ""

# طرق الدفع (تظهر قابلة للنسخ). اترك المتغير فارغاً لإخفاء الطريقة.
PAY_METHODS = [
    (label, val.strip())
    for label, val in (
        (f"{SYRIATEL_ICON} سيرتيل كاش", os.getenv("SYRIATEL_CASH", "")),
        (f"{SHAM_ICON} شام كاش", os.getenv("SHAM_CASH", "")),
    )
    if val.strip()
]
if not PAY_METHODS:
    raise SystemExit("❌ ضع SYRIATEL_CASH و/أو SHAM_CASH في متغيرات البيئة")

BRANCHES = {
    "communications": {
        "name": "قسم هندسة الاتصالات 📡",
        "courses": ["ري1 - R1", "فيزيا", "خوارزميات",
                    "ري4 - R4", "الكترون", "OOP", "دارات", "رقمية", "منطقية", "بنية حاسب" , "قياسات", "خطية لا خطية",
                    "هوائيات", "مقاسم", "تلفزيون", "نمذجة", "خليوي2", "تصميم شبكات", "دارات مكروية" , "الشبكات" ],
    },
    "electronics": {
        "name": "قسم الطاقة الكهربائية ⚡",
        "courses": ["ميكانيك هندسي", "فيزيا١", "مدخل إلى الحاسب","ر١", "رسم هندسي", "ورش",
    "ر٣", "هيدروليك (أسس الآلات عملية)", "دارات","مقاومة مواد", "برمجة", "انظم قدرة١","احتمالات", "الآلات", "اقتصاد هندسي",
    "اسس ألكترون", "الكترونيات قدرة ٢", "توتر ٢",
    "تحكم الي", "الآلات المتواقتة", "توليد طاقة كهربائية",
    "حماية نظم ١", "قيادة كهربائية", "تصميم الآلات الكهربائية",
    "تحليل شبكات كهربائية"],
    },
    "power": {
        "name": "قسم القوى 🔌",
        "courses":[
    "رياضيات ١", "ورشة تقنية", "فيزياء ١", "هندسة وصفية", "كيمياء صناعية", "فيزياء ٢",
    "رياضيات ٢", "مدخل إلى الحاسب", "رسم هندسي ١", "أوتوكاد", "أسس كهربا", "رياضيات ٣",
    "رسم هندسي ٢", "ميكانيك هندسي ١", "علم المواد", "برمجة", "طرائق تصنيع ١", "ميكانيك هندسي ٢",
    "ترموديناميك ١", "رياضيات ٤", "مقاومة مواد ١", "ترموديناميك ٢", "ميكانيك سوائل", "طرائق تصنيع ٢",
    "مقاومة مواد ٢", "علم معاون", "ورشة (ثالثة)", "إلكترونيات", "قياسات", "وقود وزيوت",
    "ميكانيك سوائل ٢", "نظرية آلات", "تصميم آلات", "محركات", "مراجل بخارية", "انتقال حرارة",
    "اهتزازات", "آلات مائية", "تصميم بمعونة الحاسب", "احتراق داخلي", "تصميم ثلاث", "ديناميك غازات",
    "تجهيزات كهربائية", "آلات الجريان", "ديناميك آلات", "تصميم محركات احتراق", "محطات توليد طاقة",
    "آلات حرارية", "تدفئة وتكييف", "تبريد", "طاقات متجددة", "تحكم", "نمذجة"],
    },
    "computers": {
        "name": "قسم الحاسبات والتحكم الآلي 💻",
        "courses": [
    "رياضيات", "بحوث عمليات", "اسس هندسة الكترونية",
    "برمجة", "برمجة ٢ تحليل نظم حاسوبية", "بينة حاسب ١",
    "نظم اتصالات رقمية", "قواعد بيانات", "تحكم الي ١",
    "رسم وتصميم بمعونة الحاسب", "تحليل ومعالجة اشارة", "شبكات",
    "حساسات", "تحكم ٢", "شبكات ١",
    "شبكات عصبونية", "تصميم انظمة المعالجات دقيقة", "معالجة الصور",
    "برمجة غرضية التوجه", "امن المعلومات", "النظم والمعالجات التغرعية",
    "فيزيا", "مهارات الحاسوب"],
    },
    "mechanical_1": {
        "name": "قسم الإنتاج والتصميم ⚙️",
        "courses": [
    "ورشات تخصصية", "فيزياء1", "كيمياء صناعية",
    "رياضيات 1", "هندسة وصفية", "رياضيات 3",
    "رسم هندسي 2", "برمجة 1", "ترموديناميك",
    "اسس هندسة كهربائية", "ميكانيك 2", "قياسات ميكانيكية",
    "محطات توليد الطاقة", "ميكانيك الموائع", "علم المعادن",
    "طرائق تصنيع 2", "مقاومة مواد 2", "تصميم آلات 2",
    "ديناميك الات و اهتزازات", "الات نقل", "خطط الإنتاج",
    "التشكيل و الاته", "تصميم بمساعدة الحاسوب", "نظرية القطع",
    "تصميم آلات التشغيل", "دلائل و مثبتات", "اقتصاد صناعي",
    "امن صناعي"],
    },
    "mechanical_2": {
        "name": "قسم البحرية 🚢",
         "courses": [
    "فيزيا ١", "عملي كيميا", "هندسة وصفية",
    "ر١", "علم المواد", "ميكانيك هندسي",
    "ر٣", "اسس هندسة كهربائية", "هندسة انتاج",
    "رسم هندسي", "تحليل انشائي للسفن", "اتزان سفن",
    "ميكانيك سوائل", "قياسات مسائل", "ترموديناميك",
    "نظرية الات", "ديناميك الالات واهتزازات", "محطات قدرة",
    "قيادة وحماية كهربائية", "ديناميك الات", "هيدرو ديناميك السفن",
    "انتقال حرارة", "محطات قدرة", "اجهزة مساعدى في السفن",
    "تصميم انشائي للسفن", "تكنلوجيا بناء السفن", "تصميم السفن",
    "اتصالات وانظمة الملاحة البحرية"],
    },
    "Mechatronics": {
        "name": "قسم الميكاترونيك 🤖",
        "courses": [
    "رسم هندسي", "فيزياء ١", "رياضيات ١",
    "ماتلاب","ترموديناميك",
    "اسس هندسة كهربائية", "مدخل حاسب", "اسس هندسة إلكترونية ٢",
    "ديناميك إلكترونيات تضبيط تجريبية ١", "مقاومة مواد وخواصها", "رياضيات ٣",
    "ميكانيك هندسي", "ديناميك آلات", "تصميم آلات",
    "آلات ١", "إلكترونيات صناعية", "إلكترونيات رقمية",
    "تحكم آلي ١", "تطبيقات ميكاترونيك ١", "نظم اتصالات ١",
    "PLC", "محاكاة و نمذجة", "تحكم باستخدام الحاسب",
    "معالجة صورة", "تطبيقات هيكل", "نظم الزمن الحقيقي",
    "تجهيزات كهرابائية"
],
    },
    "general_prep": {
        "name": "قسم الطبية 📚",
         "courses": [
    "رسم هندسي", "كيميا حيوية", "ر١",
    "فيزيا ١", "مدخل الى الحسوب", "برمجة ٢",
    "ر٣", "علم المواد وخواصها", "ميكانيك سوائل حيوية",
    "ترموديناميك", "مواد طبية", "عناصر الات",
    "حقول كهرطيسية", "هندسة الكترونية", "قياسات واجهزة القياس",
    "اطراف صناعية", "الكترونيات طبية", "تحكم الي مسائل +مخبر برمجيات طبية",
    "معالجة اشارة", "هندسة مشافي", "اعضاء صناعية",
    "معالجة صورة ٢", "استراتيجيات صيانة", "اجهزة طبية"],
    },
}

REJECT_REASONS = [
    "رقم العملية / الإيصال غير صحيح",
    "المبلغ غير مطابق",
    "بيانات الطالب غير مكتملة",
]

ACTIVE = ("pending", "awaiting_proof", "rejecting")
SY_TZ = timezone(timedelta(hours=3))


def now_str():
    return datetime.now(SY_TZ).strftime("%Y-%m-%d %H:%M")


esc = html.escape

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def norm_digits(s):
    return (s or "").translate(_AR_DIGITS)


# ════════════════════════════ قاعدة البيانات ════════════════════════════
Result = namedtuple("Result", "rows rowcount last_id")


class DB:
    """Turso عبر HTTP (بدون مكتبات إضافية) أو SQLite محلي إذا لم يُضبط Turso."""

    def __init__(self):
        url = os.getenv("TURSO_DATABASE_URL", "").strip()
        self.token = os.getenv("TURSO_AUTH_TOKEN", "").strip()
        if url:
            self.mode = "turso"
            self.url = url.replace("libsql://", "https://").rstrip("/") + "/v2/pipeline"
            self.http = requests.Session()
            log.info("DB: Turso")
        else:
            self.mode = "sqlite"
            self.lock = threading.Lock()
            self.conn = sqlite3.connect(os.getenv("SQLITE_PATH", "bot.db"), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            log.warning("DB: SQLite محلي (على Render يُمسح مع كل نشر — استعمل Turso)")

    def execute(self, sql, params=()):
        return self._sqlite(sql, params) if self.mode == "sqlite" else self._turso(sql, params)

    def _sqlite(self, sql, params):
        with self.lock:
            cur = self.conn.execute(sql, tuple(params))
            rows = [dict(r) for r in cur.fetchall()] if cur.description else []
            self.conn.commit()
            return Result(rows, cur.rowcount, cur.lastrowid)

    @staticmethod
    def _enc(v):
        if v is None:
            return {"type": "null"}
        if isinstance(v, bool):
            v = int(v)
        if isinstance(v, int):
            return {"type": "integer", "value": str(v)}
        if isinstance(v, float):
            return {"type": "float", "value": v}
        return {"type": "text", "value": str(v)}

    @staticmethod
    def _dec(cell):
        t = cell.get("type")
        if t == "null":
            return None
        v = cell.get("value")
        if t == "integer":
            return int(v)
        if t == "float":
            return float(v)
        return v

    def _turso(self, sql, params):
        payload = {"requests": [
            {"type": "execute", "stmt": {"sql": sql, "args": [self._enc(p) for p in params]}},
            {"type": "close"},
        ]}
        headers = {"Authorization": f"Bearer {self.token}"}
        last = None
        for attempt in range(3):
            try:
                r = self.http.post(self.url, json=payload, headers=headers, timeout=15)
                r.raise_for_status()
                break
            except requests.exceptions.ConnectionError as e:   # الطلب لم يصل → آمن للإعادة
                last = e
                time.sleep(0.6 * (attempt + 1))
        else:
            raise last
        res = r.json()["results"][0]
        if res["type"] == "error":
            raise RuntimeError(res["error"].get("message", "turso error"))
        result = res["response"]["result"]
        cols = [c["name"] for c in result.get("cols", [])]
        rows = [{c: self._dec(cell) for c, cell in zip(cols, row)} for row in result.get("rows", [])]
        lid = result.get("last_insert_rowid")
        return Result(rows, result.get("affected_row_count", 0), int(lid) if lid is not None else None)


db = DB()

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY, username TEXT, first_seen TEXT)""",
    """CREATE TABLE IF NOT EXISTS sessions(
        key TEXT PRIMARY KEY, data TEXT)""",
    """CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY, value TEXT)""",
    """CREATE TABLE IF NOT EXISTS requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, username TEXT, student_info TEXT,
        branch TEXT, courses TEXT, price INTEGER,
        proof_text TEXT, proof_ref TEXT, proof_photo TEXT, proof_unique TEXT,
        status TEXT, handled_by INTEGER, handled_name TEXT,
        reject_reason TEXT, created_at TEXT, decided_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS admin_msgs(
        request_id INTEGER, admin_id INTEGER, message_id INTEGER, is_photo INTEGER,
        PRIMARY KEY(request_id, admin_id))""",
    "CREATE INDEX IF NOT EXISTS idx_req_user ON requests(user_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_req_ref ON requests(proof_ref)",
    "CREATE INDEX IF NOT EXISTS idx_req_uniq ON requests(proof_unique)",
]


def init_db():
    for s in SCHEMA:
        db.execute(s)


# ── الإعدادات (السعر / فتح وإغلاق التسجيل) ──
def get_setting(key, default=None):
    rows = db.execute("SELECT value FROM settings WHERE key=?", (key,)).rows
    return rows[0]["value"] if rows else default


def set_setting(key, value):
    db.execute("INSERT INTO settings(key,value) VALUES(?,?) "
               "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


def get_price():
    try:
        return int(get_setting("price", DEFAULT_PRICE))
    except (TypeError, ValueError):
        return DEFAULT_PRICE


def is_open():
    return get_setting("open", "1") == "1"


# ── الجلسات (محفوظة بالقاعدة + كاش بالذاكرة) ──
_cache = {}
_cache_lock = threading.Lock()


def get_state(key):
    with _cache_lock:
        if key in _cache:
            return _cache[key]
    rows = db.execute("SELECT data FROM sessions WHERE key=?", (key,)).rows
    data = json.loads(rows[0]["data"]) if rows else None
    with _cache_lock:
        _cache[key] = data
    return data


def set_state(key, data):
    with _cache_lock:
        _cache[key] = data
    db.execute("INSERT INTO sessions(key,data) VALUES(?,?) "
               "ON CONFLICT(key) DO UPDATE SET data=excluded.data",
               (key, json.dumps(data, ensure_ascii=False)))


def clear_state(key):
    with _cache_lock:
        _cache[key] = None
    db.execute("DELETE FROM sessions WHERE key=?", (key,))


# ════════════════════════════ البوت ════════════════════════════
class _Handler(telebot.ExceptionHandler):
    def handle(self, exception):
        log.exception("handler error: %s", exception)
        return True


bot = telebot.TeleBot(TOKEN, parse_mode=None, exception_handler=_Handler())


def is_admin(uid):
    return uid in ADMIN_IDS


_CUSTOM_EMOJI_RE = re.compile(r'<tg-emoji emoji-id="\d+">(.*?)</tg-emoji>', re.S)


def react(m, emoji="👍"):
    """ريأكشن من البوت على رسالة الطالب (يتجاهل الخطأ إذا نسخة المكتبة قديمة)."""
    try:
        from telebot.types import ReactionTypeEmoji
        bot.set_message_reaction(m.chat.id, m.message_id, [ReactionTypeEmoji(emoji)])
    except Exception as e:
        log.info("reaction skipped: %s", e)


def safe_send(chat_id, text, effect=None, **kw):
    mode = kw.pop("parse_mode", "HTML")
    if effect:
        try:
            bot.send_message(chat_id, text, parse_mode=mode, message_effect_id=effect, **kw)
            return True
        except Exception as e:
            log.info("message effect skipped (%s)", e)
    try:
        bot.send_message(chat_id, text, parse_mode=mode, **kw)
        return True
    except Exception as e:
        plain = _CUSTOM_EMOJI_RE.sub(r"\1", text)
        if plain != text:          # الإيموجي المخصص مرفوض؟ أعد الإرسال بالإيموجي العادي
            log.warning("custom emoji refused (%s) → fallback to plain emoji", e)
            try:
                bot.send_message(chat_id, plain, parse_mode=mode, **kw)
                return True
            except Exception as e2:
                e = e2
        log.warning("send_message to %s failed: %s", chat_id, e)
        return False


_STICKER_FALLBACK = {"WELCOME": "👋", "SYRIATEL": "📱", "SHAM": "💠",
                     "RECEIVED": "✅", "APPROVED": "🎉", "REJECTED": "⚠️"}


def send_sticker_safe(chat_id, key):
    """يرسل ملصق أو إيموجي مخصص كبير (حسب القيمة بالمتغير) ولا يعطّل البوت إذا فشل.
    - قيمة كلها أرقام  → رقم إيموجي مخصص: يُرسل برسالة لوحده فيظهر كبير ومتحرك.
    - غير ذلك          → file_id لملصق عادي."""
    fid = STICKERS.get(key)
    if not fid:
        return False
    if fid.isdigit():
        return safe_send(chat_id, f'<tg-emoji emoji-id="{fid}">{_STICKER_FALLBACK.get(key, "⭐")}</tg-emoji>')
    try:
        bot.send_sticker(chat_id, fid)
        return True
    except Exception as e:
        log.warning("send_sticker %s to %s failed: %s", key, chat_id, e)
        return False


def send_payment_info(chat_id, prefix=""):
    """ملصق سيرتيل + ملصق شام (لكل طريقة مفعّلة) ثم رسالة الدفع القابلة للنسخ."""
    if os.getenv("SYRIATEL_CASH", "").strip():
        send_sticker_safe(chat_id, "SYRIATEL")
    if os.getenv("SHAM_CASH", "").strip():
        send_sticker_safe(chat_id, "SHAM")
    safe_send(chat_id, prefix + payment_text())


def safe_answer(call, text=None, alert=False):
    try:
        bot.answer_callback_query(call.id, text, show_alert=alert)
    except Exception:
        pass


def edit_call(call, text, markup=None, raise_errors=False):
    """تعديل رسالة الكول باك (صورة → caption، نص → text)."""
    m = call.message
    try:
        if m.content_type == "photo":
            bot.edit_message_caption(caption=text, chat_id=m.chat.id, message_id=m.message_id,
                                     parse_mode="HTML", reply_markup=markup)
        else:
            bot.edit_message_text(text=text, chat_id=m.chat.id, message_id=m.message_id,
                                  parse_mode="HTML", reply_markup=markup)
    except ApiTelegramException as e:
        if "not modified" in str(e):
            return
        if raise_errors:
            raise
        log.warning("edit_call failed: %s", e)


# ─────────────── أزرار ملونة + أيقونات متحركة (مع تراجع تلقائي لو رفضها تليجرام) ───────────────
_LRM = "\u200e"
_ui = {"level": 2, "since": 0.0}   # 2 = أيقونات+ألوان ، 1 = ألوان فقط ، 0 = عادي
_BENIGN = ("not modified", "message to edit not found", "message can't be edited",
           "query is too old", "chat not found", "blocked")


def ui_level():
    if _ui["level"] < 2 and time.time() - _ui["since"] > 600:   # بعد 10 دقايق نجرّب من جديد
        _ui["level"] = 2
    return _ui["level"]


def tg_markup_call(fn, build):
    """build(lvl) -> payload ، fn(payload) ينفّذ نداء تليجرام. إذا رفض الأيقونات/الألوان ننزل مستوى الواجهة."""
    last = None
    for _ in range(3):
        lvl = ui_level()
        try:
            return fn(build(lvl))
        except ApiTelegramException as e:
            msg = str(e).lower()
            if "not modified" in msg:
                return None
            if lvl == 0 or any(b in msg for b in _BENIGN):
                raise
            log.warning("UI level %s refused (%s) → degrade", lvl, e)
            _ui["level"] = lvl - 1
            _ui["since"] = time.time()
            last = e
    raise last


def show_view(call, build):
    """تعديل رسالة الكول باك بواجهة build(lvl) -> (text, markup)."""
    try:
        tg_markup_call(lambda v: edit_call(call, v[0], v[1], raise_errors=True), build)
    except ApiTelegramException as e:
        log.warning("show_view failed: %s", e)


class StyledInlineButton(InlineKeyboardButton):
    """زر Inline + أيقونة متحركة + لون (Bot API 9.4) — يشتغل حتى لو مكتبة تليجرام قديمة."""

    def __init__(self, text, callback_data=None, icon_custom_emoji_id=None, style=None):
        super().__init__(text, callback_data=callback_data)
        self._icon_id = icon_custom_emoji_id
        self._style = style

    def to_dict(self):
        d = super().to_dict()
        if self._icon_id:
            d["icon_custom_emoji_id"] = str(self._icon_id)
        if self._style:
            d["style"] = self._style
        return d


def ibtn(plain, fallback, cb, icon_key=None, style=None, lvl=2):
    """مع أيقونة: نص بسيط + أيقونة متحركة. بدونها: النص القديم بإيموجيه العادي. اللون يضل إذا lvl>=1."""
    eid = EMOJI_IDS.get(icon_key, "") if icon_key else ""
    if lvl >= 2 and eid.isdigit():
        text = (_LRM + plain) if ICON_SIDE == "left" else plain
        return StyledInlineButton(text, callback_data=cb, icon_custom_emoji_id=eid, style=style)
    return StyledInlineButton(fallback, callback_data=cb, style=style if lvl >= 1 else None)


def branch_plain(name):
    """اسم الفرع بدون إيموجيه الأخير: «قسم القوى 🔌» → «قسم القوى»."""
    head, _, tail = name.rpartition(" ")
    return head if head and not re.search(r"\w", tail) else name


def branch_title_html(key, lvl=2):
    name = BRANCHES[key]["name"]
    eid = EMOJI_IDS.get(f"branch_{key}", "")
    if lvl >= 2 and eid.isdigit():
        emo = name.rsplit(" ", 1)[-1]
        return f'{esc(branch_plain(name))} <tg-emoji emoji-id="{eid}">{emo}</tg-emoji>'
    return esc(name)


def active_request(uid):
    rows = db.execute(
        "SELECT id,status FROM requests WHERE user_id=? AND status IN ('pending','awaiting_proof','rejecting') "
        "ORDER BY id DESC LIMIT 1", (uid,)).rows
    return rows[0] if rows else None


# ─────────────── واجهة الطالب ───────────────
def branches_markup(lvl=None):
    lvl = ui_level() if lvl is None else lvl
    mk = InlineKeyboardMarkup(row_width=1)
    for k, b in BRANCHES.items():          # من الاتصالات إلى الطبية، لكل فرع أيقونته
        mk.add(ibtn(branch_plain(b["name"]), b["name"], f"b_{k}", icon_key=f"branch_{k}", lvl=lvl))
    return mk


def courses_markup(branch_key, selected, lvl=None):
    lvl = ui_level() if lvl is None else lvl
    mk = InlineKeyboardMarkup(row_width=2)
    btns = []
    for i, c in enumerate(BRANCHES[branch_key]["courses"]):
        if i in selected:   # المختارة: أيقونة ✅ متحركة + لون أزرق
            btns.append(ibtn(c, f"✅ {c}", f"c_{i}", icon_key="selected", style="primary", lvl=lvl))
        else:
            btns.append(StyledInlineButton(f"⬜ {c}", callback_data=f"c_{i}"))
    for j in range(0, len(btns), 2):        # كل مادتين جنب بعض
        mk.row(*btns[j:j + 2])
    n = len(selected)
    cont = f"متابعة ({n})" if n else "متابعة"
    mk.row(ibtn(cont, f"➡️ {cont}", "done", icon_key="continue", style="success", lvl=lvl))        # أخضر ولحاله
    mk.row(ibtn("تغيير الفرع", "🔙 تغيير الفرع", "chg", icon_key="change_branch", style="danger", lvl=lvl))  # أحمر ولحاله
    return mk


def courses_text(branch_key, lvl=None):
    lvl = ui_level() if lvl is None else lvl
    return (f"لقد اخترت: <b>{branch_title_html(branch_key, lvl)}</b>\n\n"
            "اضغط على المواد المطلوبة (اضغط مرة ثانية لإلغاء الاختيار):\n"
            f"💰 رسوم الطلب ثابتة: <b>{get_price():,} {esc(CURRENCY)}</b> مهما كان عدد المواد.")


def courses_view(branch_key, selected, lvl):
    return courses_text(branch_key, lvl), courses_markup(branch_key, selected, lvl)


def welcome_text():
    return ("🎓 <b>أهلاً بك في بوت طلبات إعادة العملي الرسمية</b>\n"
            "🏛️ جامعة اللاذقية - كلية الهمك\n\n"
            "📌 اختر فرعك الدراسي لبدء تقديم الطلب:\n"
            "<i>(للإلغاء في أي وقت اكتب /cancel)</i>")


def payment_text():
    lines = [
        f"💳 <b>رسوم الطلب بالعملة الجديدة:</b> <code>{get_price()}</code> {esc(CURRENCY)}",
        "<i>(ثابتة سواء كان طلبك لمادة واحدة أو عدة مواد)</i>",
        "",
        "حوّل المبلغ بإحدى الطرق التالية — <b>اضغط على الرقم لنسخه</b> 👇",
        "",
    ]
    for label, val in PAY_METHODS:
        lines.append(f"{label}:")
        lines.append(f"<code>{esc(val)}</code>")
        lines.append("")
    lines.append("بعد التحويل أرسل هنا <b>صورة الإيصال</b> أو <b>رقم عملية التحويل</b>.")
    return "\n".join(lines)


def valid_info(text):
    t = norm_digits(text).strip()
    if not (8 <= len(t) <= 150):
        return False
    words = re.findall(r"[^\W\d_]+", t)
    digits = re.findall(r"\d", t)
    return len(words) >= 2 and len(digits) >= 3


STATUS_STUDENT = {
    "pending": "⏳ قيد المراجعة",
    "awaiting_proof": "⏳ قيد المعالجة",
    "rejecting": "⏳ قيد المعالجة",
    "approved": "✅ مقبول",
    "rejected": "❌ مرفوض",
}


# ─────────────── رسائل الأدمن ───────────────
def status_line(r):
    s = r["status"]
    n = esc(r.get("handled_name") or "")
    if s == "pending":
        return "🟡 <b>الحالة:</b> بانتظار المراجعة"
    if s == "awaiting_proof":
        return f"🟠 <b>الحالة:</b> قيد المعالجة بواسطة {n} (بانتظار صورة الإثبات)"
    if s == "rejecting":
        return f"🟠 <b>الحالة:</b> {n} يختار سبب الرفض"
    if s == "approved":
        return f"🟢 <b>الحالة:</b> تم القبول بواسطة {n}"
    return f"🔴 <b>الحالة:</b> مرفوض بواسطة {n}\n📝 السبب: {esc(r.get('reject_reason') or '-')}"


def admin_text(r):
    uname = f"@{esc(r['username'])}" if r.get("username") else "لا يوجد"
    proof = f"<code>{esc(r['proof_text'])}</code>" if r.get("proof_text") else "صورة الإيصال مرفقة 📎"
    if r.get("proof_photo") and r.get("proof_text"):
        proof = f"صورة مرفقة 📎 + <code>{esc(r['proof_text'])}</code>"
    return (
        f"🚨 <b>طلب إعادة عملي #{r['id']}</b>\n\n"
        f"👤 <b>الطالب:</b> {esc(r['student_info'])}\n"
        f"🌐 <b>اليوزر:</b> {uname}\n"
        f"🆔 <code>{r['user_id']}</code> — <a href=\"tg://user?id={r['user_id']}\">فتح المحادثة</a>\n"
        f"🏢 <b>الفرع:</b> {esc(r['branch'])}\n"
        f"📚 <b>المواد:</b> {esc(r['courses'])}\n"
        f"💰 <b>الرسوم:</b> {r['price']:,} {esc(CURRENCY)}\n"
        f"💬 <b>تفاصيل الدفع:</b> {proof}\n"
        f"🕒 {esc(r['created_at'])}\n\n"
        f"{status_line(r)}"
    )


def admin_markup(r, admin_id):
    rid, st = r["id"], r["status"]
    mk = InlineKeyboardMarkup(row_width=2)
    if st == "pending":
        mk.add(InlineKeyboardButton("✅ قبول", callback_data=f"ok_{rid}"),
               InlineKeyboardButton("❌ رفض", callback_data=f"no_{rid}"))
    elif st == "rejecting" and r.get("handled_by") == admin_id:
        for i, reason in enumerate(REJECT_REASONS):
            mk.add(InlineKeyboardButton(reason, callback_data=f"rr_{rid}_{i}"))
        mk.add(InlineKeyboardButton("✍️ سبب آخر (اكتبه)", callback_data=f"rr_{rid}_c"))
        mk.add(InlineKeyboardButton("🔙 رجوع", callback_data=f"bk_{rid}"))
    return mk if mk.keyboard else None


def get_request(rid):
    rows = db.execute("SELECT * FROM requests WHERE id=?", (rid,)).rows
    return rows[0] if rows else None


def refresh_admin_messages(rid):
    """يحدّث رسالة الطلب عند كل الأدمن (الحالة + الأزرار)."""
    r = get_request(rid)
    if not r:
        return
    text = admin_text(r)
    for m in db.execute("SELECT * FROM admin_msgs WHERE request_id=?", (rid,)).rows:
        try:
            if m["is_photo"]:
                bot.edit_message_caption(caption=text, chat_id=m["admin_id"], message_id=m["message_id"],
                                         parse_mode="HTML", reply_markup=admin_markup(r, m["admin_id"]))
            else:
                bot.edit_message_text(text=text, chat_id=m["admin_id"], message_id=m["message_id"],
                                      parse_mode="HTML", reply_markup=admin_markup(r, m["admin_id"]))
        except ApiTelegramException as e:
            if "not modified" not in str(e):
                log.warning("refresh admin msg failed: %s", e)
        except Exception as e:
            log.warning("refresh admin msg failed: %s", e)


def dispatch_to_admins(r):
    """يرسل الطلب لكل الأدمن. يرجع عدد من وصلهم الطلب."""
    ok = 0
    text = admin_text(r)
    for aid in ADMIN_IDS:
        try:
            mk = admin_markup(r, aid)
            if r.get("proof_photo"):
                msg = bot.send_photo(aid, r["proof_photo"], caption=text, parse_mode="HTML", reply_markup=mk)
                is_photo = 1
            else:
                msg = bot.send_message(aid, text, parse_mode="HTML", reply_markup=mk)
                is_photo = 0
            db.execute("INSERT OR REPLACE INTO admin_msgs(request_id,admin_id,message_id,is_photo) VALUES(?,?,?,?)",
                       (r["id"], aid, msg.message_id, is_photo))
            ok += 1
        except Exception as e:
            log.warning("dispatch to admin %s failed: %s", aid, e)
    return ok


# ════════════════════════════ أوامر الطالب ════════════════════════════
@bot.message_handler(commands=["start"], chat_types=["private"])
def cmd_start(m):
    uid = m.from_user.id
    db.execute("INSERT OR IGNORE INTO users(user_id,username,first_seen) VALUES(?,?,?)",
               (uid, m.from_user.username, now_str()))
    if not is_open():
        safe_send(m.chat.id, "⛔ باب تقديم الطلبات مغلق حالياً. سيتم الإعلان عن فتحه لاحقاً.")
        return
    act = active_request(uid)
    if act:
        safe_send(m.chat.id, f"⏳ لديك طلب قيد المراجعة <b>#{act['id']}</b>.\n"
                             "انتظر النتيجة أو تابع حالته عبر /status")
        return
    set_state(f"u:{uid}", {"step": "branch"})
    send_sticker_safe(m.chat.id, "WELCOME")

    def _send_menu(view):
        text, mk = view
        try:
            if not BANNER:
                raise ValueError("no banner")
            bot.send_photo(m.chat.id, BANNER, caption=text, parse_mode="HTML", reply_markup=mk)
            return
        except Exception:
            pass
        bot.send_message(m.chat.id, text, parse_mode="HTML", reply_markup=mk)

    try:
        tg_markup_call(_send_menu, lambda lvl: (welcome_text(), branches_markup(lvl)))
    except ApiTelegramException as e:
        log.warning("send branch menu failed: %s", e)


@bot.message_handler(commands=["cancel"], chat_types=["private"])
def cmd_cancel(m):
    uid = m.from_user.id
    clear_state(f"u:{uid}")
    if is_admin(uid):
        st = get_state(f"a:{uid}")
        if st:
            r = get_request(st["req"])
            if r and r["handled_by"] == uid and r["status"] in ("awaiting_proof", "rejecting"):
                db.execute("UPDATE requests SET status='pending', handled_by=NULL, handled_name=NULL WHERE id=?",
                           (r["id"],))
                refresh_admin_messages(r["id"])
            clear_state(f"a:{uid}")
    safe_send(m.chat.id, "❌ تم إلغاء العملية الحالية. للبدء من جديد اكتب /start")


@bot.message_handler(commands=["status"], chat_types=["private"])
def cmd_status(m):
    rows = db.execute("SELECT id,status,reject_reason,created_at FROM requests "
                      "WHERE user_id=? ORDER BY id DESC LIMIT 5", (m.from_user.id,)).rows
    if not rows:
        safe_send(m.chat.id, "ما عندك طلبات سابقة. اكتب /start لتقديم طلب.")
        return
    lines = ["📋 <b>آخر طلباتك:</b>\n"]
    for r in rows:
        line = f"#{r['id']} — {STATUS_STUDENT.get(r['status'], r['status'])} — {esc(r['created_at'])}"
        if r["status"] == "rejected" and r["reject_reason"]:
            line += f"\n   📝 {esc(r['reject_reason'])}"
        lines.append(line)
    safe_send(m.chat.id, "\n".join(lines))


@bot.message_handler(commands=["pay"], chat_types=["private"])
def cmd_pay(m):
    send_payment_info(m.chat.id)


@bot.message_handler(commands=["help"], chat_types=["private"])
def cmd_help(m):
    safe_send(m.chat.id, "/start — تقديم طلب جديد\n/status — حالة طلباتي\n"
                         "/pay — أرقام الدفع\n/cancel — إلغاء العملية الحالية")


# ════════════════════════════ كول باك الطالب ════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data.startswith("b_"))
def cb_branch(call):
    uid = call.from_user.id
    key = call.data[2:]                      # ← إصلاح باك الفروع (mechanical_1 ...)
    st = get_state(f"u:{uid}")
    if key not in BRANCHES or not st:
        safe_answer(call, "انتهت الجلسة، اكتب /start من جديد.", True)
        return
    set_state(f"u:{uid}", {"step": "courses", "branch": key, "sel": []})
    show_view(call, lambda lvl: courses_view(key, set(), lvl))
    safe_answer(call)


@bot.callback_query_handler(func=lambda c: c.data == "chg")
def cb_change_branch(call):
    uid = call.from_user.id
    if not get_state(f"u:{uid}"):
        safe_answer(call, "انتهت الجلسة، اكتب /start من جديد.", True)
        return
    set_state(f"u:{uid}", {"step": "branch"})
    show_view(call, lambda lvl: (welcome_text(), branches_markup(lvl)))
    safe_answer(call)


@bot.callback_query_handler(func=lambda c: re.fullmatch(r"c_\d+", c.data) is not None)
def cb_course(call):
    uid = call.from_user.id
    st = get_state(f"u:{uid}")
    if not st or st.get("step") != "courses":
        safe_answer(call, "انتهت الجلسة، اكتب /start من جديد.", True)
        return
    i = int(call.data[2:])
    if i >= len(BRANCHES[st["branch"]]["courses"]):
        safe_answer(call)
        return
    sel = set(st["sel"])
    sel ^= {i}
    st["sel"] = sorted(sel)
    set_state(f"u:{uid}", st)
    try:
        tg_markup_call(
            lambda mk: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                     reply_markup=mk),
            lambda lvl: courses_markup(st["branch"], sel, lvl))
    except ApiTelegramException:
        pass
    safe_answer(call)


@bot.callback_query_handler(func=lambda c: c.data == "done")
def cb_done(call):
    uid = call.from_user.id
    st = get_state(f"u:{uid}")
    if not st or st.get("step") != "courses":
        safe_answer(call, "انتهت الجلسة، اكتب /start من جديد.", True)
        return
    if not st["sel"]:
        safe_answer(call, "لم تختر أي مادة بعد!", True)
        return
    names = [BRANCHES[st["branch"]]["courses"][i] for i in st["sel"]]
    st["step"] = "info"
    set_state(f"u:{uid}", st)
    edit_call(call,
              "✅ تم حفظ اختيارك:\n" + "\n".join(f"• {esc(n)}" for n in names) +
              "\n\nأرسل الآن معلوماتك برسالة نصية واحدة:\n<b>الاسم الثلاثي + موقع السكن + رقمك + يوزر الموقع + كلمة السر</b>\n\n"
              "<i>(مثال: احمد محمد علي المشروع السابع 0988111222 اليوزر STxxxxx الكلمة @STxxxxx)</i>\n\n<i>للإلغاء: /cancel</i>")
    safe_answer(call)


# ════════════════════════════ كول باك الأدمن ════════════════════════════
def _admin_busy(aid, rid):
    st = get_state(f"a:{aid}")
    if st and st.get("req") != rid:
        r = get_request(st["req"])
        if r and r["handled_by"] == aid and r["status"] in ("awaiting_proof", "rejecting"):
            return st["req"]
        clear_state(f"a:{aid}")          # حالة قديمة عالقة → نظّفها
    return None


@bot.callback_query_handler(func=lambda c: re.fullmatch(r"(ok|no|bk)_\d+", c.data) is not None)
def cb_admin_main(call):
    aid = call.from_user.id
    if not is_admin(aid):
        safe_answer(call, "عذراً، هذا الزر للإدارة فقط.", True)
        return
    action, rid = call.data.split("_")
    rid = int(rid)
    name = call.from_user.first_name or str(aid)

    if action == "bk":
        res = db.execute("UPDATE requests SET status='pending', handled_by=NULL, handled_name=NULL "
                         "WHERE id=? AND status='rejecting' AND handled_by=?", (rid, aid))
        if res.rowcount == 1:
            clear_state(f"a:{aid}")
        refresh_admin_messages(rid)
        safe_answer(call, "تم الرجوع.")
        return

    busy = _admin_busy(aid, rid)
    if busy:
        safe_answer(call, f"لديك طلب قيد المعالجة #{busy}. أنهِه أو اكتب /cancel أولاً.", True)
        return

    if action == "ok":
        res = db.execute("UPDATE requests SET status='awaiting_proof', handled_by=?, handled_name=? "
                         "WHERE id=? AND status='pending'", (aid, name, rid))
        if res.rowcount != 1:
            safe_answer(call, "تم التعامل مع هذا الطلب مسبقاً من أدمن آخر.", True)
            refresh_admin_messages(rid)
            return
        set_state(f"a:{aid}", {"mode": "proof", "req": rid})
        safe_answer(call, "تم استلام الطلب.")
        refresh_admin_messages(rid)
        safe_send(aid, f"✅ طلب <b>#{rid}</b> بعهدتك.\nأرسل الآن <b>صورة إثبات الاعتماد</b> ليحوّلها البوت للطالب.\n"
                       "<i>للتراجع: /cancel</i>")
    else:  # no
        res = db.execute("UPDATE requests SET status='rejecting', handled_by=?, handled_name=? "
                         "WHERE id=? AND status='pending'", (aid, name, rid))
        if res.rowcount != 1:
            safe_answer(call, "تم التعامل مع هذا الطلب مسبقاً من أدمن آخر.", True)
            refresh_admin_messages(rid)
            return
        set_state(f"a:{aid}", {"mode": "rejecting", "req": rid})
        safe_answer(call, "اختر سبب الرفض.")
        refresh_admin_messages(rid)


@bot.callback_query_handler(func=lambda c: re.fullmatch(r"rr_\d+_(\d+|c)", c.data) is not None)
def cb_reject_reason(call):
    aid = call.from_user.id
    if not is_admin(aid):
        safe_answer(call, "للإدارة فقط.", True)
        return
    _, rid, which = call.data.split("_")
    rid = int(rid)
    r = get_request(rid)
    if not r or r["status"] != "rejecting" or r["handled_by"] != aid:
        safe_answer(call, "هذا الطلب لم يعد بعهدتك.", True)
        return
    if which == "c":
        set_state(f"a:{aid}", {"mode": "reason", "req": rid})
        safe_answer(call)
        safe_send(aid, f"✍️ اكتب سبب رفض الطلب <b>#{rid}</b> (رسالة نصية):\n<i>للتراجع: /cancel</i>")
        return
    idx = int(which)
    if idx >= len(REJECT_REASONS):
        safe_answer(call)
        return
    finalize_reject(rid, aid, REJECT_REASONS[idx])
    safe_answer(call, "تم الرفض.")


def finalize_reject(rid, aid, reason):
    res = db.execute("UPDATE requests SET status='rejected', reject_reason=?, decided_at=? "
                     "WHERE id=? AND status='rejecting' AND handled_by=?", (reason, now_str(), rid, aid))
    if res.rowcount != 1:
        return False
    clear_state(f"a:{aid}")
    r = get_request(rid)
    safe_send(r["user_id"],
              f"⚠️ عذراً، تم رفض طلبك <b>#{rid}</b>.\n📝 <b>السبب:</b> {esc(reason)}\n\n"
              "يمكنك المحاولة من جديد عبر /start")
    send_sticker_safe(r["user_id"], "REJECTED")
    refresh_admin_messages(rid)
    return True


# ════════════════════════════ أوامر الأدمن ════════════════════════════
def admin_only(fn):
    def wrapper(m):
        if not is_admin(m.from_user.id):
            return
        return fn(m)
    wrapper.__name__ = fn.__name__
    return wrapper


def _arg(m):
    parts = (m.text or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


@bot.message_handler(commands=["admin"], chat_types=["private"])
@admin_only
def cmd_admin(m):
    safe_send(m.chat.id,
              "🛠 <b>أوامر الإدارة</b>\n"
              "/pending — الطلبات المفتوحة\n"
              "/stats — إحصائيات\n"
              "/find &lt;اسم | رقم جامعي | رقم طلب | ID&gt; — بحث\n"
              "/release &lt;رقم الطلب&gt; — تحرير طلب عالق وإعادته للمراجعة\n"
              "/setprice &lt;المبلغ&gt; — تغيير سعر الطلب\n"
              "/open — فتح التسجيل   /close — إغلاقه\n"
              "/export — ملف CSV بكل الطلبات\n"
              "/broadcast &lt;نص&gt; — رسالة لكل مستخدمي البوت")


def _short(r):
    info = r["student_info"]
    return esc(info[:40] + ("…" if len(info) > 40 else ""))


@bot.message_handler(commands=["pending"], chat_types=["private"])
@admin_only
def cmd_pending(m):
    rows = db.execute("SELECT * FROM requests WHERE status IN ('pending','awaiting_proof','rejecting') "
                      "ORDER BY id LIMIT 40").rows
    if not rows:
        safe_send(m.chat.id, "✅ لا يوجد طلبات مفتوحة.")
        return
    lines = [f"📥 <b>الطلبات المفتوحة ({len(rows)}):</b>\n"]
    for r in rows:
        who = f" — {esc(r['handled_name'])}" if r["handled_name"] else ""
        lines.append(f"#{r['id']} • {_short(r)} • {STATUS_STUDENT[r['status']]}{who}")
    safe_send(m.chat.id, "\n".join(lines))


@bot.message_handler(commands=["stats"], chat_types=["private"])
@admin_only
def cmd_stats(m):
    rows = db.execute("SELECT status, COUNT(*) AS n FROM requests GROUP BY status").rows
    cnt = {r["status"]: r["n"] for r in rows}
    users = db.execute("SELECT COUNT(*) AS n FROM users").rows[0]["n"]
    total = sum(cnt.values())
    safe_send(m.chat.id,
              "📊 <b>إحصائيات</b>\n"
              f"إجمالي الطلبات: {total}\n"
              f"🟡 بانتظار: {cnt.get('pending', 0)}\n"
              f"🟠 قيد المعالجة: {cnt.get('awaiting_proof', 0) + cnt.get('rejecting', 0)}\n"
              f"🟢 مقبولة: {cnt.get('approved', 0)}\n"
              f"🔴 مرفوضة: {cnt.get('rejected', 0)}\n"
              f"👥 مستخدمو البوت: {users}\n"
              f"💰 السعر الحالي: {get_price():,} {esc(CURRENCY)}\n"
              f"🚪 التسجيل: {'مفتوح' if is_open() else 'مغلق'}")


@bot.message_handler(commands=["find"], chat_types=["private"])
@admin_only
def cmd_find(m):
    q = norm_digits(_arg(m))
    if not q:
        safe_send(m.chat.id, "الاستخدام: /find اسم أو رقم")
        return
    like = f"%{q}%"
    if q.isdigit():
        rows = db.execute("SELECT * FROM requests WHERE id=? OR user_id=? OR student_info LIKE ? "
                          "ORDER BY id DESC LIMIT 10", (int(q), int(q), like)).rows
    else:
        rows = db.execute("SELECT * FROM requests WHERE student_info LIKE ? OR username LIKE ? "
                          "ORDER BY id DESC LIMIT 10", (like, like)).rows
    if not rows:
        safe_send(m.chat.id, "لا نتائج.")
        return
    lines = []
    for r in rows:
        lines.append(f"#{r['id']} • {esc(r['student_info'])}\n   {STATUS_STUDENT[r['status']]} • {esc(r['courses'])} • {esc(r['created_at'])}")
    safe_send(m.chat.id, "\n\n".join(lines))


@bot.message_handler(commands=["release"], chat_types=["private"])
@admin_only
def cmd_release(m):
    a = _arg(m)
    if not a.isdigit():
        safe_send(m.chat.id, "الاستخدام: /release رقم_الطلب")
        return
    rid = int(a)
    r = get_request(rid)
    if not r or r["status"] not in ("awaiting_proof", "rejecting"):
        safe_send(m.chat.id, "هذا الطلب ليس قيد المعالجة.")
        return
    db.execute("UPDATE requests SET status='pending', handled_by=NULL, handled_name=NULL WHERE id=?", (rid,))
    if r["handled_by"]:
        st = get_state(f"a:{r['handled_by']}")
        if st and st.get("req") == rid:
            clear_state(f"a:{r['handled_by']}")
    refresh_admin_messages(rid)
    safe_send(m.chat.id, f"🔓 تم تحرير الطلب #{rid} وإعادته للمراجعة.")


@bot.message_handler(commands=["setprice"], chat_types=["private"])
@admin_only
def cmd_setprice(m):
    a = norm_digits(_arg(m)).replace(",", "")
    if not a.isdigit() or int(a) <= 0:
        safe_send(m.chat.id, "الاستخدام: /setprice 15000")
        return
    set_setting("price", int(a))
    safe_send(m.chat.id, f"✅ السعر الجديد: <b>{int(a):,}</b> {esc(CURRENCY)}")


@bot.message_handler(commands=["open", "close"], chat_types=["private"])
@admin_only
def cmd_open_close(m):
    opening = m.text.startswith("/open")
    set_setting("open", "1" if opening else "0")
    safe_send(m.chat.id, "🚪 تم فتح التسجيل." if opening else "⛔ تم إغلاق التسجيل.")


@bot.message_handler(commands=["export"], chat_types=["private"])
@admin_only
def cmd_export(m):
    rows = db.execute("SELECT * FROM requests ORDER BY id").rows
    buf = io.StringIO()
    cols = ["id", "created_at", "user_id", "username", "student_info", "branch", "courses", "price",
            "status", "handled_name", "reject_reason", "decided_at", "proof_text"]
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        w.writerow([r.get(c, "") for c in cols])
    data = io.BytesIO(("\ufeff" + buf.getvalue()).encode("utf-8"))   # BOM ليفتح العربي صح بالإكسل
    data.name = f"requests_{datetime.now(SY_TZ).strftime('%Y%m%d_%H%M')}.csv"
    bot.send_document(m.chat.id, data, caption=f"📤 {len(rows)} طلب")


@bot.message_handler(commands=["broadcast"], chat_types=["private"])
@admin_only
def cmd_broadcast(m):
    text = _arg(m)
    if not text:
        safe_send(m.chat.id, "الاستخدام: /broadcast نص الرسالة")
        return
    ids = [r["user_id"] for r in db.execute("SELECT user_id FROM users").rows]
    safe_send(m.chat.id, f"📣 جاري الإرسال إلى {len(ids)} مستخدم...")

    def run():
        ok = 0
        for uid in ids:
            if safe_send(uid, esc(text)):
                ok += 1
            time.sleep(0.05)
        safe_send(m.chat.id, f"✅ وصلت لـ {ok} من {len(ids)}.")
    threading.Thread(target=run, daemon=True).start()


# ════════════════════════════ الراوتر العام للرسائل ════════════════════════════
@bot.message_handler(content_types=util.content_type_media, chat_types=["private"])
def router(m):
    uid = m.from_user.id

    # 1) جلسة أدمن (إثبات / سبب رفض)
    if is_admin(uid):
        ast = get_state(f"a:{uid}")
        if ast:
            return admin_flow(m, ast)

    # 1.5) أداة للأدمن: أرسل ملصق أو إيموجي مخصص فيرد البوت برقمه
    if is_admin(uid):
        if m.content_type == "sticker":
            safe_send(m.chat.id, "🆔 <b>file_id</b> للملصق (اضغط للنسخ):\n"
                                 f"<code>{esc(m.sticker.file_id)}</code>")
            return
        ids = [e.custom_emoji_id for e in (getattr(m, "entities", None) or [])
               if getattr(e, "type", "") == "custom_emoji"]
        if ids:
            safe_send(m.chat.id, "🆔 <b>emoji id</b> (اضغط للنسخ):\n" +
                      "\n".join(f"<code>{esc(i)}</code>" for i in dict.fromkeys(ids)))
            return

    # 2) جلسة طالب
    st = get_state(f"u:{uid}")
    if not st:
        safe_send(m.chat.id, "اكتب /start لتقديم طلب، أو /status لمتابعة طلباتك.")
        return
    step = st.get("step")

    if step == "info":
        if m.content_type != "text" or m.text.startswith("/"):
            safe_send(m.chat.id, "⚠️ أرسل معلوماتك كرسالة <b>نصية</b>: الاسم الثلاثي + الرقم الجامعي.")
            return
        info = norm_digits(m.text).strip()
        if not valid_info(info):
            safe_send(m.chat.id, "⚠️ المعلومات غير مكتملة. اكتب <b>الاسم الثلاثي + الرقم الجامعي</b> في رسالة واحدة.\n"
                                 "<i>مثال: أحمد محمد علي 123456</i>")
            return
        st["info"] = info
        st["step"] = "payment"
        set_state(f"u:{uid}", st)
        send_payment_info(m.chat.id, "ممتاز ✅ الآن خطوة الدفع:\n\n")
        return

    if step == "payment":
        return receive_payment_proof(m, st)

    safe_send(m.chat.id, "اضغط على أحد الأزرار أعلاه للمتابعة، أو /cancel للإلغاء.")


def receive_payment_proof(m, st):
    uid = m.from_user.id
    photo_id = photo_unique = None
    proof_text = None
    ref = None

    if m.content_type == "photo":
        photo_id = m.photo[-1].file_id
        photo_unique = m.photo[-1].file_unique_id
        proof_text = (m.caption or "").strip()[:300] or None
    elif m.content_type == "text" and not m.text.startswith("/"):
        proof_text = norm_digits(m.text).strip()[:300]
        if len(re.findall(r"\d", proof_text)) < 4:
            safe_send(m.chat.id, "⚠️ رقم العملية غير صالح. أرسل <b>رقم عملية التحويل</b> كاملاً أو <b>صورة الإيصال</b>.")
            return
        runs = re.findall(r"\d+", proof_text)               # أطول رقم داخل النص = رقم العملية
        longest = max(runs, key=len) if runs else ""
        ref = longest if len(longest) >= 6 else None         # أقصر من 6 أرقام: لا نعتمده للمقارنة
    else:
        safe_send(m.chat.id, "⚠️ أرسل <b>صورة الإيصال</b> أو <b>رقم عملية التحويل</b> فقط.")
        return

    # منع تكرار نفس الإيصال / رقم العملية
    if ref:
        dup = db.execute("SELECT id FROM requests WHERE proof_ref=? AND status!='rejected' LIMIT 1", (ref,)).rows
    else:
        dup = db.execute("SELECT id FROM requests WHERE proof_unique=? AND status!='rejected' LIMIT 1",
                         (photo_unique,)).rows
    if dup:
        safe_send(m.chat.id, "🚫 هذا الإيصال / رقم العملية مستخدم مسبقاً في طلب آخر. إذا كان هناك خطأ تواصل مع المندوب.")
        return

    if not is_open():
        clear_state(f"u:{uid}")
        safe_send(m.chat.id, "⛔ تم إغلاق باب التسجيل قبل إتمام طلبك.")
        return
    if active_request(uid):
        clear_state(f"u:{uid}")
        safe_send(m.chat.id, "⏳ لديك طلب قيد المراجعة بالفعل. تابعه عبر /status")
        return

    courses = [BRANCHES[st["branch"]]["courses"][i] for i in st["sel"]]
    res = db.execute(
        "INSERT INTO requests(user_id,username,student_info,branch,courses,price,proof_text,proof_ref,"
        "proof_photo,proof_unique,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (uid, m.from_user.username, st["info"], BRANCHES[st["branch"]]["name"], "، ".join(courses),
         get_price(), proof_text, ref, photo_id, photo_unique, "pending", now_str()))
    rid = res.last_id
    r = get_request(rid)

    if dispatch_to_admins(r) == 0:
        db.execute("DELETE FROM requests WHERE id=?", (rid,))
        safe_send(m.chat.id, "⚠️ تعذّر إرسال طلبك للإدارة حالياً. حاول بعد قليل بإرسال الإيصال مرة ثانية.")
        return

    clear_state(f"u:{uid}")
    react(m, "👍")
    safe_send(m.chat.id, f"✅ تم استلام طلبك رقم <b>#{rid}</b> وإيصال الدفع.\n"
                         "يتم الآن مراجعته من قبل المندوبين وسيصلك الرد هنا. تابع الحالة عبر /status",
              effect=EFFECTS["received"] or None)
    send_sticker_safe(m.chat.id, "RECEIVED")


def admin_flow(m, ast):
    aid = m.from_user.id
    rid = ast["req"]
    r = get_request(rid)

    if not r or r["handled_by"] != aid:
        clear_state(f"a:{aid}")
        safe_send(m.chat.id, "هذا الطلب لم يعد بعهدتك.")
        return

    if ast["mode"] == "proof":
        if r["status"] != "awaiting_proof":
            clear_state(f"a:{aid}")
            return
        if m.content_type != "photo":
            safe_send(m.chat.id, f"📸 أرسل <b>صورة</b> إثبات الاعتماد للطلب #{rid} (أو /cancel).")
            return
        try:
            _caption = (f"🎉 مبروك! تم قبول طلب إعادة العملي <b>#{rid}</b> وتوثيقه رسمياً.\n"
                        "إليك صورة إثبات الاعتماد والمصداقية:")
            _sent = False
            if EFFECTS["approved"]:
                try:
                    bot.send_photo(r["user_id"], m.photo[-1].file_id, caption=_caption, parse_mode="HTML",
                                   message_effect_id=EFFECTS["approved"])
                    _sent = True
                except Exception as e1:
                    log.info("approve effect skipped (%s)", e1)
            if not _sent:
                bot.send_photo(r["user_id"], m.photo[-1].file_id, caption=_caption, parse_mode="HTML")
        except Exception as e:
            log.warning("send proof to student failed: %s", e)
            safe_send(m.chat.id, "⚠️ تعذّر إرسال الصورة للطالب (ربما حظر البوت). الطلب ما زال بعهدتك — "
                                 "تواصل معه مباشرة ثم /release أو /cancel.")
            return
        send_sticker_safe(r["user_id"], "APPROVED")
        db.execute("UPDATE requests SET status='approved', decided_at=? WHERE id=?", (now_str(), rid))
        clear_state(f"a:{aid}")
        refresh_admin_messages(rid)
        safe_send(m.chat.id, f"✅ تم إرسال الإثبات للطالب وإغلاق الطلب #{rid}.")

    elif ast["mode"] == "reason":
        if m.content_type != "text" or m.text.startswith("/"):
            safe_send(m.chat.id, "✍️ اكتب سبب الرفض كنص (أو /cancel).")
            return
        finalize_reject(rid, aid, m.text.strip()[:300])
        safe_send(m.chat.id, f"🔴 تم رفض الطلب #{rid} وإبلاغ الطالب.")

    else:  # rejecting: بانتظار ضغط زر السبب
        safe_send(m.chat.id, f"اختر سبب رفض الطلب #{rid} من الأزرار، أو /cancel للتراجع.")


# ════════════════════════════ الويب (Render) ════════════════════════════
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is running 🚀"


@app.route("/health")
def health():
    return "ok"


def run_web():
    port = int(os.environ.get("PORT", 8080))
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=port)
    except ImportError:
        app.run(host="0.0.0.0", port=port)


def setup_commands():
    user_cmds = [BotCommand("start", "تقديم طلب جديد"), BotCommand("status", "حالة طلباتي"),
                 BotCommand("pay", "تفاصيل الدفع"), BotCommand("cancel", "إلغاء العملية")]
    admin_cmds = [BotCommand("admin", "أوامر الإدارة"), BotCommand("pending", "الطلبات المفتوحة"),
                  BotCommand("stats", "إحصائيات"), BotCommand("export", "تصدير CSV")]
    try:
        bot.set_my_commands(user_cmds)
        for a in ADMIN_IDS:
            try:
                bot.set_my_commands(user_cmds + admin_cmds, scope=BotCommandScopeChat(a))
            except Exception:
                pass
    except Exception as e:
        log.warning("set_my_commands failed: %s", e)


if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_web, daemon=True).start()
    try:
        bot.remove_webhook()
    except Exception:
        pass
    setup_commands()
    log.info("Bot started. Admins: %s | price: %s", ADMIN_IDS, get_price())
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
