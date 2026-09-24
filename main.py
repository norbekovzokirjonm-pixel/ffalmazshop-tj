import os, logging, sqlite3
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = "@Zokirjon0555"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN ёфт нашуд!")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

conn = sqlite3.connect('taj_donat.db', check_same_thread=False)
cur = conn.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT, balance REAL DEFAULT 0, referrals INTEGER DEFAULT 0, invited_by INTEGER)')
conn.commit()

PRODUCTS = {
    "almaz": [("💎 110 Алмаз — 7.80с", "110 Алмаз", 7.8), ("💎 341 Алмаз — 24.6с", "341 Алмаз", 24.6), ("💎 572 Алмаз — 43.5с", "572 Алмаз", 43.5), ("💎 1166 Алмаз — 80с", "1166 Алмаз", 80), ("💎 2398 Алмаз — 183с", "2398 Алмаз", 183), ("💎 6160 Алмаз — 460с", "6160 Алмаз", 460)],
    "voucher": [("🎟️ ВАУЧЕР ХАФТА — 16с", "Хафта", 16), ("🎟️ ВАУЧЕР ЛАЙТ — 5.5с", "Лайт", 5.5), ("🎟️ ВАУЧЕР МОХОНА — 57.5с", "Мохона", 57.5)],
    "level": [("📈 Level Up 6 — 5.5с", "6", 5.5), ("📈 Level Up 10 — 6с", "10", 6), ("📈 Level Up 15 — 7с", "15", 7), ("📈 Level Up 20 — 8с", "20", 8), ("📈 Level Up 25 — 8с", "25", 8), ("📈 Level Up 30 — 9с", "30", 9)],
    "evo": [("⚡ Evo 3 руз — 10с", "3 руз", 10), ("⚡ Evo 7 руз — 15с", "7 руз", 15), ("⚡ Evo 30 руз — 32с", "30 руз", 32)]
}

def main_menu():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton("💎 Алмазхо"), KeyboardButton("👤 Профили ман")],
        [KeyboardButton("🎟️ Ваучерхо"), KeyboardButton("📈 Level Up")],
        [KeyboardButton("⚡ Evo Access"), KeyboardButton("💰 Баланс")],
        [KeyboardButton("🔗 Реферал"), KeyboardButton("📞 Админ")],
    ])

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    args = message.get_args()
    invited_by = int(args) if args and args.isdigit() and int(args)!= user_id else None
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (user_id, name, invited_by) VALUES (?,?,?)", (user_id, message.from_user.full_name, invited_by))
        if invited_by:
            cur.execute("UPDATE users SET referrals=referrals+1, balance=balance+1 WHERE user_id=?", (invited_by,))
        conn.commit()
    await message.answer(f"🔥 Хуш омадед ба TAJ DONAT.FF! 🇹🇯\n\n💎 Беҳтарин дӯкони Free Fire\n👇 Менюро интихоб кн:", reply_markup=main_menu())

@dp.message_handler(lambda m: m.text == "👤 Профили ман")
async def profile(message: types.Message):
    cur.execute("SELECT balance, referrals FROM users WHERE user_id=?", (message.from_user.id,))
    bal, refs = cur.fetchone() or (0,0)
    await message.answer(f"👤 Профил\n\n🆔 ID: {message.from_user.id}\n💰 Баланс: {bal}с\n👥 Даъват: {refs} нафар\n\n🔗 https://t.me/Tajdonat26_bot?start={message.from_user.id}")

@dp.message_handler(lambda m: m.text in ["💎 Алмазхо", "🎟️ Ваучерхо", "📈 Level Up", "⚡ Evo Access"])
async def shop(message: types.Message):
    cat = "almaz" if "Алмаз" in message.text else "voucher" if "Ваучер" in message.text else "level" if "Level" in message.text else "evo"
    kb = InlineKeyboardMarkup(row_width=1)
    for txt, _, price in PRODUCTS[cat]:
        kb.add(InlineKeyboardButton(txt, callback_data=f"buy_{price}_{txt}"))
    await message.answer(f"{message.text} - Интихоб кн:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("buy_"))
async def buy(call: types.CallbackQuery):
    _, price, name = call.data.split("_", 2)
    await call.message.answer(f"🛒 {name}\n💰 Нарх: {price}с\n\n📝 ID-и Free Fire-ро фирист!\n💳 Баъд ба Alif парто ва чекро ба {ADMIN_USERNAME} фирист!")
    await call.answer()

@dp.message_handler(lambda m: m.text == "💰 Баланс")
async def bal(message: types.Message):
    await message.answer(f"💰 Alif: +992 93 XXX XX XX\nЧекатонро ба {ADMIN_USERNAME} фиристед!")

@dp.message_handler(lambda m: m.text == "🔗 Реферал")
async def ref(message: types.Message):
    await message.answer(f"🔗 Линки шумо:\nhttps://t.me/Tajdonat26_bot?start={message.from_user.id}\n\n+1с барои ҳар нафар!")

@dp.message_handler(lambda m: m.text == "📞 Админ")
async def adm(message: types.Message):
    await message.answer(f"📞 {ADMIN_USERNAME}")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
