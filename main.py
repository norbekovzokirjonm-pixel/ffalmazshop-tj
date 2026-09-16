import os
import sqlite3
import secrets
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============================================================
# TAJ.DONAT.FF
# Telegram bot for Free Fire / PUBG orders.
#
# IMPORTANT:
# - Do not hard-code the BotFather token in this file.
# - Set BOT_TOKEN as an environment variable.
# - Set ADMIN_USERNAME without @, e.g. Zokirjon0555
# - Set REQUIRED_CHANNEL to the channel username, e.g. @my_channel
# - Real automatic Fazercards/game delivery needs the provider's
#   official API credentials and API documentation. This code
#   keeps that part behind a safe adapter and uses admin approval
#   by default instead of pretending a payment/receipt is verified.
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Zokirjon0555")
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "")  # e.g. @my_channel

BOT_NAME = "TAJ.DONAT.FF"
PAYMENT_PHONE = "+992935710406"
DB_FILE = "donatiko.db"

# Products are editable from the admin panel.
# "price" is in somoni. Change the values to your real prices.
DEFAULT_PRODUCTS = [
    ("ff_cis_20", "🌍 Free Fire СНГ", "20 💎", 20.00, "ff_cis"),
    ("ff_cis_40", "🌍 Free Fire СНГ", "40 💎", 40.00, "ff_cis"),
    ("ff_cis_80", "🌍 Free Fire СНГ", "80 💎", 80.00, "ff_cis"),
    ("ff_cis_100", "🌍 Free Fire СНГ", "100 💎", 100.00, "ff_cis"),
    ("ff_cis_200", "🌍 Free Fire СНГ", "200 💎", 200.00, "ff_cis"),
    ("ff_cis_300", "🌍 Free Fire СНГ", "300 💎", 300.00, "ff_cis"),
    ("ff_cis_400", "🌍 Free Fire СНГ", "400 💎", 400.00, "ff_cis"),

    ("ff_id_20", "🇮🇩 Free Fire Indonesia", "20 💎", 20.00, "ff_id"),
    ("ff_id_40", "🇮🇩 Free Fire Indonesia", "40 💎", 40.00, "ff_id"),
    ("ff_id_80", "🇮🇩 Free Fire Indonesia", "80 💎", 80.00, "ff_id"),
    ("ff_id_100", "🇮🇩 Free Fire Indonesia", "100 💎", 100.00, "ff_id"),
    ("ff_id_200", "🇮🇩 Free Fire Indonesia", "200 💎", 200.00, "ff_id"),
    ("ff_id_300", "🇮🇩 Free Fire Indonesia", "300 💎", 300.00, "ff_id"),
    ("ff_id_400", "🇮🇩 Free Fire Indonesia", "400 💎", 400.00, "ff_id"),
]


# ------------------------- DATABASE -------------------------

def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            code TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            amount TEXT NOT NULL,
            price REAL NOT NULL,
            region TEXT NOT NULL,
            enabled INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            product_code TEXT NOT NULL,
            game_id TEXT,
            nickname TEXT,
            region TEXT,
            amount TEXT NOT NULL,
            price REAL NOT NULL,
            payment_method TEXT,
            status TEXT NOT NULL,
            receipt_file_id TEXT,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
    """)

    for p in DEFAULT_PRODUCTS:
        cur.execute("""
            INSERT OR IGNORE INTO products
            (code, title, amount, price, region, enabled)
            VALUES (?, ?, ?, ?, ?, 1)
        """, p)

    conn.commit()
    conn.close()


def save_user(user):
    conn = db()
    conn.execute("""
        INSERT INTO users(user_id, username, first_name, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name
    """, (
        user.id,
        user.username or "",
        user.first_name or "",
        datetime.now().isoformat(timespec="seconds"),
    ))
    conn.commit()
    conn.close()


def get_product(code):
    conn = db()
    row = conn.execute(
        "SELECT * FROM products WHERE code=? AND enabled=1", (code,)
    ).fetchone()
    conn.close()
    return row


def get_order(order_no):
    conn = db()
    row = conn.execute(
        "SELECT * FROM orders WHERE order_no=?", (order_no,)
    ).fetchone()
    conn.close()
    return row


def is_admin(user):
    return (user.username or "").lower() == ADMIN_USERNAME.lower()


def new_order_no():
    # Example: SH-DONAT TJ #21345
    conn = db()
    while True:
        number = secrets.randbelow(90000) + 10000
        order_no = f"SH-DONAT TJ #{number}"
        exists = conn.execute(
            "SELECT 1 FROM orders WHERE order_no=?", (order_no,)
        ).fetchone()
        if not exists:
            conn.close()
            return order_no


# ------------------------- SUBSCRIPTION -------------------------

async def subscribed(user, context):
    if not REQUIRED_CHANNEL:
        return True

    try:
        member = await context.bot.get_chat_member(
            chat_id=REQUIRED_CHANNEL,
            user_id=user.id,
        )
        return member.status in ("member", "administrator", "creator")
    except Exception:
        # If the bot cannot check the channel, do not falsely claim
        # the user is subscribed.
        return False


def subscription_keyboard():
    rows = []
    if REQUIRED_CHANNEL:
        rows.append([
            InlineKeyboardButton(
                "📢 Обуна шудан",
                url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}",
            )
        ])
    rows.append([
        InlineKeyboardButton("✅ Обуна шудам", callback_data="check_sub")
    ])
    return InlineKeyboardMarkup(rows)


async def subscription_gate(update, context):
    user = update.effective_user
    if await subscribed(user, context):
        return True

    text = (
        f"👋 <b>Хуш омадед ба {BOT_NAME}!</b>\n\n"
        "Барои истифодаи бот аввал ба канали мо обуна шавед.\n\n"
        "1️⃣ «📢 Обуна шудан»-ро пахш кунед\n"
        "2️⃣ Ба канал обуна шавед\n"
        "3️⃣ Баъд «✅ Обуна шудам»-ро пахш кунед"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=subscription_keyboard(),
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=subscription_keyboard(),
        )
    return False


# ------------------------- KEYBOARDS -------------------------

def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎮 Бозиҳо", callback_data="games"),
            InlineKeyboardButton("✈️ Telegram", callback_data="telegram"),
        ],
        [
            InlineKeyboardButton("👤 Профил", callback_data="profile"),
            InlineKeyboardButton("🔗 Реферал", callback_data="referral"),
        ],
        [
            InlineKeyboardButton("⭐ Отзыв", callback_data="review"),
            InlineKeyboardButton("🆘 Дастгирӣ", callback_data="support"),
        ],
        [
            InlineKeyboardButton("❓ Саволҳои маъмул", callback_data="faq"),
            InlineKeyboardButton("📚 Дастур", callback_data="guide"),
        ],
        [
            InlineKeyboardButton("🎁 Тӯҳфаи ройгон", callback_data="gift"),
        ],
    ])


def games_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌍 Free Fire — СНГ", callback_data="ff_cis")],
        [InlineKeyboardButton("🇮🇩 Free Fire — Indonesia", callback_data="ff_id")],
        [InlineKeyboardButton("🇧🇷 Free Fire Brazil", callback_data="ff_br")],
        [InlineKeyboardButton("🎮 PUBG Mobile", callback_data="pubg")],
        [InlineKeyboardButton("↩️ Бозгашт", callback_data="back")],
    ])


def admin_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Нархҳо", callback_data="admin_prices"),
            InlineKeyboardButton("📦 Фармоишҳо", callback_data="admin_orders"),
        ],
        [
            InlineKeyboardButton("➕ Иловаи товар", callback_data="admin_add_help"),
            InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        ],
        [
            InlineKeyboardButton("↩️ Меню", callback_data="back"),
        ],
    ])


def payment_keyboard(order_no):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "💰 Пардохт кардан",
            callback_data=f"pay_{order_no}"
        )],
        [InlineKeyboardButton(
            "📸 Чекро фиристодам",
            callback_data=f"receipt_{order_no}"
        )],
        [InlineKeyboardButton(
            "❌ Бекор кардан",
            callback_data=f"cancel_{order_no}"
        )],
    ])


# ------------------------- START -------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)

    if not await subscription_gate(update, context):
        return

    user = update.effective_user
    text = (
        f"💎 <b>{BOT_NAME}</b>\n\n"
        f"Хуш омадед, <b>{user.first_name}</b>! ✨\n\n"
        f"🆔 ID-и шумо: <code>{user.id}</code>\n\n"
        "🔥 Донати худкор — зуд ва осон!\n"
        "✅ Пардохт бо усулҳои дастрас\n\n"
        "👇 Аз меню интихоб кунед:"
    )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


# ------------------------- ORDER FLOW -------------------------

async def show_products(query, region):
    conn = db()
    rows = conn.execute("""
        SELECT * FROM products
        WHERE region=? AND enabled=1
        ORDER BY price ASC
    """, (region,)).fetchall()
    conn.close()

    if not rows:
        await query.edit_message_text(
            "Ҳоло товарҳо барои ин минтақа нестанд.",
            reply_markup=games_menu(),
        )
        return

    buttons = []
    for row in rows:
        buttons.append([
            InlineKeyboardButton(
                f"{row['amount']} — {row['price']:.2f} см",
                callback_data=f"product_{row['code']}",
            )
        ])
    buttons.append([
        InlineKeyboardButton("↩️ Бозгашт", callback_data="games")
    ])

    title = rows[0]["title"]
    await query.edit_message_text(
        f"🎮 <b>{title}</b>\n\n"
        "Миқдори донатро интихоб кунед:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def create_order(update, context, product_code):
    query = update.callback_query
    product = get_product(product_code)

    if not product:
        await query.edit_message_text(
            "❌ Товар ёфт нашуд.",
            reply_markup=games_menu(),
        )
        return

    context.user_data["pending_product"] = product_code
    context.user_data["order_step"] = "game_id"

    await query.edit_message_text(
        f"💎 <b>{product['title']}</b>\n"
        f"📦 {product['amount']}\n"
        f"💰 {product['price']:.2f} см\n\n"
        "🆔 <b>ID-и бозигарро фиристед:</b>\n"
        "Масалан: <code>6439367152</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Бекор", callback_data="back")]
        ]),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)

    if not await subscribed(update.effective_user, context):
        await subscription_gate(update, context)
        return

    step = context.user_data.get("order_step")

    if step == "game_id":
        game_id = update.message.text.strip()

        if not game_id.isdigit():
            await update.message.reply_text(
                "❌ ID бояд рақам бошад. Дубора фиристед."
            )
            return

        context.user_data["game_id"] = game_id
        context.user_data["order_step"] = "nickname"

        await update.message.reply_text(
            "👤 <b>Ники бозигарро фиристед:</b>\n\n"
            "Масалан: Player0555",
            parse_mode=ParseMode.HTML,
        )
        return

    if step == "nickname":
        nickname = update.message.text.strip()

        if len(nickname) < 2 or len(nickname) > 32:
            await update.message.reply_text(
                "❌ Ник бояд аз 2 то 32 аломат бошад."
            )
            return

        context.user_data["nickname"] = nickname
        context.user_data["order_step"] = "region"

        await update.message.reply_text(
            "🌍 <b>Регионро интихоб кунед:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌍 СНГ", callback_data="region_cis")],
                [InlineKeyboardButton("🇮🇩 Indonesia", callback_data="region_id")],
                [InlineKeyboardButton("🇧🇷 Brazil", callback_data="region_br")],
            ]),
        )
        return

    await update.message.reply_text(
        "Аз меню истифода баред 👇",
        reply_markup=main_menu(),
    )


async def choose_region(query, context, region):
    product_code = context.user_data.get("pending_product")
    product = get_product(product_code)

    if not product:
        await query.edit_message_text(
            "❌ Фармоиш ёфт нашуд.",
            reply_markup=games_menu(),
        )
        return

    # Generate order number and save it.
    order_no = new_order_no()
    now = datetime.now()
    expires = now + timedelta(minutes=10)

    conn = db()
    conn.execute("""
        INSERT INTO orders(
            order_no, user_id, product_code, game_id, nickname, region,
            amount, price, payment_method, status,
            receipt_file_id, created_at, expires_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_no,
        query.from_user.id,
        product["code"],
        context.user_data.get("game_id", ""),
        context.user_data.get("nickname", ""),
        region,
        product["amount"],
        product["price"],
        "",
        "WAITING_PAYMENT",
        "",
        now.isoformat(timespec="seconds"),
        expires.isoformat(timespec="seconds"),
    ))
    conn.commit()
    conn.close()

    context.user_data.clear()

    text = (
        "💳 <b>Пардохт тавассути 🏦 Эсхата Online / ICB Mobile</b>\n\n"
        f"🆔 <b>Фармоиш:</b> {order_no}\n"
        f"📦 <b>{product['amount']}</b>\n"
        f"💰 <b>Маблағи дақиқ:</b> {product['price']:.2f} см\n\n"
        "1️⃣ Тугмаи «💰 Пардохт кардан»-ро пахш кунед\n"
        f"2️⃣ Маблағи дақиқ <b>{product['price']:.2f} см</b>-ро пардохт кунед\n"
        "3️⃣ Расми чекро ба ҳамин чат фиристед\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "📱 <b>Эсхата Online</b> — маблағро ба ин рақам равон кунед:\n\n"
        f"<code>{PAYMENT_PHONE}</code>\n"
        "👆 Рақамро пахш карда нусхабардорӣ кунед\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "⏳ Шумо <b>10 дақиқа</b> вақт доред!\n"
        "⚠️ Маблағ бояд дақиқ бошад!\n\n"
        "📸 Баъди пардохт чеки воқеиро ба ҳамин чат фиристед."
    )

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=payment_keyboard(order_no),
    )


# ------------------------- RECEIPT -------------------------

async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await subscribed(update.effective_user, context):
        await subscription_gate(update, context)
        return

    photo = update.message.photo[-1]
    caption = (update.message.caption or "").strip()

    # User may send the order number in the caption.
    order_no = caption if caption.startswith("SH-DONAT TJ #") else None

    if not order_no:
        # If there is exactly one recent waiting order, use it.
        conn = db()
        row = conn.execute("""
            SELECT order_no FROM orders
            WHERE user_id=?
              AND status='WAITING_PAYMENT'
            ORDER BY id DESC LIMIT 1
        """, (update.effective_user.id,)).fetchone()
        conn.close()
        if row:
            order_no = row["order_no"]

    if not order_no:
        await update.message.reply_text(
            "❌ Рақами фармоишро муайян карда натавонистам.\n"
            "Чекро бо caption-и монанди <code>SH-DONAT TJ #21345</code> фиристед.",
            parse_mode=ParseMode.HTML,
        )
        return

    order = get_order(order_no)
    if not order or order["user_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Фармоиш ёфт нашуд.")
        return

    if order["status"] != "WAITING_PAYMENT":
        await update.message.reply_text(
            f"ℹ️ Фармоиш аллакай дар ҳолати: {order['status']}"
        )
        return

    conn = db()
    conn.execute("""
        UPDATE orders
        SET receipt_file_id=?, status='RECEIPT_RECEIVED'
        WHERE order_no=?
    """, (photo.file_id, order_no))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Чек қабул шуд!\n\n"
        f"🆔 Фармоиш: <code>{order_no}</code>\n"
        "⏳ Чек барои санҷиш фиристода шуд.\n"
        "Пас аз тасдиқ фармоиш иҷро мешавад.",
        parse_mode=ParseMode.HTML,
    )

    # Send receipt to admin with approve/reject buttons.
    try:
        admin_chat = await context.bot.get_chat(f"@{ADMIN_USERNAME}")
        await context.bot.send_photo(
            chat_id=admin_chat.id,
            photo=photo.file_id,
            caption=(
                f"📥 <b>ЧЕКИ НАВ</b>\n\n"
                f"🆔 {order_no}\n"
                f"👤 @{update.effective_user.username or 'без username'}\n"
                f"📦 {order['amount']}\n"
                f"💰 {order['price']:.2f} см\n"
                f"🎮 ID: {order['game_id']}\n"
                f"👤 Ник: {order['nickname']}\n"
                f"🌍 Регион: {order['region']}"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "✅ Тасдиқ",
                        callback_data=f"approve_{order_no}"
                    ),
                    InlineKeyboardButton(
                        "❌ Рад",
                        callback_data=f"reject_{order_no}"
                    ),
                ]
            ]),
        )
    except Exception:
        # Admin can still use the order list if username/chat access
        # is unavailable.
        pass


# ------------------------- CALLBACKS -------------------------

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    save_user(user)

    data = query.data

    if data == "check_sub":
        if await subscribed(user, context):
            await query.edit_message_text(
                f"✅ Обуна тасдиқ шуд!\n\n"
                f"Хуш омадед ба <b>{BOT_NAME}</b> 👋",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu(),
            )
        else:
            await query.answer(
                "❌ Ҳоло обуна будани шумо тасдиқ нашуд.",
                show_alert=True,
            )
        return

    if not await subscribed(user, context):
        await subscription_gate(update, context)
        return

    if data == "games":
        await query.edit_message_text(
            "🎮 <b>Бозиҳо</b>\n\nБарои кадом бозӣ харидан мехоҳед?",
            parse_mode=ParseMode.HTML,
            reply_markup=games_menu(),
        )
        return

    if data in ("ff_cis", "ff_id", "ff_br"):
        region = {
            "ff_cis": "ff_cis",
            "ff_id": "ff_id",
            "ff_br": "ff_br",
        }[data]
        await show_products(query, region)
        return

    if data.startswith("product_"):
        await create_order(update, context, data.replace("product_", ""))
        return

    if data.startswith("region_"):
        await choose_region(
            query,
            context,
            data.replace("region_", ""),
        )
        return

    if data == "pubg":
        await query.edit_message_text(
            "🎮 <b>PUBG Mobile</b>\n\n"
            "Барои PUBG API/товарҳои алоҳида илова кардан мумкин аст.",
            parse_mode=ParseMode.HTML,
            reply_markup=games_menu(),
        )
        return

    if data.startswith("pay_"):
        order_no = data.replace("pay_", "", 1)
        order = get_order(order_no)

        if not order:
            await query.answer("Фармоиш ёфт нашуд.", show_alert=True)
            return

        await query.answer(
            f"Маблағ: {order['price']:.2f} см",
            show_alert=True,
        )
        return

    if data.startswith("receipt_"):
        order_no = data.replace("receipt_", "", 1)
        await query.edit_message_text(
            f"📸 <b>Чеки фармоиш {order_no}</b>\n\n"
            "Ҳоло расми чеки пардохтро ба ҳамин чат фиристед.\n"
            "Дар caption рақами фармоишро ҳам навишта метавонед.",
            parse_mode=ParseMode.HTML,
        )
        return

    if data.startswith("cancel_"):
        order_no = data.replace("cancel_", "", 1)
        conn = db()
        conn.execute(
            "UPDATE orders SET status='CANCELLED' "
            "WHERE order_no=? AND user_id=? AND status='WAITING_PAYMENT'",
            (order_no, user.id),
        )
        conn.commit()
        conn.close()

        await query.edit_message_text(
            "❌ Фармоиш бекор карда шуд.",
            reply_markup=main_menu(),
        )
        return

    # -------- ADMIN --------
    if data.startswith("approve_") or data.startswith("reject_"):
        if not is_admin(user):
            await query.answer(
                "⛔ Танҳо админ метавонад ин амалро иҷро кунад.",
                show_alert=True,
            )
            return

        approve = data.startswith("approve_")
        order_no = data.split("_", 1)[1]
        order = get_order(order_no)

        if not order:
            await query.answer("Фармоиш ёфт нашуд.", show_alert=True)
            return

        new_status = "APPROVED" if approve else "REJECTED"

        conn = db()
        conn.execute(
            "UPDATE orders SET status=? WHERE order_no=?",
            (new_status, order_no),
        )
        conn.commit()
        conn.close()

        try:
            if approve:
                await context.bot.send_message(
                    order["user_id"],
                    f"✅ <b>Пардохт тасдиқ шуд!</b>\n\n"
                    f"🆔 {order_no}\n"
                    f"📦 {order['amount']}\n\n"
                    "Фармоиш барои иҷро қабул шуд.",
                    parse_mode=ParseMode.HTML,
                )
            else:
                await context.bot.send_message(
                    order["user_id"],
                    f"❌ <b>Чек тасдиқ нашуд.</b>\n\n"
                    f"🆔 {order_no}\n"
                    "Лутфан чеки дуруст фиристед ё ба админ муроҷиат кунед.",
                    parse_mode=ParseMode.HTML,
                )
        except Exception:
            pass

        await query.edit_message_caption(
            caption=(
                f"📦 {order_no}\n"
                f"Статус: {'✅ APPROVED' if approve else '❌ REJECTED'}"
            )
        )
        return

    if data == "admin_prices":
        if not is_admin(user):
            await query.answer("⛔ Дастрасӣ нест.", show_alert=True)
            return

        conn = db()
        rows = conn.execute(
            "SELECT * FROM products ORDER BY region, price"
        ).fetchall()
        conn.close()

        buttons = []
        for row in rows:
            buttons.append([
                InlineKeyboardButton(
                    f"{row['title']} | {row['amount']} = {row['price']:.2f} см",
                    callback_data=f"editprice_{row['code']}",
                )
            ])

        buttons.append([
            InlineKeyboardButton("↩️ Админ", callback_data="admin")
        ])

        await query.edit_message_text(
            "💰 <b>Нархҳо</b>\n\n"
            "Барои тағйир додани нарх товарро интихоб кунед.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    if data.startswith("editprice_"):
        if not is_admin(user):
            return

        code = data.replace("editprice_", "")
        product = get_product(code)
        if not product:
            await query.answer("Товар ёфт нашуд.", show_alert=True)
            return

        context.user_data["admin_action"] = f"price:{code}"

        await query.edit_message_text(
            f"✏️ <b>Тағйири нарх</b>\n\n"
            f"{product['title']} — {product['amount']}\n"
            f"Нархи ҳозира: {product['price']:.2f} см\n\n"
            "Нархи нави сомониро фиристед.\n"
            "Масалан: <code>26.50</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    if data == "admin_add_help":
        if not is_admin(user):
            return

        await query.edit_message_text(
            "➕ <b>Иловаи товар</b>\n\n"
            "Барои содда нигоҳ доштани бот, товарҳои асосӣ дар DB ҳастанд.\n"
            "Нархҳоро аз «💰 Нархҳо» иваз кунед.\n\n"
            "Барои иловаи региона/маҳсулоти нав, DEFAULT_PRODUCTS "
            "дар main.py-ро тағйир диҳед.",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_menu(),
        )
        return

    if data == "admin_orders":
        if not is_admin(user):
            return

        conn = db()
        rows = conn.execute("""
            SELECT * FROM orders
            ORDER BY id DESC LIMIT 10
        """).fetchall()
        conn.close()

        if not rows:
            text = "📦 Фармоишҳо ҳоло нестанд."
        else:
            lines = ["📦 <b>10 фармоиши охирин</b>\n"]
            for row in rows:
                lines.append(
                    f"🆔 <code>{row['order_no']}</code>\n"
                    f"📦 {row['amount']} | 💰 {row['price']:.2f} см\n"
                    f"📌 {row['status']}\n"
                    f"🎮 ID: {row['game_id']}\n"
                )
            text = "\n".join(lines)

        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=admin_menu(),
        )
        return

    if data == "admin_stats":
        if not is_admin(user):
            return

        conn = db()
        users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        orders = conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
        approved = conn.execute(
            "SELECT COUNT(*) c FROM orders WHERE status='APPROVED'"
        ).fetchone()["c"]
        revenue = conn.execute(
            "SELECT COALESCE(SUM(price),0) s FROM orders WHERE status='APPROVED'"
        ).fetchone()["s"]
        conn.close()

        await query.edit_message_text(
            f"📊 <b>Статистика</b>\n\n"
            f"👥 Корбарон: {users}\n"
            f"📦 Фармоишҳо: {orders}\n"
            f"✅ Тасдиқшуда: {approved}\n"
            f"💰 Даромади тасдиқшуда: {revenue:.2f} см",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_menu(),
        )
        return

    if data == "admin":
        if not is_admin(user):
            await query.answer("⛔ Дастрасӣ нест.", show_alert=True)
            return

        await query.edit_message_text(
            f"👨‍💻 <b>Админ-панели {BOT_NAME}</b>\n\n"
            "Нархҳо ва фармоишҳоро аз ҳамин ҷо идора кунед.",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_menu(),
        )
        return

    # -------- MAIN MENU --------

    if data == "telegram":
        await query.edit_message_text(
            "✈️ <b>Telegram</b>\n\n"
            "Қисми Telegram.",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )
        return

    if data == "profile":
        conn = db()
        row = conn.execute(
            "SELECT * FROM users WHERE user_id=?", (user.id,)
        ).fetchone()
        conn.close()

        balance = row["balance"] if row else 0
        await query.edit_message_text(
            f"👤 <b>Профил</b>\n\n"
            f"👤 {user.first_name}\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"💰 Баланс: <b>{balance:.2f} см</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )
        return

    if data == "referral":
        me = await context.bot.get_me()
        link = f"https://t.me/{me.username}?start=ref_{user.id}"
        await query.edit_message_text(
            "🔗 <b>Реферал</b>\n\n"
            "Линки шахсии шумо:\n"
            f"<code>{link}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )
        return

    if data == "review":
        await query.edit_message_text(
            "⭐ <b>Отзыв</b>\n\n"
            f"Ба админ нависед: @{ADMIN_USERNAME}",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )
        return

    if data == "support":
        await query.edit_message_text(
            "🆘 <b>Дастгирӣ</b>\n\n"
            f"Админ: @{ADMIN_USERNAME}",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )
        return

    if data == "faq":
        await query.edit_message_text(
            "❓ <b>Саволҳои маъмул</b>\n\n"
            "1️⃣ Донат чанд вақт мегирад?\n"
            "→ Баъди тасдиқи пардохт иҷро мешавад.\n\n"
            "2️⃣ Агар чек нодуруст бошад?\n"
            "→ Админ чекро рад мекунад ва шумо метавонед чеки дуруст фиристед.\n\n"
            "3️⃣ Барои мушкилӣ ба кӣ нависам?\n"
            f"→ @{ADMIN_USERNAME}",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )
        return

    if data == "guide":
        await query.edit_message_text(
            "📚 <b>Дастур</b>\n\n"
            "1️⃣ Бозиҳоро интихоб кунед.\n"
            "2️⃣ Регионро интихоб кунед.\n"
            "3️⃣ Миқдори донатро интихоб кунед.\n"
            "4️⃣ ID-и бозигарро нависед.\n"
            "5️⃣ Никро нависед.\n"
            "6️⃣ Регионро тасдиқ кунед.\n"
            "7️⃣ Маблағи дақиқро пардохт кунед.\n"
            "8️⃣ Расми чекро фиристед.\n"
            "9️⃣ Баъди тасдиқ фармоиш иҷро мешавад.",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )
        return

    if data == "gift":
        await query.edit_message_text(
            "🎁 <b>Тӯҳфаи ройгон</b>\n\n"
            "Баъзе харидорон метавонанд тӯҳфаи тасодуфӣ гиранд.",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )
        return

    if data == "back":
        await query.edit_message_text(
            "👇 <b>Менюи асосӣ</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )
        return


# ------------------------- ADMIN TEXT COMMANDS -------------------------

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("⛔ Дастрасӣ нест.")
        return

    await update.message.reply_text(
        f"👨‍💻 <b>{BOT_NAME} — Админ</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_menu(),
    )


async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        return

    action = context.user_data.get("admin_action")
    if not action:
        return

    if action.startswith("price:"):
        code = action.split(":", 1)[1]

        try:
            price = float(update.message.text.replace(",", ".").strip())
            if price <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Нарх нодуруст аст. Масалан: 26.50"
            )
            return

        conn = db()
        conn.execute(
            "UPDATE products SET price=? WHERE code=?",
            (price, code),
        )
        conn.commit()
        conn.close()

        context.user_data.pop("admin_action", None)

        await update.message.reply_text(
            f"✅ Нарх ба <b>{price:.2f} см</b> иваз шуд.",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_menu(),
        )


# ------------------------- ERROR / RUN -------------------------

async def error_handler(update, context):
    print("ERROR:", context.error)


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN ёфт нашуд. Дар GitHub/hosting онро ҳамчун Secret/Environment Variable гузоред."
        )

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))

    app.add_handler(CallbackQueryHandler(callbacks))

    # Photos = receipts
    app.add_handler(MessageHandler(
        filters.PHOTO,
        receive_photo,
    ))

    # Text = ID / nickname / admin price
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_text,
    ))

    app.add_error_handler(error_handler)

    print(f"{BOT_NAME} started...")
    app.run_polling()


if __name__ == "__main__":
    main()
