import os
import re
import asyncio
import logging
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from fazercards import FazerCardsAsyncClient


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
FAZER_API_KEY = os.getenv("FAZER_API_KEY", "")

# Telegram ID-и админро дар Secrets гузор
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Агар FazerCards category_id-ро донӣ, дар Secret гузор.
# Агар холӣ бошад, бот кӯшиш мекунад Free Fire category-ро пайдо кунад.
FAZER_FF_CATEGORY_ID = os.getenv("FAZER_FF_CATEGORY_ID", "").strip()

# Маълумоти пардохт
PAYMENT_PHONE = os.getenv("PAYMENT_PHONE", "+992935710406")
PAYMENT_CARD = os.getenv("PAYMENT_CARD", "#21345")

SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@Zokirjon0555")

DB_FILE = "orders.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("taj_donat")


# =========================================================
# PRICE LIST
# =========================================================

PRODUCTS = {
    "110": {
        "name": "💎 110 Алмаз",
        "price": 7.80,
    },
    "341": {
        "name": "💎 341 Алмаз",
        "price": 24.60,
    },
    "572": {
        "name": "💎 572 Алмаз",
        "price": 43.50,
    },
    "1166": {
        "name": "💎 1166 Алмаз",
        "price": 80.00,
    },
    "2398": {
        "name": "💎 2398 Алмаз",
        "price": 183.00,
    },
    "6160": {
        "name": "💎 6160 Алмаз",
        "price": 460.00,
    },
    "weekly": {
        "name": "🎟 ВАУЧЕР ҲАФТА",
        "price": 16.00,
    },
    "lite": {
        "name": "🎟 ВАУЧЕР ЛАЙТ",
        "price": 5.50,
    },
    "monthly": {
        "name": "🎟 ВАУЧЕР МОҲОНА",
        "price": 57.50,
    },
    "levelup6": {
        "name": "🎁 Level Up Package 6",
        "price": 5.50,
    },
    "levelup10": {
        "name": "🎁 Level Up Package 10",
        "price": 6.00,
    },
    "levelup15": {
        "name": "🎁 Level Up Package 15",
        "price": 7.00,
    },
    "levelup20": {
        "name": "🎁 Level Up Package 20",
        "price": 8.00,
    },
    "levelup25": {
        "name": "🎁 Level Up Package 25",
        "price": 8.00,
    },
    "levelup30": {
        "name": "🎁 Level Up Package 30",
        "price": 9.00,
    },
}


# =========================================================
# DATABASE
# =========================================================

def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            username TEXT,
            product_key TEXT NOT NULL,
            product_name TEXT NOT NULL,
            price REAL NOT NULL,
            player_id TEXT,
            nickname TEXT,
            status TEXT NOT NULL DEFAULT 'waiting_payment',
            receipt_file_id TEXT,
            fazer_order_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def create_order(
    telegram_id,
    username,
    product_key,
    product_name,
    price
):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = db()

    cur = conn.execute("""
        INSERT INTO orders (
            telegram_id,
            username,
            product_key,
            product_name,
            price,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        telegram_id,
        username,
        product_key,
        product_name,
        price,
        "waiting_uid",
        now,
        now
    ))

    order_id = cur.lastrowid

    conn.commit()
    conn.close()

    return order_id


def get_order(order_id):
    conn = db()
    row = conn.execute(
        "SELECT * FROM orders WHERE id = ?",
        (order_id,)
    ).fetchone()
    conn.close()
    return row


def update_order(order_id, **fields):
    if not fields:
        return

    fields["updated_at"] = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    columns = []
    values = []

    for key, value in fields.items():
        columns.append(f"{key} = ?")
        values.append(value)

    values.append(order_id)

    conn = db()

    conn.execute(
        f"""
        UPDATE orders
        SET {", ".join(columns)}
        WHERE id = ?
        """,
        values
    )

    conn.commit()
    conn.close()


# =========================================================
# FSM
# =========================================================

class OrderState(StatesGroup):
    waiting_uid = State()
    waiting_nickname = State()
    waiting_receipt = State()


# =========================================================
# BOT
# =========================================================

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

fz = None


# =========================================================
# KEYBOARDS
# =========================================================

def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💎 Донат кардан",
                    callback_data="buy"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👤 Профил",
                    callback_data="profile"
                ),
                InlineKeyboardButton(
                    text="📦 Фармоишҳо",
                    callback_data="orders"
                )
            ],
            [
                InlineKeyboardButton(
                    text="ℹ️ Маълумот",
                    callback_data="info"
                ),
                InlineKeyboardButton(
                    text="🆘 Дастгирӣ",
                    callback_data="support"
                )
            ],
        ]
    )


def products_keyboard():
    rows = []

    for key, product in PRODUCTS.items():
        rows.append([
            InlineKeyboardButton(
                text=f"{product['name']} — {product['price']:.2f} с.",
                callback_data=f"product:{key}"
            )
        ])

    rows.append([
        InlineKeyboardButton(
            text="🔙 Бозгашт",
            callback_data="home"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_order_keyboard(order_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ ҚАБУЛ КАРДАН",
                    callback_data=f"admin_accept:{order_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ БЕКОР КАРДАН",
                    callback_data=f"admin_reject:{order_id}"
                )
            ]
        ]
    )


# =========================================================
# HELPERS
# =========================================================

def money(value):
    return f"{value:.2f}"


def get_username(message: Message):
    if message.from_user.username:
        return f"@{message.from_user.username}"

    return message.from_user.full_name


async def find_free_fire_category():
    """
    Агар FAZER_FF_CATEGORY_ID гузошта нашуда бошад,
    категорияи Free Fire-ро аз FazerCards меёбад.
    """

    if FAZER_FF_CATEGORY_ID:
        return FAZER_FF_CATEGORY_ID

    try:
        result = await fz.topups.categories()

        items = (
            result.get("items")
            or result.get("categories")
            or result.get("data")
            or []
        )

        for item in items:
            category_id = str(
                item.get("category_id")
                or item.get("id")
                or ""
            )

            name = str(
                item.get("name")
                or item.get("title")
                or ""
            ).lower()

            combined = f"{category_id} {name}"

            if "free_fire" in combined or "free fire" in combined:
                return category_id

        logger.warning("Free Fire category not found")

    except Exception:
        logger.exception("Cannot get FazerCards categories")

    return None


async def find_offer(product_key):
    """
    Offer-и FazerCards-ро меёбад.
    Барои offer_id-и дақиқ метавон Secret-и
    FAZER_OFFER_110, FAZER_OFFER_341 ва ғайра истифода бурд.
    """

    env_name = f"FAZER_OFFER_{product_key.upper()}"

    manual_offer = os.getenv(env_name, "").strip()

    if manual_offer:
        return manual_offer

    category_id = await find_free_fire_category()

    if not category_id:
        return None

    result = await fz.topups.offers(category_id)

    offers = (
        result.get("offers")
        or result.get("items")
        or result.get("data")
        or []
    )

    wanted = product_key.lower()

    for offer in offers:
        text = " ".join(
            str(offer.get(key, ""))
            for key in (
                "name",
                "title",
                "label",
                "description",
                "offer_id",
                "id"
            )
        ).lower()

        if wanted in text:
            return (
                offer.get("offer_id")
                or offer.get("id")
            )

    return None


async def validate_player(player_id):
    """
    Пеш аз фармоиш UID-ро бо FazerCards санҷидан.
    """

    category_id = await find_free_fire_category()

    if not category_id:
        return {
            "ok": False,
            "message": "Категорияи Free Fire дар FazerCards ёфт нашуд."
        }

    try:
        result = await fz.topups.validate_id(
            category_id=category_id,
            fields={
                "player_id": player_id
            }
        )

        return {
            "ok": bool(result.get("valid", False)),
            "nickname": result.get("player_name"),
            "region": result.get("region"),
            "raw": result
        }

    except Exception as e:
        logger.exception("UID validation error")

        return {
            "ok": False,
            "message": str(e)
        }


async def send_fazer_order(order_id):
    """
    Фармоишро ба FazerCards мефиристад.
    """

    order = get_order(order_id)

    if not order:
        raise ValueError("Order not found")

    product_key = order["product_key"]

    category_id = await find_free_fire_category()

    if not category_id:
        raise ValueError(
            "Free Fire category_id ёфт нашуд"
        )

    offer_id = await find_offer(product_key)

    if not offer_id:
        raise ValueError(
            f"Offer барои {product_key} ёфт нашуд"
        )

    logger.info(
        "Creating FazerCards order: local=%s product=%s offer=%s",
        order_id,
        product_key,
        offer_id
    )

    result = await fz.topups.order(
        category_id=category_id,
        offer_id=offer_id,
        fields={
            "player_id": str(order["player_id"])
        },
        idempotency_key=f"taj-donat-{order_id}"
    )

    fazer_order = result.get("order", result)

    fazer_order_id = (
        fazer_order.get("id")
        or fazer_order.get("order_id")
    )

    status = (
        fazer_order.get("status")
        or result.get("status")
        or "processing"
    )

    update_order(
        order_id,
        fazer_order_id=fazer_order_id,
        status=f"fazer_{status}"
    )

    return fazer_order


# =========================================================
# /START
# =========================================================

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()

    text = (
        "🔥 <b>TAJ.DONAT.FF</b>\n\n"
        "💎 Донати Free Fire\n"
        "⚡ Қабули фармоиш зуд\n"
        "🔐 Пардохти бехатар\n"
        "💬 Дастгирӣ 24/7\n\n"
        "Барои оғоз тугмаро интихоб кунед 👇"
    )

    await message.answer(
        text,
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


# =========================================================
# BUY
# =========================================================

@dp.callback_query(F.data == "buy")
async def buy_handler(callback: CallbackQuery):
    await callback.answer()

    await callback.message.edit_text(
        "💎 <b>НАРХНОМАИ FREE FIRE</b>\n\n"
        "Алмази лозимиро интихоб кунед 👇",
        reply_markup=products_keyboard(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("product:"))
async def product_handler(
    callback: CallbackQuery,
    state: FSMContext
):
    await callback.answer()

    product_key = callback.data.split(":", 1)[1]

    product = PRODUCTS.get(product_key)

    if not product:
        return

    order_id = create_order(
        telegram_id=callback.from_user.id,
        username=(
            f"@{callback.from_user.username}"
            if callback.from_user.username
            else callback.from_user.full_name
        ),
        product_key=product_key,
        product_name=product["name"],
        price=product["price"]
    )

    await state.update_data(
        order_id=order_id,
        product_key=product_key
    )

    await state.set_state(OrderState.waiting_uid)

    await callback.message.edit_text(
        f"🛒 <b>ФАРМОИШ №{order_id}</b>\n\n"
        f"📦 {product['name']}\n"
        f"💰 Нарх: <b>{money(product['price'])} с.</b>\n\n"
        "🎮 Ҳоло <b>UID-и Free Fire</b>-ро фиристед.\n\n"
        "⚠️ UID-ро бодиққат нависед.",
        parse_mode="HTML"
    )


# =========================================================
# UID
# =========================================================

@dp.message(OrderState.waiting_uid)
async def uid_handler(message: Message, state: FSMContext):
    player_id = message.text.strip()

    if not player_id:
        await message.answer("❌ UID нодуруст аст.")
        return

    if not re.fullmatch(r"\d{5,15}", player_id):
        await message.answer(
            "❌ UID нодуруст аст.\n\n"
            "UID бояд танҳо рақам бошад."
        )
        return

    data = await state.get_data()
    order_id = data["order_id"]

    await message.answer(
        "⏳ UID санҷида шуда истодааст..."
    )

    validation = await validate_player(player_id)

    if not validation.get("ok"):
        await message.answer(
            "❌ <b>UID тасдиқ нашуд.</b>\n\n"
            "UID-ро санҷед ва аз нав фиристед.",
            parse_mode="HTML"
        )
        return

    nickname = validation.get("nickname") or "Муайян нашуд"

    update_order(
        order_id,
        player_id=player_id,
        nickname=nickname,
        status="waiting_payment"
    )

    await state.update_data(
        player_id=player_id,
        nickname=nickname
    )

    await state.set_state(OrderState.waiting_receipt)

    order = get_order(order_id)

    await message.answer(
        f"✅ <b>UID тасдиқ шуд!</b>\n\n"
        f"🎮 UID: <code>{player_id}</code>\n"
        f"👤 Nickname: <b>{nickname}</b>\n"
        f"💎 {order['product_name']}\n"
        f"💰 Нарх: <b>{money(order['price'])} с.</b>\n\n"
        "💳 <b>УСУЛИ ПАРДОХТ</b>\n\n"
        "🏦 Эсхата Онлайн\n"
        "📱 ICB Mobile\n"
        f"📞 {PAYMENT_PHONE}\n"
        f"🔢 Рақами корт: {PAYMENT_CARD}\n\n"
        "1️⃣ Пардохт кунед.\n"
        "2️⃣ Скриншот/чеки пардохтро ҳамин ҷо фиристед.\n"
        "3️⃣ Баъди санҷиши админ фармоиш иҷро мешавад.\n\n"
        "⚠️ Пеш аз пардохт рақамро бодиққат санҷед.",
        parse_mode="HTML"
    )


# =========================================================
# RECEIPT
# =========================================================

@dp.message(OrderState.waiting_receipt, F.photo)
async def receipt_photo_handler(
    message: Message,
    state: FSMContext
):
    data = await state.get_data()

    order_id = data["order_id"]

    photo = message.photo[-1]

    update_order(
        order_id,
        receipt_file_id=photo.file_id,
        status="waiting_admin"
    )

    order = get_order(order_id)

    caption = (
        "🔔 <b>ФАРМОИШИ НАВ</b>\n\n"
        f"🆔 Фармоиш: <b>#{order_id}</b>\n"
        f"👤 Username: {order['username']}\n"
        f"👤 Nickname: <b>{order['nickname']}</b>\n"
        f"🎮 UID: <code>{order['player_id']}</code>\n"
        f"📦 {order['product_name']}\n"
        f"💰 Нарх: <b>{money(order['price'])} с.</b>\n"
        f"🕐 Вақт: {order['created_at']}\n\n"
        "📸 Чек фиристода шуд.\n"
        "👇 Амалро интихоб кунед:"
    )

    if ADMIN_ID:
        await bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo.file_id,
            caption=caption,
            reply_markup=admin_order_keyboard(order_id),
            parse_mode="HTML"
        )

    await message.answer(
        f"✅ Чек қабул шуд.\n\n"
        f"🧾 Фармоиш <b>#{order_id}</b>\n"
        "⏳ Дар интизори тасдиқи админ...\n\n"
        "💬 Дастгирӣ 24/7",
        parse_mode="HTML"
    )

    await state.clear()


@dp.message(OrderState.waiting_receipt)
async def receipt_other_handler(
    message: Message
):
    await message.answer(
        "📸 Лутфан <b>акси чек/скриншоти пардохт</b>-ро фиристед.",
        parse_mode="HTML"
    )


# =========================================================
# ADMIN ACCEPT
# =========================================================

@dp.callback_query(F.data.startswith("admin_accept:"))
async def admin_accept_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer(
            "❌ Дастрасӣ нест.",
            show_alert=True
        )
        return

    await callback.answer("⏳ Фармоиш қабул шуд.")

    order_id = int(
        callback.data.split(":", 1)[1]
    )

    order = get_order(order_id)

    if not order:
        await callback.message.answer(
            "❌ Фармоиш ёфт нашуд."
        )
        return

    if order["status"] not in (
        "waiting_admin",
        "fazer_failed",
        "fazer_refund"
    ):
        await callback.message.answer(
            f"⚠️ Фармоиш аллакай дар ҳолати:\n"
            f"<b>{order['status']}</b>",
            parse_mode="HTML"
        )
        return

    update_order(
        order_id,
        status="processing"
    )

    await callback.message.edit_caption(
        caption=(
            f"⚡ <b>ФАРМОИШ #{order_id}</b>\n\n"
            "🟡 Дар FazerCards фиристода шуда истодааст...\n\n"
            f"👤 {order['nickname']}\n"
            f"🎮 UID: <code>{order['player_id']}</code>\n"
            f"📦 {order['product_name']}"
        ),
        parse_mode="HTML"
    )

    try:
        fazer_order = await send_fazer_order(order_id)

        fazer_id = (
            fazer_order.get("id")
            or fazer_order.get("order_id")
            or "—"
        )

        status = (
            fazer_order.get("status")
            or "processing"
        )

        await callback.message.answer(
            f"✅ <b>Фармоиш ба FazerCards фиристода шуд!</b>\n\n"
            f"🧾 Фармоиш: <b>#{order_id}</b>\n"
            f"⚡ FazerCards: <code>{fazer_id}</code>\n"
            f"📊 Status: <b>{status}</b>",
            parse_mode="HTML"
        )

        # Агар аллакай completed бошад, ба мизоҷ хабар медиҳем.
        if status == "completed":
            await send_success_to_customer(order_id)

        else:
            asyncio.create_task(
                wait_for_fazer_order(order_id, fazer_id)
            )

    except Exception as e:
        logger.exception(
            "FazerCards order failed"
        )

        update_order(
            order_id,
            status="fazer_failed"
        )

        await callback.message.answer(
            "❌ <b>Фармоиш ба FazerCards фиристода нашуд.</b>\n\n"
            f"Хато: <code>{str(e)[:500]}</code>\n\n"
            "Фармоишро аз нав санҷед.",
            parse_mode="HTML"
        )

        try:
            await bot.send_message(
                order["telegram_id"],
                f"❌ <b>Фармоиш #{order_id}</b>\n\n"
                "Ҳангоми иҷрои автоматии донат мушкил пайдо шуд.\n"
                "Админ фармоишро санҷида истодааст.",
                parse_mode="HTML"
            )
        except Exception:
            pass


# =========================================================
# WAIT FOR FAZER ORDER
# =========================================================

async def wait_for_fazer_order(order_id, fazer_order_id):
    if not fazer_order_id:
        return

    try:
        final = await fz.orders.wait(
            fazer_order_id,
            timeout=600,
            interval=5
        )

        status = final.get("status", "")

        update_order(
            order_id,
            status=f"fazer_{status}"
        )

        if status == "completed":
            await send_success_to_customer(order_id)

        elif status in ("failed", "refund"):
            await send_failed_to_customer(
                order_id,
                status
            )

    except Exception as e:
        logger.exception(
            "Waiting FazerCards order failed"
        )


# =========================================================
# CUSTOMER SUCCESS
# =========================================================

async def send_success_to_customer(order_id):
    order = get_order(order_id)

    if not order:
        return

    text = (
        "🎉 <b>ДОНАТ БО МУВАФФАҚИЯТ ИҶРО ШУД!</b>\n\n"
        f"🧾 Фармоиш: <b>#{order_id}</b>\n"
        f"🎮 UID: <code>{order['player_id']}</code>\n"
        f"👤 Nickname: <b>{order['nickname']}</b>\n"
        f"💎 {order['product_name']}\n"
        f"💰 Пардохт: <b>{money(order['price'])} с.</b>\n"
        f"🕐 Вақт: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        "✅ Алмазҳо ба ID-и шумо фиристода шуданд.\n\n"
        "🔥 <b>TAJ.DONAT.FF</b>\n"
        "💬 Дастгирӣ 24/7"
    )

    try:
        await bot.send_message(
            order["telegram_id"],
            text,
            parse_mode="HTML"
        )
    except Exception:
        logger.exception(
            "Cannot send success message"
        )


# =========================================================
# CUSTOMER FAILED
# =========================================================

async def send_failed_to_customer(order_id, status):
    order = get_order(order_id)

    if not order:
        return

    await bot.send_message(
        order["telegram_id"],
        f"⚠️ <b>Фармоиш #{order_id}</b>\n\n"
        "Донат дар FazerCards иҷро нашуд.\n"
        f"📊 Status: <b>{status}</b>\n\n"
        "👨‍💻 Админ фармоишро месанҷад.\n"
        "💬 Дастгирӣ 24/7",
        parse_mode="HTML"
    )


# =========================================================
# ADMIN REJECT
# =========================================================

@dp.callback_query(F.data.startswith("admin_reject:"))
async def admin_reject_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer(
            "❌ Дастрасӣ нест.",
            show_alert=True
        )
        return

    await callback.answer(
        "Фармоиш бекор карда шуд."
    )

    order_id = int(
        callback.data.split(":", 1)[1]
    )

    order = get_order(order_id)

    if not order:
        return

    update_order(
        order_id,
        status="rejected"
    )

    try:
        await callback.message.edit_caption(
            caption=(
                f"❌ <b>ФАРМОИШ #{order_id} БЕКОР ШУД</b>\n\n"
                f"👤 {order['nickname']}\n"
                f"🎮 UID: <code>{order['player_id']}</code>\n"
                f"📦 {order['product_name']}"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass

    await bot.send_message(
        order["telegram_id"],
        f"❌ <b>Фармоиш #{order_id} бекор карда шуд.</b>\n\n"
        "Агар пардохт карда бошед, бо дастгирӣ тамос гиред.\n\n"
        f"💬 Дастгирӣ: {SUPPORT_USERNAME}",
        parse_mode="HTML"
    )


# =========================================================
# PROFILE
# =========================================================

@dp.callback_query(F.data == "profile")
async def profile_handler(callback: CallbackQuery):
    await callback.answer()

    conn = db()

    total = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM orders
        WHERE telegram_id = ?
        """,
        (callback.from_user.id,)
    ).fetchone()["count"]

    conn.close()

    await callback.message.edit_text(
        "👤 <b>ПРОФИЛ</b>\n\n"
        f"🆔 Telegram ID: <code>{callback.from_user.id}</code>\n"
        f"📦 Фармоишҳо: <b>{total}</b>\n\n"
        "🔥 TAJ.DONAT.FF",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Бозгашт",
                        callback_data="home"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )


# =========================================================
# ORDERS
# =========================================================

@dp.callback_query(F.data == "orders")
async def orders_handler(callback: CallbackQuery):
    await callback.answer()

    conn = db()

    rows = conn.execute(
        """
        SELECT id, product_name, price, status, created_at
        FROM orders
        WHERE telegram_id = ?
        ORDER BY id DESC
        LIMIT 10
        """,
        (callback.from_user.id,)
    ).fetchall()

    conn.close()

    if not rows:
        text = (
            "📦 <b>ФАРМОИШҲО</b>\n\n"
            "Ҳоло фармоише нест."
        )

    else:
        lines = [
            "📦 <b>ФАРМОИШҲОИ ШУМО</b>\n"
        ]

        for row in rows:
            lines.append(
                f"🧾 #{row['id']} | "
                f"{row['product_name']} | "
                f"{money(row['price'])} с.\n"
                f"📊 {row['status']}\n"
                f"🕐 {row['created_at']}\n"
            )

        text = "\n".join(lines)

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Бозгашт",
                        callback_data="home"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )


# =========================================================
# INFO
# =========================================================

@dp.callback_query(F.data == "info")
async def info_handler(callback: CallbackQuery):
    await callback.answer()

    await callback.message.edit_text(
        "ℹ️ <b>ДАР БОРАИ TAJ.DONAT.FF</b>\n\n"
        "💎 Донати Free Fire\n"
        "⚡ Қабули фармоиш онлайн\n"
        "🔐 Пардохт бо усулҳои дастрас\n"
        "🎮 Барои донат UID лозим аст\n"
        "📸 Чек баъди пардохт қабул мешавад\n"
        "🕐 Дастгирӣ 24/7\n\n"
        "⚠️ Пеш аз фиристодани фармоиш UID-ро санҷед.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Бозгашт",
                        callback_data="home"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )


# =========================================================
# SUPPORT
# =========================================================

@dp.callback_query(F.data == "support")
async def support_handler(callback: CallbackQuery):
    await callback.answer()

    await callback.message.edit_text(
        "🆘 <b>ДАСТГИРӢ 24/7</b>\n\n"
        f"👨‍💻 Админ: {SUPPORT_USERNAME}\n\n"
        "Агар дар пардохт ё фармоиш мушкил пайдо шавад,\n"
        "бо админ тамос гиред.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💬 Тамос бо админ",
                        url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Бозгашт",
                        callback_data="home"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )


# =========================================================
# HOME
# =========================================================

@dp.callback_query(F.data == "home")
async def home_handler(callback: CallbackQuery):
    await callback.answer()

    await callback.message.edit_text(
        "🔥 <b>TAJ.DONAT.FF</b>\n\n"
        "💎 Донати Free Fire\n"
        "⚡ Қабули фармоиш зуд\n"
        "🔐 Пардохти бехатар\n"
        "💬 Дастгирӣ 24/7\n\n"
        "Барои оғоз интихоб кунед 👇",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


# =========================================================
# ADMIN COMMANDS
# =========================================================

@dp.message(Command("admin"))
async def admin_handler(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "👨‍💻 <b>ADMIN PANEL</b>\n\n"
        "/balance — баланси FazerCards\n"
        "/offers — пешниҳодҳои Free Fire\n"
        "/orders — фармоишҳои охирин\n",
        parse_mode="HTML"
    )


@dp.message(Command("balance"))
async def balance_handler(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        balance = await fz.balance.get()

        await message.answer(
            "💰 <b>FAZERCARDS BALANCE</b>\n\n"
            f"💵 Balance: <b>{balance.get('balance')}</b>\n"
            f"💱 Currency: <b>{balance.get('currency')}</b>",
            parse_mode="HTML"
        )

    except Exception as e:
        await message.answer(
            f"❌ Хато:\n<code>{str(e)[:500]}</code>",
            parse_mode="HTML"
        )


@dp.message(Command("offers"))
async def offers_handler(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        category_id = await find_free_fire_category()

        if not category_id:
            await message.answer(
                "❌ Free Fire category_id ёфт нашуд."
            )
            return

        result = await fz.topups.offers(category_id)

        offers = (
            result.get("offers")
            or result.get("items")
            or []
        )

        if not offers:
            await message.answer(
                "❌ Offer ёфт нашуд."
            )
            return

        text = (
            "💎 <b>FREE FIRE OFFERS</b>\n\n"
            f"Category: <code>{category_id}</code>\n\n"
        )

        for offer in offers[:50]:
            offer_id = (
                offer.get("offer_id")
                or offer.get("id")
                or "—"
            )

            name = (
                offer.get("name")
                or offer.get("title")
                or "—"
            )

            price = (
                offer.get("price_usd")
                or offer.get("price")
                or "—"
            )

            text += (
                f"🔹 <b>{name}</b>\n"
                f"ID: <code>{offer_id}</code>\n"
                f"USD: {price}\n\n"
            )

        await message.answer(
            text[:4000],
            parse_mode="HTML"
        )

    except Exception as e:
        await message.answer(
            f"❌ Хато:\n<code>{str(e)[:500]}</code>",
            parse_mode="HTML"
        )


@dp.message(Command("orders"))
async def admin_orders_handler(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    conn = db()

    rows = conn.execute(
        """
        SELECT *
        FROM orders
        ORDER BY id DESC
        LIMIT 20
        """
    ).fetchall()

    conn.close()

    if not rows:
        await message.answer(
            "📦 Фармоиш нест."
        )
        return

    text = "📦 <b>ОХИРИН ФАРМОИШҲО</b>\n\n"

    for row in rows:
        text += (
            f"🧾 #{row['id']}\n"
            f"👤 {row['nickname'] or '—'}\n"
            f"🎮 {row['player_id'] or '—'}\n"
            f"📦 {row['product_name']}\n"
            f"💰 {money(row['price'])} с.\n"
            f"📊 {row['status']}\n"
            f"🕐 {row['created_at']}\n\n"
        )

    await message.answer(
        text[:4000],
        parse_mode="HTML"
    )


# =========================================================
# STARTUP
# =========================================================

async def main():
    global fz

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN дар Secrets гузошта нашудааст."
        )

    if not FAZER_API_KEY:
        raise RuntimeError(
            "FAZER_API_KEY дар Secrets гузошта нашудааст."
        )

    if not ADMIN_ID:
        raise RuntimeError(
            "ADMIN_ID дар Secrets гузошта нашудааст."
        )

    init_db()

    fz = FazerCardsAsyncClient(
        api_key=FAZER_API_KEY,
        app_name="TAJ.DONAT.FF/1.0"
    )

    logger.info("TAJ.DONAT.FF starting...")

    try:
        await dp.start_polling(bot)
    finally:
        await fz.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
