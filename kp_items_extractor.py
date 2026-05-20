import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def extract_kp_items(text: str) -> list:
    prompt = f"""
Ты специалист ОМТС в строительстве.

Извлеки из КП табличные позиции товаров/работ/материалов.

Верни строго JSON-массив без пояснений.

Формат:
[
  {{
    "name": "",
    "unit": "",
    "quantity": "",
    "price": "",
    "amount": ""
  }}
]

Правила:
- name — наименование позиции.
- unit — единица измерения: шт, м2, м3, кг, т, компл и т.д.
- quantity — количество.
- price — цена за единицу.
- amount — сумма по строке.
- Если данных нет — пиши "не указано".
- Не добавляй итоговые строки типа "Итого", "НДС", "Всего к оплате".
- Не придумывай позиции.

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
        return json.loads(content)
    except Exception:
        return []