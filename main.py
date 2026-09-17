import asyncio, logging, os, sqlite3, uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from html import escape
import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN","").strip()
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME","@Zokirjon0555")
a = os.getenv("ADMIN_ID") or os.getenv("ADMIN_IDS","0").split(",")[0]
try: ADMIN_ID = int(str(a).strip())
except: ADMIN_ID = 0
BOT_NAME = os.getenv("BOT_NAME","TAJ.DONAT.FF")
SUPPORT_URL = os.getenv("SUPPORT_URL","https://t.me/otsivho")
PAYMENT_PHONE = os.getenv("PAYMENT_PHONE","+992935710406")
FAZER_API_KEY = os.getenv("FAZER_API_KEY","").strip()
FAZER_BASE = os.getenv("FAZER_BASE","https://api.fzr.cards/api/v2").strip()
DB_PATH = "bot.db"
RECEIPT_DIR = Path("receipts"); RECEIPT_DIR.mkdir(exist_ok=True)

PRODUCTS = [
    ("ff_110","💎 110 Алмаз",Decimal("7.80"),110),
    ("ff_341","💎 341 Алмаз",Decimal("24.60"),341),
    ("ff_572","💎 572 Алмаз",Decimal("43.50"),572),
    ("ff_1166","💎 1166 Алмаз",Decimal("80.00"),1166),
    ("ff_2398","💎 2398 Алмаз",Decimal("183.00"),2398),
    ("ff_6160","💎 6160 Алмаз",Decimal("460.00"),6160),
    ("week","🎟️ Ваучер Хафта",Decimal("16.00"),None),
    ("lite","🎟️ Ваучер Лайт",Decimal("5.50"),None),
    ("monthly","🎟️ Ваучер Мохона",Decimal("57.50"),None),
]

PRODUCT_MAP = {p[0]:p for p in PRODUCTS}

def db(): con=sqlite3.connect(DB_PATH); con.row_factory=sqlite3.Row; return con
def init_db():
    con=db()
    con.executescript("CREATE TABLE IF NOT EXISTS users(tg_id INTEGER PRIMARY KEY,username TEXT,first_name TEXT,balance REAL DEFAULT 0,created_at TEXT);CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT,tg_id INTEGER,amount REAL,method TEXT,status TEXT DEFAULT 'pending',proof_file_id TEXT,created_at TEXT);CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,order_no INTEGER UNIQUE,tg_id INTEGER,product_id TEXT,product_name TEXT,price REAL,player_id TEXT,nickname TEXT,region TEXT,fazer_order_id TEXT,status TEXT DEFAULT 'created',created_at TEXT);CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);")
    if not con.execute("SELECT value FROM settings WHERE key='next_order_no'").fetchone(): con.execute("INSERT INTO settings VALUES('next_order_no','21345')")
    con.commit(); con.close()
def ensure_user(u): con=db(); con.execute("INSERT INTO users(tg_id,username,first_name,created_at) VALUES(?,?,?,?) ON CONFLICT(tg_id) DO UPDATE SET username=excluded.username",(u.id,u.username or "",u.first_name or "",datetime.now().isoformat())); con.commit(); con.close()
def get_balance(tg_id): con=db(); r=con.execute("SELECT balance FROM users WHERE tg_id=?",(tg_id,)).fetchone(); con.close(); return Decimal(str(r["balance"] if r else 0))
def add_balance(tg_id,amount): con=db(); con.execute("UPDATE users SET balance=balance+? WHERE tg_id=?",(float(amount),tg_id)); con.commit(); con.close()
def take_balance(tg_id,amount): con=db(); r=con.execute("SELECT balance FROM users WHERE tg_id=?",(tg_id,)).fetchone();
    if not r or Decimal(str(r["balance"]))<amount: con.close(); return False
    con.execute("UPDATE users SET balance=balance-? WHERE tg_id=?",(float(amount),tg_id)); con.commit(); con.close(); return True

def main_menu():
    b=InlineKeyboardBuilder()
    b.button(text="🔥 Free Fire Алмазхо",callback_data="products")
    b.button(text="👤 Профил",callback_data="balance")
    b.button(text="📞 Дастгирӣ",url=SUPPORT_URL)
    b.adjust(1); return b.as_markup()
def products_kb():
    b=InlineKeyboardBuilder()
    for pid,name,price,_ in PRODUCTS: b.button(text=f"{name} — {price:g}с",callback_data=f"buy:{pid}")
    b.button(text="⬅️ Бозгашт",callback_data="home"); b.adjust(1); return b.as_markup()

class OrderState(StatesGroup): waiting_id=State(); waiting_nick=State(); waiting_region=State()
bot=Bot(BOT_TOKEN); dp=Dispatcher()

@dp.message(CommandStart())
async def start(m:Message):
    ensure_user(m.from_user)
    await m.answer(f"🎮 FF ALMAZ SHOP TJ 🎮\n\nХуш омадед! Алмазхои арзон ва зуд!\n💎 Тугмаро пахш кн:",reply_markup=main_menu())

@dp.callback_query(F.data=="home")
async def home(c:CallbackQuery,s:FSMContext):
    await s.clear(); await c.message.edit_text("🎮 FF ALMAZ SHOP TJ\nТугмаро пахш кн:",reply_markup=main_menu())

@dp.callback_query(F.data=="balance")
async def bal(c:CallbackQuery):
    b=get_balance(c.from_user.id)
    await c.message.edit_text(f"👤 Профили шумо\n💰 Баланс: {b:.2f} сом",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Бозгашт",callback_data="home")]]))

@dp.callback_query(F.data=="products")
async def prods(c:CallbackQuery):
    await c.message.edit_text("💎 Махсулотро интихоб кн - бо нарх:",reply_markup=products_kb())

@dp.callback_query(F.data.startswith("buy:"))
async def buy(c:CallbackQuery,s:FSMContext):
    pid=c.data.split(":")[1]; p=PRODUCT_MAP.get(pid)
    if not p: await c.answer("Ёфт нашуд"); return
    await s.update_data(product=p)
    await s.set_state(OrderState.waiting_id)
    await c.message.edit_text(f"🛒 {p[1]}\n💰 Нарх: {p[2]} сом\n\n🔢 UID-и Free Fire-ро навиш:")

@dp.message(OrderState.waiting_id)
async def get_id(m:Message,s:FSMContext):
    if not m.text.isdigit(): await m.answer("❌ UID факат ракам!"); return
    await s.update_data(uid=m.text); await s.set_state(OrderState.waiting_nick)
    await m.answer("👤 Nickname-ро навиш:")

@dp.message(OrderState.waiting_nick)
async def get_nick(m:Message,s:FSMContext):
    await s.update_data(nick=m.text); await s.set_state(OrderState.waiting_region)
    await m.answer("🌍 Регионро навиш (CIS):")

@dp.message(OrderState.waiting_region)
async def get_reg(m:Message,s:FSMContext):
    data=await s.get_data(); p=data['product']
    await s.clear()
    await m.answer(f"✅ Фармоиш кабул шуд!\n\n📦 {p[1]}\n💰 {p[2]} сом\n🔢 UID: {data['uid']}\n👤 Ник: {data['nick']}\n🌍 Регион: {m.text}\n\nАдмин бо шумо мепайвандад!",reply_markup=main_menu())
    if ADMIN_ID:
        try: await bot.send_message(ADMIN_ID,f"🆕 Фармоиш #{p[0]}\n👤 {m.from_user.id} @{m.from_user.username}\n{p[1]} {p[2]}с\nUID:{data['uid']}\nНик:{data['nick']}\nРегион:{m.text}")
        except: pass

async def main(): init_db(); await dp.start_polling(bot)
if __name__=="__main__": logging.basicConfig(level=logging.INFO); asyncio.run(main())
