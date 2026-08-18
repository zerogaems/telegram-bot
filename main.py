import os
from threading import Thread
from flask import Flask

# سيرفر خفيف لإبقاء الخدمة نشطة في Render
app = Flask('')

@app.route('/')
def home():
    return "البوت يعمل بنجاح!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# تشغيل السيرفر في مسار خلفي
Thread(target=run_web).start()

# ==========================================
# ضع كود البوت كاملاً أسفل هذا السطر
# ==========================================
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8784917944:AAGD5Ry6zPQJwscA0PD-V4vttp5afwYdTss"
# ... اكمل باقي الكود الخاص بك هنا ...

CHANNEL_USERNAME = "@Hamak456"  # ضع معرف قناتك هنا

bot = telebot.TeleBot(TOKEN)
user_states = {}

@bot.message_handler(content_types=['document', 'photo', 'audio', 'video'])
def print_my_file_id(message):
    if message.document:
        f_id = message.document.file_id
        print(f"MY BOT FILE ID: {f_id}")
        bot.reply_to(message, f"هذا هو الـ File ID الخاص ببوتك:\n{f_id}", parse_mode="Markdown")

database = {
    # ------------ السنة الأولى ------------
    "year_1_sem_1": [
        {"name": "ري1 📐", "content": {"محاضرة 1 📄": "BQACAgQAAxkBAAICD2qEBmeR935OBUjFG8Ont08sWztlAAKoIAAC18EhUMGVwq8N9P5HPQQ","📝 دورات سابقة": "BQACAgQAAxkBAAICEWqEBsO8pAchkmOl8-A4CyLXSQn-AALJHAACCa4gUMy9w9nebpVYPQQ"}},
        {"name": "فيزيا ⚡", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
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
        {"name": "ري3 📐", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "برمجة غرضية التوجه 💻", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "الكترون 🔌", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "دارات ⚡", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "بنى 🏗️", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "لغة3 🇬🇧", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "تصميم 🎨", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}}
    ],
    "year_2_sem_2": [
        {"name": "ري4 📐", "content": {"محاضرة 1 📄": "BQACAgQAAxkBAAEtuFJqhAKq9r7dkjf7LeWtWB_jxb-uZAACqCAAAtfBIVDjAgdIdi8NOT0E","📝 دورات سابقة": "BQACAgQAAxkBAAEtuD1qg_8olRC5E90Z_jmuzCOz01WgFAAC_B0AAoW5IFKzCUj-ilqa9z0E"}},
        {"name": "تمثيلية 📊", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مضخمات 🔊", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "اقتصاد 💰", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "انتشار 📡", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "اشارات 📶", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "لغة4 🇬🇧", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}}
    ],

    # ------------ السنة الثالثة ------------
    "year_3_sem_1": [
        {"name": "رقمية 🔢", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "بنية حاسب 🖥️", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "قياسات 📏", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "دارات منطقية ⚡", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "معالجة اشارة 📶", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "دارات الكترونية 🔌", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "نظرية الاحتمالات 🎲", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}}
    ],
    "year_3_sem_2": [
        {"name": "دارات متكاملة 🎛️", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "معلومات وترميز 🔐", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "الرسم والتصميم ✏️", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "المعالجة والمتحكمات 🤖", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "تحكم آلي 🕹️", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "امواج مكروية 📡", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "تراسل المعلومات 🌐", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}}
    ],
    # ------------ السنة الرابعة ------------
    "year_4_sem_1": [
        {"name": "مادة 1 - س4 ف1 📚", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 2 - س4 ف1 📚", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 3 - س4 ف1 📚", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 4 - س4 ف1 📚", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 5 - س4 ف1 📚", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 6 - س4 ف1 📚", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 7 - س4 ف1 📚", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}}
    ],
    "year_4_sem_2": [
        {"name": "مادة 1 - س4 ف2 📚", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 2 - س4 ف2 📚", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 3 - س4 ف2 📚", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 4 - س4 ف2 📚", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 5 - س4 ف2 📚", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 6 - س4 ف2 📚", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 7 - س4 ف2 📚", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}}
    ],

    # ------------ السنة الخامسة ------------
    "year_5_sem_1": [
        {"name": "مادة 1 - س5 ف1 🎓", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 2 - س5 ف1 🎓", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 3 - س5 ف1 🎓", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 4 - س5 ف1 🎓", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 5 - س5 ف1 🎓", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 6 - س5 ف1 🎓", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 7 - س5 ف1 🎓", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}}
    ],
    "year_5_sem_2": [
        {"name": "مادة 1 - س5 ف2 🎓", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 2 - س5 ف2 🎓", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 3 - س5 ف2 🎓", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 4 - س5 ف2 🎓", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 5 - س5 ف2 🎓", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مادة 6 - س5 ف2 🎓", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}},
        {"name": "مشروع التخرج 🎓", "content": {"محاضرة 1 📄": "PASTE_FILE_ID_HERE", "محاضرة 2 📄": "PASTE_FILE_ID_HERE", "محاضرة 3 📄": "PASTE_FILE_ID_HERE", "محاضرة 4 📄": "PASTE_FILE_ID_HERE", "محاضرة 5 📄": "PASTE_FILE_ID_HERE", "محاضرة 6 📄": "PASTE_FILE_ID_HERE", "محاضرة 7 📄": "PASTE_FILE_ID_HERE", "محاضرة 8 📄": "PASTE_FILE_ID_HERE", "محاضرة 9 📄": "PASTE_FILE_ID_HERE", "محاضرة 10 📄": "PASTE_FILE_ID_HERE", "📝 دورات سابقة": "PASTE_FILE_ID_HERE"}}
    ]
}

# --- لوحات المفاتيح (Keyboards) ---

def get_years_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("السنة الأولى 1️⃣", "السنة الثانية 2️⃣")
    markup.row("السنة الثالثة 3️⃣", "السنة الرابعة 4️⃣")
    markup.row("السنة الخامسة 5️⃣")
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

def get_content_keyboard(content_dict):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for key in content_dict.keys():
        if key == "📝 دورات سابقة":
            continue
        row.append(KeyboardButton(key))
        if len(row) == 2:
            markup.row(*row)
            row = []
    if row:
        markup.row(*row)
    
    if "📝 دورات سابقة" in content_dict:
        markup.row("📝 دورات سابقة")
        
    markup.row("🔙 رجوع للمواد", "🏠 العودة للرئيسية")
    return markup

def get_sub_inline_markup():
    markup = InlineKeyboardMarkup()
    channel_url = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
    markup.add(InlineKeyboardButton("📢 رابط القناة", url=channel_url))
    markup.add(InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_subscription"))
    return markup

def check_sub(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['creator', 'administrator', 'member']
    except Exception:
        return False

# --- معالجة الرسائل ---

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    chat_id = message.chat.id
    text = message.text
    user_id = message.from_user.id

    if not check_sub(user_id):
        bot.send_message(
            chat_id,
            f"⚠️ عذراً عزيزي، يجب عليك الاشتراك في القناة أولاً لاستخدام البوت:\n{CHANNEL_USERNAME}",
            reply_markup=get_sub_inline_markup()
        )
        return

    if text in ["/start", "ابدأ من جديد 🔄", "🏠 العودة للرئيسية"]:
        user_states[chat_id] = {"year": None, "sem": None, "material": None}
        bot.send_message(chat_id, "أهلاً بالمهندس العظيم! اختر السنة الدراسية:", reply_markup=get_years_keyboard())
        return

    years_map = {
        "السنة الأولى 1️⃣": 1, "السنة الثانية 2️⃣": 2,
        "السنة الثالثة 3️⃣": 3, "السنة الرابعة 4️⃣": 4, "السنة الخامسة 5️⃣": 5
    }
    if text in years_map:
        user_states[chat_id] = {"year": years_map[text], "sem": None, "material": None}
        bot.send_message(chat_id, f"اختر الفصل الدراسي لـ {text}:", reply_markup=get_semesters_keyboard())
        return

    sems_map = {"الفصل الأول 📘": 1, "الفصل الثاني 📙": 2}
    if text in sems_map:
        c_year = user_states.get(chat_id, {}).get("year")
        if not c_year:
            bot.send_message(chat_id, "يرجى اختيار السنة الدراسية أولاً:", reply_markup=get_years_keyboard())
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
            for mat in materials:
                if mat["name"] == c_mat:
                    if text in mat["content"]:
                        file_id = mat["content"][text]
                        if file_id == "PASTE_FILE_ID_HERE":
                            bot.send_message(chat_id, f"⚠️ لم يتم رفع ملف [{text}] لمادة [{c_mat}] حتى الآن.")
                        else:
                            bot.send_document(chat_id, file_id, caption=f"📄 {text} - مادة {c_mat}")
                        return

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.answer_callback_query(call.id)
    if call.data == "check_subscription":
        if check_sub(call.from_user.id):
            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
            user_states[call.message.chat.id] = {"year": None, "sem": None, "material": None}
            bot.send_message(call.message.chat.id, "أهلاً بالمهندس العظيم! اختر السنة الدراسية:", reply_markup=get_years_keyboard())
        else:
            bot.answer_callback_query(call.id, "❌ أنت غير مشترك في القناة بعد!", show_alert=True)

print("البوت مكتمل 100% وبدون أي نقص إطلاقاً!")
bot.infinity_polling()


