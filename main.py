import os
import pandas as pd
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from openai import OpenAI
from dotenv import load_dotenv
import asyncio

# Загружаем .env
load_dotenv()

# Получаем токены
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# OpenAI клиент
client = OpenAI(api_key=OPENAI_API_KEY)

# Telegram бот
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# Команда /start
@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Привет!\n\n"
        "Отправь Excel файл с КП, и я попробую его проанализировать."
    )

# Обработка Excel файлов
@dp.message(lambda message: message.document)
async def handle_document(message: Message):

    document = message.document

    # Проверяем расширение
    if not document.file_name.endswith((".xlsx", ".xls")):
        await message.answer("Пожалуйста, отправь Excel файл.")
        return

    await message.answer("Файл получен. Анализирую...")

    # Скачиваем файл
    file = await bot.get_file(document.file_id)
    file_path = file.file_path

    downloaded_file = await bot.download_file(file_path)

    local_file = "temp.xlsx"

    with open(local_file, "wb") as f:
        f.write(downloaded_file.read())

    try:
        # Читаем Excel
        df = pd.read_excel(local_file)

        # Берём первые строки
        preview = df.head(15).to_string()

        # Отправляем в OpenAI
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты специалист ОМТС и строительных закупок. "
                        "Проанализируй таблицу КП и кратко опиши:\n"
                        "- что находится в таблице\n"
                        "- есть ли подозрительные моменты\n"
                        "- какие позиции стоит проверить\n"
                        "- есть ли возможные завышения"
                    )
                },
                {
                    "role": "user",
                    "content": preview
                }
            ]
        )

        result = response.choices[0].message.content

        await message.answer(
            f"<b>Результат анализа:</b>\n\n{result}"
        )

    except Exception as e:
        await message.answer(f"Ошибка:\n{e}")

# Запуск бота
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())