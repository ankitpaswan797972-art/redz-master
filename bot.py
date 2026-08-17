#!/usr/bin/env python3
import os, sqlite3, logging, asyncio, threading, requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
from flask import Flask

# ======================== MASTER CONFIGURATION (Secrets Removed) ========================
MASTER_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "0").split(",") if x]

DB_PATH = "master.db"
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# APIs - Ab Environment Variables se aayegi, hack nahi hogi!
API_NUM = os.environ.get("API_NUM", "")
API_AADHAR = os.environ.get("API_AADHAR", "")

# ======================== FLASK WEB SERVER ========================
app_web = Flask(__name__)
@app_web.route('/')
def home(): return "🚀 Master Bot & Clones are Running 24/7!"
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
        
    msg += "\n🚀 <b>REDZONE OSINT</b>"
    return msg

# ======================== CLONE BOT LOGIC ========================
async def clone_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = context.bot_data['token']; user = update.effective_user
    db = get_db(); c = db.cursor()
    c.execute('SELECT * FROM clones WHERE bot_token = ?', (token,)); clone = c.fetchone()
    if clone and clone['is_banned']: return await update.message.reply_text("🚫 This bot is banned by Master Admin.")
    
    c.execute('SELECT * FROM users WHERE bot_token = ? AND telegram_id = ?', (token, user.id)); u = c.fetchone()
    if not u:
        c.execute('INSERT INTO users (bot_token, telegram_id, first_name, coins) VALUES (?, ?, ?, 5)', (token, user.id, user.first_name))
        db.commit()
    
    kb = [
        [InlineKeyboardButton("📱 Number → Info", callback_data="src_num"), InlineKeyboardButton("🪪 Aadhaar → Info", callback_data="src_aadhar")],
        [InlineKeyboardButton("🪙 My Credits", callback_data="menu_coins")]
    ]
    await update.message.reply_text(f"🚀 <b>Welcome to REDZONE OSINT</b>\n\n👤 {user.first_name}\n🪙 Coins: 5\n\nSelect an option:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    db.close()

async def clone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); data = q.data; user = update.effective_user
    token = context.bot_data['token']
    
    if data == "menu_back":
        kb = [[InlineKeyboardButton("📱 Number → Info", callback_data="src_num"), InlineKeyboardButton("🪪 Aadhaar → Info", callback_data="src_aadhar")], [InlineKeyboardButton("🪙 My Credits", callback_data="menu_coins")]]
        return await q.edit_message_text("🚀 <b>REDZONE OSINT</b>\n\nSelect an option:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    elif data.startswith("src_"):
        context.user_data['stype'] = 'num' if data == "src_num" else 'aadhar'
        await q.edit_message_text(f"📥 Please send your {context.user_data['stype']}:")
    elif data == "menu_coins":
        db = get_db(); c = db.cursor()
        u = c.execute('SELECT coins FROM users WHERE bot_token = ? AND telegram_id = ?', (token, user.id)).fetchone()
        db.close()
        await q.edit_message_text(f"🪙 <b>My Credits</b>\n\n💰 Balance: {u['coins'] if u else 0}", parse_mode='HTML')

async def clone_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; msg = update.message.text; token = context.bot_data['token']
    stype = context.user_data.get('stype')
    if not stype: return await update.message.reply_text("Use /start first.")
    
    db = get_db(); c = db.cursor()
    u = c.execute('SELECT * FROM users WHERE bot_token = ? AND telegram_id = ?', (token, user.id)).fetchone()
    if not u: return
    if u['coins'] <= 0: return await update.message.reply_text("❌ Insufficient credits!")
    
    c.execute('UPDATE users SET coins = coins - 1, total_searches = total_searches + 1 WHERE id = ?', (u['id'],))
    db.commit(); db.close()
    
    await update.message.reply_text("⏳ Searching...")
    result = execute_search(msg, stype)
    context.user_data['stype'] = None
    try: await update.message.reply_text(result, parse_mode='HTML')
    except: await update.message.reply_text("❌ Error formatting result.")

def run_clone(token):
    app = Application.builder().token(token).build()
    app.bot_data['token'] = token
    app.add_handler(CommandHandler("start", clone_start))
    app.add_handler(CallbackQueryHandler(clone_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, clone_message))
    app.run_polling(stop_signals=None)

# ======================== MASTER BOT LOGIC ========================
async def master_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome to Master Bot.\nUse /clone <BOT_TOKEN> to deploy your REDZONE OSINT Bot.")

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
    
    # Start clone in thread
    threading.Thread(target=run_clone, args=(token,), daemon=True).start()
    await update.message.reply_text(f"✅ Bot @{bname} cloned successfully! It is now online.")

async def master_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    db = get_db(); c = db.cursor()
    clones = c.execute('SELECT * FROM clones').fetchall()
    db.close()
    
    text = "🔧 <b>Master Admin Panel</b>\n\n<b>Cloned Bots:</b>\n"
    for cl in clones:
        status = "🚫 Banned" if cl['is_banned'] else "✅ Active"
        text += f"\n🤖 @{cl['bot_username']}\n   👑 Owner: <code>{cl['owner_id']}</code>\n   🔑 Token: <code>{cl['bot_token']}</code>\n   {status}\n"
    
    text += "\n\nCommands:\n/ban <token> - Ban a cloned bot\n/unban <token> - Unban bot\n/users - See total users"
    await update.message.reply_text(text, parse_mode='HTML')

async def master_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    if not context.args: return await update.message.reply_text("Usage: /ban <token>")
    db = get_db(); c = db.cursor()
    c.execute('UPDATE clones SET is_banned = 1 WHERE bot_token = ?', (context.args[0],))
    db.commit(); db.close()
    await update.message.reply_text("✅ Bot banned successfully.")

async def master_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    db = get_db(); c = db.cursor()
    users = c.execute('SELECT * FROM users LIMIT 50').fetchall()
    clones = c.execute('SELECT * FROM clones').fetchall()
    text = f"📊 <b>Stats</b>\n\nTotal Clones: {len(clones)}\nTotal Users: {len(users)}\n\n<b>Recent Users:</b>\n"
    for u in users: text += f"• {u['first_name']} (<code>{u['telegram_id']}</code>) - Searches: {u['total_searches']}\n"
    db.close()
    await update.message.reply_text(text, parse_mode='HTML')

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
    app.add_handler(CommandHandler("start", master_start))
    app.add_handler(CommandHandler("clone", master_clone))
    app.add_handler(CommandHandler("admin", master_admin))
    app.add_handler(CommandHandler("ban", master_ban))
    app.add_handler(CommandHandler("users", master_users))
    print("🚀 Master Bot is running with clones...")
    app.run_polling()

if __name__ == '__main__':
    main()
