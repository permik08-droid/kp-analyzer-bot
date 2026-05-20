import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def extract_kp_structure(text: str) -> dict:
    prompt = f"""
Ты опытный начальник ОМТС в строительстве.

Твоя задача — извлечь из коммерческого предложения данные для закупочного Excel-отчёта.

Важно:
- Не придумывай данные.
- Если поле не найдено, пиши "не указано".
- Общая сумма — это итоговая сумма к оплате, а не цена отдельной позиции.
- Если есть несколько сумм, выбирай "Итого", "Всего к оплате", "Итого с НДС", "Сумма счета".
- Если НДС включён, так и пиши: "включён".
- Если написано "Без НДС", пиши "без НДС".
- Если доставка не указана явно, пиши "не указано".
- Срок поставки ищи по словам: срок, поставка, готовность, отгрузка, наличие, рабочие дни, календарные дни.
- Условия оплаты ищи по словам: оплата, предоплата, аванс, постоплата, отсрочка, по факту.
- Гарантию ищи по словам: гарантия, гарантийный срок, гарантийные обязательства.
- Срок действия КП ищи по словам: действительно, срок действия, предложение действительно.
- Производителя ищи по словам: производитель, изготовитель, бренд, марка.
- Страну ищи по словам: страна происхождения, происхождение товара, страна производства.
Верни строго JSON без пояснений и без markdown.

Формат:
{{
  "supplier": "",
  "total_amount": "",
  "vat": "",
  "delivery": "",
   "delivery_time": "",
  "payment_terms": "",
  "warranty": "",
  "valid_until": "",
  "manufacturer": "",
  "country": "",
  "comment": ""
}}

В comment кратко укажи важные условия или что не удалось найти.

Текст КП:
{text}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "Ты извлекаешь структурированные данные из коммерческих предложений для закупщика ОМТС."
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
        return {
            "supplier": "ошибка извлечения",
            "total_amount": "не указано",
            "vat": "не указано",
            "delivery": "не указано",
            "delivery_time": "не указано",
            "payment_terms": "не указано",
            "warranty": "не указано",
            "valid_until": "не указано",
            "manufacturer": "не указано",
            "country": "не указано",
            "comment": content
        }