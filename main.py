import os
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)
ADMIN_ID = os.getenv("ADMIN_ID")

PRICES = {
    "100 💎": "12 сомон",
    "210 💎": "23 сомон", 
    "530 💎": "55 сомон",
    "1080 💎": "105 сомон",
}

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("100 💎", "210 💎")
    markup.add("530 💎", "1080 💎")
    bot.send_message(message.chat.id, "Салом! Ба FF Shop хуш омадед! Алмоз интихоб кн:", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def handle(message):
    if message.text in PRICES:
        bot.send_message(message.chat.id, f"Ту {message.text} интихоб кардӣ! Нарх: {PRICES[message.text]}\nID-и Free Fire-и худро равон кн!")
    else:
        bot.send_message(message.chat.id, f"ID қабул шуд: {message.text}. Мудир алоқа мегирад!")
    if ADMIN_ID:
        try:
            bot.send_message(int(ADMIN_ID), f"Заказ нав!\nАз: @{message.from_user.username}\nМатн: {message.text}")
        except:
            pass

bot.infinity_polling()
