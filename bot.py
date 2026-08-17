#!/usr/bin/env python3
import os, sqlite3, logging, asyncio, threading, requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
from flask import Flask

# ======================== CONFIGURATION (Secrets from Render) ========================
MASTER_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "0").split(",") if x]

DB_PATH = "master.db"
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# APIs - Environment Variables se aayegi, hack nahi hogi!
API_NUM = os.environ.get("API_NUM", "")
API_AADHAR = os.environ.get("API_AADHAR", "")

# ======================== FLASK WEB SERVER ========================
app_web = Flask(__name__)
@app_web.route('/')
def home(): return "🔴 REDZONE Master Bot & Clones are Running 24/7!"
def run_web():
    port = int(os.environ.get('PORT', 8080))
    app_web.run(host='0.0.0.0', port=port)

# ======================== DATABASE ========================
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db(); c = db.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS clones (
        id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER, bot_token TEXT UNIQUE, bot_username TEXT, 
        is_banned INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, bot_token TEXT, telegram_id INTEGER, 
        first_name TEXT, coins INTEGER DEFAULT 5, total_searches INTEGER DEFAULT 0
    )''')
    db.commit(); db.close()

# ======================== UI & KEYBOARDS ========================
def get_main_menu_text_and_kb():
    text = ("🔎 Select an option:\n\n"
            "🕵️‍♂️ OSINT Search\n"
            "💳 Add Credits\n"
            "📊 My Profile\n"
            "⚙️ Settings\n\n"
            "🔴 REDZONE • Intelligence System")
    kb = [
        [InlineKeyboardButton("🕵️‍♂️ OSINT Search", callback_data="menu_search")],
        [InlineKeyboardButton("💳 Add Credits", callback_data="menu_buy"), InlineKeyboardButton("📊 My Profile", callback_data="menu_profile")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings")]
    ]
    return text, InlineKeyboardMarkup(kb)

def get_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 Cloned Bots", callback_data="adm_bots"), InlineKeyboardButton("📊 Global Stats", callback_data="adm_stats")],
        [InlineKeyboardButton("🚫 Ban Bot", callback_data="adm_ban"), InlineKeyboardButton("✅ Unban Bot", callback_data="adm_unban")],
        [InlineKeyboardButton("📣 Broadcast", callback_data="adm_broadcast")]
    ])

# ======================== API FORMATTER ========================
def execute_search(query, stype):
    if stype == 'aadhar' and not API_AADHAR: return "❌ Aadhar API not configured."
    if stype == 'num' and not API_NUM: return "❌ Number API not configured."
        
    url = (API_AADHAR if stype == 'aadhar' else API_NUM).replace("{query}", query)
    try:
        data = requests.get(url, timeout=15).json()
    except: return "❌ API Network Error."

    msg = f"┌──────────────────────────┐\n│ 🔍 SEARCH RESULT\n├──────────────────────────┤\n│ 📋 Type: {stype.upper()}\n│ 🔑 Query: {query}\n└──────────────────────────┘\n\n"
    
    if stype == 'aadhar':
        if data.get('response', {}).get('parameters', {}).get('success'):
            msg += "✅ <b>Aadhaar Records Found</b>\n\n"
            for r in data['response']['data']:
                msg += f"👤 Name: {r.get('name', 'N/A')}\n👨 Father: {r.get('fname', 'N/A')}\n📱 Mobile: {r.get('num', 'N/A')}\n📍 Address: {str(r.get('address', 'N/A')).replace('!', ', ')}\n🔄 Circle: {r.get('circle', 'N/A')}\n\n━━━━━━━━━━━━━━━\n"
        else: msg += "❌ No records found."
    elif stype == 'num':
        if data.get('status'):
            d = data.get('data', {}).get('data', {})
            msg += "✅ <b>Number Details Found</b>\n\n"
            msg += f"👤 Name: {d.get('name', 'N/A')}\n👨 Father: {d.get('fname', 'N/A')}\n📱 Mobile: {d.get('mobile', 'N/A')}\n📍 Address: {str(d.get('address', 'N/A')).replace('!', ', ')}\n🔄 Circle: {d.get('circle', 'N/A')}\n"
        else: msg += "❌ No records found."
        
    msg += "\n🔴 <b>REDZONE OSINT</b>"
    return msg

# ======================== BOT LOGIC (Works for Master & Clones) ========================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = context.bot.token; user = update.effective_user
    db = get_db(); c = db.cursor()
    
    # Check if clone is banned
    c.execute('SELECT * FROM clones WHERE bot_token = ?', (token,)); clone = c.fetchone()
    if clone and clone['is_banned']: return await update.message.reply_text("🚫 This bot is banned by REDZONE Master Admin.")
    
    # Register User
    c.execute('SELECT * FROM users WHERE bot_token = ? AND telegram_id = ?', (token, user.id)); u = c.fetchone()
    if not u:
        c.execute('INSERT INTO users (bot_token, telegram_id, first_name, coins) VALUES (?, ?, ?, 5)', (token, user.id, user.first_name))
        db.commit()
    db.close()
    
    text, kb = get_main_menu_text_and_kb()
    await update.message.reply_text(text, reply_markup=kb, parse_mode='HTML')

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); data = q.data; user = update.effective_user
    token = context.bot.token
    
    if data == "menu_back":
        text, kb = get_main_menu_text_and_kb()
        return await q.edit_message_text(text, reply_markup=kb, parse_mode='HTML')
        
    elif data == "menu_search":
        kb = [
            [InlineKeyboardButton("📱 Number → Info", callback_data="src_num"), InlineKeyboardButton("🪪 Aadhaar → Info", callback_data="src_aadhar")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]
        ]
        await q.edit_message_text("🕵️‍♂️ <b>OSINT Search</b>\n\nSelect search type:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
        
    elif data.startswith("src_"):
        context.user_data['stype'] = 'num' if data == "src_num" else 'aadhar'
        await q.edit_message_text(f"📥 Please send your {context.user_data['stype']}:")
        
    elif data == "menu_buy":
        await q.edit_message_text("💳 <b>Add Credits</b>\n\n1 Credit = 5 Rs\n10 Credits = 40 Rs\n\nContact Admin to buy credits.", parse_mode='HTML')
        
    elif data == "menu_profile":
        db = get_db(); c = db.cursor()
        u = c.execute('SELECT * FROM users WHERE bot_token = ? AND telegram_id = ?', (token, user.id)).fetchone()
        db.close()
        if u:
            await q.edit_message_text(f"📊 <b>My Profile</b>\n\n👤 Name: {u['first_name']}\n🪙 Credits: {u['coins']}\n🔍 Searches: {u['total_searches']}", parse_mode='HTML')
            
    elif data == "menu_settings":
        await q.edit_message_text("⚙️ <b>Settings</b>\n\nBot: REDZONE OSINT\nVersion: 1.0\nStatus: Active", parse_mode='HTML')

    # Admin Callbacks
    elif data.startswith("adm_"):
        if user.id not in ADMIN_IDS: return
        if data == "adm_bots":
            db = get_db(); c = db.cursor()
            clones = c.execute('SELECT * FROM clones').fetchall(); db.close()
            text = "🤖 <b>Cloned Bots</b>\n\n"
            for cl in clones:
                status = "🚫 Banned" if cl['is_banned'] else "✅ Active"
                text += f"🤖 @{cl['bot_username']}\n   👑 Owner: <code>{cl['owner_id']}</code>\n   🔑 Token: <code>{cl['bot_token']}</code>\n   {status}\n\n"
            await q.edit_message_text(text, parse_mode='HTML')
        elif data == "adm_stats":
            db = get_db(); c = db.cursor()
            t_clones = c.execute('SELECT COUNT(*) FROM clones').fetchone()[0]
            t_users = c.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            db.close()
            await q.edit_message_text(f"📊 <b>Global Stats</b>\n\n🤖 Total Clones: {t_clones}\n👥 Total Users: {t_users}", parse_mode='HTML')
        elif data == "adm_ban":
            context.user_data['admin_state'] = 'ban_bot'
            await q.edit_message_text("🚫 Send the Bot Token to ban:")
        elif data == "adm_unban":
            context.user_data['admin_state'] = 'unban_bot'
            await q.edit_message_text("✅ Send the Bot Token to unban:")
        elif data == "adm_broadcast":
            context.user_data['admin_state'] = 'broadcast'
            await q.edit_message_text("📣 Send the message to broadcast to ALL users across ALL bots:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; msg = update.message.text; token = context.bot.token
    
    # Admin Commands
    if user.id in ADMIN_IDS and context.user_data.get('admin_state'):
        state = context.user_data['admin_state']
        db = get_db(); c = db.cursor()
        if state == 'ban_bot':
            c.execute('UPDATE clones SET is_banned = 1 WHERE bot_token = ?', (msg,)); db.commit()
            await update.message.reply_text(f"✅ Bot {msg} banned successfully.")
        elif state == 'unban_bot':
            c.execute('UPDATE clones SET is_banned = 0 WHERE bot_token = ?', (msg,)); db.commit()
            await update.message.reply_text(f"✅ Bot {msg} unbanned successfully.")
        elif state == 'broadcast':
            users = c.execute('SELECT telegram_id, bot_token FROM users').fetchall()
            s = 0
            for u in users:
                try:
                    # Send message via the specific bot the user is using
                    requests.get(f"https://api.telegram.org/bot{u['bot_token']}/sendMessage?chat_id={u['telegram_id']}&text={msg}")
                    s += 1
                except: pass
            await update.message.reply_text(f"✅ Broadcast sent to {s} users.")
        context.user_data['admin_state'] = None
        db.close()
        return

    # Normal User Search Flow
    stype = context.user_data.get('stype')
    if not stype: return await update.message.reply_text("Use /start to see menu.")
    
    db = get_db(); c = db.cursor()
    u = c.execute('SELECT * FROM users WHERE bot_token = ? AND telegram_id = ?', (token, user.id)).fetchone()
    if not u: return
    if u['coins'] <= 0: return await update.message.reply_text("❌ Insufficient 🪙 credits!")
    
    c.execute('UPDATE users SET coins = coins - 1, total_searches = total_searches + 1 WHERE id = ?', (u['id'],))
    db.commit(); db.close()
    
    await update.message.reply_text("⏳ Searching...")
    result = execute_search(msg, stype)
    context.user_data['stype'] = None
    try: await update.message.reply_text(result, parse_mode='HTML')
    except: await update.message.reply_text("❌ Error formatting result.")

def run_clone(token):
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(stop_signals=None)

# ======================== MASTER SPECIFIC COMMANDS ========================
async def master_clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args: return await update.message.reply_text("Usage: /clone <BOT_TOKEN>")
    token = context.args[0]
    
    try:
        bot_info = requests.get(f"https://api.telegram.org/bot{token}/getMe").json()
        if not bot_info.get('ok'): return await update.message.reply_text("❌ Invalid Token.")
        bname = bot_info['result']['username']
    except: return await update.message.reply_text("❌ Failed to verify token.")
    
    db = get_db(); c = db.cursor()
    c.execute('SELECT * FROM clones WHERE bot_token = ?', (token,))
    if c.fetchone(): return await update.message.reply_text("❌ This bot is already cloned.")
    
    c.execute('INSERT INTO clones (owner_id, bot_token, bot_username) VALUES (?, ?, ?)', (user.id, token, bname))
    db.commit(); db.close()
    
    threading.Thread(target=run_clone, args=(token,), daemon=True).start()
    await update.message.reply_text(f"✅ Bot @{bname} cloned successfully! It is now online.")

async def master_redzone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    await update.message.reply_text("🔴 <b>REDZONE Master Admin Panel</b>\n\nSelect an option:", reply_markup=get_admin_keyboard(), parse_mode='HTML')

# ======================== MAIN ========================
def main():
    init_db()
    threading.Thread(target=run_web, daemon=True).start()
    
    # Start already existing clones from DB
    db = get_db(); c = db.cursor()
    clones = c.execute('SELECT bot_token FROM clones WHERE is_banned = 0').fetchall()
    db.close()
    for cl in clones:
        threading.Thread(target=run_clone, args=(cl['bot_token'],), daemon=True).start()
    
    # Start Master Bot
    app = Application.builder().token(MASTER_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clone", master_clone))
    app.add_handler(CommandHandler("redzone", master_redzone))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🔴 REDZONE Master Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
