import re


def normalize(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def is_empty(value):
    text = normalize(value)
    return text in ["", "не указано", "нет данных", "none", "null", "-"]


def extract_days(value):
    text = normalize(value)
    numbers = re.findall(r"\d+", text)

    if not numbers:
        return None

    return int(numbers[0])


def analyze_procurement_risks(items):
    risks = []

    delivery_days = []

    for item in items:
        days = extract_days(item.get("delivery_time"))
        if days is not None:
            delivery_days.append(days)

    avg_delivery = None
    if delivery_days:
        avg_delivery = sum(delivery_days) / len(delivery_days)

    for item in items:
        supplier = item.get("supplier", "не указано")

        payment_terms = normalize(item.get("payment_terms"))
        warranty = item.get("warranty")
        delivery = normalize(item.get("delivery"))
        delivery_time = item.get("delivery_time")
        vat = normalize(item.get("vat"))
        manufacturer = item.get("manufacturer")

        if "100" in payment_terms or "полная предоплата" in payment_terms:
            risks.append({
                "supplier": supplier,
                "risk": "100% предоплата",
                "level": "Высокий",
                "field": "Условия оплаты",
                "value": item.get("payment_terms", "не указано"),
                "comment": "Поставщик требует полную предоплату. Нужно проверить надежность поставщика и возможность оплаты по факту или частичной предоплаты."
            })

        if is_empty(warranty):
            risks.append({
                "supplier": supplier,
                "risk": "Гарантия не указана",
                "level": "Средний",
                "field": "Гарантия",
                "value": item.get("warranty", "не указано"),
                "comment": "В КП не указана гарантия. Нужно запросить срок гарантии письменно."
            })

        if (
            "отдельно" in delivery
            or "не включ" in delivery
            or "за счет покупателя" in delivery
            or "за счёт покупателя" in delivery
        ):
            risks.append({
                "supplier": supplier,
                "risk": "Доставка отдельно",
                "level": "Средний",
                "field": "Доставка",
                "value": item.get("delivery", "не указано"),
                "comment": "Доставка может увеличить итоговую стоимость закупки."
            })

        days = extract_days(delivery_time)
        if avg_delivery is not None and days is not None and days > avg_delivery * 1.5:
            risks.append({
                "supplier": supplier,
                "risk": "Срок поставки больше конкурентов",
                "level": "Средний",
                "field": "Срок поставки",
                "value": delivery_time,
                "comment": f"Срок поставки {days} дней заметно выше среднего срока по КП."
            })

        if "без ндс" in vat or is_empty(vat):
            risks.append({
                "supplier": supplier,
                "risk": "НДС отсутствует или не указан",
                "level": "Средний",
                "field": "НДС",
                "value": item.get("vat", "не указано"),
                "comment": "Нужно проверить, включен ли НДС в цену и корректно ли оформлены документы."
            })

        if is_empty(manufacturer):
            risks.append({
                "supplier": supplier,
                "risk": "Производитель не указан",
                "level": "Низкий",
                "field": "Производитель",
                "value": item.get("manufacturer", "не указано"),
                "comment": "Нужно запросить производителя или бренд товара."
            })

    return risks