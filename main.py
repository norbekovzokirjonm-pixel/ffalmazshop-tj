import os, logging, sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN ёфт нашуд! Дар Render Environment гузор!")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# База
conn = sqlite3.connect("taj_donat.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, user_id INTEGER, username TEXT, diamond TEXT, price TEXT, game_id TEXT)")
conn.commit()

class OrderState(StatesGroup):
    waiting_id = State()

PACKS = {"10":"7 TJS", "50":"35 TJS", "110":"70 TJS", "560":"320 TJS", "1150":"650 TJS"}

def shop_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    for k,v in PACKS.items():
        kb.add(InlineKeyboardButton(f"{k} 💎 - {v}", callback_data=f"buy_{k}"))
    return kb

@dp.message_handler(commands=['start'])
async def start(m: types.Message):
    await m.answer(f"Салом {m.from_user.first_name}! 🇹🇯\n\nБа TAJ DONAT хуш омадед!\n💎 Арзонтарин алмазҳо:\n\n10💎 - 7 TJS\n50💎 - 35 TJS\n110💎 - 70 TJS\n560💎 - 320 TJS\n1150💎 - 650 TJS\n\n👇 Интихоб кн:", reply_markup=shop_kb())

@dp.callback_query_handler(lambda c: c.data.startswith('buy_'))
async def buy(call: types.CallbackQuery, state: FSMContext):
    pack = call.data.split("_")[1]
    await state.update_data(pack=pack, price=PACKS[pack])
    await call.message.answer(f"Шумо {pack} алмаз интихоб кардед\n🎮 ID-и Free Fire-ро нависед:")
    await OrderState.waiting_id.set()
    await call.answer()

@dp.message_handler(state=OrderState.waiting_id)
async def get_id(m: types.Message, state: FSMContext):
    data = await state.get_data()
    cur.execute("INSERT INTO orders (user_id, username, diamond, price, game_id) VALUES (?,?,?,?,?)", (m.from_user.id, m.from_user.username, data['pack'], data['price'], m.text))
    conn.commit()
    await m.answer(f"✅ Қабул шуд! {data['pack']} 💎 - ID: {m.text}\n💳 DC: 992... чекро фирист!")
    if ADMIN_ID:
        try:
            await bot.send_message(int(ADMIN_ID), f"🔥 Фармоиш: {data['pack']} 💎 | ID: {m.text} | @{m.from_user.username}")
        except: pass
    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
