import os
import asyncio
import pandas as pd
import fitz

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from openai import OpenAI
from kp_extractor import extract_kp_structure
from kp_items_extractor import extract_kp_items
from excel_report import create_procurement_report
from history import add_history_record, load_history
from dotenv import load_dotenv
import pytesseract
from pdf2image import convert_from_path

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

user_files = {}
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/compare")],
        [KeyboardButton(text="/history")],
        [KeyboardButton(text="/clear")],
        [KeyboardButton(text="/help")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
    input_field_placeholder="Выберите действие"
)


def extract_text_from_pdf(file_path):
    text = ""

    # Сначала пробуем обычное извлечение текста
    with fitz.open(file_path) as doc:
        for page in doc:
            text += page.get_text() + "\n"

    text = text.strip()

    if len(text) > 100:
        return text

    # Если текста мало — считаем, что это скан, и запускаем OCR
    ocr_text = ""

    try:
        pages = convert_from_path(file_path, dpi=200)

        for page in pages:
            page_text = pytesseract.image_to_string(
                page,
                lang="rus+eng"
            )
            ocr_text += page_text + "\n"

        return ocr_text.strip()

    except Exception as e:
        return text
    text = ""
    with fitz.open(file_path) as doc:
        for page in doc:
            text += page.get_text() + "\n"
    return text.strip()


def extract_text_from_excel(file_path):
    df = pd.read_excel(file_path)
    return df.head(50).to_string()


@dp.message(CommandStart())
async def start_handler(message: Message):
    user_files[message.from_user.id] = []

    await message.answer(
        "Привет!\n\n"
        "Отправь от 2 до 5 КП в формате PDF или Excel.\n"
        "Когда загрузишь все файлы, напиши /compare.\n\n"
        "Команды:\n"
        "/compare — сравнить загруженные КП\n"
        "/history — история анализов\n"
        "/clear — очистить загруженные файлы",
        reply_markup=main_keyboard
    )


@dp.message(Command("clear"))
async def clear_handler(message: Message):
    user_files[message.from_user.id] = []
    await message.answer("Загруженные файлы очищены. Можно отправлять новые КП.")
@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "<b>Как пользоваться ботом</b>\n\n"
        "1. Отправьте от 2 до 5 КП в формате PDF или Excel.\n"
        "2. Нажмите /compare.\n"
        "3. Бот сформирует анализ и Excel-отчёт.\n\n"
        "<b>Что есть в отчёте:</b>\n"
        "• сравнение КП\n"
        "• позиции КП\n"
        "• конкурентная карта\n"
        "• итоги поставщиков\n"
        "• риски закупки\n"
        "• заключение\n\n"
        "<b>Команды:</b>\n"
        "/compare — сравнить КП\n"
        "/history — история анализов\n"
        "/clear — очистить загруженные файлы\n"
        "/help — помощь"
    )
@dp.message(Command("history"))
async def history_handler(message: Message):
    history = load_history()

    if not history:
        await message.answer("История анализов пока пустая.")
        return

    last_records = history[-10:]
    lines = ["<b>Последние анализы:</b>"]

    for record in reversed(last_records):
        lines.append(
            (
                "\n"
                f"Дата: {record.get('date', 'не указано')}\n"
                f"КП: {record.get('kp_count', 0)}\n"
                f"Победитель: {record.get('winner', 'не определён')}\n"
                f"Экономия: {record.get('saving', 0):,.0f} ₽\n".replace(",", " ")
                + f"Рисков: {record.get('risks_count', 0)}"
            )
        )

    await message.answer("\n".join(lines))

@dp.message(Command("compare"))
async def compare_handler(message: Message):
    user_id = message.from_user.id
    files = user_files.get(user_id, [])

    if len(files) < 2:
        await message.answer(
            "Для сравнения нужно минимум 2 КП.\n"
            "Отправь ещё один файл PDF или Excel."
        )
        return

    await message.answer(f"Получено КП: {len(files)}. Сравниваю...")

    combined_text = ""

    for i, item in enumerate(files, start=1):
        combined_text += f"\n\n--- КП №{i}: {item['file_name']} ---\n"
        combined_text += item["text"][:6000]

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты опытный начальник ОМТС в строительной компании. "
                        "Твоя задача — сравнить несколько коммерческих предложений. "
                        "Пиши кратко, практически и по делу.\n\n"
                        "Сделай анализ по структуре:\n"
                        "1. Краткий итог сравнения\n"
                        "2. По каждому КП отдельный блок: поставщик, сумма, срок, доставка, НДС, важные условия\n"
                        "Не используй таблицы. Ответ должен быть удобен для чтения в Telegram.\n"
                        "3. Самое выгодное предложение\n"
                        "4. Риски и аномалии\n"
                        "5. Какие вопросы задать поставщикам\n"
                        "6. Рекомендация для закупщика"
                    )
                },
                {
                    "role": "user",
                    "content": combined_text[:25000]
                }
            ]
        )

        result = response.choices[0].message.content

        report_path = f"Сравнение_КП_{user_id}.xlsx"

        structured_items = []

        for item in files:
            data = extract_kp_structure(item["text"][:12000])
            data["file_name"] = item["file_name"]
            data["items"] = extract_kp_items(item["text"][:12000])
            structured_items.append(data)

        create_procurement_report(structured_items, report_path)
        add_history_record(structured_items)

        await message.answer(
            f"<b>Сравнение КП:</b>\n\n{result}"
        )

        await message.answer_document(
            FSInputFile(report_path),
            caption="Готово. Сформировал Excel-отчёт по сравнению КП."
        )

    except Exception as e:
        await message.answer(f"Ошибка при сравнении:\n{e}")


@dp.message(lambda message: message.document)
async def handle_document(message: Message):
    document = message.document
    file_name = document.file_name.lower()
    user_id = message.from_user.id

    if not file_name.endswith((".xlsx", ".xls", ".pdf")):
        await message.answer("Пожалуйста, отправь КП в формате PDF или Excel.")
        return

    if user_id not in user_files:
        user_files[user_id] = []

    if len(user_files[user_id]) >= 5:
        await message.answer(
            "Уже загружено 5 КП. Напиши /compare для сравнения или /clear для очистки."
        )
        return

    await message.answer("Файл получен. Читаю содержимое...")

    file = await bot.get_file(document.file_id)
    downloaded_file = await bot.download_file(file.file_path)

    if file_name.endswith(".pdf"):
        local_file = f"temp_{user_id}_{len(user_files[user_id]) + 1}.pdf"
    else:
        local_file = f"temp_{user_id}_{len(user_files[user_id]) + 1}.xlsx"

    with open(local_file, "wb") as f:
        f.write(downloaded_file.read())

    try:
        if file_name.endswith(".pdf"):
            text = extract_text_from_pdf(local_file)
        else:
            text = extract_text_from_excel(local_file)

        if not text:
            await message.answer(
                "Не удалось прочитать текст из файла. Возможно, PDF сделан как скан-картинка."
            )
            return

        user_files[user_id].append({
            "file_name": document.file_name,
            "text": text
        })

        count = len(user_files[user_id])

        await message.answer(
            f"КП добавлено: {count}.\n\n"
            "Можешь отправить ещё КП или написать /compare для сравнения."
        )

    except Exception as e:
        await message.answer(f"Ошибка при чтении файла:\n{e}")


async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
