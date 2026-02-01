import json
import os
from telebot import TeleBot
from telebot.types import Message
from dotenv import load_dotenv
from os import getenv

load_dotenv()

BOT_TOKEN = getenv("BOT_TOKEN")
CACHE_FILE = "users_cache.json"

bot = TeleBot(BOT_TOKEN, parse_mode="HTML")


# ---------- cache utils ----------

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


chat_users = load_cache()


# ---------- handlers ----------

@bot.message_handler(content_types=['text'])
def main_handler(message: Message):
    chat_id = str(message.chat.id)
    user = message.from_user

    if not user or user.is_bot:
        return

    # инициализация чата
    if chat_id not in chat_users:
        chat_users[chat_id] = {}

    # сохраняем пользователя
    chat_users[chat_id][str(user.id)] = {
        "id": user.id,
        "first_name": user.first_name or "user"
    }

    save_cache(chat_users)

    # обработка /all
    if message.text.strip().startswith("/all"):
        users = chat_users.get(chat_id, {}).values()

        if not users:
            bot.reply_to(message, "Некого тегать 😢")
            return

        mentions = [
            f'<a href="tg://user?id={u["id"]}">{u["first_name"]}</a>'
            for u in users
        ]

        bot.send_message(
            message.chat.id,
            "🔔 Внимание!\n" + " ".join(mentions)
        )


print("Бот запущен с файловым кэшем")
bot.infinity_polling()
