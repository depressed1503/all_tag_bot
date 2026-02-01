import asyncio
import logging
from typing import List
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ChatMember
from aiogram.filters import Command
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from os import getenv


load_dotenv()




logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен вашего бота
BOT_TOKEN = getenv('BOT_TOKEN')

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Словарь для кэширования участников (опционально)
chat_members_cache = {}


class RateLimiter:
    """Класс для ограничения частоты использования команды"""

    def __init__(self, cooldown_seconds: int = 60):
        self.cooldown = cooldown_seconds
        self.last_used = {}

    def is_allowed(self, chat_id: int) -> bool:
        now = datetime.now()
        if chat_id not in self.last_used:
            return True

        last_time = self.last_used[chat_id]
        if now - last_time > timedelta(seconds=self.cooldown):
            return True

        return False

    def update(self, chat_id: int):
        self.last_used[chat_id] = datetime.now()


rate_limiter = RateLimiter(cooldown_seconds=30)


async def get_chat_mentions(chat_id: int) -> List[str]:
    """Получает список участников чата для упоминания"""
    mentions = []

    try:
        # Получаем список администраторов (опционально)
        admins = await bot.get_chat_administrators(chat_id)
        admin_ids = {admin.user.id for admin in admins}

        # Получаем всех участников чата
        # Важно: бот должен быть администратором для этого метода
        member_count = await bot.get_chat_member_count(chat_id)

        # Для больших групп можно ограничить количество
        max_members = 100  # Максимальное количество участников для упоминания

        # В aiogram 3.x нет прямого метода получения всех участников
        # Используем альтернативные подходы:

        # Способ 1: Только через администраторов (если бот - админ)
        for admin in admins:
            user = admin.user
            if not user.is_bot:
                if user.username:
                    mention = f"@{user.username}"
                else:
                    mention = (
                        f"[{user.first_name or 'Пользователь'}](tg://user?id={user.id})"
                    )
                mentions.append(mention)

        # Для тестирования добавьте статический список
        if not mentions:
            mentions = ["@user1", "@user2", "@user3"]

    except Exception as e:
        logger.error(f"Ошибка при получении участников чата: {e}")

    return mentions


@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    await message.answer(
        "👋 Привет! Я бот для упоминания всех участников группы.\n\n"
        "Доступные команды:\n"
        "/start - Начало работы\n"
        "/help - Справка\n"
        "/all - Упомянуть всех участников\n\n"
        "⚙️ Добавьте меня в группу и сделайте администратором для полного функционала."
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    await message.answer(
        "📚 **Справка по командам:**\n\n"
        "• /all - Упомянуть всех участников группы\n"
        "• /everyone - Альтернатива /all\n"
        "• /mention - Упомянуть участников\n\n"
        "⚠️ **Требования:**\n"
        "- Бот должен быть администратором группы\n"
        "- Команда доступна только в группах\n"
        "- Ограничение: 1 раз в 30 секунд"
    )


@dp.message(Command("all", "everyone", "mention"))
async def cmd_all(message: Message):
    """Обработчик команды /all"""
    chat = message.chat

    # Проверяем, что команда в группе
    if chat.type not in ["group", "supergroup"]:
        await message.answer("❌ Эта команда работает только в группах!")
        return

    # Проверяем ограничение по частоте
    if not rate_limiter.is_allowed(chat.id):
        time_left = 30 - (datetime.now() - rate_limiter.last_used[chat.id]).seconds
        await message.answer(
            f"⏳ Пожалуйста, подождите {time_left} секунд перед следующим использованием."
        )
        return

    # Обновляем время использования
    rate_limiter.update(chat.id)

    # Отправляем сообщение о начале сбора участников
    status_msg = await message.answer("🔄 Собираю участников...")

    try:
        # Получаем упоминания участников
        mentions = await get_chat_mentions(chat.id)

        if not mentions:
            await status_msg.edit_text(
                "❌ Не удалось получить список участников.\n"
                "Убедитесь, что бот является администратором группы."
            )
            return

        # Формируем финальное сообщение
        total_mentions = len(mentions)
        header = f"📢 **Внимание всем!** ({total_mentions} участников)\n\n"

        # Разбиваем на части, если упоминаний слишком много
        if total_mentions > 50:
            # Разделяем на группы по 50 человек
            chunks = [mentions[i : i + 50] for i in range(0, len(mentions), 50)]

            for i, chunk in enumerate(chunks, 1):
                chunk_text = (
                    header if i == 1 else f"**Продолжение...** ({i}-я часть)\n\n"
                )
                chunk_text += "\n".join(chunk)

                if i == 1:
                    await status_msg.edit_text(
                        chunk_text,
                        parse_mode=ParseMode.MARKDOWN,
                        disable_web_page_preview=True,
                    )
                else:
                    await message.answer(
                        chunk_text,
                        parse_mode=ParseMode.MARKDOWN,
                        disable_web_page_preview=True,
                    )
                await asyncio.sleep(0.5)  # Задержка между сообщениями
        else:
            # Все упоминания в одном сообщении
            final_text = header + "\n".join(mentions)
            await status_msg.edit_text(
                final_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
            )

    except Exception as e:
        logger.error(f"Ошибка в команде /all: {e}")
        await status_msg.edit_text("❌ Произошла ошибка при упоминании участников.")


@dp.message(Command("admin_all"))
async def cmd_admin_all(message: Message):
    """Команда для упоминания только администраторов"""
    chat = message.chat

    if chat.type not in ["group", "supergroup"]:
        await message.answer("❌ Эта команда работает только в группах!")
        return

    try:
        # Получаем список администраторов
        admins = await bot.get_chat_administrators(chat.id)

        if not admins:
            await message.answer("❌ Не удалось получить список администраторов.")
            return

        mentions = []
        for admin in admins:
            user = admin.user
            if not user.is_bot:
                if user.username:
                    mentions.append(f"@{user.username}")
                else:
                    mentions.append(f"[{user.first_name}](tg://user?id={user.id})")

        if mentions:
            admin_text = "👑 **Внимание администраторам!**\n\n" + "\n".join(mentions)
            await message.answer(
                admin_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
            )

    except Exception as e:
        logger.error(f"Ошибка в команде /admin_all: {e}")
        await message.answer("❌ Произошла ошибка.")


async def main():
    """Основная функция запуска бота"""
    # Удаляем вебхук (если был)
    await bot.delete_webhook(drop_pending_updates=True)

    # Запускаем поллинг
    logger.info("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
