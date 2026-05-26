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
        country = item.get("country")
        valid_until = item.get("valid_until")
        total_amount = item.get("total_amount")

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
        if is_empty(payment_terms):
            risks.append({
                "supplier": supplier,
                "risk": "Условия оплаты не указаны",
                "level": "Средний",
                "field": "Условия оплаты",
                "value": item.get("payment_terms", "не указано"),
                "comment": "В КП отсутствуют условия оплаты. Необходимо запросить порядок и сроки оплаты."
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
        if is_empty(delivery_time):
            risks.append({
                "supplier": supplier,
                "risk": "Срок поставки не указан",
                "level": "Средний",
                "field": "Срок поставки",
                "value": item.get("delivery_time", "не указано"),
                "comment": "В КП отсутствует срок поставки. Необходимо запросить сроки поставки письменно."
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
        if is_empty(country):
            risks.append({
                "supplier": supplier,
                "risk": "Страна происхождения не указана",
                "level": "Низкий",
                "field": "Страна",
                "value": item.get("country", "не указано"),
                "comment": "В КП не указана страна происхождения товара. При необходимости запросить у поставщика."
            })

        if is_empty(valid_until):
            risks.append({
                "supplier": supplier,
                "risk": "Срок действия КП не указан",
                "level": "Низкий",
                "field": "Срок действия КП",
                "value": item.get("valid_until", "не указано"),
                "comment": "В КП не указан срок действия предложения. Нужно уточнить, до какой даты действуют цены."
            })

        if is_empty(total_amount):
            risks.append({
                "supplier": supplier,
                "risk": "Сумма КП не определена",
                "level": "Средний",
                "field": "Сумма",
                "value": item.get("total_amount", "не указано"),
                "comment": "Не удалось определить общую сумму КП. Нужно проверить файл вручную."
            })

    return risks