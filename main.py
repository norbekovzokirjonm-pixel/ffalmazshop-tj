import os
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN" 8651384882:AAHgdB64Rf5Y78Oji_vDkyjNpZuhJl5fMYA")
bot = telebot.TeleBot(TOKEN)

ADMIN_ID = 123456789 # Инҷо ID-и худатро навиш (аз @userinfobot гир)

PRICES = {
    "100 💎": "12 сомон",
    "210 💎": "23 сомон",
    "530 💎": "55 сомон",
    "1080 💎": "105 сомон",
}

@bot.message_handler(commands=['start'])
def start(m):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("💎 Алмаз харидан", "💰 Нархҳо")
    markup.add("📞 Админ", "📜 Дастгирӣ")
    bot.send_message(m.chat.id, f"Салом {m.from_user.first_name}!\n\nБа Ff Almaz Shop TJ хуш омадед! 🎮\nID-и Free Fire-и худро омода кн ва алмаз интихоб кн.", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "💰 Нархҳо")
def prices(m):
    text = "💰 Нархҳои мо:\n\n"
    for k,v in PRICES.items():
        text += f"{k} - {v}\n"
    bot.send_message(m.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "💎 Алмаз харидан")
def buy(m):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = [types.InlineKeyboardButton(k, callback_data=k) for k in PRICES.keys()]
    markup.add(*btns)
    bot.send_message(m.chat.id, "Кадом пакетро мехоҳӣ?", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    bot.send_message(c.message.chat.id, f"Ту {c.data} -ро интихоб кардӣ!\n\n📝 Лутфан ID-и Free Fire-и худро равон кн:")
    bot.register_next_step_handler(c.message, get_id, c.data)

def get_id(m, paket):
    user_id_game = m.text
    bot.send_message(m.chat.id, f"✅ ID қабул шуд: {user_id_game}\n\nПакет: {paket} - {PRICES[paket]}\n\n💳 Ба ин рақам пардохт кн:\nDC: +992 XXX XXX XXX\n\nБаъд чеки пардохтро ба ҳамин ҷо равон кн.")
    bot.register_next_step_handler(m, get_check, paket, user_id_game)

def get_check(m, paket, game_id):
    bot.send_message(m.chat.id, "Раҳмат! Чекатон қабул шуд, админ зуд мебинад. 🙏")
    bot.send_message(ADMIN_ID, f"🔥 ЗАКАЗИ НАВ!\n\nКлиент: @{m.from_user.username}\nID-и бозӣ: {game_id}\nПакет: {paket}\nЧек дар поён 👇")
    bot.forward_message(ADMIN_ID, m.chat.id, m.message_id)

@bot.message_handler(content_types=['text','photo','document'])
def all_msg(m):
    if m.text not in ["💎 Алмаз харидан", "💰 Нархҳо", "📞 Админ"]:
        bot.send_message(m.chat.id, "Барои харидан тугмаи 💎 Алмаз харидан-ро пахш кн.")

print("Bot started...")
bot.infinity_polling()
