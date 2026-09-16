"""
Diamond Shop Telegram bot.

Run:
    pip install -r requirements.txt
    export TELEGRAM_BOT_TOKEN="token-from-botfather"
    python main.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
PAYMENT_MODE = os.getenv("PAYMENT_MODE", "manual").strip().lower()
PAYMENT_PROVIDER_TOKEN = os.getenv(
    "TELEGRAM_PAYMENT_PROVIDER_TOKEN", ""
).strip()

PAYMENT_CARD_NUMBER = os.getenv(
    "PAYMENT_CARD_NUMBER",
    "Кортро дар настройка нависед",
).strip()

PAYMENT_CARD_NAME = os.getenv(
    "PAYMENT_CARD_NAME",
    "Diamond Shop",
).strip()

PAYMENT_INSTRUCTIONS = os.getenv(
    "PAYMENT_INSTRUCTIONS",
    "Пас аз пардохт расиди пардохтро ҳамчун акс фиристед.",
).strip()

ADMIN_IDS = {
    int(value.strip())
    for value in os.getenv("ADMIN_IDS", "").split(",")
    if value.strip().isdigit()
}

ORDERS_FILE = Path(os.getenv("ORDERS_FILE", "orders.json"))


PACKAGES: dict[str, dict[str, Any]] = {
    "d100": {
        "diamonds": 100,
        "price": 12,
        "label": "100 алмос",
        "popular": False,
    },
    "d310": {
        "diamonds": 310,
        "price": 34,
        "label": "310 алмос",
        "popular": True,
    },
    "d520": {
        "diamonds": 520,
        "price": 55,
        "label": "520 алмос",
        "popular": False,
    },
    "d1060": {
        "diamonds": 1060,
        "price": 105,
        "label": "1060 алмос",
        "popular": False,
    },
    "d2180": {
        "diamonds": 2180,
        "price": 205,
        "label": "2180 алмос",
        "popular": False,
    },
    "d5600": {
        "diamonds": 5600,
        "price": 490,
        "label": "5600 алмос",
        "popular": False,
    },
}


REGIONS = {
    "region_cis": "CIS / СНГ",
    "region_eu": "Europe / Аврупо",
    "region_me": "Middle East / Ховари Миёна",
    "region_other": "Дигар",
}


(
    CHOOSING_PACKAGE,
    ENTERING_PLAYER_ID,
    ENTERING_NICKNAME,
    CHOOSING_REGION,
    CONFIRMING_ORDER,
    WAITING_RECEIPT,
) = range(6)


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("diamond-shop")

_orders_lock = asyncio.Lock()


def _read_orders() -> list[dict[str, Any]]:
    if not ORDERS_FILE.exists():
        return []

    try:
        data = json.loads(
            ORDERS_FILE.read_text(encoding="utf-8")
        )

        if isinstance(data, list):
            return data

        return []

    except (OSError, json.JSONDecodeError):
        logger.exception("Could not read orders file")
        return []


async def _save_orders(orders: list[dict[str, Any]]) -> None:
    async with _orders_lock:
        temporary = ORDERS_FILE.with_suffix(".tmp")

        temporary.write_text(
            json.dumps(
                orders,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temporary.replace(ORDERS_FILE)


async def create_order(
    user: Any,
    package_key: str,
    player_id: str,
    nickname: str,
    region: str,
) -> dict[str, Any]:
    package = PACKAGES[package_key]

    order = {
        "id": (
            f"DM-{datetime.now(timezone.utc):%y%m%d}-"
            f"{secrets.token_hex(3).upper()}"
        ),
        "status": "awaiting_payment",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "telegram_user_id": user.id,
        "telegram_username": user.username or "",
        "telegram_name": user.full_name,
        "package_key": package_key,
        "diamonds": package["diamonds"],
        "amount": package["price"],
        "currency": "TJS",
        "player_id": player_id,
        "nickname": nickname,
        "region": region,
        "receipt_file_id": "",
        "receipt_type": "",
        "admin_note": "",
    }

    orders = _read_orders()
    orders.append(order)

    await _save_orders(orders)

    return order


async def update_order(
    order_id: str,
    **changes: Any,
) -> dict[str, Any] | None:
    orders = _read_orders()
    found = None

    for order in orders:
        if order.get("id") == order_id:
            order.update(changes)
            found = order
            break

    if found:
        await _save_orders(orders)

    return found


def find_order(order_id: str | None) -> dict[str, Any] | None:
    if not order_id:
        return None

    return next(
        (
            item
            for item in _read_orders()
            if item.get("id") == order_id
        ),
        None,
    )


def money(amount: int) -> str:
    return f"{amount} сомонӣ"


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💎 Харидани алмос",
                    callback_data="buy",
                )
            ],
            [
                InlineKeyboardButton(
                    "📦 Фармоишҳои ман",
                    callback_data="my_orders",
                ),
                InlineKeyboardButton(
                    "ℹ️ Ёрӣ",
                    callback_data="help",
                ),
            ],
        ]
    )


def package_menu() -> InlineKeyboardMarkup:
    rows = []

    for key, package in PACKAGES.items():
        suffix = ""

        if package["popular"]:
            suffix = " • маъмул"

        rows.append(
            [
                InlineKeyboardButton(
                    (
                        f"{package['label']} — "
                        f"{money(package['price'])}"
                        f"{suffix}"
                    ),
                    callback_data=f"package:{key}",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                "⬅️ Ба меню",
                callback_data="home",
            )
        ]
    )

    return InlineKeyboardMarkup(rows)


def region_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "CIS / СНГ",
                    callback_data="region_cis",
                ),
                InlineKeyboardButton(
                    "Europe",
                    callback_data="region_eu",
                ),
            ],
            [
                InlineKeyboardButton(
                    "Middle East",
                    callback_data="region_me",
                ),
                InlineKeyboardButton(
                    "Дигар",
                    callback_data="region_other",
                ),
            ],
        ]
    )


def order_summary(data: dict[str, Any]) -> str:
    package = PACKAGES[data["package_key"]]

    return (
        "🧾 <b>Тафсилоти фармоиш</b>\n\n"
        f"💎 Пакет: <b>{package['label']}</b>\n"
        f"💰 Нарх: <b>{money(package['price'])}</b>\n"
        f"🆔 Player ID: "
        f"<code>{data['player_id']}</code>\n"
        f"👤 Nickname: <b>{data['nickname']}</b>\n"
        f"🌍 Region: <b>{data['region']}</b>\n\n"
        "Маълумотро санҷед. Агар ҳамааш дуруст бошад, тасдиқ кунед."
    )


def confirmation_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Тасдиқ ва пардохт",
                    callback_data="confirm_order",
                )
            ],
            [
                InlineKeyboardButton(
                    "✏️ Аз нав пур кардан",
                    callback_data="buy",
                ),
                InlineKeyboardButton(
                    "❌ Бекор кардан",
                    callback_data="cancel",
                ),
            ],
        ]
    )


def status_label(status: str) -> str:
    statuses = {
        "awaiting_payment": "Интизори пардохт",
        "receipt_submitted": "Расид фиристода шуд",
        "paid": "Пардохт шуд",
        "approved": "Иҷро шуд",
        "rejected": "Рад шуд",
        "payment_error": "Хатои пардохт",
    }

    return statuses.get(status, status)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_order_menu(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Тасдиқ",
                    callback_data=f"admin_approve:{order_id}",
                ),
                InlineKeyboardButton(
                    "❌ Рад",
                    callback_data=f"admin_reject:{order_id}",
                ),
            ]
        ]
    )


async def send_to_admins(
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
        except Exception:
            logger.exception(
                "Could not notify admin %s",
                admin_id,
            )


async def notify_admin_about_order(
    context: ContextTypes.DEFAULT_TYPE,
    order: dict[str, Any],
    receipt: bool = False,
) -> None:
    title = (
        "📥 <b>Расиди нав</b>"
        if receipt
        else "🛒 <b>Фармоиши нав</b>"
    )

    text = (
        f"{title}\n\n"
        f"🔖 ID: <code>{order['id']}</code>\n"
        f"💎 Пакет: <b>{order['diamonds']} алмос</b>\n"
        f"💰 Маблағ: <b>{money(order['amount'])}</b>\n"
        f"🆔 Player ID: "
        f"<code>{order['player_id']}</code>\n"
        f"👤 Nickname: <b>{order['nickname']}</b>\n"
        f"🌍 Region: <b>{order['region']}</b>\n"
        f"👨‍💻 User: "
        f"@{order['telegram_username'] or 'бе username'} "
        f"(<code>{order['telegram_user_id']}</code>)"
    )

    await send_to_admins(
        context,
        text,
        admin_order_menu(order["id"]),
    )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    context.user_data.clear()

    message = update.effective_message

    await message.reply_text(
        "💎 <b>Diamond Shop</b>\n\n"
        "Алмосро зуд ва осон харед.\n"
        "Пакетро интихоб кунед, Player ID ва nickname-ро нависед.",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )

    return ConversationHandler.END


async def show_home(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query

    await query.answer()

    context.user_data.clear()

    await query.edit_message_text(
        "💎 <b>Diamond Shop</b>\n\n"
        "Аз меню амалро интихоб кунед:",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )

    return ConversationHandler.END


async def begin_buy(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query

    await query.answer()

    context.user_data.clear()

    await query.edit_message_text(
        "💎 <b>Пакети алмосро интихоб кунед:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=package_menu(),
    )

    return CHOOSING_PACKAGE


async def choose_package(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query

    await query.answer()

    package_key = query.data.split(":", 1)[1]

    if package_key not in PACKAGES:
        await query.edit_message_text(
            "Ин пакет дигар дастрас нест. Аз нав кӯшиш кунед."
        )
        return ConversationHandler.END

    context.user_data["package_key"] = package_key

    await query.edit_message_text(
        "🆔 <b>Player ID-ро фиристед</b>\n\n"
        "Мисол: <code>123456789</code>\n"
        "Танҳо рақам нависед.",
        parse_mode=ParseMode.HTML,
    )

    return ENTERING_PLAYER_ID


async def receive_player_id(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    player_id = update.effective_message.text.strip()

    if not re.fullmatch(r"\d{5,15}", player_id):
        await update.effective_message.reply_text(
            "Player ID нодуруст аст. Аз 5 то 15 рақам фиристед."
        )
        return ENTERING_PLAYER_ID

    context.user_data["player_id"] = player_id

    await update.effective_message.reply_text(
        "👤 <b>Nickname-и бозингарро фиристед:</b>\n\n"
        "Мисол: <code>ALMAZ_PRO</code>",
        parse_mode=ParseMode.HTML,
    )

    return ENTERING_NICKNAME


async def receive_nickname(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    nickname = update.effective_message.text.strip()

    if not 2 <= len(nickname) <= 30:
        await update.effective_message.reply_text(
            "Nickname бояд аз 2 то 30 аломат бошад."
        )
        return ENTERING_NICKNAME

    context.user_data["nickname"] = nickname

    await update.effective_message.reply_text(
        "🌍 <b>Region-и аккаунтро интихоб кунед:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=region_menu(),
    )

    return CHOOSING_REGION


async def choose_region(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query

    await query.answer()

    region = REGIONS.get(query.data)

    if not region:
        return CHOOSING_REGION

    context.user_data["region"] = region

    await query.edit_message_text(
        order_summary(context.user_data),
        parse_mode=ParseMode.HTML,
        reply_markup=confirmation_menu(),
    )

    return CONFIRMING_ORDER


async def confirm_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query

    await query.answer()

    data = context.user_data

    required = {
        "package_key",
        "player_id",
        "nickname",
        "region",
    }

    if not required.issubset(data):
        await query.edit_message_text(
            "Сессия ба охир расид. "
            "Лутфан аз нав оғоз кунед: /start"
        )
        return ConversationHandler.END

    order = await create_order(
        update.effective_user,
        data["package_key"],
        data["player_id"],
        data["nickname"],
        data["region"],
    )

    context.user_data["order_id"] = order["id"]

    if PAYMENT_MODE == "telegram":
        if not PAYMENT_PROVIDER_TOKEN:
            await update_order(
                order["id"],
                status="payment_error",
            )

            await query.edit_message_text(
                "Пардохти онлайн ҳоло танзим нашудааст. "
                "Ба админ нависед."
            )

            logger.error(
                "Telegram payment token is missing"
            )

            return ConversationHandler.END

        package = PACKAGES[order["package_key"]]

        await query.edit_message_text(
            "Пардохтро кушода истодаем..."
        )

        await context.bot.send_invoice(
            chat_id=update.effective_chat.id,
            title=f"Diamond Shop — {package['label']}",
            description=(
                f"Алмос барои Player ID "
                f"{order['player_id']}"
            ),
            payload=order["id"],
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="TJS",
            prices=[
                LabeledPrice(
                    package["label"],
                    package["price"] * 100,
                )
            ],
            start_parameter=f"diamond-{order['id']}",
        )

        return ConversationHandler.END

    await notify_admin_about_order(
        context,
        order,
    )

    await query.edit_message_text(
        "✅ <b>Фармоиш қабул шуд</b>\n\n"
        f"🔖 Рақами фармоиш: "
        f"<code>{order['id']}</code>\n"
        f"💰 Маблағ: "
        f"<b>{money(order['amount'])}</b>\n\n"
        "💳 <b>Пардохт ба корт</b>\n"
        f"Рақами корт: "
        f"<code>{PAYMENT_CARD_NUMBER}</code>\n"
        f"Номи қабулкунанда: "
        f"<b>{PAYMENT_CARD_NAME}</b>\n\n"
        f"{PAYMENT_INSTRUCTIONS}\n"
        "Расидро ҳамин ҷо ҳамчун акс ё файл фиристед.",
        parse_mode=ParseMode.HTML,
    )

    return WAITING_RECEIPT


async def receive_receipt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    order_id = context.user_data.get("order_id")
    order = find_order(order_id)

    if not order:
        await update.effective_message.reply_text(
            "Фармоиш ёфт нашуд. "
            "Аз нав бо /start оғоз кунед."
        )
        return ConversationHandler.END

    message = update.effective_message

    if message.photo:
        file_id = message.photo[-1].file_id
        receipt_type = "photo"
    elif message.document:
        file_id = message.document.file_id
        receipt_type = "document"
    else:
        file_id = ""
        receipt_type = "text"

    await update_order(
        order_id,
        status="receipt_submitted",
        receipt_file_id=file_id,
        receipt_type=receipt_type,
        receipt_text=(
            message.text
            or message.caption
            or ""
        ),
    )

    updated = find_order(order_id) or order

    await notify_admin_about_order(
        context,
        updated,
        receipt=True,
    )

    for admin_id in ADMIN_IDS:
        try:
            if message.photo:
                await context.bot.send_photo(
                    admin_id,
                    photo=file_id,
                    caption=f"Расид барои {order_id}",
                )
            elif message.document:
                await context.bot.send_document(
                    admin_id,
                    document=file_id,
                    caption=f"Расид барои {order_id}",
                )
        except Exception:
            logger.exception(
                "Could not forward receipt to admin %s",
                admin_id,
            )

    await message.reply_text(
        f"✅ Расид қабул шуд.\n"
        f"Рақами фармоиш: {order_id}\n\n"
        "Админ пардохтро месанҷад ва баъд "
        "алмос фиристода мешавад."
    )

    return ConversationHandler.END


async def list_my_orders(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query

    await query.answer()

    user_id = update.effective_user.id

    orders = [
        order
        for order in _read_orders()
        if order.get("telegram_user_id") == user_id
    ][-10:]

    if not orders:
        await query.edit_message_text(
            "📦 Ҳоло фармоиш надоред.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "💎 Харидани алмос",
                            callback_data="buy",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "⬅️ Ба меню",
                            callback_data="home",
                        )
                    ],
                ]
            ),
        )

        return ConversationHandler.END

    lines = ["📦 <b>Фармоишҳои ман</b>\n"]

    for order in reversed(orders):
        lines.append(
            f"🔖 <code>{order['id']}</code> — "
            f"{order['diamonds']} алмос\n"
            f"   {money(order['amount'])} • "
            f"{status_label(order['status'])}\n"
        )

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "💎 Фармоиши нав",
                        callback_data="buy",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⬅️ Ба меню",
                        callback_data="home",
                    )
                ],
            ]
        ),
    )

    return ConversationHandler.END


async def show_help(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query

    await query.answer()

    await query.edit_message_text(
        "ℹ️ <b>Чӣ тавр харидан:</b>\n\n"
        "1. Пакети алмосро интихоб кунед.\n"
        "2. Player ID, nickname ва region-ро дуруст нависед.\n"
        "3. Пардохт кунед ва расидро фиристед.\n"
        "4. Админ фармоишро месанҷад.\n\n"
        "Агар хато кардед, /cancel фиристед.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⬅️ Ба меню",
                        callback_data="home",
                    )
                ]
            ]
        ),
    )

    return ConversationHandler.END


async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    context.user_data.clear()

    if update.callback_query:
        await update.callback_query.answer()

        await update.callback_query.edit_message_text(
            "Фармоиш бекор шуд.",
            reply_markup=main_menu(),
        )
    else:
        await update.effective_message.reply_text(
            "Фармоиш бекор шуд.",
            reply_markup=main_menu(),
        )

    return ConversationHandler.END


async def pre_checkout(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.pre_checkout_query
    order = find_order(query.invoice_payload)

    if not order:
        await query.answer(
            ok=False,
            error_message="Ин фармоиш дигар фаъол нест.",
        )
        return

    if order.get("status") != "awaiting_payment":
        await query.answer(
            ok=False,
            error_message="Ин фармоиш дигар фаъол нест.",
        )
        return

    if query.currency != "TJS":
        await query.answer(
            ok=False,
            error_message="Асъори пардохт нодуруст аст.",
        )
        return

    expected = int(order["amount"]) * 100

    if query.total_amount != expected:
        await query.answer(
            ok=False,
            error_message="Маблағи пардохт нодуруст аст.",
        )
        return

    await query.answer(ok=True)


async def successful_payment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    payment = update.effective_message.successful_payment

    order = await update_order(
        payment.invoice_payload,
        status="paid",
        telegram_payment_charge_id=(
            payment.telegram_payment_charge_id
        ),
        provider_payment_charge_id=(
            payment.provider_payment_charge_id
        ),
    )

    if not order:
        await update.effective_message.reply_text(
            "Пардохт омад, вале фармоиш ёфт нашуд. "
            "Ба админ фавран нависед."
        )
        return

    await notify_admin_about_order(
        context,
        order,
        receipt=False,
    )

    await update.effective_message.reply_text(
        "✅ Пардохт қабул шуд!\n\n"
        f"Рақами фармоиш: {order['id']}\n"
        "Админ фармоишро иҷро мекунад ва "
        "натиҷаро хабар медиҳад."
    )


async def admin_orders(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not is_admin(update.effective_user.id):
        return

    pending = [
        order
        for order in _read_orders()
        if order.get("status")
        in {
            "awaiting_payment",
            "receipt_submitted",
            "paid",
        }
    ][-20:]

    if not pending:
        await update.effective_message.reply_text(
            "Фармоиши интизорӣ нест."
        )
        return

    for order in reversed(pending):
        await update.effective_message.reply_text(
            f"🔖 <code>{order['id']}</code>\n"
            f"💎 {order['diamonds']} алмос • "
            f"{money(order['amount'])}\n"
            f"🆔 <code>{order['player_id']}</code> • "
            f"{order['nickname']}\n"
            f"🌍 {order['region']}\n"
            f"📌 {status_label(order['status'])}",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_order_menu(order["id"]),
        )


async def admin_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query

    if not is_admin(update.effective_user.id):
        await query.answer(
            "Дастрасӣ нест.",
            show_alert=True,
        )
        return

    await query.answer()

    action, order_id = query.data.split(":", 1)
    order = find_order(order_id)

    if not order:
        await query.edit_message_text(
            "Фармоиш ёфт нашуд."
        )
        return

    if action == "admin_approve":
        updated = await update_order(
            order_id,
            status="approved",
        )

        status = "approved"

        user_text = (
            f"✅ Фармоиши <code>{order_id}</code> иҷро шуд.\n"
            f"{order['diamonds']} алмос ба Player ID-и "
            "шумо фиристода шуд."
        )
    else:
        updated = await update_order(
            order_id,
            status="rejected",
        )

        status = "rejected"

        user_text = (
            f"❌ Фармоиши <code>{order_id}</code> рад шуд.\n"
            "Барои маълумоти бештар ба админ нависед."
        )

    if updated:
        await query.edit_message_text(
            f"Фармоиш <code>{order_id}</code>: "
            f"<b>{status_label(status)}</b>",
            parse_mode=ParseMode.HTML,
        )

        try:
            await context.bot.send_message(
                chat_id=order["telegram_user_id"],
                text=user_text,
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            logger.exception(
                "Could not notify customer for %s",
                order_id,
            )


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    logger.exception(
        "Unhandled bot error",
        exc_info=context.error,
    )


def build_application() -> Application:
    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    conversation = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(
                begin_buy,
                pattern=r"^buy$",
            ),
        ],
        states={
            CHOOSING_PACKAGE: [
                CallbackQueryHandler(
                    choose_package,
                    pattern=r"^package:",
                )
            ],
            ENTERING_PLAYER_ID: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_player_id,
                )
            ],
            ENTERING_NICKNAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_nickname,
                )
            ],
            CHOOSING_REGION: [
                CallbackQueryHandler(
                    choose_region,
                    pattern=r"^region_",
                )
            ],
            CONFIRMING_ORDER: [
                CallbackQueryHandler(
                    confirm_order,
                    pattern=r"^confirm_order$",
                ),
                CallbackQueryHandler(
                    begin_buy,
                    pattern=r"^buy$",
                ),
                CallbackQueryHandler(
                    cancel,
                    pattern=r"^cancel$",
                ),
            ],
            WAITING_RECEIPT: [
                MessageHandler(
                    (
                        filters.PHOTO
                        | filters.Document.ALL
                        | filters.TEXT
                    )
                    & ~filters.COMMAND,
                    receive_receipt,
                )
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(
                show_home,
                pattern=r"^home$",
            ),
        ],
        allow_reentry=True,
    )

    application.add_handler(conversation)

    application.add_handler(
        CommandHandler("cancel", cancel)
    )

    application.add_handler(
        CommandHandler("orders", admin_orders) **…**

_This response is too long to display in full._
