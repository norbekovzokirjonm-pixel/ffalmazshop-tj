import asyncio
import io
import logging
import os
import sqlite3
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@Zokirjon0555")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Put your Telegram numeric ID here.
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@otsivho")
BOT_NAME = os.getenv("BOT_NAME", "TAJ.DONAT.FF")
SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/otsivho")

PAYMENT_PHONE = os.getenv("PAYMENT_PHONE", "+992935710406")
ESKHATA_TEXT = os.getenv("ESKHATA_TEXT", "Эсхата Онлайн")
ICB_TEXT = os.getenv("ICB_TEXT", "ICB Mobile")

FAZER_API_KEY = os.getenv("FAZER_API_KEY", "")
FAZER_BASE = os.getenv("FAZER_BASE", "https://api.fzr.cards/api/v2")

# Optional: if you know the exact FazerCards category, set it here.
# Otherwise the bot searches the catalog for Free Fire.
FAZER_FREE_FIRE_CATEGORY = os.getenv("FAZER_FREE_FIRE_CATEGORY", "")

DB_PATH = os.getenv("DB_PATH", "bot.db")
RECEIPT_DIR = Path(os.getenv("RECEIPT_DIR", "receipts"))
RECEIPT_DIR.mkdir(exist_ok=True)

# Customer-facing prices in Tajik somoni.
PRODUCTS = [
    ("ff_110", "💎 110 Алмаз", Decimal("7.80"), 110),
    ("ff_341", "💎 341 Алмаз", Decimal("24.60"), 341),
    ("ff_572", "💎 572 Алмаз", Decimal("43.50"), 572),
    ("ff_1166", "💎 1166 Алмаз", Decimal("80.00"), 1166),
    ("ff_2398", "💎 2398 Алмаз", Decimal("183.00"), 2398),
    ("ff_6160", "💎 6160 Алмаз", Decimal("460.00"), 6160),
    ("week", "🎟️ Ваучер Ҳафта", Decimal("16.00"), None),
    ("lite", "🎟️ Ваучер Лайт", Decimal("5.50"), None),
    ("monthly", "🎟️ Ваучер Моҳона", Decimal("57.50"), None),
    ("level_6", "📈 Level Up Package 6", Decimal("5.50"), None),
    ("level_10", "📈 Level Up Package 10", Decimal("6.00"), None),
    ("level_15", "📈 Level Up Package 15", Decimal("7.00"), None),
    ("level_20", "📈 Level Up Package 20", Decimal("8.00"), None),
    ("level_25", "📈 Level Up Package 25", Decimal("8.00"), None),
    ("level_30", "📈 Level Up Package 30", Decimal("9.00"), None),
    ("evo_30", "⚡ Evo Access — 30 рӯз", Decimal("32.00"), None),
    ("evo_7", "⚡ Evo Access — 7 рӯз", Decimal("15.00"), None),
    ("evo_3", "⚡ Evo Access — 3 рӯз", Decimal("10.00"), None),
]

TOPUP_AMOUNTS = [20, 50, 70, 100, 150, 200, 300, 500]

PRODUCT_MAP = {p[0]: p for p in PRODUCTS}


# =========================
# DATABASE
# =========================
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        tg_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        balance REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        method TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        proof_file_id TEXT,
        created_at TEXT NOT NULL,
        approved_at TEXT
    );

    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no INTEGER UNIQUE NOT NULL,
        tg_id INTEGER NOT NULL,
        product_id TEXT NOT NULL,
        product_name TEXT NOT NULL,
        price REAL NOT NULL,
        player_id TEXT NOT NULL,
        nickname TEXT NOT NULL,
        region TEXT NOT NULL,
        fazer_order_id TEXT,
        status TEXT NOT NULL DEFAULT 'created',
        created_at TEXT NOT NULL,
        completed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)
    row = con.execute("SELECT value FROM settings WHERE key='next_order_no'").fetchone()
    if not row:
        con.execute(
            "INSERT INTO settings(key,value) VALUES('next_order_no','21345')"
        )
    con.commit()
    con.close()


def ensure_user(user):
    con = db()
    con.execute(
        """
        INSERT INTO users(tg_id, username, first_name, created_at)
        VALUES(?,?,?,?)
        ON CONFLICT(tg_id) DO UPDATE SET username=excluded.username,
                                          first_name=excluded.first_name
        """,
        (user.id, user.username or "", user.first_name or "", datetime.now().isoformat()),
    )
    con.commit()
    con.close()


def get_balance(tg_id):
    con = db()
    row = con.execute("SELECT balance FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    con.close()
    return Decimal(str(row["balance"] if row else 0))


def add_balance(tg_id, amount):
    con = db()
    con.execute("UPDATE users SET balance=balance+? WHERE tg_id=?", (float(amount), tg_id))
    con.commit()
    con.close()


def take_balance(tg_id, amount):
    con = db()
    row = con.execute("SELECT balance FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    if not row or Decimal(str(row["balance"])) < amount:
        con.close()
        return False
    con.execute("UPDATE users SET balance=balance-? WHERE tg_id=?", (float(amount), tg_id))
    con.commit()
    con.close()
    return True


def refund_balance(tg_id, amount):
    add_balance(tg_id, amount)


def create_order(tg_id, product, player_id, nickname, region):
    con = db()
    row = con.execute("SELECT value FROM settings WHERE key='next_order_no'").fetchone()
    order_no = int(row["value"])
    con.execute(
        "UPDATE settings SET value=? WHERE key='next_order_no'",
        (str(order_no + 1),),
    )
    con.execute(
        """
        INSERT INTO orders(
            order_no,tg_id,product_id,product_name,price,player_id,nickname,region,status,created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            order_no, tg_id, product[0], product[1], float(product[2]),
            player_id, nickname, region, "created", datetime.now().isoformat()
        ),
    )
    order_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.commit()
    con.close()
    return order_id, order_no


def update_order(order_id, **fields):
    con = db()
    sets = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [order_id]
    con.execute(f"UPDATE orders SET {sets} WHERE id=?", vals)
    con.commit()
    con.close()


def get_order(order_id):
    con = db()
    row = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    con.close()
    return row


def next_pending_orders():
    con = db()
    rows = con.execute(
        "SELECT * FROM orders WHERE status IN ('processing','submitted') AND fazer_order_id IS NOT NULL"
    ).fetchall()
    con.close()
    return rows


# =========================
# TELEGRAM KEYBOARDS
# =========================
def main_menu():
    b = InlineKeyboardBuilder()
    b.button(text="💎 Free Fire СНГ", callback_data="products")
    b.button(text="💳 Баланс", callback_data="balance")
    b.button(text="➕ Пур кардани баланс", callback_data="topup")
    b.button(text="📦 Харидҳои ман", callback_data="my_orders")
    b.button(text="⭐ Отзыв", url=SUPPORT_URL)
    b.button(text="👨‍💼 Админ", url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")
    b.adjust(1, 2, 2, 1, 1)
    return b.as_markup()


def products_kb():
    b = InlineKeyboardBuilder()
    for pid, name, price, _ in PRODUCTS:
        b.button(text=f"{name} — {price:g}с", callback_data=f"buy:{pid}")
    b.button(text="🛒 Якчанд маҳсулот", callback_data="multi_buy")
    b.button(text="⬅️ Бозгашт", callback_data="home")
    b.adjust(1)
    return b.as_markup()


def topup_amount_kb():
    b = InlineKeyboardBuilder()
    for amount in TOPUP_AMOUNTS:
        b.button(text=f"{amount}с", callback_data=f"topup_amt:{amount}")
    b.button(text="⬅️ Бозгашт", callback_data="home")
    b.adjust(4, 4, 1)
    return b.as_markup()


def payment_method_kb(amount):
    b = InlineKeyboardBuilder()
    b.button(text=f"💳 {ESKHATA_TEXT}", callback_data=f"paymethod:eskhata:{amount}")
    b.button(text=f"💳 {ICB_TEXT}", callback_data=f"paymethod:icb:{amount}")
    b.button(text="⬅️ Бозгашт", callback_data="topup")
    b.adjust(1)
    return b.as_markup()


def admin_payment_kb(payment_id):
    b = InlineKeyboardBuilder()
    b.button(text="✅ ҚАБУЛ", callback_data=f"approve_payment:{payment_id}")
    b.button(text="❌ РАД", callback_data=f"reject_payment:{payment_id}")
    b.adjust(2)
    return b.as_markup()


# =========================
# STATES
# =========================
class TopupState(StatesGroup):
    waiting_proof = State()


class OrderState(StatesGroup):
    waiting_id = State()
    waiting_nickname = State()
    waiting_region = State()


# =========================
# FAZERCARDS
# =========================
class FazerCards:
    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            timeout=25,
            headers={
                "X-API-Key": api_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    async def close(self):
        await self.client.aclose()

    async def get(self, path, params=None):
        r = await self.client.get(f"{self.base_url}{path}", params=params)
        r.raise_for_status()
        return r.json()

    async def post(self, path, body):
        headers = {"Idempotency-Key": str(uuid.uuid4())}
        r = await self.client.post(f"{self.base_url}{path}", json=body, headers=headers)
        r.raise_for_status()
        return r.json()

    async def find_free_fire_category(self):
        if FAZER_FREE_FIRE_CATEGORY:
            return FAZER_FREE_FIRE_CATEGORY

        data = await self.get("/topups", {"limit": 100})
        for item in data.get("items", []):
            text = f"{item.get('name','')} {item.get('category_id','')}".lower()
            if "free fire" in text or "free_fire" in text:
                return item.get("category_id")
        return None

    async def offers(self, category_id):
        return await self.get("/topups/offers", {"category_id": category_id})

    async def validate_free_fire(self, player_id):
        # Validation namespace is separate from purchasable top-up category.
        body = {
            "category_id": "free_fire",
            "fields": {"player_id": player_id},
        }
        try:
            return await self.post("/topups/validate-id", body)
        except Exception:
            return {"valid": None}

    async def place_order(self, category_id, offer_id, fields):
        return await self.post(
            "/topups/order",
            {
                "category_id": category_id,
                "offer_id": offer_id,
                "fields": fields,
            },
        )

    async def get_order(self, fazer_order_id):
        return await self.get(f"/orders/{fazer_order_id}")


# =========================
# RECEIPT IMAGE
# =========================
def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for f in candidates:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def make_receipt(order, status="accepted"):
    W, H = 1100, 1500
    img = Image.new("RGB", (W, H), "#111216")
    d = ImageDraw.Draw(img)

    # Orange frame / green approval style similar to the provided examples.
    orange = "#ff8a00"
    green = "#20d56a"
    red = "#ff4d4d"
    white = "#f4f4f4"
    gray = "#a7a7ad"

    d.rounded_rectangle((35, 35, W-35, H-35), radius=35, outline=orange, width=4)
    d.rounded_rectangle((430, 80, 670, 320), radius=45, outline=orange, width=4)

    # Check / status icon
    cx, cy = 550, 420
    fill = green if status == "accepted" else red
    d.ellipse((cx-70, cy-70, cx+70, cy+70), fill=fill)
    if status == "accepted":
        d.line((cx-35, cy, cx-8, cy+28), fill="white", width=14)
        d.line((cx-8, cy+28, cx+42, cy-35), fill="white", width=14)
        status_text = "ПАРДОХТ ТАСДИҚ ШУД"
    else:
        d.line((cx-30, cy-30, cx+30, cy+30), fill="white", width=12)
        d.line((cx+30, cy-30, cx-30, cy+30), fill="white", width=12)
        status_text = "ХАТО / БОЗПАС"

    d.text((550, 350), BOT_NAME, anchor="ma", font=font(46, True), fill=orange)
    d.text((550, 515), status_text, anchor="ma", font=font(40, True), fill=white)

    title_y = 590
    d.text((90, title_y), "МАЪЛУМОТИ ФАРМОИШ", font=font(34, True), fill=gray)
    d.rounded_rectangle((70, title_y+65, W-70, 1150), radius=28, fill="#1b1c22", outline="#3b3c45", width=2)

    rows = [
        ("Фармоиш №", f"#{order['order_no']}"),
        ("ID аккаунт", order["player_id"]),
        ("Ном", order["nickname"]),
        ("Регион", order["region"]),
        ("Маҳсулот", order["product_name"]),
        ("Маблағ", f"{order['price']:.2f} сом"),
    ]

    y = title_y + 105
    for label, value in rows:
        d.text((110, y), label, font=font(27), fill=gray)
        d.text((990, y), str(value), anchor="ra", font=font(28, True), fill=white)
        d.line((105, y+58, 995, y+58), fill="#303139", width=2)
        y += 100

    d.rounded_rectangle((70, 1200, W-70, 1320), radius=28, outline=orange, width=3)
    d.text((550, 1260), "ПАРДОХТ ТАСДИҚ ШУД", anchor="mm", font=font(36, True), fill=white)

    d.text((550, 1370), BOT_NAME, anchor="ma", font=font(30, True), fill=orange)

    path = RECEIPT_DIR / f"receipt_{order['order_no']}.png"
    img.save(path, "PNG")
    return path


# =========================
# BOT
# =========================
bot = Bot(BOT_TOKEN)
dp = Dispatcher()
fz = FazerCards(FAZER_API_KEY, FAZER_BASE)


async def is_subscribed(user_id: int) -> bool:
    if not CHANNEL_USERNAME:
        return True
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in {"member", "administrator", "creator"}
    except Exception:
        # If the bot cannot inspect the channel, don't lock out customers.
        return True


def subscribe_kb():
    b = InlineKeyboardBuilder()
    b.button(text="📢 Обуна шудан", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")
    b.button(text="✅ Ман обуна шудам", callback_data="check_sub")
    b.adjust(1)
    return b.as_markup()


@dp.message(CommandStart())
async def start(message: Message):
    ensure_user(message.from_user)
    if not await is_subscribed(message.from_user.id):
        await message.answer(
            "📢 Барои истифодаи бот аввал ба канали мо обуна шавед.\n"
            "Баъд «Ман обуна шудам»-ро пахш кунед.",
            reply_markup=subscribe_kb(),
        )
        return

    await message.answer(
        f"🔥 <b>{BOT_NAME}</b>",
        reply_markup=main_menu(),
    )


@dp.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery):
    if await is_subscribed(call.from_user.id):
        await call.message.edit_text("✅ Обуна тасдиқ шуд.", reply_markup=main_menu())
    else:
        await call.answer("❌ Аввал ба канал обуна шавед.", show_alert=True)
    await call.answer()


@dp.callback_query(F.data == "home")
async def home(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(f"🔥 <b>{BOT_NAME}</b>", reply_markup=main_menu())
    await call.answer()


@dp.callback_query(F.data == "balance")
async def balance(call: CallbackQuery):
    bal = get_balance(call.from_user.id)
    await call.message.edit_text(
        f"💳 <b>Баланс</b>\n\n"
        f"💰 Баланси шумо: <b>{bal:.2f} сом</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Пур кардан", callback_data="topup")],
            [InlineKeyboardButton(text="⬅️ Бозгашт", callback_data="home")],
        ]),
    )
    await call.answer()


@dp.callback_query(F.data == "topup")
async def topup(call: CallbackQuery):
    await call.message.edit_text(
        "💳 <b>Маблағи пуркунии балансро интихоб кунед:</b>",
        reply_markup=topup_amount_kb(),
    )
    await call.answer()


@dp.callback_query(F.data.startswith("topup_amt:"))
async def topup_amount(call: CallbackQuery):
    amount = int(call.data.split(":")[1])
    await call.message.edit_text(
        f"💳 Шумо <b>{amount} сом</b> интихоб кардед.\n\n"
        "Усули пардохтро интихоб кунед:",
        reply_markup=payment_method_kb(amount),
    )
    await call.answer()


@dp.callback_query(F.data.startswith("paymethod:"))
async def payment_method(call: CallbackQuery, state: FSMContext):
    _, method, amount_s = call.data.split(":")
    amount = int(amount_s)
    method_name = ESKHATA_TEXT if method == "eskhata" else ICB_TEXT

    await state.update_data(amount=amount, method=method_name)
    await state.set_state(TopupState.waiting_proof)

    await call.message.edit_text(
        f"💳 <b>Пур кардани баланс — {amount} сом</b>\n\n"
        f"🏦 Усул: <b>{method_name}</b>\n"
        f"📱 Рақам: <code>{PAYMENT_PHONE}</code>\n\n"
        "1) Ба ҳамин рақам пардохт кунед.\n"
        "2) Скриншот/чеки пардохтро ҳамин ҷо фиристед.\n"
        "3) Админ пардохтро тасдиқ мекунад ва баланс автоматӣ зиёд мешавад.\n\n"
        "⚠️ То тасдиқи админ баланс зиёд намешавад.",
    )
    await call.answer()


@dp.message(TopupState.waiting_proof, F.photo)
async def payment_proof(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("amount"):
        await state.clear()
        await message.answer("❌ Сессия гузаштааст. Аз меню дубора балансро пур кунед.")
        return

    amount = Decimal(str(data["amount"]))
    method = data["method"]
    file_id = message.photo[-1].file_id

    con = db()
    cur = con.execute(
        """
        INSERT INTO payments(tg_id,amount,method,status,proof_file_id,created_at)
        VALUES(?,?,?,?,?,?)
        """,
        (message.from_user.id, float(amount), method, "pending", file_id, datetime.now().isoformat()),
    )
    payment_id = cur.lastrowid
    con.commit()
    con.close()

    await state.clear()

    await message.answer(
        f"✅ Чек қабул шуд.\n\n"
        f"💰 Маблағ: <b>{amount:.2f} сом</b>\n"
        "⏳ Интизор шавед, админ пардохтро месанҷад.",
        reply_markup=main_menu(),
    )

    if ADMIN_ID:
        caption = (
            f"💳 <b>ПАРДОХТИ НАВ #{payment_id}</b>\n\n"
            f"👤 User ID: <code>{message.from_user.id}</code>\n"
            f"👤 @{message.from_user.username or '—'}\n"
            f"💰 Маблағ: <b>{amount:.2f} сом</b>\n"
            f"🏦 Усул: <b>{method}</b>"
        )
        await bot.send_photo(
            ADMIN_ID,
            file_id,
            caption=caption,
            reply_markup=admin_payment_kb(payment_id),
        )


@dp.message(TopupState.waiting_proof)
async def payment_proof_wrong(message: Message):
    await message.answer("📸 Лутфан чеки пардохтро ҳамчун сурат фиристед.")


@dp.callback_query(F.data.startswith("approve_payment:"))
async def approve_payment(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Дастрасӣ надоред.", show_alert=True)
        return

    payment_id = int(call.data.split(":")[1])
    con = db()
    row = con.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone()
    if not row:
        con.close()
        await call.answer("Пардохт ёфт нашуд.", show_alert=True)
        return
    if row["status"] != "pending":
        con.close()
        await call.answer("Ин пардохт аллакай коркард шудааст.", show_alert=True)
        return

    con.execute(
        "UPDATE payments SET status='approved', approved_at=? WHERE id=?",
        (datetime.now().isoformat(), payment_id),
    )
    con.commit()
    con.close()

    add_balance(row["tg_id"], Decimal(str(row["amount"])))

    await call.message.edit_caption(
        caption=(call.message.caption or "") + "\n\n✅ <b>ТАСДИҚ ШУД</b>",
        reply_markup=None,
    )

    await bot.send_message(
        row["tg_id"],
        f"✅ <b>Пардохт тасдиқ шуд!</b>\n\n"
        f"💰 +{row['amount']:.2f} сом\n"
        f"💳 Баланси нав: <b>{get_balance(row['tg_id']):.2f} сом</b>",
    )
    await call.answer("Тасдиқ шуд.")


@dp.callback_query(F.data.startswith("reject_payment:"))
async def reject_payment(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Дастрасӣ надоред.", show_alert=True)
        return

    payment_id = int(call.data.split(":")[1])
    con = db()
    row = con.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone()
    if not row:
        con.close()
        await call.answer("Пардохт ёфт нашуд.", show_alert=True)
        return
    if row["status"] != "pending":
        con.close()
        await call.answer("Ин пардохт аллакай коркард шудааст.", show_alert=True)
        return

    con.execute("UPDATE payments SET status='rejected' WHERE id=?", (payment_id,))
    con.commit()
    con.close()

    await call.message.edit_caption(
        caption=(call.message.caption or "") + "\n\n❌ <b>РАД ШУД</b>",
        reply_markup=None,
    )
    await bot.send_message(
        row["tg_id"],
        "❌ Пардохти шумо тасдиқ нашуд. Агар маблағро воқеан пардохт карда бошед, ба админ муроҷиат кунед.",
    )
    await call.answer("Рад шуд.")


@dp.callback_query(F.data == "products")
async def products(call: CallbackQuery):
    await call.message.edit_text(
        "💎 <b>FREE FIRE СНГ 🇹🇯</b>\n\n"
        "Маҳсулотро интихоб кунед:",
        reply_markup=products_kb(),
    )
    await call.answer()


@dp.callback_query(F.data.startswith("buy:"))
async def buy_start(call: CallbackQuery, state: FSMContext):
    pid = call.data.split(":")[1]
    if pid not in PRODUCT_MAP:
        await call.answer("Маҳсулот ёфт нашуд.", show_alert=True)
        return

    product = PRODUCT_MAP[pid]
    bal = get_balance(call.from_user.id)

    if bal < product[2]:
        await call.message.edit_text(
            f"❌ Баланс нокифоя аст.\n\n"
            f"💰 Нарх: <b>{product[2]:.2f} сом</b>\n"
            f"💳 Баланси шумо: <b>{bal:.2f} сом</b>\n\n"
            "Аввал балансро пур кунед.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Пур кардани баланс", callback_data="topup")],
                [InlineKeyboardButton(text="⬅️ Бозгашт", callback_data="products")],
            ]),
        )
        await call.answer()
        return

    await state.update_data(product_id=pid)
    await state.set_state(OrderState.waiting_id)
    await call.message.edit_text(
        f"🛒 <b>{product[1]}</b>\n"
        f"💰 Нарх: <b>{product[2]:.2f} сом</b>\n\n"
        "🔢 UID-и Free Fire-ро фиристед:"
    )
    await call.answer()


@dp.message(OrderState.waiting_id)
async def order_id(message: Message, state: FSMContext):
    player_id = message.text.strip()
    if not player_id.isdigit() or len(player_id) < 5:
        await message.answer("❌ UID нодуруст аст. Танҳо рақам фиристед.")
        return

    await state.update_data(player_id=player_id)
    await state.set_state(OrderState.waiting_nickname)
    await message.answer("👤 Nickname-и аккаунтро фиристед:")


@dp.message(OrderState.waiting_nickname)
async def order_nickname(message: Message, state: FSMContext):
    nickname = message.text.strip()
    if len(nickname) < 1 or len(nickname) > 50:
        await message.answer("❌ Nickname нодуруст аст.")
        return

    await state.update_data(nickname=nickname)
    await state.set_state(OrderState.waiting_region)
    await message.answer(
        "🌍 Region-ро фиристед.\nМисол: <code>CIS</code> ё <code>RU</code>"
    )


@dp.message(OrderState.waiting_region)
async def order_region(message: Message, state: FSMContext):
    region = message.text.strip()
    if len(region) < 1 or len(region) > 30:
        await message.answer("❌ Region нодуруст аст.")
        return

    data = await state.get_data()
    pid = data["product_id"]
    product = PRODUCT_MAP[pid]
    price = product[2]

    # Re-check balance immediately before charging.
    if get_balance(message.from_user.id) < price:
        await state.clear()
        await message.answer(
            "❌ Баланс дигар кофӣ нест. Балансро пур кунед.",
            reply_markup=main_menu(),
        )
        return

    # Create local order number before the provider call.
    order_id, order_no = create_order(
        message.from_user.id, product, data["player_id"], data["nickname"], region
    )

    # Deduct customer balance first; if FazerCards fails, it is refunded.
    if not take_balance(message.from_user.id, price):
        update_order(order_id, status="failed")
        await state.clear()
        await message.answer("❌ Баланс нокифоя шуд.", reply_markup=main_menu())
        return

    await message.answer(
        f"⏳ Фармоиш <b>#{order_no}</b> қабул шуд.\n"
        "🔄 Ҳисоби Free Fire санҷида шуда истодааст..."
    )

    try:
        category_id = await fz.find_free_fire_category()
        if not category_id:
            raise RuntimeError("Free Fire category not found in FazerCards catalog")

        offers_data = await fz.offers(category_id)
        offers = offers_data.get("offers", [])

        # Best-effort offer matching by diamond/package number/name.
        offer = match_offer(product, offers)
        if not offer:
            raise RuntimeError(f"No FazerCards offer matched {product[1]}")

        # Read provider fields instead of guessing them.
        fields_schema = offers_data.get("fields", [])
        fields = {}
        for field in fields_schema:
            key = field.get("key", "")
            kl = key.lower()
            if kl in {"player_id", "uid", "id", "game_id"}:
                fields[key] = data["player_id"]
            elif "region" in kl:
                fields[key] = region
            elif "nick" in kl or "name" in kl:
                fields[key] = data["nickname"]

        # If provider requires a field we did not map, fail safely rather than send bad data.
        required = [f.get("key") for f in fields_schema if f.get("required", True)]
        missing = [k for k in required if k not in fields]
        if missing:
            raise RuntimeError("FazerCards requires fields not mapped: " + ", ".join(missing))

        result = await fz.place_order(
            category_id=category_id,
            offer_id=offer["offer_id"],
            fields=fields,
        )

        provider_order = result.get("order", result)
        provider_id = provider_order.get("id")
        status = provider_order.get("status", "processing")

        update_order(
            order_id,
            fazer_order_id=provider_id,
            status="processing" if status in {"processing", "pending"} else status,
        )

        await message.answer(
            f"✅ Фармоиш <b>#{order_no}</b> ба FazerCards фиристода шуд.\n"
            f"📦 Status: <b>{status}</b>\n\n"
            "Пас аз тасдиқи delivery чек автоматӣ фиристода мешавад.",
        )

    except Exception as exc:
        logging.exception("FazerCards order failed")
        refund_balance(message.from_user.id, price)
        update_order(order_id, status="failed")
        await message.answer(
            f"❌ Фармоиш <b>#{order_no}</b> иҷро нашуд.\n"
            "💰 Маблағ ба баланси шумо баргардонида шуд.\n\n"
            "Бо админ тамос гиред агар мушкил такрор шавад.",
            reply_markup=main_menu(),
        )
        if ADMIN_ID:
            await bot.send_message(
                ADMIN_ID,
                f"⚠️ FazerCards error\nOrder #{order_no}\nUser {message.from_user.id}\n{exc}",
            )

    await state.clear()


def match_offer(product, offers):
    pid, name, price, quantity = product
    text = name.lower()

    # Prefer exact numeric diamond amount.
    if quantity:
        for o in offers:
            s = f"{o.get('name','')} {o.get('offer_id','')}".lower()
            if str(quantity) in s and ("diamond" in s or "diamond" in text or "almaz" in s):
                return o
        for o in offers:
            s = f"{o.get('name','')} {o.get('offer_id','')}".lower()
            if str(quantity) in s:
                return o

    # For packages/vouchers, use broad text matching.
    keys = []
    if "ҳафта" in text or "week" in text:
        keys = ["week", "weekly", "ҳафта"]
    elif "лайт" in text or "lite" in text:
        keys = ["lite", "light", "лайт"]
    elif "моҳона" in text or "monthly" in text:
        keys = ["monthly", "month", "моҳ"]
    elif "level up package" in text:
        number = "".join(ch for ch in text if ch.isdigit())
        keys = [f"level up package {number}", f"level_up_{number}", f"level {number}"]
    elif "evo access" in text:
        number = "".join(ch for ch in text if ch.isdigit())
        keys = [f"evo access {number}", f"evo_{number}", f"evo {number}"]

    for o in offers:
        s = f"{o.get('name','')} {o.get('offer_id','')}".lower()
        if any(k.lower() in s for k in keys):
            return o

    return None


@dp.callback_query(F.data == "multi_buy")
async def multi_buy(call: CallbackQuery):
    await call.message.edit_text(
        "🛒 Барои хариди чанд маҳсулот пай дар пай, аз рӯйхат ҳар маҳсулотро алоҳида интихоб кунед.\n"
        "Пас аз ҳар харид баланс автоматӣ кам мешавад.",
        reply_markup=products_kb(),
    )
    await call.answer()


@dp.callback_query(F.data == "my_orders")
async def my_orders(call: CallbackQuery):
    con = db()
    rows = con.execute(
        "SELECT * FROM orders WHERE tg_id=? ORDER BY id DESC LIMIT 10",
        (call.from_user.id,),
    ).fetchall()
    con.close()

    if not rows:
        text = "📦 Ҳоло фармоише надоред."
    else:
        lines = ["📦 <b>Фармоишҳои охирин</b>\n"]
        for r in rows:
            lines.append(
                f"#{r['order_no']} — {r['product_name']} — {r['price']:.2f}с — <b>{r['status']}</b>"
            )
        text = "\n".join(lines)

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Бозгашт", callback_data="home")]]
    ))
    await call.answer()


async def poll_provider_orders():
    while True:
        try:
            rows = next_pending_orders()
            for order in rows:
                try:
                    data = await fz.get_order(order["fazer_order_id"])
                    provider = data.get("order", data)
                    status = provider.get("status", "processing")

                    if status in {"completed", "success", "delivered"}:
                        update_order(
                            order["id"],
                            status="completed",
                            completed_at=datetime.now().isoformat(),
                        )
                        fresh = get_order(order["id"])
                        receipt = make_receipt(fresh, "accepted")
                        await bot.send_photo(
                            order["tg_id"],
                            receipt.open("rb"),
                            caption=(
                                f"✅ <b>Фармоиш #{order['order_no']} иҷро шуд!</b>\n"
                                f"💎 {order['product_name']}\n"
                                f"👤 {order['nickname']}\n"
                                f"🔢 UID: <code>{order['player_id']}</code>\n"
                                f"💰 {order['price']:.2f} сом"
                            ),
                        )
                        if ADMIN_ID:
                            await bot.send_message(
                                ADMIN_ID,
                                f"✅ Order #{order['order_no']} completed automatically.",
                            )

                    elif status in {"failed", "refunded", "cancelled"}:
                        # Provider should return wholesale funds to reseller on failure.
                        # We also refund the customer's local balance.
                        refund_balance(order["tg_id"], Decimal(str(order["price"])))
                        update_order(order["id"], status="failed")
                        await bot.send_message(
                            order["tg_id"],
                            f"❌ Фармоиш #{order['order_no']} иҷро нашуд.\n"
                            f"💰 {order['price']:.2f} сом ба баланс баргардонида шуд.",
                        )
                except Exception:
                    logging.exception("Polling provider order failed")
        except Exception:
            logging.exception("Provider poll loop failed")
        await asyncio.sleep(8)


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing in .env")
    if not ADMIN_ID:
        raise RuntimeError("ADMIN_ID is missing in .env")
    if not FAZER_API_KEY:
        raise RuntimeError("FAZER_API_KEY is missing in .env")

    init_db()
    asyncio.create_task(poll_provider_orders())

    logging.info("Bot started")
    try:
        await dp.start_polling(bot)
    finally:
        await fz.close()
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
