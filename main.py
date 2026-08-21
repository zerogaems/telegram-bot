import os
import time
import sqlite3
from datetime import datetime
from threading import Thread
from flask import Flask
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ==========================================
# 1. إعدادات البوت وقاعدة البيانات
# ==========================================

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', "8784917944:AAGD5Ry6zPQJwscA0PD-V4vttp5afwYdTss")
CHANNEL_USERNAME = "@Hamak456"
ADMIN_ID = 7547218555

bot = telebot.TeleBot(TOKEN)

# ضبط قائمة الأوامر (تظهر زر القائمة Menu بجانب صندوق الكتابة)
bot.set_my_commands([
    telebot.types.BotCommand("start", "إعادة تشغيل البوت")
])

user_states = {}
last_interaction_time = {}
admin_broadcast_state = {}
admin_add_file_state = {}
admin_delete_file_state = {}
admin_post_announcement_state = {}
admin_exam_schedule_state = {}
admin_ban_state = {}
user_feedback_state = {}

app = Flask('')

@app.route('/')
def home():
    return "البوت يعمل بنجاح!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web, daemon=True).start()

# --- إدارة قاعدة البيانات SQLite ---

def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS materials_content (
            db_key TEXT,
            material_name TEXT,
            lecture_name TEXT,
            file_id TEXT,
            PRIMARY KEY (db_key, material_name, lecture_name)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type TEXT,
            text_content TEXT,
            file_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS banned_users (
            user_id INTEGER PRIMARY KEY,
            banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_user(user_id, first_name):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, first_name) VALUES (?, ?)', (user_id, first_name))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    conn.close()
    return [user[0] for user in users]

def get_users_count():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def save_file_to_db(db_key, material_name, lecture_name, file_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO materials_content (db_key, material_name, lecture_name, file_id)
        VALUES (?, ?, ?, ?)
    ''', (db_key, material_name, lecture_name, file_id))
    conn.commit()
    conn.close()

def delete_file_from_db(db_key, material_name, lecture_name):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM materials_content 
        WHERE db_key = ? AND material_name = ? AND lecture_name = ?
    ''', (db_key, material_name, lecture_name))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def get_file_from_db(db_key, material_name, lecture_name):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT file_id FROM materials_content 
        WHERE db_key = ? AND material_name = ? AND lecture_name = ?
    ''', (db_key, material_name, lecture_name))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def save_exam_schedule(file_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES ("exam_schedule_photo", ?)', (file_id,))
    conn.commit()
    conn.close()

def get_exam_schedule():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = "exam_schedule_photo"')
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def ban_user(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO banned_users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

def unban_user(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM banned_users WHERE user_id = ?', (user_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def is_user_banned(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM banned_users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

init_db()

# خيط النسخ الاحتياطي التلقائي الأسبوعي
def auto_backup_thread():
    while True:
        try:
            time.sleep(7 * 24 * 3600)
            if os.path.exists('bot_database.db'):
                with open('bot_database.db', 'rb') as doc:
                    bot.send_document(
                        ADMIN_ID, 
                        doc, 
                        caption=f"📦 **نسخة احتياطية تلقائية أسبوعية لقاعدة البيانات**\n📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 
                        parse_mode="Markdown"
                    )
        except Exception as e:
            print(f"Auto Backup Error: {e}")

Thread(target=auto_backup_thread, daemon=True).start()

# ==========================================
# 2. الهيكل التأسيسي للمواد
# ==========================================

database = {  
    # ------------ السنة الأولى ------------
    "year_1_sem_1": [
        {"name": "ري1 📐", "content": {"محاضرة 1 📄": "BQACAgQAAxkBAAICD2qEBmeR935OBUjFG8Ont08sWztlAAKoIAAC18EhUMGVwq8N9P5HPQQ", "📝 دورات سابقة": "BQACAgQAAxkBAAICEWqEBsO8pAchkmOl8-A4CyLXSQn-AALJHAACCa4gUMy9w9nebpVYPQQ"}},
        {"name": "فيزيا ⚡", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "تقانة 💻", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "خوارزميات 🧩", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "لغة1 🇬🇧", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "حماية بيئة 🌿", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "لغة عربية 📖", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}}
    ],
    "year_1_sem_2": [
        {"name": "ري2 📐", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "ميكانيك ⚙️", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "برمجة 💻", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "لغة2 🇬🇧", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "اسس كهربا 🔌", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "صحة عامة 🏥", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "ثقافة 📚", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}}
    ],

    # ------------ السنة الثانية ------------
    "year_2_sem_1": [
        {"name": "ري3 📐", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "برمجة غرضية التوجه 💻", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "الكترون 🔌", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "دارات ⚡", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "بنى 🏗️", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "لغة3 🇬🇧", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "تصميم 🎨", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}}
    ],
    "year_2_sem_2": [
        {"name": "ري4 📐", "content": {"محاضرة 1 📄": "BQACAgQAAxkBAAEtuFJqhAKq9r7dkjf7LeWtWB_jxb-uZAACqCAAAtfBIVDjAgdIdi8NOT0E", "📝 دورات سابقة": "BQACAgQAAxkBAAEtuD1qg_8olRC5E90Z_jmuzCOz01WgFAAC_B0AAoW5IFKzCUj-ilqa9z0E"}},
        {"name": "تمثيلية 📊", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مضخمات 🔊", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "اقتصاد 💰", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "انتشار 📡", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "اشارات 📶", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "لغة4 🇬🇧", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}}
    ],

    # ------------ السنة الثالثة ------------
    "year_3_sem_1": [
        {"name": "رقمية 🔢", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE"}},
        {"name": "بنية حاسب 🖥️", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE"}}
    ],
    "year_3_sem_2": [
        {"name": "دارات متكاملة 🎛️", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE"}}
    ],
    # ------------ السنة الرابعة ------------
    "year_4_sem_1": [
        {"name": "مادة 1 - س4 ف1 📚", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE"}}
    ],
    "year_4_sem_2": [
        {"name": "مادة 1 - س4 ف2 📚", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE"}}
    ],
    # ------------ السنة الخامسة ------------
    "year_5_sem_1": [
        {"name": "مادة 1 - س5 ف1 🎓", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE"}}
    ],
    "year_5_sem_2": [
        {"name": "مشروع التخرج 🎓", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE"}}
    ]
}


# ==========================================
# 3. لوحات المفاتيح (Keyboards)
# ==========================================

def get_years_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("السنة الأولى 1️⃣", "السنة الثانية 2️⃣")
    markup.row("السنة الثالثة 3️⃣", "السنة الرابعة 4️⃣")
    markup.row("السنة الخامسة 5️⃣", "📅 برنامج الامتحان")
    markup.row("💬 أرسل ملاحظة/استفسار")
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
            markup.row(*row)
            row = []
    if row:
        markup.row(*row)
    markup.row("🔙 رجوع للفصول", "🏠 العودة للرئيسية")
    return markup

def get_content_keyboard(content_list):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for key in content_list:
        if key == "📝 دورات سابقة":
            continue
        row.append(KeyboardButton(key))
        if len(row) == 2:
            markup.row(*row)
            row = []
    if row:
        markup.row(*row)
    
    if "📝 دورات سابقة" in content_list:
        markup.row("📝 دورات سابقة")
        
    markup.row("🔙 رجوع للمواد", "🏠 العودة للرئيسية")
    return markup

def get_admin_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📊 إحصائيات البوت", "📢 إرسال إذاعة")
    markup.row("➕ تحديث File ID لمادة", "🗑️ حذف ملف مادة")
    markup.row("📸 رفع صورة برنامج الامتحان", "📦 نسخة احتياطية فورية")
    markup.row("🚫 حظر / إلغاء حظر مستخدم")
    markup.row("🏠 العودة للرئيسية")
    return markup

def get_sub_inline_markup():
    markup = InlineKeyboardMarkup()
    clean_username = CHANNEL_USERNAME.replace('@', '')
    channel_url = f"https://t.me/{clean_username}"
    markup.add(InlineKeyboardButton("📢 رابط القناة", url=channel_url))
    markup.add(InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_subscription"))
    return markup

def check_sub(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['creator', 'administrator', 'member']
    except Exception:
        return False

# ==========================================
# 4. معالجة الرسائل والملفات
# ==========================================

@bot.message_handler(content_types=['document', 'photo', 'video', 'audio', 'voice'])
def handle_admin_media(message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        file_id = None
        
        if message.document:
            file_id = message.document.file_id
        elif message.photo:
            file_id = message.photo[-1].file_id
        elif message.video:
            file_id = message.video.file_id

        if admin_exam_schedule_state.get(user_id):
            if file_id:
                save_exam_schedule(file_id)
                bot.reply_to(message, "✅ تم حفظ صورة برنامج الامتحان بنجاح!")
            else:
                bot.reply_to(message, "❌ يرجى إرسال صورة أو ملف فقط.")
            admin_exam_schedule_state[user_id] = False
            return

        if admin_add_file_state.get(user_id):
            state = admin_add_file_state[user_id]
            save_file_to_db(state['db_key'], state['material'], state['lecture'], file_id)
            bot.reply_to(message, f"✅ تم حفظ/تحديث الملف بنجاح للمادة [{state['material']}] - [{state['lecture']}]!")
            admin_add_file_state[user_id] = None
            return

        if file_id:
            bot.reply_to(message, f"🔑 **File ID الخاص بالمستند:**\n\n`{file_id}`", parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text
    
    if is_user_banned(user_id) and user_id != ADMIN_ID:
        bot.send_message(chat_id, "🚫 تم حظرك من استخدام هذا البوت بسبب مخالفة القوانين.")
        return

    add_user(user_id, message.from_user.first_name)

    current_time = time.time()
    if user_id in last_interaction_time and current_time - last_interaction_time[user_id] < 1.0:
        return
    last_interaction_time[user_id] = current_time

    try:
        # ---- لوحة الأدمن ----
        if user_id == ADMIN_ID:
            if text == "/admin":
                bot.send_message(chat_id, "🔧 **لوحة تحكم الأدمن:**", reply_markup=get_admin_keyboard(), parse_mode="Markdown")
                return

            if text == "📊 إحصائيات البوت":
                count = get_users_count()
                bot.send_message(chat_id, f"📈 **عدد مستخدمي البوت:** `{count}` مستخدم", parse_mode="Markdown")
                return

            if text == "📦 نسخة احتياطية فورية":
                if os.path.exists('bot_database.db'):
                    with open('bot_database.db', 'rb') as doc:
                        bot.send_document(chat_id, doc, caption="📦 **نسخة احتياطية فورية لقاعدة البيانات**")
                return

            if text == "📢 إرسال إذاعة":
                admin_broadcast_state[user_id] = True
                bot.send_message(chat_id, "أرسل نص الرسالة التي تريد إرسالها للجميع:")
                return

            if admin_broadcast_state.get(user_id):
                admin_broadcast_state[user_id] = False
                users = get_all_users()
                success, failed = 0, 0
                bot.send_message(chat_id, f"⏳ جاري الإرسال إلى {len(users)} مستخدم...")
                for u_id in users:
                    try:
                        bot.send_message(u_id, text)
                        success += 1
                        time.sleep(0.05)
                    except Exception:
                        failed += 1
                bot.send_message(chat_id, f"✅ اكتملت الإذاعة!\n• نجاح: {success}\n• فشل: {failed}")
                return

            if text == "📸 رفع صورة برنامج الامتحان":
                admin_exam_schedule_state[user_id] = True
                bot.send_message(chat_id, "أرسل الآن صورة برنامج الامتحان أو قم بإرسال الـ File ID الخاص بالصورة كرسالة نصية:")
                return

            if admin_exam_schedule_state.get(user_id):
                admin_exam_schedule_state[user_id] = False
                save_exam_schedule(text.strip())
                bot.send_message(chat_id, f"✅ تم حفظ File ID لبرنامج الامتحان بنجاح:\n`{text.strip()}`", parse_mode="Markdown")
                return

            if text == "➕ تحديث File ID لمادة":
                c_year = user_states.get(chat_id, {}).get("year")
                c_sem = user_states.get(chat_id, {}).get("sem")
                c_mat = user_states.get(chat_id, {}).get("material")
                if c_year and c_sem and c_mat:
                    bot.send_message(chat_id, f"أرسل اسم المحاضرة/الدورة التي تريد رفع أو استبدال ملف لها (مثال: محاضرة 1 📄):")
                    admin_add_file_state[user_id] = {"step": "WAIT_LECTURE", "db_key": f"year_{c_year}_sem_{c_sem}", "material": c_mat}
                else:
                    bot.send_message(chat_id, "⚠️ يرجى التوجه للمادة والمحاضرة المطلوبة عبر الأزرار أولاً ثم الضغط على هذا الزر.")
                return

            if admin_add_file_state.get(user_id) and admin_add_file_state[user_id].get("step") == "WAIT_LECTURE":
                admin_add_file_state[user_id]["lecture"] = text
                admin_add_file_state[user_id]["step"] = "WAIT_FILE"
                bot.send_message(chat_id, f"قم برفع/إرسال الملف الآن ليتم ربطه أو استبداله بـ [{text}]:")
                return

            if text == "🗑️ حذف ملف مادة":
                c_year = user_states.get(chat_id, {}).get("year")
                c_sem = user_states.get(chat_id, {}).get("sem")
                c_mat = user_states.get(chat_id, {}).get("material")
                if c_year and c_sem and c_mat:
                    bot.send_message(chat_id, f"أرسل اسم المحاضرة التي تريد حذفها نهائياً من مادة [{c_mat}] (مثال: محاضرة 1 📄):")
                    admin_delete_file_state[user_id] = {"step": "WAIT_LECTURE", "db_key": f"year_{c_year}_sem_{c_sem}", "material": c_mat}
                else:
                    bot.send_message(chat_id, "⚠️ يرجى التوجه للمادة المطلوبة عبر الأزرار أولاً ثم الضغط على هذا الزر.")
                return

            if admin_delete_file_state.get(user_id) and admin_delete_file_state[user_id].get("step") == "WAIT_LECTURE":
                state = admin_delete_file_state[user_id]
                success = delete_file_from_db(state['db_key'], state['material'], text)
                if success:
                    bot.send_message(chat_id, f"✅ تم حذف ملف [{text}] من المادة [{state['material']}] بنجاح!")
                else:
                    bot.send_message(chat_id, f"❌ لم يتم العثور على ملف باسم [{text}] لهذه المادة.")
                admin_delete_file_state[user_id] = None
                return

            if text == "🚫 حظر / إلغاء حظر مستخدم":
                admin_ban_state[user_id] = True
                bot.send_message(chat_id, "أدخل الـ User ID الخاص بالطالب للحظر/إلغاء الحظر:")
                return

            if admin_ban_state.get(user_id):
                admin_ban_state[user_id] = False
                try:
                    target_id = int(text.strip())
                    if is_user_banned(target_id):
                        unban_user(target_id)
                        bot.send_message(chat_id, f"✅ تم إلغاء حظر المستخدم `{target_id}` بنجاح!", parse_mode="Markdown")
                    else:
                        ban_user(target_id)
                        bot.send_message(chat_id, f"🚫 تم حظر المستخدم `{target_id}` بنجاح!", parse_mode="Markdown")
                except ValueError:
                    bot.send_message(chat_id, "❌ خطأ: يرجى إدخال رقم User ID صحيح.")
                return

        # ---- الرد على مقترحات الطلاب ----
        if message.reply_to_message and user_id == ADMIN_ID:
            try:
                orig_text = message.reply_to_message.text
                if "ID:" in orig_text:
                    target_user_id = int(orig_text.split("ID:")[1].split(")")[0].strip())
                    bot.send_message(target_user_id, f"📬 **رد من إدارة البوت:**\n\n{text}", parse_mode="Markdown")
                    bot.send_message(chat_id, "✅ تم إرسال الرد للطالب بنجاح!")
                    return
            except Exception as e:
                print(f"خطأ في الرد: {e}")

        # ---- فحص الاشتراك ----
        if user_id != ADMIN_ID and not check_sub(user_id):
            bot.send_message(
                chat_id,
                f"⚠️ يجب عليك الاشتراك في القناة أولاً لاستخدام البوت:\n{CHANNEL_USERNAME}",
                reply_markup=get_sub_inline_markup()
            )
            return

        # ---- عرض صورة برنامج الامتحان ----
        if text == "📅 برنامج الامتحان":
            file_id = get_exam_schedule()
            if file_id:
                try:
                    bot.send_photo(chat_id, file_id, caption="📅 **برنامج الامتحانات الرسمية:**")
                except Exception:
                    bot.send_document(chat_id, file_id, caption="📅 **برنامج الامتحانات الرسمية:**")
            else:
                bot.send_message(chat_id, "ℹ️ لم يتم رفع صورة برنامج الامتحان بعد من قبل إدارة الكلية.")
            return

        # ---- استقبال الملاحظات والاستفسارات ----
        if text == "💬 أرسل ملاحظة/استفسار":
            user_feedback_state[user_id] = True
            bot.send_message(chat_id, "اكتب استفسارك أو ملاحظتك الآن وسوف تصل لإدارة البوت فوراً:")
            return

        if user_feedback_state.get(user_id):
            user_feedback_state[user_id] = False
            bot.send_message(
                ADMIN_ID, 
                f"📩 **رسالة/ملاحظة جديدة:**\n\nمن: {message.from_user.first_name}\n(ID: `{user_id}`)\n\nالرسالة:\n{text}\n\n*(للرد على هذا الطالب، قم بعمل Reply على هذه الرسالة واكتب ردك)*", 
                parse_mode="Markdown"
            )
            bot.send_message(chat_id, "✅ تم إرسال ملاحظتك بنجاح للإدارة، شكراً لك!")
            return

        # ---- التنقل الرئيسي ----
        if text in ["/start", "ابدأ من جديد 🔄", "🏠 العودة للرئيسية"]:
            user_states[chat_id] = {"year": None, "sem": None, "material": None}
            welcome_text = (
                f"👋 ** أهلاً بك يا  {message.from_user.first_name}!**\n\n"
                f"🎓 مرحباً بك في بوت الاتصالات المساعد.\n"
                f"🎓 هذا البوت باشراف ممثل الاتصالات.\n"
                f"📚 يمكنك الوصول لجميع المحاضرات والمقررات بسهولة.\n\n"
                f"👇 **يرجى اختيار السنة الدراسية للبدء:**"
            )
            bot.send_message(chat_id, welcome_text, reply_markup=get_years_keyboard(), parse_mode="Markdown")
            return

        years_map = {"السنة الأولى 1️⃣": 1, "السنة الثانية 2️⃣": 2, "السنة الثالثة 3️⃣": 3, "السنة الرابعة 4️⃣": 4, "السنة الخامسة 5️⃣": 5}
        if text in years_map:
            user_states[chat_id] = {"year": years_map[text], "sem": None, "material": None}
            bot.send_message(chat_id, f"اختر الفصل الدراسي لـ {text}:", reply_markup=get_semesters_keyboard())
            return

        sems_map = {"الفصل الأول 📘": 1, "الفصل الثاني 📙": 2}
        if text in sems_map:
            c_year = user_states.get(chat_id, {}).get("year")
            if not c_year:
                bot.send_message(chat_id, "اختر السنة الدراسية أولاً:", reply_markup=get_years_keyboard())
                return
            user_states[chat_id]["sem"] = sems_map[text]
            user_states[chat_id]["material"] = None
            db_key = f"year_{c_year}_sem_{sems_map[text]}"
            materials = database.get(db_key, [])
            bot.send_message(chat_id, f"إليك مواد السنة {c_year} - الفصل {sems_map[text]}:", reply_markup=get_materials_keyboard(materials))
            return

        if text == "🔙 رجوع للفصول":
            c_year = user_states.get(chat_id, {}).get("year")
            if c_year:
                user_states[chat_id]["material"] = None
                bot.send_message(chat_id, "اختر الفصل الدراسي:", reply_markup=get_semesters_keyboard())
            else:
                bot.send_message(chat_id, "اختر السنة الدراسية:", reply_markup=get_years_keyboard())
            return

        if text == "🔙 رجوع للمواد":
            c_year = user_states.get(chat_id, {}).get("year")
            c_sem = user_states.get(chat_id, {}).get("sem")
            if c_year and c_sem:
                user_states[chat_id]["material"] = None
                db_key = f"year_{c_year}_sem_{c_sem}"
                bot.send_message(chat_id, "اختر المادة:", reply_markup=get_materials_keyboard(database.get(db_key, [])))
            else:
                bot.send_message(chat_id, "اختر السنة الدراسية:", reply_markup=get_years_keyboard())
            return

        # ---- إرسال واسترجاع الملفات للمواد ----
        c_year = user_states.get(chat_id, {}).get("year")
        c_sem = user_states.get(chat_id, {}).get("sem")
        if c_year and c_sem:
            db_key = f"year_{c_year}_sem_{c_sem}"
            materials = database.get(db_key, [])
            
            for mat in materials:
                if mat["name"] == text:
                    user_states[chat_id]["material"] = text
                    bot.send_message(
                        chat_id,
                        f"📚 اختر المحاضرة أو الدورات المتاحة لمادة [{text}]:",
                        reply_markup=get_content_keyboard(mat["content"])
                    )
                    return

            c_mat = user_states.get(chat_id, {}).get("material")
            if c_mat:
                file_id = get_file_from_db(db_key, c_mat, text)
                if file_id:
                    bot.send_chat_action(chat_id, 'upload_document')
                    caption_text = (
                        f"📌 **المادة:** {c_mat}\n"
                        f"📑 **المحتوى:** {text}\n\n"
                        f"✨ بالتوفيق والنجاح!"
                    )
                    bot.send_document(chat_id, file_id, caption=caption_text, parse_mode="Markdown")
                else:
                    bot.send_message(
                        chat_id, 
                        f"⏳ **المحاضرة لم تُعطَ بعد**\n\n"
                        f"📖 لم يتم رفع ملف [{text}] لمادة [{c_mat}] حتى الآن.\n"
                        f"🔔 سيتم إدراجها فور صدورها رسمياً.", 
                        parse_mode="Markdown"
                    )
                return

    except Exception as e:
        print(f"حدث خطأ: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        if call.data == "check_subscription":
            if check_sub(call.from_user.id):
                bot.answer_callback_query(call.id, "✅ تم التحقق من الاشتراك بنجاح!")
                bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
                user_states[call.message.chat.id] = {"year": None, "sem": None, "material": None}
                bot.send_message(call.message.chat.id, "شرفتنا", reply_markup=get_years_keyboard())
            else:
                bot.answer_callback_query(call.id, "❌ أنت غير مشترك في القناة بعد!", show_alert=True)
    except Exception as e:
        print(f"Callback Error: {e}")

if __name__ == "__main__":
    print("البوت يعمل بنجاح...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

