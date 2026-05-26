import json
import os
import re
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def normalize_item_name(name: str) -> str:
    if not name:
        return ""

    normalized = str(name).lower()
    normalized = normalized.replace("ё", "е")
    normalized = normalized.replace("х", "x")
    normalized = normalized.replace(",", ".")
    normalized = " ".join(normalized.split())

    return normalized


def normalize_match_key(value: str) -> str:
    if not value:
        return ""

    text = str(value).upper()
    text = text.replace("Ё", "Е")
    text = text.replace("Х", "X")
    text = text.replace(",", ".")

    text = re.sub(r"[^A-ZА-Я0-9.]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if "PZS" in text and re.search(r"\d+\s*AH", text):
        text = re.sub(r"\b\d+\s*V\b", "", text)
        text = re.sub(r"\s+", " ", text).strip()

    match = re.search(r"(\d*)\s*PZS\s*(\d+)(?:\s*AH)?", text)

    if match:
        prefix = match.group(1) or "3"
        capacity = match.group(2)
        return f"{prefix}PZS {capacity}AH"

    return text

def extract_kp_items(text: str) -> list:
    prompt = f"""
Ты специалист ОМТС в строительстве.

Извлеки из КП табличные позиции товаров/работ/материалов.

Верни строго JSON-массив без пояснений.

Формат:
[
  {{
    "name": "",
    "match_key": "",
    "unit": "",
    "quantity": "",
    "price": "",
    "amount": ""
  }}
]

Правила:
- name — наименование позиции.
- match_key — короткий ключ для сопоставления одинаковых позиций у разных поставщиков.
- Если есть артикул, модель, марка или типоразмер — используй их.
- Если артикула нет — сформируй краткое нормализованное название без лишних слов.
- Примеры:
  АКБ 12XPS375 и Аккумуляторная батарея 12XPS375 → 12XPS375
  Кабель ВВГнг-LS 3х2,5 и ВВГнг LS 3x2.5 → ВВГНГ-LS 3X2.5
- unit — единица измерения: шт, м2, м3, кг, т, компл и т.д.
- quantity — количество.
- price — цена за единицу.
  - В числах с пробелами пробел является разделителем тысяч, а не разрывом строки.
  - Примеры цен:
    8 900,10 → 8900.10
    10 406,27 → 10406.27
    17 927,00 → 17927.00
  - Нельзя отбрасывать первую часть цены до пробела.
  - Если в строке есть цена и сумма, price бери из колонки "Цена", amount — из колонки "Сумма".
- amount — сумма по строке.
- Если данных нет — пиши "не указано".
- Не добавляй итоговые строки типа "Итого", "НДС", "Всего к оплате".
- Не придумывай позиции.
- match_key должен быть одинаковым для одинаковой позиции, даже если поставщики написали название по-разному.
- Не включай в match_key бренд, поставщика, страну, номер счёта, внутренний номер или лишнее описание, если они не являются частью модели.
- Для технических товаров сохраняй только модель, типоразмер и ключевые параметры.
- Пример:
  24V 3PZS 375AH, JAC 24V 3PZS 375AH 24080100 и PZS375 → 3PZS 375AH

Текст КП:
{text}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "Ты извлекаешь табличные позиции из коммерческих предложений."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    content = response.choices[0].message.content.strip()

    if content.startswith("```"):
        content = content.replace("```json", "").replace("```", "").strip()

    try:
        items = json.loads(content)

        for item in items:
            item["normalized_name"] = normalize_item_name(
                item.get("name", "")
            )

            item["match_key"] = normalize_match_key(
                item.get("match_key") or item.get("name", "")
            )

        return items

    except Exception:
        return []