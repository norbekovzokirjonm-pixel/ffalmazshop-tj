import os
import logging
import sqlite3
import datetime
from decimal import Decimal
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# --- CONFIG ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
FAZERCARDS_API_KEY = os.getenv("FAZERCARDS_API_KEY", "")
FAZERCARDS_BASE_URL = os.getenv("FAZERCARDS_BASE_URL", "https://api.fazercards.com/v1")

CARD_NUMBER = "+992935710406"
CARD_BANKS = "Эсхата Онлайн 🏦 / ICB Mobile 📱"
BOT_NAME = "TAJ.DONAT.FF"
SHOP_NAME = "FF Almaz Shop 💎"

logging.basicConfig(level=logging.INFO)

# --- DATABASE ---
con = sqlite3.connect("almaz.db", check_same_thread=False)
cur = con.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER UNIQUE, balance TEXT DEFAULT '0')""")
con.commit()

def get_balance(tid):
    cur.execute("SELECT balance FROM users WHERE telegram_id=?", (tid,))
    r = cur.fetchone()
    return Decimal(r[0]) if r and r[0] else Decimal("0")

def check_fazercards_nick(player_id):
    try:
        headers = {"Authorization": f"Bearer {FAZERCARDS_API_KEY}", "Content-Type": "application/json"}
        resp = requests.post(f"{FAZERCARDS_BASE_URL}/check", json={"player_id": player_id, "region": "ME"}, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("nickname") or data.get("name") or "Ёфт шуд"
        return "Санҷида нашуд"
    except:
        return "Санҷида нашуд"

def main_menu():
    return ReplyKeyboardMarkup([["👤 Профил","💎 Хариди Алмаз"],["💰 Баланс","ℹ️ Кӯмак"]], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Салом! 💎\nБот: @{BOT_NAME}\n\n💳 {CARD_NUMBER}\n🏦 {CARD_BANKS}\n\nID-и худро барои хариди автоматӣ равон кн!", reply_markup=main_menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "💎 Хариди Алмаз":
        context.user_data["step"] = "ask_id"
        await update.message.reply_text("🆔 ID-и Free Fire-и худро равон кн:")
    elif text == "💰 Баланс":
        await update.message.reply_text(f"💰 Баланс: {get_balance(update.effective_user.id)} сом")
    elif context.user_data.get("step") == "ask_id" and text.isdigit():
        player_id = text
        context.user_data["player_id"] = player_id
        await update.message.reply_text(f"⏳ ID {player_id} санҷида истодааст...")
        nickname = check_fazercards_nick(player_id)
        context.user_data["nickname"] = nickname
        kb = [[InlineKeyboardButton("100 💎 - 12.34 сом", callback_data="buy_100")],
              [InlineKeyboardButton("310 💎 - 35 сом", callback_data="buy_310")],
              [InlineKeyboardButton("520 💎 - 60 сом", callback_data="buy_520")],
              [InlineKeyboardButton("1060 💎 - 115 сом", callback_data="buy_1060")]]
        await update.message.reply_text(f"✅ ID: {player_id}\n👤 Ник: {nickname}\n🌍 ME\nИнтихоб кн:", reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("buy_"):
        diamonds = query.data.split("_")[1]
        prices = {"100": "12.34", "310": "35", "520": "60", "1060": "115"}
        price = prices.get(diamonds, "0")
        player_id = context.user_data.get("player_id", "???")
        nickname = context.user_data.get("nickname", "???")

        await query.message.reply_text(f"⏳ {diamonds} 💎 барои {player_id} ({nickname}) аз Fazercards фиристода истодааст...")

        # === АВТОМАТ АЗ FAZERCARDS ===
        ok = False
        resp_text = ""
        try:
            headers = {"Authorization": f"Bearer {FAZERCARDS_API_KEY}", "Content-Type": "application/json"}
            payload = {"player_id": player_id, "diamonds": int(diamonds), "region": "ME", "external_id": f"{query.from_user.id}_{player_id}_{diamonds}"}
            r = requests.post(f"{FAZERCARDS_BASE_URL}/order", json=payload, headers=headers, timeout=20)
            resp_text = r.text
            ok = r.status_code == 200
            logging.info(f"Fazercards order {r.status_code}: {resp_text}")
        except Exception as e:
            resp_text = str(e)
            logging.error(f"Auto order error: {e}")

        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        if ok:
            status = "✅ АЛМАЗ АЗ FAZERCARDS ФИРИСТОДА ШУД! 1-5 дақ меояд!"
        else:
            status = "⏳ Заказ қабул шуд! Админ дастӣ мефиристад"

        receipt = f"""🧾 ЧЕК - {SHOP_NAME}
🤖 @{BOT_NAME}
{status}

🆔 ID: {player_id}
👤 Ник: {nickname}
💎 Алмаз: {diamonds}
💰 Нарх: {price} сом

💳 Пардохт: {CARD_NUMBER}
🏦 {CARD_BANKS}
📅 {now}
"""
        await query.message.reply_text(receipt)

        if ADMIN_ID:
            try:
                await context.bot.send_message(ADMIN_ID, f"🔔 ЗАКАЗИ АВТОМАТ\n{receipt}\n\nFazercards javob: {resp_text[:1000]}")
            except: pass

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
