import asyncio
import logging
import os
import sqlite3
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from html import escape
import httpx
from PIL import Image, ImageDraw, ImageFont
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
_raw_admin = os.getenv("ADMIN_ID") or os.getenv("ADMIN_IDS","0").split(",")[0]
try: ADMIN_ID = int(str(_raw_admin).strip())
except: ADMIN_ID = 0

CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME","")
BOT_NAME = os.getenv("BOT_NAME","TAJ.DONAT.FF")
SUPPORT_URL = os.getenv("SUPPORT_URL","https://t.me/otsivho")
PAYMENT_PHONE = os.getenv("PAYMENT_PHONE","+992935710406")
ESKHATA_TEXT = os.getenv("ESKHATA_TEXT","Эсхата Онлайн")
ICB_TEXT = os.getenv("ICB_TEXT","ICB Mobile")
FAZER_API_KEY = os.getenv("FAZER_API_KEY","").strip()
FAZER_BASE = os.getenv("FAZER_BASE","https://api.fzr.cards/api/v2").strip()
FAZER_FREE_FIRE_CATEGORY = os.getenv("FAZER_FREE_FIRE_CATEGORY","free_fire_cis_auto")
DB_PATH = "bot.db"
RECEIPT_DIR = Path("receipts")
RECEIPT_DIR.mkdir(exist_ok=True)

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
    ("level_6","📈 Level 6",Decimal("5.50"),None),
    ("level_10","📈 Level 10",Decimal("6.00"),None),
    ("level_15","📈 Level 15",Decimal("7.00"),None),
    ("level_20","📈 Level 20",Decimal("8.00"),None),
    ("level_25","📈 Level 25",Decimal("8.00"),None),
    ("level_30","📈 Level 30",Decimal("9.00"),None),
    ("evo_30","⚡ Evo 30 руз",Decimal("32.00"),None),
    ("evo_7","⚡ Evo 7 руз",Decimal("15.00"),None),
    ("evo_3","⚡ Evo 3 руз",Decimal("10.00"),None),
]
TOPUP_AMOUNTS = [20,50,70,100,150,200,300,500]
PRODUCT_MAP = {p[0]:p for p in PRODUCTS}

def db():
    con=sqlite3.connect(DB_PATH); con.row_factory=sqlite3.Row; return con
def init_db():
    con=db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(tg_id INTEGER PRIMARY KEY,username TEXT,first_name TEXT,balance REAL DEFAULT 0,created_at TEXT);
    CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT,tg_id INTEGER,amount REAL,method TEXT,status TEXT DEFAULT 'pending',proof_file_id TEXT,created_at TEXT,approved_at TEXT);
    CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,order_no INTEGER UNIQUE,tg_id INTEGER,product_id TEXT,product_name TEXT,price REAL,player_id TEXT,nickname TEXT,region TEXT,fazer_order_id TEXT,status TEXT DEFAULT 'created',created_at TEXT,completed_at TEXT);
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
    """)
    if not con.execute("SELECT value FROM settings WHERE key='next_order_no'").fetchone():
        con.execute("INSERT INTO settings VALUES('next_order_no','21345')")
    con.commit(); con.close()
def ensure_user(u):
    con=db(); con.execute("INSERT INTO users(tg_id,username,first_name,created_at) VALUES(?,?,?,?) ON CONFLICT(tg_id) DO UPDATE SET username=excluded.username,first_name=excluded.first_name",(u.id,u.username or "",u.first_name or "",datetime.now().isoformat())); con.commit(); con.close()
def get_balance(tg_id):
    con=db(); r=con.execute("SELECT balance FROM users WHERE tg_id=?",(tg_id,)).fetchone(); con.close(); return Decimal(str(r["balance"] if r else 0))
def add_balance(tg_id,amount):
    con=db(); con.execute("UPDATE users SET balance=balance+? WHERE tg_id=?",(float(amount),tg_id)); con.commit(); con.close()
def take_balance(tg_id,amount):
    con=db(); r=con.execute("SELECT balance FROM users WHERE tg_id=?",(tg_id,)).fetchone()
    if not r or Decimal(str(r["balance"]))<amount: con.close(); return False
    con.execute("UPDATE users SET balance=balance-? WHERE tg_id=?",(float(amount),tg_id)); con.commit(); con.close(); return True
def refund_balance(tg_id,amount): add_balance(tg_id,amount)
def create_order(tg_id,product,player_id,nickname,region):
    con=db(); order_no=int(con.execute("SELECT value FROM settings WHERE key='next_order_no'").fetchone()["value"])
    con.execute("UPDATE settings SET value=? WHERE key='next_order_no'",(str(order_no+1),))
    con.execute("INSERT INTO orders(order_no,tg_id,product_id,product_name,price,player_id,nickname,region,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(order_no,tg_id,product[0],product[1],float(product[2]),player_id,nickname,region,"created",datetime.now().isoformat()))
    oid=con.execute("SELECT last_insert_rowid()").fetchone()[0]; con.commit(); con.close(); return oid,order_no
def update_order(oid,**fields):
    con=db(); sets=", ".join(f"{k}=?" for k in fields); vals=list(fields.values())+[oid]; con.execute(f"UPDATE orders SET {sets} WHERE id=?",vals); con.commit(); con.close()
def get_order(oid):
    con=db(); r=con.execute("SELECT * FROM orders WHERE id=?",(oid,)).fetchone(); con.close(); return r
def next_pending_orders():
    con=db(); rows=con.execute("SELECT * FROM orders WHERE status IN ('processing','submitted') AND fazer_order_id IS NOT NULL").fetchall(); con.close(); return rows

def main_menu():
    b=InlineKeyboardBuilder()
    b.button(text="💎 Free Fire СНГ",callback_data="products")
    b.button(text="💳 Баланс",callback_data="balance")
    b.button(text="➕ Пур кардани баланс",callback_data="topup")
    b.button(text="📦 Харидхои ман",callback_data="my_orders")
    b.button(text="⭐ Отзыв",url=SUPPORT_URL)
    b.button(text="👨‍💼 Админ",url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")
    b.adjust(1,2,2,1,1); return b.as_markup()
def products_kb():
    b=InlineKeyboardBuilder()
    for pid,name,price,_ in PRODUCTS: b.button(text=f"{name} — {price:g}с",callback_data=f"buy:{pid}")
    b.button(text="⬅️ Бозгашт",callback_data="home"); b.adjust(1); return b.as_markup()
def topup_amount_kb():
    b=InlineKeyboardBuilder()
    for a in TOPUP_AMOUNTS: b.button(text=f"{a}с",callback_data=f"topup_amt:{a}")
    b.button(text="⬅️ Бозгашт",callback_data="home"); b.adjust(4,4,1); return b.as_markup()
def payment_method_kb(amount):
    b=InlineKeyboardBuilder()
    b.button(text=f"💳 {ESKHATA_TEXT}",callback_data=f"paymethod:eskhata:{amount}")
    b.button(text=f"💳 {ICB_TEXT}",callback_data=f"paymethod:icb:{amount}")
    b.button(text="⬅️ Бозгашт",callback_data="topup"); b.adjust(1); return b.as_markup()
def admin_payment_kb(pid):
    b=InlineKeyboardBuilder(); b.button(text="✅ КАБУЛ",callback_data=f"approve_payment:{pid}"); b.button(text="❌ РАД",callback_data=f"reject_payment:{pid}"); b.adjust(2); return b.as_markup()

class TopupState(StatesGroup): waiting_proof=State()
class OrderState(StatesGroup): waiting_id=State(); waiting_nickname=State(); waiting_region=State()

class FazerCards:
    def __init__(self,api_key,base_url):
        self.base_url=base_url.rstrip("/"); self.client=httpx.AsyncClient(timeout=25,headers={"X-API-Key":api_key,"Accept":"application/json","Content-Type":"application/json"})
    async def close(self): await self.client.aclose()
    async def get(self,path,params=None):
        r=await self.client.get(f"{self.base_url}{path}",params=params); r.raise_for_status(); return r.json()
    async def post(self,path,body):
        r=await self.client.post(f"{self.base_url}{path}",json=body,headers={"Idempotency-Key":str(uuid.uuid4())}); r.raise_for_status(); return r.json()
    async def find_free_fire_category(self):
        if FAZER_FREE_FIRE_CATEGORY: return FAZER_FREE_FIRE_CATEGORY
        return "free_fire_cis_auto"
    async def offers(self,cat):
        try: return await self.get("/topups/offers",{"category_id":cat})
        except: return {"offers":[],"fields":[]}
    async def place_order(self,category_id,offer_id,fields): return await self.post("/topups/order",{"category_id":category_id,"offer_id":offer_id,"fields":fields})
    async def get_order(self,fid): return await self.get(f"/orders/{fid}")

def font(size,bold=False):
    p="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if os.path.exists(p): return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def make_receipt(order,status="accepted"):
    W,H=1100,1500; img=Image.new("RGB",(W,H),"#111216"); d=ImageDraw.Draw(img)
    orange="#ff8a00"; green="#20d56a"; white="#f4f4f4"; gray="#a7a7ad"
    d.rounded_rectangle((35,35,W-35,H-35),radius=35,outline=orange,width=4)
    d.ellipse((480,350,620,490),fill=green)
    d.text((550,250),BOT_NAME,anchor="ma",font=font(46,True),fill=orange)
    d.text((550,540),"ПАРДОХТ ТАСДИК ШУД",anchor="ma",font=font(40,True),fill=white)
    d.rounded_rectangle((70,600,W-70,1150),radius=28,fill="#1b1c22",outline="#3b3c45",width=2)
    rows=[("Фармоиш №",f"#{order['order_no']}"),("ID",order["player_id"]),("Ник",order["nickname"]),("Регион",order["region"]),("Махсулот",order["product_name"]),("Маблаг",f"{order['price']:.2f} сом")]
    y=640
    for l,v in rows:
        d.text((110,y),l,font=font(27),fill=gray); d.text((990,y),str(v),anchor="ra",font=font(28,True),fill=white); y+=90
    path=RECEIPT_DIR/f"receipt_{order['order_no']}.png"; img.save(path,"PNG"); return path

bot=Bot(BOT_TOKEN) if BOT_TOKEN else None
dp=Dispatcher()
fz=FazerCards(FAZER_API_KEY,FAZER_BASE)

@dp.message(CommandStart())
async def start(message:Message):
    ensure_user(message.from_user)
    await message.answer(f"🔥 <b>{BOT_NAME}</b>\n\n💎 Алмазҳои арзон, тез ва бо нархи хуб!\nID + Ник + Регион лозим!",reply_markup=main_menu())

@dp.callback_query(F.data=="home")
async def home(call:CallbackQuery,state:FSMContext):
    await state.clear(); await call.message.edit_text(f"🔥 <b>{BOT_NAME}</b>\nМенюи асосӣ:",reply_markup=main_menu()); await call.answer()

@dp.callback_query(F.data=="balance")
async def bal(call:CallbackQuery):
    b=get_balance(call.from_user.id)
    await call.message.edit_text(f"💳 Баланс: <b>{b:.2f} сом</b>",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Пур кардан",callback_data="topup")],[InlineKeyboardButton(text="⬅️ Бозгашт",callback_data="home")]])); await call.answer()

@dp.callback_query(F.data=="topup")
async def top(call:CallbackQuery):
    await call.message.edit_text("💳 Маблағро интихоб кн:",reply_markup=topup_amount_kb()); await call.answer()

@dp.callback_query(F.data.startswith("topup_amt:"))
async def top_amt(call:CallbackQuery):
    a=int(call.data.split(":")[1]); await call.message.edit_text(f"💳 {a} сом интихоб кардед. Усулро интихоб кн:",reply_markup=payment_method_kb(a)); await call.answer()

@dp.callback_query(F.data.startswith("paymethod:"))
async def pay_m(call:CallbackQuery,state:FSMContext):
    _,m,a=call.data.split(":"); amt=int(a); name=ESKHATA_TEXT if m=="eskhata" else ICB_TEXT
    await state.update_data(amount=amt,method=name); await state.set_state(TopupState.waiting_proof)
    await call.message.edit_text(f"💳 {amt} сом\n🏦 {name}\n📱 {PAYMENT_PHONE}\n\n1. Пардохт кн\n2. Чекашро акс кн равон кн"); await call.answer()

@dp.message(TopupState.waiting_proof,F.photo)
async def proof(message:Message,state:FSMContext):
    data=await state.get_data(); amt=Decimal(str(data["amount"])); meth=data["method"]; fid=message.photo[-1].file_id
    con=db(); cur=con.execute("INSERT INTO payments(tg_id,amount,method,status,proof_file_id,created_at) VALUES(?,?,?,?,?,?)",(message.from_user.id,float(amt),meth,"pending",fid,datetime.now().isoformat())); pid=cur.lastrowid; con.commit(); con.close()
    await state.clear(); await message.answer(f"✅ Чек кабул шуд {amt} сом. Админ месанчад.",reply_markup=main_menu())
    if ADMIN_ID:
        try: await bot.send_photo(ADMIN_ID,fid,caption=f"💳 ПАРДОХТ #{pid}\nID:{message.from_user.id}\n{amt} сом\n{meth}",reply_markup=admin_payment_kb(pid))
        except: pass

@dp.callback_query(F.data.startswith("approve_payment:"))
async def approve(call:CallbackQuery):
    pid=int(call.data.split(":")[1]); con=db(); row=con.execute("SELECT * FROM payments WHERE id=?",(pid,)).fetchone()
    if not row or row["status"]!="pending": con.close(); await call.answer("Коркард шудааст"); return
    con.execute("UPDATE payments SET status='approved',approved_at=? WHERE id=?",(datetime.now().isoformat(),pid)); con.commit(); con.close()
    add_balance(row["tg_id"],Decimal(str(row["amount"])))
    await bot.send_message(row["tg_id"],f"✅ Тасдик шуд +{row['amount']:.2f} сом\nБаланс: {get_balance(row['tg_id']):.2f} сом")
    try: await call.message.edit_caption(caption=(call.message.caption or "")+"\n✅ ТАСДИК ШУД",reply_markup=None)
    except: pass
    await call.answer()

@dp.callback_query(F.data.startswith("reject_payment:"))
async def reject(call:CallbackQuery):
    pid=int(call.data.split(":")[1]); con=db(); con.execute("UPDATE payments SET status='rejected' WHERE id=?",(pid,)); con.commit(); con.close()
    await call.answer("Рад шуд")

@dp.callback_query(F.data=="products")
async def prods(call:CallbackQuery):
    await call.message.edit_text("💎 <b>FREE FIRE - Нархҳо бо сомонӣ</b>\nИнтихоб кн:",reply_markup=products_kb()); await call.answer()

@dp.callback_query(F.data.startswith("buy:"))
async def buy_start(call:CallbackQuery,state:FSMContext):
    pid=call.data.split(":")[1]; product=PRODUCT_MAP.get(pid)
    if not product: await call.answer("Ёфт нашуд"); return
    if get_balance(call.from_user.id)<product[2]:
        await call.message.edit_text(f"❌ Баланс нокифоя\nНарх {product[2]:.2f} сом\nБаланси ту {get_balance(call.from_user.id):.2f} сом",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Пур кардан",callback_data="topup")],[InlineKeyboardButton(text="⬅️ Бозгашт",callback_data="products")]])); await call.answer(); return
    await state.update_data(product_id=pid); await state.set_state(OrderState.waiting_id)
    await call.message.edit_text(f"🛒 {product[1]}\n💰 {product[2]:.2f} сом\n\n🔢 UID-и Free Fire-ро равон кн (факат ракам):"); await call.answer()

@dp.message(OrderState.waiting_id)
async def oid(message:Message,state:FSMContext):
    if not message.text.strip().isdigit(): await message.answer("❌ UID факат ракам бошад!"); return
    await state.update_data(player_id=message.text.strip()); await state.set_state(OrderState.waiting_nickname)
    await message.answer("👤 Nickname-ро равон кн:")

@dp.message(OrderState.waiting_nickname)
async def onick(message:Message,state:FSMContext):
    if len(message.text.strip())<2: await message.answer("❌ Ник кутох"); return
    await state.update_data(nickname=message.text.strip()); await state.set_state(OrderState.waiting_region)
    await message.answer("🌍 Регионро равон кн (CIS навиш):")

@dp.message(OrderState.waiting_region)
async def oreg(message:Message,state:FSMContext):
    region=message.text.strip() or "CIS"; data=await state.get_data(); product=PRODUCT_MAP[data["product_id"]]; price=product[2]
    if get_balance(message.from_user.id)<price: await state.clear(); await message.answer("❌ Баланс нест",reply_markup=main_menu()); return
    oid,ono=create_order(message.from_user.id,product,data["player_id"],data["nickname"],region)
    if not take_balance(message.from_user.id,price): update_order(oid,status="failed"); await state.clear(); await message.answer("❌ Баланс нокифоя"); return
    await message.answer(f"⏳ Фармоиш #{ono} кабул шуд...")
    try:
        cat=await fz.find_free_fire_category(); offers_data=await fz.offers(cat); offers=offers_data.get("offers",[]) or offers_data.get("items",[])
        offer=None
        if product[3]:
            for o in offers:
                if str(product[3]) in str(o.get("name","")): offer=o; break
        if not offer and offers: offer=offers[0]
        if not offer: raise RuntimeError("Offer нест")
        fields=offers_data.get("fields",[])
        flds={}
        if not fields: flds={"player_id":data["player_id"],"region":region,"nickname":data["nickname"]}
        else:
            for f in fields:
                k=f.get("key",""); kl=k.lower()
                if kl in {"player_id","uid","id","game_id"}: flds[k]=data["player_id"]
                elif "region" in kl: flds[k]=region
                elif "nick" in kl or "name" in kl: flds[k]=data["nickname"]
        res=await fz.place_order(cat,offer.get("offer_id") or offer.get("id"),flds)
        porder=res.get("order",res); fid=porder.get("id"); update_order(oid,fazer_order_id=fid,status="processing")
        await message.answer(f"✅ Фармоиш #{ono} фиристода шуд! Тез меояд 💎")
    except Exception as e:
        logging.exception("order fail"); refund_balance(message.from_user.id,price); update_order(oid,status="failed")
        await message.answer(f"❌ Хато шуд #{ono}\n💰 Пул баргашт\nСабаб: {e}",reply_markup=main_menu())
    await state.clear()

@dp.callback_query(F.data=="my_orders")
async def myo(call:CallbackQuery):
    con=db(); rows=con.execute("SELECT * FROM orders WHERE tg_id=? ORDER BY id DESC LIMIT 10",(call.from_user.id,)).fetchall(); con.close()
    if not rows: txt="📦 Харид нест"
    else: txt="📦 <b>Фармоишхо:</b>\n"+"\n".join([f"#{r['order_no']} {escape(r['product_name'])} {r['price']:.2f}с {r['status']}" for r in rows])
    await call.message.edit_text(txt,reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Бозгашт",callback_data="home")]])); await call.answer()

async def poll():
    while True:
        try:
            for o in next_pending_orders():
                try:
                    d=await fz.get_order(o["fazer_order_id"]); p=d.get("order",d); s=p.get("status","processing")
                    if s in {"completed","success","delivered"}:
                        update_order(o["id"],status="completed",completed_at=datetime.now().isoformat())
                        fresh=get_order(o["id"]); receipt=make_receipt(fresh)
                        await bot.send_photo(o["tg_id"],FSInputFile(str(receipt)),caption=f"✅ Фармоиш #{o['order_no']} ичро шуд!")
                    elif s in {"failed","refunded","cancelled"}:
                        refund_balance(o["tg_id"],Decimal(str(o["price"]))); update_order(o["id"],status="failed")
                        await bot.send_message(o["tg_id"],f"❌ Фармоиш #{o['order_no']} нашуд. Пул баргашт.")
                except: pass
        except: pass
        await asyncio.sleep(15)

@dp.errors()
async def err(event): logging.exception("error"); return True

async def main():
    if not BOT_TOKEN: raise RuntimeError("BOT_TOKEN нест")
    init_db(); asyncio.create_task(poll()); logging.info("Bot started"); await dp.start_polling(bot)

if __name__=="__main__":
    logging.basicConfig(level=logging.INFO); asyncio.run(main())
