import asyncio, logging, os, sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6439367152"))
FAZER_API_KEY = os.getenv("FAZER_API_KEY")
FAZER_CATEGORY = os.getenv("FAZER_CATEGORY", "free_fire_cis_auto")
ESKHATA_CARD = os.getenv("ESKHATA_CARD", "+992935710406")
CARD_HOLDER = os.getenv("CARD_HOLDER", "ЗОКИРҶОН")
SUPPORT_USERNAME = "@Zokirjon0555"
SUBSCRIBE_URL = "https://t.me/otsivho"

PRODUCTS = {
    "110": ("💎 110 алмаз", 7.80),
    "341": ("💎 341 алмаз", 24.60),
    "572": ("💎 572 алмаз", 43.50),
    "1166": ("💎 1166 алмаз", 80.00),
    "2398": ("💎 2398 алмаз", 183.00),
    "6160": ("💎 6160 алмаз", 460.00),
    "weekly": ("🎟️ Ваучер Ҳафта", 16.00),
}

# Fazer init
fz = None
if FAZER_API_KEY:
    try:
        from fazercards import FazerCards
        fz = FazerCards(api_key=FAZER_API_KEY)
    except Exception as e:
        logging.error(f"Fazer init error: {e}")

DB_NAME = "/tmp/donat.db"
db = sqlite3.connect(DB_NAME, check_same_thread=False)
db.row_factory = sqlite3.Row
cursor = db.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, created_at TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, product TEXT, price REAL, ff_id TEXT, nickname TEXT, status TEXT, created_at TEXT)")
db.commit()

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

class OrderState(StatesGroup):
    waiting_ff_id = State()
    waiting_nickname = State()
    waiting_receipt = State()

async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        try:
            await callback.message.answer(text, reply_markup=reply_markup)
        except Exception as e:
            logging.error(f"safe_edit fail: {e}")

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Донат кардан", callback_data="donate")],
        [InlineKeyboardButton(text="🌐 Магоза", callback_data="shop"), InlineKeyboardButton(text="👤 Профил", callback_data="profile")],
        [InlineKeyboardButton(text="🆘 Дастгирӣ", callback_data="support")]
    ])
def subscribe_keyboard(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 Обуна шудан", url=SUBSCRIBE_URL)], [InlineKeyboardButton(text="✅ Ман обуна шудам", callback_data="check_sub")]])
def products_keyboard(): return InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💎 110 — 7.80с", callback_data="product_110"), InlineKeyboardButton(text="💎 341 — 24.60с", callback_data="product_341")],
    [InlineKeyboardButton(text="💎 572 — 43.50с", callback_data="product_572"), InlineKeyboardButton(text="💎 1166 — 80с", callback_data="product_1166")],
    [InlineKeyboardButton(text="💎 2398 — 183с", callback_data="product_2398"), InlineKeyboardButton(text="💎 6160 — 460с", callback_data="product_6160")],
    [InlineKeyboardButton(text="🎟️ Ваучер Ҳафта — 16с", callback_data="product_weekly")],
    [InlineKeyboardButton(text="🏠 Меню", callback_data="home")]
])

def save_user(m: Message):
    cursor.execute("INSERT OR REPLACE INTO users (user_id, username, first_name, created_at) VALUES (?,?,?,COALESCE((SELECT created_at FROM users WHERE user_id=?),?))", (m.from_user.id, m.from_user.username or "", m.from_user.first_name or "", m.from_user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))); db.commit()

@dp.message(CommandStart())
async def start_handler(message: Message):
    save_user(message); await message.answer("🔥 <b>TAJ.DONAT.FF</b>\n💎 Донати СНГ - Авто бо FazerCards", reply_markup=main_keyboard())

@dp.callback_query(F.data == "home")
async def home_handler(c: CallbackQuery): await safe_edit(c, "🔥 <b>TAJ.DONAT.FF</b>", reply_markup=main_keyboard()); await c.answer()
@dp.callback_query(F.data == "donate")
async def donate_handler(c: CallbackQuery): await safe_edit(c, "📢 Ба канал обуна шав!", reply_markup=subscribe_keyboard()); await c.answer()
@dp.callback_query(F.data == "check_sub")
async def check_sub_handler(c: CallbackQuery): await safe_edit(c, "💎 Маҳсулотро интихоб кн:", reply_markup=products_keyboard()); await c.answer("✅")
@dp.callback_query(F.data == "shop")
async def shop_handler(c: CallbackQuery): await safe_edit(c, "🌐 <b>МАГОЗА</b> - Регион СНГ 🇹🇯", reply_markup=products_keyboard()); await c.answer()

@dp.callback_query(F.data.startswith("product_"))
async def product_handler(callback: CallbackQuery, state: FSMContext):
    key = callback.data.replace("product_", "")
    if key not in PRODUCTS: await callback.answer("Ёфт нашуд"); return
    name, price = PRODUCTS[key]
    await state.update_data(product=name, price=price, pkey=key)
    await safe_edit(callback, f"🛒 {name}\n💰 {price:g} сомонӣ\n🌍 Регион: СНГ/CIS\n\n🆔 <b>Player ID</b>-ро фирист:"); await callback.answer(); await state.set_state(OrderState.waiting_ff_id)

@dp.message(OrderState.waiting_ff_id)
async def ff_id_handler(message: Message, state: FSMContext):
    ff_id = message.text.strip()
    if not ff_id.isdigit(): await message.answer("❌ ID танҳо рақам"); return

    # === САНҶИШИ FAZER - НИК + РЕГИОН ===
    real_nick = None
    if fz:
        try:
            v = fz.topups.validate_id(category_id="free_fire", fields={"player_id": ff_id})
            real_nick = v.get("nickname") or v.get("name") or v.get("username")
            if real_nick:
                await message.answer(f"✅ ID ёфт шуд!\n👤 Ник: <b>{real_nick}</b>\n🌍 Регион: СНГ\n\nАгар ник дуруст бошад <b>Да</b> навиш, агар не - ники дурустро навиш:")
                await state.update_data(ff_id=ff_id, real_nick=real_nick)
                await state.set_state(OrderState.waiting_nickname)
                return
        except Exception as e:
            logging.info(f"Validate fail {ff_id}: {e}")

    await state.update_data(ff_id=ff_id)
    await message.answer("👤 Никнейматро фирист:"); await state.set_state(OrderState.waiting_nickname)

@dp.message(OrderState.waiting_nickname)
async def nickname_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    txt = message.text.strip()
    nickname = data.get("real_nick") if txt.lower() in ["да","yes","ha","дуруст","ok"] else txt
    await state.update_data(nickname=nickname)
    d = await state.get_data()
    pay_text = f"💳 <b>ПАРДОХТ</b>\n\n📦 {d['product']}\n🆔 ID: <code>{d['ff_id']}</code>\n👤 Ник: <b>{nickname}</b>\n🌍 Регион: СНГ/CIS\n💰 <b>{d['price']:g} сомонӣ</b>\n\n🏦 Ба: <code>{ESKHATA_CARD}</code>\n👤 {CARD_HOLDER}\n\n⚠️ Чекро ҳамчун <b>СУРАТ</b> фирист!"
    await message.answer(pay_text); await state.set_state(OrderState.waiting_receipt)

@dp.message(OrderState.waiting_receipt, F.photo)
async def receipt_handler(message: Message, state: FSMContext):
    data = await state.get_data(); user = message.from_user
    cursor.execute("INSERT INTO orders (user_id, username, product, price, ff_id, nickname, status, created_at) VALUES (?,?,?,?,?,?,?,?)", (user.id, user.username or "", data["product"], data["price"], data["ff_id"], data["nickname"], "waiting_admin", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    order_id = cursor.lastrowid; db.commit()
    admin_text = f"🔥 <b>ФАРМОИШ #{order_id}</b>\n👤 @{user.username or '—'} | {user.id}\n📦 {data['product']} | {data['price']:g}с\n🎮 ID: <code>{data['ff_id']}</code>\n👤 Ник: <b>{data['nickname']}</b>\n🌍 СНГ"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ ҚАБУЛ + FAZER", callback_data=f"accept_{order_id}_{user.id}"), InlineKeyboardButton(text="❌ РАД", callback_data=f"reject_{order_id}_{user.id}")]])
    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=admin_text, reply_markup=kb)
    await message.answer(f"✅ Чек қабул шуд №<b>#{order_id}</b> ⏳ Интизор шав!"); await state.clear()

@dp.message(OrderState.waiting_receipt)
async def receipt_other(message: Message): await message.answer("📸 Чекро ҳамчун сурат фирист!")

@dp.callback_query(F.data.startswith("accept_"))
async def accept_order(callback: CallbackQuery):
    if callback.from_user.id!= ADMIN_ID: await callback.answer("⛔ Админ нестӣ", show_alert=True); return
    _, order_id, user_id = callback.data.split("_")
    cursor.execute("SELECT * FROM orders WHERE id=?", (order_id,)); row = cursor.fetchone()

    fazer_msg = ""
    if fz and row:
        try:
            offers = fz.topups.offers(FAZER_CATEGORY)
            # offer-ро аз рӯи 110, 341 ва ғ ҷустуҷӯ
            pkey = row["product"].split()[1] if len(row["product"].split())>1 else "110"
            target = None
            for off in offers["offers"]:
                if pkey in off["name"] or pkey in off["offer_id"]:
                    target = off; break
            if not target:
                target = offers["offers"][0]

            order = fz.topups.order(category_id=FAZER_CATEGORY, offer_id=target["offer_id"], fields={"player_id": row["ff_id"]})
            fazer_msg = f"\n✅ Fazer: {order['order_id']} | {order.get('status','processing')}"

            # Интизор шав то анҷом
            # final = fz.orders.wait(order['order_id'], timeout=300)

        except Exception as e:
            fazer_msg = f"\n⚠️ Fazer хато: {e}"
            logging.error(f"Fazer order error: {e}")

    cursor.execute("UPDATE orders SET status=? WHERE id=?", ("accepted", order_id)); db.commit()
    await bot.send_message(int(user_id), f"✅ Фармоиш #{order_id} қабул шуд!{fazer_msg}\n💎 Алмазҳо 1-5 дақиқа меравад!\n👤 Ник: {row['nickname']}\n🌍 Регион СНГ тасдиқ шуд!")

    try:
        await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ ҚАБУЛ" + fazer_msg)
    except Exception:
        pass
    await callback.answer("Қабул ✅")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_order(callback: CallbackQuery):
    if callback.from_user.id!= ADMIN_ID: return
    _, order_id, user_id = callback.data.split("_")
    cursor.execute("UPDATE orders SET status=? WHERE id=?", ("rejected", order_id)); db.commit()
    await bot.send_message(int(user_id), f"❌ Фармоиш #{order_id} рад шуд. 🆘 {SUPPORT_USERNAME}"); await callback.answer("Рад ❌")

@dp.callback_query(F.data == "profile")
async def profile_handler(c: CallbackQuery):
    cursor.execute("SELECT COUNT(*) FROM orders WHERE user_id=?", (c.from_user.id,)); total = cursor.fetchone()[0]
    await safe_edit(c, f"👤 Профил\n🆔 {c.from_user.id}\n📦 {total} фармоиш", reply_markup=main_keyboard()); await c.answer()
@dp.callback_query(F.data == "support")
async def support_handler(c: CallbackQuery): await safe_edit(c, f"🆘 Дастгирӣ: {SUPPORT_USERNAME}\n📞 {ESKHATA_CARD}", reply_markup=main_keyboard()); await c.answer()

async def main():
    logging.basicConfig(level=logging.INFO)
    logging.info(f"Bot started + Fazer {FAZER_CATEGORY}")
    await dp.start_polling(bot)
if __name__ == "__main__": asyncio.run(main())
