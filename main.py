import asyncio
import logging
import os
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_ID = 6439367152
SUPPORT_USERNAME = "@Zokirjon0555"

SUBSCRIBE_URL = "https://t.me/otsivho"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set")


# =========================================================
# PRICES
# =========================================================

PRODUCTS = {
    "110": ("💎 110 алмаз", 7.80),
    "341": ("💎 341 алмаз", 24.60),
    "572": ("💎 572 алмаз", 43.50),
    "1166": ("💎 1166 алмаз", 80.00),
    "2398": ("💎 2398 алмаз", 183.00),
    "6160": ("💎 6160 алмаз", 460.00),

    "weekly": ("🎟️ Ваучер Ҳафта", 16.00),
    "lite": ("🎟️ Ваучер Лайт", 5.50),
    "monthly": ("🎟️ Ваучер Моҳона", 57.50),

    "level6": ("🚀 Level Up Package 6", 5.50),
    "level10": ("🚀 Level Up Package 10", 6.00),
    "level15": ("🚀 Level Up Package 15", 7.00),
    "level20": ("🚀 Level Up Package 20", 8.00),
    "level25": ("🚀 Level Up Package 25", 8.00),
    "level30": ("🚀 Level Up Package 30", 9.00),
}


# =========================================================
# DATABASE
# =========================================================

DB_NAME = "donat.db"

db = sqlite3.connect(DB_NAME, check_same_thread=False)
db.row_factory = sqlite3.Row

cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    created_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    product TEXT,
    price REAL,
    ff_id TEXT,
    nickname TEXT,
    status TEXT,
    created_at TEXT
)
""")

db.commit()


# =========================================================
# BOT
# =========================================================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()


# =========================================================
# STATES
# =========================================================

class OrderState(StatesGroup):
    waiting_ff_id = State()
    waiting_nickname = State()
    waiting_receipt = State()


# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💎 Донат кардан",
                    callback_data="donate"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🌐 Магоза",
                    callback_data="shop"
                ),
                InlineKeyboardButton(
                    text="👤 Профил",
                    callback_data="profile"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Танзимоти FF",
                    callback_data="ff_settings"
                ),
                InlineKeyboardButton(
                    text="ℹ️ Маълумот",
                    callback_data="info"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🆘 Дастгирӣ",
                    callback_data="support"
                )
            ]
        ]
    )


def subscribe_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Обуна шудан",
                    url=SUBSCRIBE_URL
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Ман обуна шудам",
                    callback_data="check_sub"
                )
            ]
        ]
    )


def products_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💎 110 — 7.80с",
                    callback_data="product_110"
                ),
                InlineKeyboardButton(
                    text="💎 341 — 24.60с",
                    callback_data="product_341"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💎 572 — 43.50с",
                    callback_data="product_572"
                ),
                InlineKeyboardButton(
                    text="💎 1166 — 80с",
                    callback_data="product_1166"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💎 2398 — 183с",
                    callback_data="product_2398"
                ),
                InlineKeyboardButton(
                    text="💎 6160 — 460с",
                    callback_data="product_6160"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎟️ Ваучерҳо",
                    callback_data="vouchers"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚀 Level Up",
                    callback_data="levelup"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Меню",
                    callback_data="home"
                )
            ]
        ]
    )


def voucher_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎟️ Ҳафта — 16с",
                    callback_data="product_weekly"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎟️ Лайт — 5.5с",
                    callback_data="product_lite"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎟️ Моҳона — 57.5с",
                    callback_data="product_monthly"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Бозгашт",
                    callback_data="shop"
                )
            ]
        ]
    )


def levelup_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="6 — 5.5с",
                    callback_data="product_level6"
                ),
                InlineKeyboardButton(
                    text="10 — 6с",
                    callback_data="product_level10"
                )
            ],
            [
                InlineKeyboardButton(
                    text="15 — 7с",
                    callback_data="product_level15"
                ),
                InlineKeyboardButton(
                    text="20 — 8с",
                    callback_data="product_level20"
                )
            ],
            [
                InlineKeyboardButton(
                    text="25 — 8с",
                    callback_data="product_level25"
                ),
                InlineKeyboardButton(
                    text="30 — 9с",
                    callback_data="product_level30"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Бозгашт",
                    callback_data="shop"
                )
            ]
        ]
    )


# =========================================================
# USER DATABASE
# =========================================================

def save_user(message: Message):
    user = message.from_user

    cursor.execute("""
    INSERT OR REPLACE INTO users
    (user_id, username, first_name, created_at)
    VALUES (?, ?, ?, COALESCE(
        (SELECT created_at FROM users WHERE user_id = ?),
        ?
    ))
    """, (
        user.id,
        user.username or "",
        user.first_name or "",
        user.id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    db.commit()


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start_handler(message: Message):
    save_user(message)

    text = (
        "🔥 <b>TAJ.DONAT.FF</b>\n\n"
        "💎 Донати Free Fire СНГ\n"
        "⚡ Қабули фармоиш зуд\n"
        "🔐 Пардохти бехатар\n"
        "💬 Дастгирӣ 24/7\n\n"
        "Хуш омадед! 👋\n"
        "Аз меню хизматрасории лозимаро интихоб кунед."
    )

    await message.answer(
        text,
        reply_markup=main_keyboard()
    )


# =========================================================
# HOME
# =========================================================

@dp.callback_query(F.data == "home")
async def home_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔥 <b>TAJ.DONAT.FF</b>\n\n"
        "💎 Донати Free Fire СНГ\n"
        "⚡ Тез • Бехатар • 24/7",
        reply_markup=main_keyboard()
    )

    await callback.answer()


# =========================================================
# DONATE
# =========================================================

@dp.callback_query(F.data == "donate")
async def donate_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "📢 <b>Қадами аввал</b>\n\n"
        "Барои истифодаи бот аввал ба канали мо обуна шавед.\n\n"
        "Баъд тугмаи «Ман обуна шудам»-ро пахш кунед.",
        reply_markup=subscribe_keyboard()
    )

    await callback.answer()


@dp.callback_query(F.data == "check_sub")
async def check_sub_handler(callback: CallbackQuery):
    # Барои он ки бот бе channel_id ҳам кор кунад,
    # ин ҷо танҳо қадамро идома медиҳем.
    await callback.message.edit_text(
        "💎 <b>Интихоби маҳсулот</b>\n\n"
        "Маҳсулоти лозимаро интихоб кунед:",
        reply_markup=products_keyboard()
    )

    await callback.answer("Обуна тасдиқ шуд ✅")


# =========================================================
# SHOP
# =========================================================

@dp.callback_query(F.data == "shop")
async def shop_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "🌐 <b>МАГОЗА</b>\n\n"
        "💎 АЛМАЗҲОИ FREE FIRE СНГ 🇹🇯\n\n"
        "Ҳамаи нархҳо бо сомонӣ мебошанд.\n"
        "⚡ Кор 24/7",
        reply_markup=products_keyboard()
    )

    await callback.answer()


@dp.callback_query(F.data == "vouchers")
async def vouchers_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎟️ <b>ВАУЧЕРҲО</b>\n\n"
        "Маҳсулоти лозимаро интихоб кунед:",
        reply_markup=voucher_keyboard()
    )

    await callback.answer()


@dp.callback_query(F.data == "levelup")
async def levelup_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "🚀 <b>LEVEL UP PACKAGE</b>\n\n"
        "Пакети лозимаро интихоб кунед:",
        reply_markup=levelup_keyboard()
    )

    await callback.answer()


# =========================================================
# PRODUCT SELECT
# =========================================================

@dp.callback_query(F.data.startswith("product_"))
async def product_handler(
    callback: CallbackQuery,
    state: FSMContext
):
    key = callback.data.replace("product_", "")

    if key not in PRODUCTS:
        await callback.answer("Маҳсулот ёфт нашуд ❌")
        return

    product_name, price = PRODUCTS[key]

    await state.update_data(
        product=product_name,
        price=price
    )

    await callback.message.edit_text(
        f"🛒 <b>Фармоиш</b>\n\n"
        f"📦 Маҳсулот: <b>{product_name}</b>\n"
        f"💰 Нарх: <b>{price:g} сомонӣ</b>\n\n"
        "🆔 Акнун <b>Player ID</b>-и Free Fire-ро фиристед:",
    )

    await state.set_state(OrderState.waiting_ff_id)

    await callback.answer()


# =========================================================
# FF ID
# =========================================================

@dp.message(OrderState.waiting_ff_id)
async def ff_id_handler(
    message: Message,
    state: FSMContext
):
    ff_id = message.text.strip()

    if not ff_id.isdigit():
        await message.answer(
            "❌ ID нодуруст аст.\n\n"
            "Лутфан танҳо рақами Player ID-ро фиристед."
        )
        return

    await state.update_data(ff_id=ff_id)

    await message.answer(
        "👤 <b>Nickname</b>-и Free Fire-ро фиристед:"
    )

    await state.set_state(OrderState.waiting_nickname)


# =========================================================
# NICKNAME
# =========================================================

@dp.message(OrderState.waiting_nickname)
async def nickname_handler(
    message: Message,
    state: FSMContext
):
    nickname = message.text.strip()

    if len(nickname) < 2:
        await message.answer(
            "❌ Nickname нодуруст аст.\n"
            "Лутфан nickname-и дурустро фиристед."
        )
        return

    await state.update_data(nickname=nickname)

    data = await state.get_data()

    await message.answer(
        "💳 <b>Пардохт</b>\n\n"
        f"📦 {data['product']}\n"
        f"🆔 ID: <code>{data['ff_id']}</code>\n"
        f"👤 Nickname: <b>{data['nickname']}</b>\n"
        f"💰 Сумма: <b>{data['price']:g} сомонӣ</b>\n\n"
        "🏦 <b>Усулҳои пардохт:</b>\n"
        "• Эсхата Онлайн\n"
        "• ICB Mobile\n"
        "• Бонк\n\n"
        "Пас аз пардохт 🧾 чек ё скриншоти пардохтро ҳамин ҷо фиристед."
    )

    await state.set_state(OrderState.waiting_receipt)


# =========================================================
# RECEIPT PHOTO
# =========================================================

@dp.message(
    OrderState.waiting_receipt,
    F.photo
)
async def receipt_handler(
    message: Message,
    state: FSMContext
):
    data = await state.get_data()

    user = message.from_user

    cursor.execute("""
    INSERT INTO orders
    (user_id, username, product, price, ff_id, nickname, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user.id,
        user.username or "",
        data["product"],
        data["price"],
        data["ff_id"],
        data["nickname"],
        "waiting_admin",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    order_id = cursor.lastrowid
    db.commit()

    admin_text = (
        "🔥 <b>ФАРМОИШИ НАВ!</b>\n\n"
        f"🧾 Заказ №<b>{order_id}</b>\n"
        f"👤 User: @{user.username or '—'}\n"
        f"🆔 Telegram ID: <code>{user.id}</code>\n\n"
        f"📦 Маҳсулот: <b>{data['product']}</b>\n"
        f"💰 Нарх: <b>{data['price']:g} сомонӣ</b>\n"
        f"🎮 Free Fire ID: <code>{data['ff_id']}</code>\n"
        f"👤 Nickname: <b>{data['nickname']}</b>\n"
        f"🕐 Вақт: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )

    admin_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ ҚАБУЛ",
                    callback_data=f"accept_{order_id}_{user.id}"
                ),
                InlineKeyboardButton(
                    text="❌ РАД",
                    callback_data=f"reject_{order_id}_{user.id}"
                )
            ]
        ]
    )

    await bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=admin_text,
        reply_markup=admin_keyboard
    )

    await message.answer(
        "✅ <b>Чек қабул шуд!</b>\n\n"
        f"🧾 Рақами фармоиш: <b>#{order_id}</b>\n"
        "👨‍💼 Фармоиш ба админ фиристода шуд.\n\n"
        "⏳ Лутфан интизор шавед.\n"
        "💬 Дастгирӣ: @Zokirjon0555"
    )

    await state.clear()


# =========================================================
# RECEIPT DOCUMENT
# =========================================================

@dp.message(
    OrderState.waiting_receipt,
    F.document
)
async def receipt_document_handler(
    message: Message,
    state: FSMContext
):
    await message.answer(
        "📸 Лутфан чекро ҳамчун <b>сурат</b> фиристед."
    )


# =========================================================
# ADMIN ACCEPT
# =========================================================

@dp.callback_query(F.data.startswith("accept_"))
async def accept_order(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer(
            "⛔ Шумо админ нестед.",
            show_alert=True
        )
        return

    _, order_id, user_id = callback.data.split("_")

    cursor.execute(
        "UPDATE orders SET status = ? WHERE id = ?",
        ("accepted", order_id)
    )

    db.commit()

    await bot.send_message(
        int(user_id),
        f"✅ <b>Фармоиш #{order_id} қабул шуд!</b>\n\n"
        "💎 Фармоиши шумо барои иҷро қабул гардид.\n"
        "⚡ Лутфан каме интизор шавед.\n\n"
        "🆘 Дастгирӣ: @Zokirjon0555"
    )

    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n✅ <b>ҚАБУЛ ШУД</b>"
    )

    await callback.answer("Фармоиш қабул шуд ✅")


# =========================================================
# ADMIN REJECT
# =========================================================

@dp.callback_query(F.data.startswith("reject_"))
async def reject_order(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer(
            "⛔ Шумо админ нестед.",
            show_alert=True
        )
        return

    _, order_id, user_id = callback.data.split("_")

    cursor.execute(
        "UPDATE orders SET status = ? WHERE id = ?",
        ("rejected", order_id)
    )

    db.commit()

    await bot.send_message(
        int(user_id),
        f"❌ <b>Фармоиш #{order_id} рад шуд.</b>\n\n"
        "Агар савол дошта бошед, бо дастгирӣ тамос гиред:\n"
        "🆘 @Zokirjon0555"
    )

    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n❌ <b>РАД ШУД</b>"
    )

    await callback.answer("Фармоиш рад шуд ❌")


# =========================================================
# PROFILE
# =========================================================

@dp.callback_query(F.data == "profile")
async def profile_handler(callback: CallbackQuery):
    user_id = callback.from_user.id

    cursor.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id = ?",
        (user_id,)
    )

    total = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id = ? AND status = 'accepted'",
        (user_id,)
    )

    accepted = cursor.fetchone()[0]

    await callback.message.edit_text(
        "👤 <b>ПРОФИЛ</b>\n\n"
        f"🆔 Telegram ID: <code>{user_id}</code>\n"
        f"📦 Ҳамаи фармоишҳо: <b>{total}</b>\n"
        f"✅ Фармоишҳои қабулшуда: <b>{accepted}</b>\n\n"
        "🔥 TAJ.DONAT.FF\n"
        "⚡ Хизматрасонӣ 24/7",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💎 Донат кардан",
                        callback_data="donate"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 Меню",
                        callback_data="home"
                    )
                ]
            ]
        )
    )

    await callback.answer()


# =========================================================
# SUPPORT
# =========================================================

@dp.callback_query(F.data == "support")
async def support_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "🆘 <b>ДАСТГИРӢ 24/7</b>\n\n"
        "Агар савол ё мушкилӣ дошта бошед, ба администратор нависед:\n\n"
        f"👨‍💼 {SUPPORT_USERNAME}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💬 Навиштан ба админ",
                        url="https://t.me/Zokirjon0555"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 Меню",
                        callback_data="home"
                    )
                ]
            ]
        )
    )

    await callback.answer()


# =========================================================
# INFO
# =========================================================

@dp.callback_query(F.data == "info")
async def info_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "ℹ️ <b>ДАР БОРАИ TAJ.DONAT.FF</b>\n\n"
        "💎 Донати Free Fire СНГ\n"
        "⚡ Қабули фармоиш зуд\n"
        "🔐 Пардохти бехатар\n"
        "🧾 Санҷиши чек\n"
        "👨‍💼 Назорати админ\n"
        "💬 Дастгирӣ 24/7\n\n"
        "🔥 TAJ.DONAT.FF",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🏠 Меню",
                        callback_data="home"
                    )
                ]
            ]
        )
    )

    await callback.answer()


# =========================================================
# FF SETTINGS
# =========================================================

@dp.callback_query(F.data == "ff_settings")
async def ff_settings_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎯 <b>ТАНЗИМОТИ FREE FIRE</b>\n\n"
        "Дар ин қисм баъдтар метавонем:\n\n"
        "🎯 Sensitivity\n"
        "🔫 HUD\n"
        "📱 DPI\n"
        "⚡ Settings барои телефонҳои гуногун\n\n"
        "Ин бахш омода барои васеъкунӣ аст.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🏠 Меню",
                        callback_data="home"
                    )
                ]
            ]
        )
    )

    await callback.answer()


# =========================================================
# ERROR HANDLER
# =========================================================

@dp.errors()
async def errors_handler(event):
    logging.exception("Bot error: %s", event.exception)


# =========================================================
# RUN
# =========================================================

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    logging.info("TAJ.DONAT.FF bot started")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
