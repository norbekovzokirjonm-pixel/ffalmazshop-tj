import asyncio, logging, os, sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# === CONFIG ENV ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6439367152"))
FAZER_API_KEY = os.getenv("FAZER_API_KEY")
FAZER_CATEGORY = os.getenv("FAZER_CATEGORY", "free_fire_cis_auto")

# === КАРТАҲОИ ПАРДОХТ - ИНҶО РАҚАМҲОИ ХУДАТРО МОН ===
ESKHATA_CARD = os.getenv("ESKHATA_CARD", "935710406") # Рақами Эсхата
DC_CARD = os.getenv("DC_CARD", "992935710406") # DC
ALIF_CARD = os.getenv("ALIF_CARD", "935710406")

SUPPORT_USERNAME = "@Zokirjon0555"
SUBSCRIBE_URL = "https://t.me/otsivho"

PRODUCTS = {
    "110": ("💎 110 алмаз", 7.80, "110"),
    "341": ("💎 341 алмаз", 24.60, "341"),
    "572": ("💎 572 алмаз", 43.50, "572"),
    "1166": ("💎 1166 алмаз", 80.00, "1166"),
    "2398": ("💎 2398 алмаз", 183.00, "2398"),
    "6160": ("💎 6160 алмаз", 460.00, "6160"),
    "weekly": ("🎟️ Ваучер Ҳафта", 16.00, "weekly"),
    "lite": ("🎟️ Ваучер Лайт", 5.50, "lite"),
    "monthly": ("🎟️ Ваучер Моҳона", 57.50, "monthly"),
}

# Fazercards
fz = None
if FAZER_API_KEY:
    try:
        from fazercards import FazerCards
        fz = FazerCards(api_key=FAZER_API_KEY)
        logging.info(f"FazerCards connected: {FAZER_CATEGORY}")
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

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Донат кардан", callback_data="donate")],
        [InlineKeyboardButton(text="🌐 Магоза", callback_data="shop"), InlineKeyboardButton(text="👤 Профил", callback_data="profile")],
        [InlineKeyboardButton(text="ℹ️ Маълумот", callback_data="info"), InlineKeyboardButton(text="🆘 Дастгирӣ", callback_data="support")]
    ])
def subscribe_keyboard(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 Обуна шудан", url=SUBSCRIBE_URL)], [InlineKeyboardButton(text="✅ Ман обуна шудам", callback_data="check_sub")]])
def products_keyboard(): return InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💎 110 — 7.80с", callback_data="product_110"), InlineKeyboardButton(text="💎 341 — 24.60с", callback_data="product_341")],
    [InlineKeyboardButton(text="💎 572 — 43.50с", callback_data="product_572"), InlineKeyboardButton(text="💎 1166 — 80с", callback_data="product_1166")],
    [InlineKeyboardButton(text="💎 2398 — 183с", callback_data="product_2398"), InlineKeyboardButton(text="💎 6160 — 460с", callback_data="product_6160")],
    [InlineKeyboardButton(text="🎟️ Ваучерҳо", callback_data="vouchers")],
    [InlineKeyboardButton(text="🏠 Меню", callback_data="home")]
])
def voucher_keyboard(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎟️ Ҳафта — 16с", callback_data="product_weekly")],[InlineKeyboardButton(text="🎟️ Лайт — 5.5с", callback_data="product_lite")],[InlineKeyboardButton(text="🎟️ Моҳона — 57.5с", callback_data="product_monthly")],[InlineKeyboardButton(text="⬅️ Бозгашт", callback_data="shop")]])

def save_user(m: Message):
    cursor.execute("INSERT OR REPLACE INTO users (user_id, username, first_name, created_at) VALUES (?,?,?,COALESCE((SELECT created_at FROM users WHERE user_id=?),?))", (m.from_user.id, m.from_user.username or "", m.from_user.first_name or "", m.from_user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))); db.commit()

@dp.message(CommandStart())
async def start_handler(message: Message):
    save_user(message); await message.answer("🔥 <b>TAJ.DONAT.FF</b>\n💎 Донати Free Fire СНГ\n⚡ Зуд • Бехатар • 24/7", reply_markup=main_keyboard())

@dp.callback_query(F.data == "home")
async def home_handler(c: CallbackQuery): await c.message.edit_text("🔥 <b>TAJ.DONAT.FF</b>", reply_markup=main_keyboard()); await c.answer()
@dp.callback_query(F.data == "donate")
async def donate_handler(c: CallbackQuery): await c.message.edit_text("📢 Ба канали мо обуна шав!", reply_markup=subscribe_keyboard()); await c.answer()
@dp.callback_query(F.data == "check_sub")
async def check_sub_handler(c: CallbackQuery): await c.message.edit_text("💎 Маҳсулотро интихоб кн:", reply_markup=products_keyboard()); await c.answer("✅")
@dp.callback_query(F.data == "shop")
async def shop_handler(c: CallbackQuery): await c.message.edit_text("🌐 <b>МАГОЗА</b>\nНархҳо бо сомонӣ", reply_markup=products_keyboard()); await c.answer()
@dp.callback_query(F.data == "vouchers")
async def vouchers_handler(c: CallbackQuery): await c.message.edit_text("🎟️ <b>ВАУЧЕРҲО</b>", reply_markup=voucher_keyboard()); await c.answer()

@dp.callback_query(F.data.startswith("product_"))
async def product_handler(callback: CallbackQuery, state: FSMContext):
    key = callback.data.replace("product_", "")
    if key not in PRODUCTS: await callback.answer("Ёфт нашуд ❌"); return
    name, price, _ = PRODUCTS[key]
    await state.update_data(product=name, price=price, pkey=key)
    await callback.message.edit_text(f"🛒 {name}\n💰 {price:g} сомонӣ\n\n🆔 <b>Player ID</b>-ро фирист:")
    await state.set_state(OrderState.waiting_ff_id); await callback.answer()

@dp.message(OrderState.waiting_ff_id)
async def ff_id_handler(message: Message, state: FSMContext):
    ff_id = message.text.strip()
    if not ff_id.isdigit(): await message.answer("❌ ID танҳо рақам бошад"); return
    # Санҷиши ник тавассути Fazer агар бошад
    real_nick = None
    if fz:
        try:
            v = fz.topups.validate_id(category_id="free_fire", fields={"player_id": ff_id})
            real_nick = v.get("nickname") or v.get("name")
            if real_nick:
                await message.answer(f"✅ ID ёфт шуд!\n👤 Ник: <b>{real_nick}</b>\n\nАгар дуруст бошад, ҳамин ник бо <b>Да/Yes</b> тасдиқ кн, ё ники дигар навиш.")
                await state.update_data(ff_id=ff_id, real_nick=real_nick)
                await state.set_state(OrderState.waiting_nickname)
                return
        except Exception:
            pass
    await state.update_data(ff_id=ff_id)
    await message.answer("👤 Никнейматро фирист:"); await state.set_state(OrderState.waiting_nickname)

@dp.message(OrderState.waiting_nickname)
async def nickname_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    nick_input = message.text.strip()
    nickname = data.get("real_nick") if nick_input.lower() in ["да","yes","ха","дуруст"] else nick_input
    if len(nickname) < 2: await message.answer("❌ Ник кӯтоҳ аст"); return
    await state.update_data(nickname=nickname)
    d = await state.get_data()
    # Ин ҷо пардохт - 1-ум усул
    text = (
        f"💳 <b>ПАРДОХТ - ҚАДАМИ 1</b>\n\n"
        f"📦 {d['product']}\n🆔 ID: <code>{d['ff_id']}</code>\n👤 Ник: <b>{nickname}</b>\n💰 <b>{d['price']:g} сомонӣ</b>\n\n"
        f"🏦 <b>Усули 1 - Эсхата Онлайн:</b>\n<code>{ESKHATA_CARD}</code>\n\n"
        f"🏦 <b>Усули 2 - DC:</b>\n<code>{DC_CARD}</code>\n\n"
        f"🏦 <b>Усули 3 - Алиф:</b>\n<code>{ALIF_CARD}</code>\n\n"
        f"⚠️ Баъди пардохт 🧾 чекро ҳамчун <b>СУРАТ</b> фирист!\n"
        f"🌍 Регион: СНГ / CIS"
    )
    await message.answer(text); await state.set_state(OrderState.waiting_receipt)

@dp.message(OrderState.waiting_receipt, F.photo)
async def receipt_handler(message: Message, state: FSMContext):
    data = await state.get_data(); user = message.from_user
    cursor.execute("INSERT INTO orders (user_id, username, product, price, ff_id, nickname, status, created_at) VALUES (?,?,?,?,?,?,?,?)", (user.id, user.username or "", data["product"], data["price"], data["ff_id"], data["nickname"], "waiting_admin", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    order_id = cursor.lastrowid; db.commit()
    admin_text = f"🔥 <b>ФАРМОИШИ НАВ #{order_id}</b>\n👤 @{user.username or '—'} | <code>{user.id}</code>\n📦 {data['product']} | 💰 {data['price']:g}с\n🎮 ID: <code>{data['ff_id']}</code>\n👤 Ник: <b>{data['nickname']}</b>\n🌍 Регион: CIS"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ ҚАБУЛ + Fazer", callback_data=f"accept_{order_id}_{user.id}"), InlineKeyboardButton(text="❌ РАД", callback_data=f"reject_{order_id}_{user.id}")]])
    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=admin_text, reply_markup=kb)
    await message.answer(f"✅ Чек қабул шуд! №<b>#{order_id}</b>\nИнтизор шав, админ месанҷад ⏳"); await state.clear()

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
            # offer-ро аз рӯи калимаи 110, 341 ва ғ пайдо мекунем
            target = None
            for off in offers["offers"]:
                if row["product"].split()[1] in off["name"] or str(row["price"]) in off["name"]: target = off; break
            if not target: target = offers["offers"][0]
            order = fz.topups.order(category_id=FAZER_CATEGORY, offer_id=target["offer_id"], fields={"player_id": row["ff_id"]})
            fazer_msg = f"\n💎 Fazer Order: {order['order_id']} - {order.get('status','processing')}"
        except Exception as e: fazer_msg = f"\n⚠️ Fazer хато: {e}"; logging.error(e)
    cursor.execute("UPDATE orders SET status=? WHERE id=?", ("accepted", order_id)); db.commit()
    await bot.send_message(int(user_id), f"✅ Фармоиш #{order_id} қабул шуд!{fazer_msg}\n⚡ Ҳозир пур карда мешавад.")
    try: await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ ҚАБУЛ ШУД" + fazer_msg)
    except: pass
    await callback.answer("Қабул ✅")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_order(callback: CallbackQuery):
    if callback.from_user.id!= ADMIN_ID: return
    _, order_id, user_id = callback.data.split("_")
    cursor.execute("UPDATE orders SET status=? WHERE id=?", ("rejected", order_id)); db.commit()
    await bot.send_message(int(user_id), f"❌ Фармоиш #{order_id} рад шуд. 🆘 {SUPPORT_USERNAME}")
    await callback.answer("Рад ❌")

@dp.callback_query(F.data == "profile")
async def profile_handler(c: CallbackQuery):
    cursor.execute("SELECT COUNT(*) FROM orders WHERE user_id=?", (c.from_user.id,)); total = cursor.fetchone()[0]
    await c.message.edit_text(f"👤 Профил\n🆔 {c.from_user.id}\n📦 Фармоишҳо: {total}", reply_markup=main_keyboard()); await c.answer()
@dp.callback_query(F.data == "support")
async def support_handler(c: CallbackQuery): await c.message.edit_text(f"🆘 Дастгирӣ: {SUPPORT_USERNAME}", reply_markup=main_keyboard()); await c.answer()
@dp.callback_query(F.data == "info")
async def info_handler(c: CallbackQuery): await c.message.edit_text("ℹ️ TAJ.DONAT.FF - Донати СНГ 24/7", reply_markup=main_keyboard()); await c.answer()

async def main():
    logging.basicConfig(level=logging.INFO); await dp.start_polling(bot)
if __name__ == "__main__": asyncio.run(main())
