import os
import logging
import asyncio
import random
from typing import Dict
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters
)
from deepseek import DeepSeek

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Инициализация DeepSeek клиента
client = DeepSeek(api_key=DEEPSEEK_API_KEY)

# Контекст для поддержания истории диалога
user_conversations: Dict[int, list] = {}

# Варианты имени бота для распознавания
BOT_NAMES = ["мику", "miku", "мику-тян", "miku-chan", "микутян", "микуша", "микусенька"]

# Системный промпт для специализации бота
SYSTEM_PROMPT = """Ты — дружелюбный ассистент по имени Мику, специализирующийся на аниме, манге и видеоиграх.

Твоя личность:
- Веселая, энергичная и немного игривая
- Любишь, когда обращаются по имени "Мику"
- Обожаешь аниме, мангу, JRPG и инди-игры
- Иногда упоминаешь, что любишь петь (как Хацунэ Мику)
- Отвечаешь естественно, как в обычном чате
- Используешь смайлики и эмодзи для выразительности 🎌🎮📺🎶

Стиль общения:
1. Обращайся к пользователю неформально (на "ты")
2. Отвечай кратко, но информативно
3. Если вопрос неясен — уточняй
4. Для рекомендаций давай 2-3 варианта с кратким описанием
5. В конце ответа иногда задавай встречный вопрос
6. Не используй маркдаун или форматирование
7. Будь естественной, как будто пишешь другу в чат

Твои экспертные области:
- Рекомендации аниме (любые жанры)
- Рекомендации игр (JRPG, инди, визуальные новеллы)
- Объяснение сюжетов без спойлеров
- Сравнение похожих тайтлов
- Советы по сезонным новинкам
- Музыкальное аниме и ритм-игры

Примеры хороших ответов:
"Привет! Мику тут 💙 Да, 'Атака титанов' просто огонь! Особенно если нравятся эпичные сражения и сложный сюжет. А ты до какого сезона досмотрел?"

"Оо, Persona 5 Royal — одна из моих любимых игр! Стиль, музыка, сюжет — всё на высоте. Советую поиграть, если любишь JRPG с социальными симуляторами. Во что ещё играл из подобного?"

"Хм, исекай... Попробуй 'Re:Zero' если нравится драма и сложные персонажи, или 'Mushoku Tensei' для более классического фэнтези. Оба отличные! Что больше по душе — серьёзное или более лёгкое?"
"""


def contains_bot_name(text: str) -> bool:
    """Проверяет, содержит ли текст имя бота"""
    text_lower = text.lower()
    for name in BOT_NAMES:
        if name in text_lower:
            return True
    return False


def extract_question(text: str) -> str:
    """Извлекает вопрос из текста, убирая имя бота"""
    text_lower = text.lower()

    for name in BOT_NAMES:
        text_lower = text_lower.replace(name, "")

    text_lower = text_lower.lstrip(" ,.!?;:-")
    return text_lower.strip()


def is_name_only(text: str) -> bool:
    """Проверяет, содержит ли текст только имя бота"""
    text_lower = text.lower().strip()

    for name in BOT_NAMES:
        if text_lower == name:
            return True
        if text_lower in [f"{name}!", f"{name}?", f"{name}.", f"{name},", f"{name}..."]:
            return True

    return False


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Основной обработчик всех сообщений"""
    user_id = update.effective_user.id
    user_message = update.message.text

    # Инициализация истории для нового пользователя
    if user_id not in user_conversations:
        user_conversations[user_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    # Если только имя
    if is_name_only(user_message):
        responses = [
            "Да, я тут! 💙 Чем могу помочь?",
            "Мику слушает! 🎤 Что тебя интересует?",
            "Ага, это я! 💫 Хочешь поговорить об аниме или играх?"
        ]
        await update.message.reply_text(random.choice(responses))
        return

    # Подготавливаем сообщение
    processed_message = user_message
    if contains_bot_name(user_message):
        processed_message = extract_question(user_message)
        if not processed_message:
            processed_message = user_message

    # Отправляем статус "печатает"
    await update.message.chat.send_action(action="typing")

    try:
        # Добавляем сообщение в историю
        user_conversations[user_id].append({"role": "user", "content": processed_message})

        # Ограничиваем историю
        if len(user_conversations[user_id]) > 8:
            user_conversations[user_id] = [user_conversations[user_id][0]] + user_conversations[user_id][-7:]

        # Отправляем запрос в DeepSeek
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="deepseek-chat",
            messages=user_conversations[user_id],
            max_tokens=1000,
            temperature=0.8
        )

        # Получаем ответ
        bot_response = response.choices[0].message.content

        # Добавляем ответ в историю
        user_conversations[user_id].append({"role": "assistant", "content": bot_response})

        # Отправляем ответ
        await update.message.reply_text(bot_response)

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("Упс, что-то пошло не так... Попробуй ещё раз! 💙")


def main():
    """Запуск бота"""
    print("🌸🎶 Запуск бота Мику...")

    # Создаем Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен! Нажми Ctrl+C для остановки.")

    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()