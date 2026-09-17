import os
import logging
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
FAZER_API_KEY = os.getenv("FAZER_API_KEY")
FAZER_BASE = os.getenv("FAZER_BASE", "https://api.fzr.cards/api/v2")
FAZER_CAT = os.getenv("FAZER_FREE_FIRE_CATEGORY", "free_fire_cis_auto")
ADMIN_IDS = os.getenv("ADMIN_IDS", "")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN нест!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def get_products():
    try:
        url = f"{FAZER_BASE}/products"
        headers = {"X-API-Key": FAZER_API_KEY}
        params = {"category": FAZER_CAT}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=15) as resp:
                data = await resp.json()
                return data.get("products", []) or data.get("data", []) or []
    except Exception as e:
        logging.error(f"API Error: {e}")
        return []

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Free Fire Алмазҳо", callback_data="ff")],
        [InlineKeyboardButton(text="👤 Профил", callback_data="profile")],
        [InlineKeyboardButton(text="📞 Дастгирӣ", callback_data="support")]
    ])
    await message.answer(
        "🎮 **FF ALMAZ SHOP TJ** 🎮\n\n"
        "Хуш омадед! Алмазҳои арзон ва зуд! 💎\n"
        "Тугмаро пахш кн:",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == "ff")
async def ff_handler(callback: types.CallbackQuery):
    await callback.answer("Юкланмоқда...")
    products = await get_products()
    
    if not products:
        await callback.message.answer("⚠️ Ҳозир маҳсулот нест. Баъдтар санҷед.\nAPI: " + FAZER_BASE)
        return

    kb = []
    for p in products[:10]:
        name = p.get("name") or p.get("title") or "Алмаз"
        price = p.get("price") or p.get("amount") or ""
        pid = p.get("id") or p.get("product_id")
        kb.append([InlineKeyboardButton(text=f"{name} - {price} сом", callback_data=f"buy_{pid}")])
    
    kb.append([InlineKeyboardButton(text="⬅️ Бозгашт", callback_data="back")])
    
    await callback.message.answer(
        "💎 **Алмазҳои Free Fire:**\nИнтихоб кн:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == "back")
async def back_handler(callback: types.CallbackQuery):
    await start_handler(callback.message)

@dp.callback_query(lambda c: c.data.startswith("buy_"))
async def buy_handler(callback: types.CallbackQuery):
    await callback.message.answer("📝 ID-и Free Fire-и худро равон кунед:\nМисол: 123456789")

async def main():
    logging.info(f"Бот сар шуд! FAZER_BASE={FAZER_BASE}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
