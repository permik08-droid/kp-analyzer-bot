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
from history import add_history_record, load_history, get_history_analytics, get_supplier_statistics
from dotenv import load_dotenv
import pytesseract
from pdf2image import convert_from_path

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DADATA_API_KEY = os.getenv("DADATA_API_KEY")

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
        [KeyboardButton(text="/analytics")],
        [KeyboardButton(text="/suppliers")],
        [KeyboardButton(text="/clear")],
        [KeyboardButton(text="/help")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
    input_field_placeholder="Выберите действие"
)


def is_missing_value(value):
    normalized = str(value).strip().lower()

    return normalized in ["", "не указано", "не указан", "none", "null"]


def clean_number(value):
    import re

    text = str(value)
    text = text.replace(" ", "")
    text = text.replace(",", ".")
    text = re.sub(r"[^0-9.]", "", text)

    if not text:
        return None

    try:
        return float(text)
    except Exception:
        return None


def detect_supplier_from_text(text):
    import re

    patterns = [
        r"ООО\s+[«\"A-ZА-ЯЁ][^\n\r,;]{2,80}",
        r"АО\s+[«\"A-ZА-ЯЁ][^\n\r,;]{2,80}",
        r"ИП\s+[A-ZА-ЯЁ][^\n\r,;]{2,80}",
        r"ТОО\s+[«\"A-ZА-ЯЁ][^\n\r,;]{2,80}"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)

        if match:
            supplier = match.group(0).strip()
            supplier = re.sub(r"\s+", " ", supplier)
            supplier = supplier.strip(" .:-")

            return supplier

    return "не указано"


def detect_supplier_from_filename(file_name):
    import re

    name = str(file_name)
    name = re.sub(r"\.(pdf|xlsx|xls)$", "", name, flags=re.IGNORECASE)
    name = name.replace("_", " ")
    name = name.replace("-", " ")
    name = re.sub(r"\s+", " ", name).strip()

    name = re.sub(r"\bКП\b", " ", name, flags=re.IGNORECASE)
    name = re.sub(r"\b(ООО|ИП|АО|ТОО)\b", " ", name, flags=re.IGNORECASE)
    name = re.sub(r"\bТД\s+УРАЛКРАН\b", " ", name, flags=re.IGNORECASE)
    name = re.sub(r"\b\d{1,2}\s*\d{1,2}\s*\d{2,4}\b", " ", name)
    name = re.sub(r"\b\d{6,}\b", " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    if len(name) < 3:
        return "не указано"

    return name


def detect_requisites_from_text(text):
    import re

    result = {
        "inn": "не указано",
        "ogrn": "не указано"
    }

    inn_match = re.search(
        r"ИНН[^0-9]{0,40}(\d{10}|\d{12})",
        text,
        flags=re.IGNORECASE
    )

    if inn_match:
        result["inn"] = inn_match.group(1)

    ogrn_match = re.search(
        r"ОГРН(?:ИП|ЮЛ)?[^0-9]{0,50}(\d[\d\s\-]{11,20}\d)",
        text,
        flags=re.IGNORECASE
    )

    if ogrn_match:
        ogrn = re.sub(r"\D", "", ogrn_match.group(1))

        if len(ogrn) in [13, 15]:
            result["ogrn"] = ogrn

    return result


def check_company_by_inn(inn):
    import requests

    result = {
        "dadata_name": "не проверялось",
        "dadata_inn": inn,
        "dadata_kpp": "не проверялось",
        "dadata_ogrn": "не проверялось",
        "dadata_status": "не проверялось"
    }

    if is_missing_value(inn) or not DADATA_API_KEY:
        return result

    try:
        response = requests.post(
            "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party",
            headers={
                "Authorization": f"Token {DADATA_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "query": inn
            },
            timeout=10
        )

        if response.status_code != 200:
            result["dadata_status"] = f"ошибка API {response.status_code}"
            return result

        suggestions = response.json().get("suggestions", [])

        if not suggestions:
            result["dadata_status"] = "не найдено"
            return result

        data = suggestions[0].get("data", {})

        result["dadata_name"] = suggestions[0].get("value", "не указано")
        result["dadata_kpp"] = data.get("kpp") or "не указано"
        result["dadata_ogrn"] = data.get("ogrn") or "не указано"
        result["dadata_status"] = data.get("state", {}).get("status") or "не указано"

        return result

    except Exception as e:
        result["dadata_status"] = f"ошибка: {e}"
        return result


def extract_text_from_pdf(file_path):
    text = ""

    # Сначала пробуем обычное извлечение текста
    with fitz.open(file_path) as doc:
        for page in doc:
            text += page.get_text() + "\n"

    text = text.strip()

    requisites = detect_requisites_from_text(text)

    if not is_missing_value(requisites.get("inn")) and len(text) > 100:
        return text

    # Если ИНН не найден, дополнительно запускаем OCR
    ocr_text = ""

    try:
        pages = convert_from_path(file_path, dpi=300)

        for page in pages:
            page_text = pytesseract.image_to_string(
                page,
                lang="rus+eng"
            )
            ocr_text += page_text + "\n"

        if pages:
            last_page = pages[-1]
            width, height = last_page.size
            bottom_part = last_page.crop((0, int(height * 0.65), width, height))

            bottom_text = pytesseract.image_to_string(
                bottom_part,
                lang="rus+eng",
                config="--psm 6"
            )
            ocr_text += "\n" + bottom_text + "\n"

        combined_text = (text + "\n" + ocr_text).strip()

        if combined_text:
            return combined_text

        return text

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
"/analytics — аналитика закупок\n"
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
@dp.message(Command("suppliers"))
async def suppliers_handler(message: Message):
    suppliers = get_supplier_statistics()

    if not suppliers:
        await message.answer("Статистика поставщиков пока отсутствует.")
        return

    lines = ["<b>Статистика поставщиков:</b>", ""]

    for index, supplier in enumerate(suppliers[:10], start=1):
        lines.append(
            f"{index}. {supplier['supplier']}\n"
            f"Участий: {supplier['participations']}\n"
            f"Побед: {supplier['wins']}\n"
            f"Процент побед: {supplier['win_rate']}%\n"
        )

    await message.answer("\n".join(lines))
@dp.message(Command("analytics"))
async def analytics_handler(message: Message):
    analytics = get_history_analytics()

    if not analytics:
        await message.answer("Аналитики пока нет. Сначала сделайте хотя бы один анализ КП.")
        return

    lines = [
        "<b>Аналитика по закупкам:</b>",
        "",
        f"Всего анализов: {analytics['total']}",
        f"Средняя экономия: {analytics['avg_saving']:,.0f} ₽".replace(",", " "),
        f"Среднее количество рисков: {analytics['avg_risks']:.1f}",
        "",
        "<b>Рейтинг победителей:</b>"
    ]

    if analytics["winners_rating"]:
        for index, (winner, count) in enumerate(analytics["winners_rating"], start=1):
            lines.append(f"{index}. {winner} — побед: {count}")
    else:
        lines.append("Пока нет определённых победителей.")

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

            if is_missing_value(data.get("supplier")):
                detected_supplier = detect_supplier_from_text(
                    item["text"][:12000]
                )

                if not is_missing_value(detected_supplier):
                    data["supplier"] = detected_supplier

            if is_missing_value(data.get("supplier")):
                detected_supplier = detect_supplier_from_filename(
                    item["file_name"]
                )

                if not is_missing_value(detected_supplier):
                    data["supplier"] = detected_supplier

            requisites = detect_requisites_from_text(
                item["text"]
            )

            if is_missing_value(data.get("inn")):
                data["inn"] = requisites.get("inn", "не указано")

            if is_missing_value(data.get("ogrn")):
                data["ogrn"] = requisites.get("ogrn", "не указано")

            company_check = check_company_by_inn(
                data.get("inn", "не указано")
            )

            data["dadata_name"] = company_check.get("dadata_name", "не проверялось")
            data["dadata_kpp"] = company_check.get("dadata_kpp", "не проверялось")
            data["dadata_ogrn"] = company_check.get("dadata_ogrn", "не проверялось")
            data["dadata_status"] = company_check.get("dadata_status", "не проверялось")

            if is_missing_value(data.get("ogrn")) and not is_missing_value(data.get("dadata_ogrn")):
                data["ogrn"] = data["dadata_ogrn"]

            data["file_name"] = item["file_name"]
            data["items"] = extract_kp_items(item["text"][:12000])

            if is_missing_value(data.get("total_amount")):
                items_total = 0

                for position in data["items"]:
                    amount = clean_number(position.get("amount"))

                    if amount:
                        items_total += amount
                        continue

                    quantity = clean_number(position.get("quantity"))
                    price = clean_number(position.get("price"))

                    if quantity and price:
                        items_total += quantity * price

                if items_total > 0:
                    data["total_amount"] = round(items_total, 2)
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
        import traceback

        print("=" * 80)
        traceback.print_exc()
        print("=" * 80)

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
