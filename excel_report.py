import re
from procurement_risks import analyze_procurement_risks
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.comments import Comment


def get_position_key(name: str) -> str:
    text = str(name).upper()

    text = text.replace("×", "X")
    text = text.replace("Х", "X")
    text = text.replace("-", " ")
    text = text.replace("/", " ")
    text = text.replace("_", " ")
    text = text.replace(" L", " ")
    text = text.replace("CKB", "СКВ")
    text = text.replace("CK", "СК")

    metric_match = re.search(r"\bM\s*(\d+)\s*X\s*(\d+(?:\.\d+)?)\b", text)
    if metric_match:
        return f"M{metric_match.group(1)}X{metric_match.group(2)}"

    text = re.sub(r"[.,;:(){}\[\]\"']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    patterns = [
        r"BT\d+\s+ER\d+\s+\d+",
        r"BT\d+\s+СКВ\d+\s+\d+",
        r"BT\d+\s+CKB\d+\s+\d+",
        r"СКВ\d+\s+TWN\d+\s+\d+",
        r"CKB\d+\s+TWN\d+\s+\d+",
        r"RDH\s+D\d+\s+\d+\s+\d+L",
        r"PS\s+BT\d+\s+\d+\s+HO",
        r"[A-ZА-Я]{2,}\d+\s+\d+"
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0).strip()

    noise_words = [
        "КУПИТЬ",
        "ПОСТАВКА",
        "ТОВАР",
        "ИЗДЕЛИЕ",
        "МАТЕРИАЛ",
        "КОМПЛЕКТ",
        "ШТ",
        "ШТ.",
        "ЕД",
        "ЕД.",
        "РУБ",
        "ТГ",
        "ТЕНГЕ"
    ]

    words = text.split()
    words = [word for word in words if word not in noise_words]

    return " ".join(words).strip()


def extract_article(name):
    text = str(name).upper()
    text = text.replace("×", "X")
    text = text.replace("Х", "X")
    text = text.replace("-", " ")
    text = re.sub(r"[.,;:(){}\[\]\"']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    patterns = [
        r"BT\d+\s+ER\d+\s+\d+",
        r"BT\d+\s+СКВ\d+\s+\d+",
        r"BT\d+\s+CKB\d+\s+\d+",
        r"СКВ\d+\s+TWN\d+\s+\d+",
        r"CKB\d+\s+TWN\d+\s+\d+",
        r"RDH\s+D\d+\s+\d+\s+\d+L",
        r"PS\s+BT\d+\s+\d+\s+HO",
        r"M\d+\s*X\s*\d+",
        r"\d+\s*X\s*\d+"
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0).strip()

    return ""


def normalize_unit(unit):
    value = str(unit).strip().lower()
    value = value.replace(".", "")

    unit_map = {
        "шт": "шт",
        "штука": "шт",
        "штук": "шт",
        "ед": "шт",
        "единица": "шт",
        "единиц": "шт",
        "комплект": "компл",
        "комплекта": "компл",
        "компл": "компл",
        "м": "м",
        "метр": "м",
        "метра": "м",
        "пм": "м",
        "пог м": "м",
        "кг": "кг",
        "килограмм": "кг",
        "тонна": "т",
        "т": "т",
        "л": "л",
        "литр": "л"
    }

    return unit_map.get(value, value)


def clean_price(price):
    try:
        value = str(price)
        value = value.replace(" ", "")
        value = value.replace(",", ".")
        value = re.sub(r"[^0-9.]", "", value)
        if value == "":
            return None
        return float(value)
    except Exception:
        return None


def is_valid_supplier(supplier):
    value = str(supplier).strip().lower()

    return value not in ["", "не указано", "не указан", "не проверялось", "none", "null"]


def get_risk_weight(risk):
    risk_name = str(risk.get("risk", "")).strip().lower()
    level = str(risk.get("level", "")).strip().lower()

    risk_weights = {
        "инн поставщика не найден": 10,
        "огрн поставщика не найден": 8,
        "организация ликвидирована": 15,
        "организация банкрот": 15,
        "организация в процессе ликвидации": 10,
        "компания зарегистрирована менее 6 месяцев назад": 5,
        "компания зарегистрирована менее 1 года назад": 3,
        "оквэд поставщика выглядит непрофильным": 3,
        "аномально низкая цена": 8,
        "100% предоплата": 5,
        "срок поставки не указан": 3,
        "срок поставки больше конкурентов": 3,
        "гарантия не указана": 2,
        "условия оплаты не указаны": 2,
        "доставка отдельно": 2,
        "ндс отсутствует или не указан": 2,
        "сумма кп не определена": 2,
        "производитель не указан": 1,
        "страна происхождения не указана": 1,
        "срок действия кп не указан": 1
    }

    if risk_name in risk_weights:
        return risk_weights[risk_name]

    if level == "высокий":
        return 5

    if level == "средний":
        return 2

    if level == "низкий":
        return 1

    return 1


def get_supplier_risk_score(supplier_risks):
    return sum(get_risk_weight(risk) for risk in supplier_risks)


def has_blocking_risk(supplier_risks):
    blocking_risks = [
        "инн поставщика не найден",
        "аномально низкая цена",
        "организация ликвидирована",
        "организация банкрот"
    ]

    for risk in supplier_risks:
        risk_name = str(risk.get("risk", "")).strip().lower()
        if risk_name in blocking_risks:
            return True

    return False


def get_supplier_rating(risk_score, supplier_risks=None):
    supplier_risks = supplier_risks or []

    if has_blocking_risk(supplier_risks):
        return "C"

    if risk_score <= 2:
        return "A"

    if risk_score <= 10:
        return "B"

    return "C"


def get_supplier_score_text(rating):
    if rating == "A":
        return "Надёжный"

    if rating == "B":
        return "Требует проверки"

    return "Высокий риск"


def style_sheet(ws, widths):
    header_fill = PatternFill("solid", fgColor="D9EAF7")
    thin = Side(border_style="thin", color="999999")

    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = Border(top=thin, bottom=thin, left=thin, right=thin)

    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = Border(top=thin, bottom=thin, left=thin, right=thin)

    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def create_procurement_report(items: list, output_path: str):
    wb = Workbook()

    green_fill = PatternFill("solid", fgColor="C6EFCE")
    yellow_fill = PatternFill("solid", fgColor="FFF2CC")
    red_fill = PatternFill(
    start_color="FFC7CE",
    end_color="FFC7CE",
    fill_type="solid"
)

    supplier_stats = {}

    # Лист 1 — Сравнение КП
    ws = wb.active
    ws.title = "Сравнение КП"

    ws.append([
        "№",
        "Поставщик",
        "Сумма",
        "НДС",
        "Доставка",
        "Срок поставки",
        "Условия оплаты",
        "Гарантия",
        "Срок действия КП",
        "Производитель",
        "Страна",
        "Комментарий"
    ])

    for index, item in enumerate(items, start=1):
        ws.append([
            index,
            item.get("supplier", "не указано"),
            item.get("total_amount", "не указано"),
            item.get("vat", "не указано"),
            item.get("delivery", "не указано"),
            item.get("delivery_time", "не указано"),
            item.get("payment_terms", "не указано"),
            item.get("warranty", "не указано"),
            item.get("valid_until", "не указано"),
            item.get("manufacturer", "не указано"),
            item.get("country", "не указано"),
            item.get("comment", "")
        ])

    style_sheet(ws, {
        "A": 6,
        "B": 30,
        "C": 18,
        "D": 15,
        "E": 35,
        "F": 25,
        "G": 28,
        "H": 18,
        "I": 22,
        "J": 25,
        "K": 18,
        "L": 45
    })

    # Лист 2 — Позиции КП
    ws_items = wb.create_sheet("Позиции КП")

    ws_items.append([
        "Файл",
        "Поставщик",
        "Ключ позиции",
        "Наименование",
        "Ед. изм.",
        "Кол-во",
        "Цена",
        "Сумма"
    ])

    for item in items:
        supplier = item.get("supplier", "не указано")
        file_name = item.get("file_name", "не указано")

        if not is_valid_supplier(supplier):
            continue

        if supplier not in supplier_stats:
            supplier_stats[supplier] = {
                "wins": 0,
                "sum_wins": 0,
                "positions": 0,
                "total_amount": clean_price(item.get("total_amount"))
            }

        for position in item.get("items", []):
            name = position.get("name", "не указано")
            key_source = (
                position.get("match_key")
                or position.get("normalized_name")
                or name
            )
            key = get_position_key(key_source)

            supplier_stats[supplier]["positions"] += 1

            ws_items.append([
                file_name,
                supplier,
                key,
                name,
                position.get("unit", "не указано"),
                position.get("quantity", "не указано"),
                position.get("price", "не указано"),
                position.get("amount", "не указано")
            ])

    style_sheet(ws_items, {
        "A": 35,
        "B": 30,
        "C": 25,
        "D": 55,
        "E": 12,
        "F": 12,
        "G": 18,
        "H": 18
    })

    # Лист 3 — Конкурентная карта
    ws_map = wb.create_sheet("Конкурентная карта")

    suppliers = []
    position_data = {}

    for item in items:
        supplier = item.get("supplier", "не указано")

        if not is_valid_supplier(supplier):
            continue

        if supplier not in suppliers:
            suppliers.append(supplier)

        for position in item.get("items", []):
            name = position.get("name", "не указано")
            key_source = (
                position.get("match_key")
                or position.get("normalized_name")
                or name
            )
            key = get_position_key(key_source)
            price = position.get("price", "не указано")

            if key not in position_data:
                position_data[key] = {
                    "name": name,
                    "prices": {}
                }

            position_data[key]["prices"][supplier] = price

    ws_map.append(
        ["Ключ позиции", "Наименование"]
        + suppliers
        + ["Победитель", "Мин. цена", "Макс. цена", "Экономия"]
    )

    total_saving = 0

    for key, data in position_data.items():
        row = [key, data["name"]]
        found_prices = []

        for supplier in suppliers:
            price = data["prices"].get(supplier, "")
            row.append(price)

            numeric_price = clean_price(price)
            if numeric_price is not None:
                found_prices.append((numeric_price, supplier))

        if found_prices:
            min_price, winner = min(found_prices, key=lambda x: x[0])
            max_price, _ = max(found_prices, key=lambda x: x[0])
            saving = max_price - min_price

            row.append(winner)
            row.append(min_price)
            row.append(max_price)
            row.append(saving)

            total_saving += saving

            if winner not in supplier_stats:
                supplier_stats[winner] = {
                    "wins": 0,
                    "sum_wins": 0,
                    "positions": 0
                }

            supplier_stats[winner]["wins"] += 1
            supplier_stats[winner]["sum_wins"] += min_price
        else:
            row.append("не определён")
            row.append("")
            row.append("")
            row.append("")

        ws_map.append(row)

    style_sheet(ws_map, {
        "A": 25,
        "B": 55,
        "C": 22,
        "D": 22,
        "E": 22,
        "F": 22,
        "G": 22,
        "H": 30,
        "I": 18,
        "J": 18,
        "K": 18
    })

    # Подсветка минимальных цен
    first_supplier_col = 3
    last_supplier_col = 2 + len(suppliers)

    for row_idx in range(2, ws_map.max_row + 1):
        prices = []

        for col_idx in range(first_supplier_col, last_supplier_col + 1):
            value = ws_map.cell(row=row_idx, column=col_idx).value
            numeric = clean_price(value)
            if numeric is not None:
                prices.append((numeric, col_idx))

        if prices:
            min_price, min_col = min(prices, key=lambda x: x[0])

            ws_map.cell(
                row=row_idx,
                column=min_col
            ).fill = green_fill

            avg_price = sum(p[0] for p in prices) / len(prices)

            if min_price < avg_price * 0.7:
                cell = ws_map.cell(
                    row=row_idx,
                    column=min_col
                )

                cell.fill = red_fill

                cell.comment = Comment(
                    "Аномально низкая цена. Проверьте комплектацию и условия поставки.",
                    "KP Bot"
                )
    # Лист 4 — Сопоставление позиций
    ws_matching = wb.create_sheet("Сопоставление позиций")

    ws_matching.append([
        "Ключ позиции",
        "Поставщик",
        "Исходное наименование",
        "match_key GPT",
        "normalized_name",
        "Ед. изм.",
        "Кол-во",
        "Цена",
        "Сумма"
    ])

    matching_groups = {}
    for item in items:
        supplier = item.get("supplier", "не указано")

        for position in item.get("items", []):
            name = position.get("name", "не указано")
            key_source = (
                position.get("match_key")
                or position.get("normalized_name")
                or name
            )
            key = get_position_key(key_source)
            if key not in matching_groups:
                matching_groups[key] = []

            matching_groups[key].append({
                "supplier": supplier,
                "name": name,
                "unit": position.get("unit", "не указано"),
                "quantity": position.get("quantity", "не указано"),
                "price": position.get("price", "не указано"),
                "amount": position.get("amount", "не указано"),
                "match_key": position.get("match_key", ""),
                "normalized_name": position.get("normalized_name", "")
            })
            ws_matching.append([
                key,
                supplier,
                name,
                position.get("match_key", ""),
                position.get("normalized_name", ""),
                position.get("unit", "не указано"),
                position.get("quantity", "не указано"),
                position.get("price", "не указано"),
                position.get("amount", "не указано")
            ])

    style_sheet(ws_matching, {
        "A": 25,
        "B": 30,
        "C": 60,
        "D": 35,
        "E": 35,
        "F": 12,
        "G": 12,
        "H": 18,
        "I": 18
    })
    # Лист 5 — Контроль сопоставления
    ws_match_control = wb.create_sheet("Контроль сопоставления")

    ws_match_control.append([
        "Ключ позиции",
        "Проблема",
        "Уровень",
        "Детали"
    ])

    for key, group in matching_groups.items():
        units = sorted(set(
            normalize_unit(position.get("unit", "не указано"))
            for position in group
            if str(position.get("unit", "не указано")).strip()
        ))

        if len(units) > 1:
            ws_match_control.append([
                key,
                "Разные единицы измерения",
                "Предупреждение",
                ", ".join(units)
            ])
        quantity_details = sorted(set(
            f"{position.get('supplier', 'не указано')}: {position.get('quantity', 'не указано')}"
            for position in group
            if str(position.get("quantity", "не указано")).strip()
        ))

        quantities = sorted(set(
            str(position.get("quantity", "")).strip()
            for position in group
            if str(position.get("quantity", "")).strip()
            and str(position.get("quantity", "")).strip().lower() != "не указано"
        ))

        if len(quantities) > 1:
            ws_match_control.append([
                key,
                "Разные количества",
                "Критично",
                " | ".join(quantity_details)
            ])
        price_details = []

        for position in group:
            numeric_price = clean_price(position.get("price", "не указано"))

            if numeric_price is not None:
                price_details.append(
                    (
                        numeric_price,
                        position.get("supplier", "не указано")
                    )
                )

        if len(price_details) > 1:
            min_price, min_supplier = min(price_details, key=lambda x: x[0])
            max_price, max_supplier = max(price_details, key=lambda x: x[0])

            if min_price > 0 and max_price / min_price > 3:
                ratio = round(max_price / min_price, 1)

                ws_match_control.append([
                    key,
                    "Большой разброс цен",
                    "Предупреждение",
                    f"{min_supplier}: {min_price} | {max_supplier}: {max_price} | x{ratio}"
                ])
        names = sorted(set(
            str(position.get("name", "не указано")).strip()
            for position in group
            if str(position.get("name", "не указано")).strip()
        ))

        if len(names) > 3:
            ws_match_control.append([
                key,
                "Много разных наименований в одной группе",
                "Предупреждение",
                " | ".join(names[:5])
            ])
        articles = sorted(set(
            extract_article(position.get("name", ""))
            for position in group
            if extract_article(position.get("name", ""))
        ))

        if len(articles) > 1:
            ws_match_control.append([
                key,
                "Разные артикулы в одной группе",
                "Критично",
                " | ".join(articles[:5])
            ])
    style_sheet(ws_match_control, {
        "A": 30,
        "B": 35,
        "C": 18,
        "D": 80
    })
    for row in ws_match_control.iter_rows(min_row=2):
        level = row[2].value

        if level == "Критично":
            for cell in row:
                cell.fill = red_fill

        elif level == "Предупреждение":
            for cell in row:
                cell.fill = yellow_fill
    risks = analyze_procurement_risks(items)
    # Лист 4 — Итоги по поставщикам
    ws_summary = wb.create_sheet("Итоги поставщиков")

    ws_summary.append([
        "Поставщик",
        "Всего позиций в КП",
        "Позиций выиграно",
        "Сумма выигранных позиций",
        "Рисков",
        "Рейтинг",
        "Комментарий"
    ])

    best_supplier = None
    best_wins = -1
    best_sum_wins = 0

    for supplier, stat in supplier_stats.items():
        wins = stat.get("wins", 0)
        sum_wins = stat.get("sum_wins", 0)

        if wins > best_wins or (wins == best_wins and sum_wins > best_sum_wins):
            best_wins = wins
            best_sum_wins = sum_wins
            best_supplier = supplier

    for supplier, stat in supplier_stats.items():
        wins = stat.get("wins", 0)
        supplier_risk_items = [
            risk for risk in risks
            if risk.get("supplier") == supplier
        ]
        supplier_risks = len(supplier_risk_items)
        risk_score = get_supplier_risk_score(supplier_risk_items)
        rating = get_supplier_rating(risk_score, supplier_risk_items)

        if supplier == best_supplier and wins > 0:
            comment = "Лидер по количеству минимальных цен"
        elif wins > 0:
            comment = "Есть выигранные позиции, но не лидер"
        else:
            comment = "Нет выигранных позиций"

        ws_summary.append([
            supplier,
            stat.get("positions", 0),
            wins,
            stat.get("sum_wins", 0),
            supplier_risks,
            rating,
            comment
        ])

    style_sheet(ws_summary, {
        "A": 35,
        "B": 20,
        "C": 20,
        "D": 25,
        "E": 12,
        "F": 12,
        "G": 45
    })

    for row_idx in range(2, ws_summary.max_row + 1):
        if ws_summary.cell(row=row_idx, column=1).value == best_supplier:
            for col_idx in range(1, 8):
                ws_summary.cell(row=row_idx, column=col_idx).fill = green_fill
    # Лист 5 — Риски закупки
    ws_risks = wb.create_sheet("Риски закупки")

    ws_risks.append([
        "Поставщик",
        "Риск",
        "Уровень",
        "Поле",
        "Значение",
        "Комментарий"
    ])



    for risk in risks:
        ws_risks.append([
            risk.get("supplier", "не указано"),
            risk.get("risk", ""),
            risk.get("level", ""),
            risk.get("field", ""),
            risk.get("value", ""),
            risk.get("comment", "")
        ])

    style_sheet(ws_risks, {
        "A": 30,
        "B": 35,
        "C": 15,
        "D": 25,
        "E": 35,
        "F": 80
    })
        # Лист 6 — Проверка поставщиков
    ws_supplier_check = wb.create_sheet("Проверка поставщиков")

    ws_supplier_check.append([
        "Поставщик",
        "ИНН",
        "ИНН найден",
        "ОГРН",
        "ОГРН найден",
        "DaData название",
        "КПП",
        "DaData ОГРН",
        "Статус DaData",
        "Адрес DaData",
        "Руководитель DaData",
        "ОКВЭД DaData",
        "Дата регистрации DaData",
        "Производитель",
        "Страна",
        "НДС",
        "Гарантия",
        "Предоплата",
        "Рисков",
        "Вес рисков",
        "Побед по позициям",
        "Рейтинг",
        "Оценка"
    ])

    for item in items:
        supplier = item.get("supplier", "не указано")
        supplier_risks = [
            risk for risk in risks
            if risk.get("supplier") == supplier
        ]

        payment_terms = str(item.get("payment_terms", "")).lower()
        prepayment = "Да" if "100" in payment_terms or "полная предоплата" in payment_terms else "Нет"

        risks_count = len(supplier_risks)
        wins_count = supplier_stats.get(supplier, {}).get("wins", 0)

        inn = item.get("inn", "не указано")
        ogrn = item.get("ogrn", "не указано")

        inn_found = "Да" if is_valid_supplier(inn) else "Нет"
        ogrn_found = "Да" if is_valid_supplier(ogrn) else "Нет"

        risk_score = get_supplier_risk_score(supplier_risks)
        rating = get_supplier_rating(risk_score, supplier_risks)
        supplier_score = get_supplier_score_text(rating)

        ws_supplier_check.append([
            supplier,
            inn,
            inn_found,
            ogrn,
            ogrn_found,
            item.get("dadata_name", "не проверялось"),
            item.get("dadata_kpp", "не проверялось"),
            item.get("dadata_ogrn", "не проверялось"),
            item.get("dadata_status", "не проверялось"),
            item.get("dadata_address", "не проверялось"),
            item.get("dadata_director", "не проверялось"),
            item.get("dadata_okved", "не проверялось"),
            item.get("dadata_registration_date", "не проверялось"),
            item.get("manufacturer", "не указано"),
            item.get("country", "не указано"),
            item.get("vat", "не указано"),
            item.get("warranty", "не указано"),
            prepayment,
            risks_count,
            risk_score,
            wins_count,
            rating,
            supplier_score
        ])

    style_sheet(ws_supplier_check, {
        "A": 35,
        "B": 18,
        "C": 14,
        "D": 18,
        "E": 14,
        "F": 45,
        "G": 18,
        "H": 18,
        "I": 18,
        "J": 55,
        "K": 30,
        "L": 18,
        "M": 22,
        "N": 18,
        "O": 30,
        "P": 18,
        "Q": 18,
        "R": 20,
        "S": 15,
        "T": 12,
        "U": 18,
        "V": 12,
        "W": 25
    })

    for row_idx in range(2, ws_supplier_check.max_row + 1):
        rating = ws_supplier_check.cell(row=row_idx, column=22).value

        if rating == "A":
            for col_idx in range(1, 24):
                ws_supplier_check.cell(row=row_idx, column=col_idx).fill = green_fill
        elif rating == "B":
            for col_idx in range(1, 24):
                ws_supplier_check.cell(row=row_idx, column=col_idx).fill = yellow_fill
        elif rating == "C":
            for col_idx in range(1, 24):
                ws_supplier_check.cell(row=row_idx, column=col_idx).fill = red_fill

    # Лист 7 — Решение по закупке
    ws_decision = wb.create_sheet("Решение по закупке")

    ws_decision.append([
        "Поставщик",
        "Сумма КП",
        "Рисков",
        "Побед по позициям",
        "Рейтинг",
        "Решение",
        "Комментарий для закупщика"
    ])

    decision_rows = []

    for supplier, stat in supplier_stats.items():
        if not is_valid_supplier(supplier):
            continue

        supplier_risk_items = [
            risk for risk in risks
            if risk.get("supplier") == supplier
        ]
        supplier_risks = len(supplier_risk_items)
        risk_score = get_supplier_risk_score(supplier_risk_items)

        wins = stat.get("wins", 0)
        total_amount = stat.get("total_amount")

        rating = get_supplier_rating(risk_score, supplier_risk_items)

        rating_penalty = {
            "A": 0,
            "B": 10,
            "C": 35
        }.get(rating, 35)

        score = wins * 5 - risk_score * 2 - rating_penalty

        decision_rows.append({
            "supplier": supplier,
            "total_amount": total_amount,
            "risks": supplier_risks,
            "risk_score": risk_score,
            "wins": wins,
            "rating": rating,
            "score": score
        })

    recommended_supplier = None

    a_suppliers = [
        row for row in decision_rows
        if row["wins"] > 0 and row["rating"] == "A"
    ]

    b_suppliers = [
        row for row in decision_rows
        if row["wins"] > 0 and row["rating"] == "B"
    ]

    if a_suppliers:
        valid_decision_rows = a_suppliers
    else:
        valid_decision_rows = b_suppliers

    if valid_decision_rows:
        best_decision = max(
            valid_decision_rows,
            key=lambda row: (
                row["score"],
                row["wins"],
                -row["risks"],
                -(row["total_amount"] or 0)
            )
        )
        recommended_supplier = best_decision["supplier"]

    for row in decision_rows:
        supplier = row["supplier"]

        if supplier == recommended_supplier:
            decision = "Рекомендован"

            supplier_risk_names = [
                risk.get("risk", "")
                for risk in sorted(
                    [
                        risk for risk in risks
                        if risk.get("supplier") == supplier
                    ],
                    key=get_risk_weight,
                    reverse=True
                )
            ]

            if supplier_risk_names:
                comment = (
                    f"Рекомендован по результатам сравнения ценовых предложений. "
                    f"Побед по позициям: {row['wins']}. "
                    f"Вес рисков: {row['risk_score']}. "
                    "Требуется дополнительная проверка: "
                    + ", ".join(supplier_risk_names[:3]) + "."
                )
            else:
                comment = (
                    f"Рекомендован по результатам сравнения ценовых предложений. "
                    f"Побед по позициям: {row['wins']}. "
                    f"Вес рисков: {row['risk_score']}. "
                    "Существенных рисков не выявлено."
                )
        elif row["rating"] == "C" and row["wins"] > 0:
            decision = "Требует согласования руководителя"
            comment = (
                "Поставщик имеет минимальные цены по позициям, но рейтинг C из-за количества рисков. "
                "Перед выбором требуется отдельное согласование руководителя."
            )
        elif row["rating"] == "C":
            decision = "Не рекомендуется"
            comment = "Много рисков и нет побед по позициям."
        else:
            decision = "Резервный вариант"
            comment = "Можно рассматривать как альтернативу при уточнении условий."

        ws_decision.append([
            supplier,
            row["total_amount"],
            row["risks"],
            row["wins"],
            row["rating"],
            decision,
            comment
        ])

    style_sheet(ws_decision, {
        "A": 35,
        "B": 18,
        "C": 12,
        "D": 18,
        "E": 12,
        "F": 22,
        "G": 70
    })

    for row_idx in range(2, ws_decision.max_row + 1):
        decision = ws_decision.cell(row=row_idx, column=6).value

        if decision == "Рекомендован":
            for col_idx in range(1, 8):
                ws_decision.cell(row=row_idx, column=col_idx).fill = green_fill

        elif decision == "Не рекомендуется":
            for col_idx in range(1, 8):
                ws_decision.cell(row=row_idx, column=col_idx).fill = red_fill
    # Лист 7 — Заключение
    ws_conclusion = wb.create_sheet("Заключение")

    total_positions = len(position_data)

    ws_conclusion.append(["Параметр", "Значение"])
    ws_conclusion.append(["Всего КП", len(items)])
    ws_conclusion.append(["Всего уникальных позиций", total_positions])
    ws_conclusion.append(["Лидер по минимальным ценам", best_supplier or "не определён"])
    ws_conclusion.append(["Рекомендованный поставщик", recommended_supplier or "не определён"])
    if recommended_supplier:
        recommended_risk_items = [
            risk for risk in risks
            if risk.get("supplier") == recommended_supplier
        ]
        recommended_risk_score = get_supplier_risk_score(recommended_risk_items)
        recommended_rating = get_supplier_rating(recommended_risk_score, recommended_risk_items)

        ws_conclusion.append(["Рейтинг рекомендованного поставщика", recommended_rating])
        ws_conclusion.append(["Количество рисков рекомендованного поставщика", len(recommended_risk_items)])
        ws_conclusion.append(["Вес рисков рекомендованного поставщика", recommended_risk_score])
    ws_conclusion.append(["Потенциальная экономия", total_saving])
    ws_conclusion.append(["Выявлено рисков закупки", len(risks)])

    ws_conclusion.append(["", ""])
    ws_conclusion.append(["Рекомендация директору", ""])

    if recommended_supplier:
        recommendation = (
            f"По результатам анализа коммерческих предложений рекомендуется выбрать "
            f"поставщика {recommended_supplier}. Выбор сделан по совокупности факторов: "
            f"количество минимальных цен по позициям, количество выявленных рисков и сумма КП. "
            f"Перед заключением договора рекомендуется дополнительно подтвердить сроки поставки, "
            f"условия оплаты, гарантию, наличие товара и включение доставки в стоимость."
        )
    else:
        recommendation = (
            "Рекомендованный поставщик не определён. Необходимо проверить корректность цен, "
            "наименований позиций и исходных данных КП."
        )

    ws_conclusion.append(["Текст заключения", recommendation])

    style_sheet(ws_conclusion, {
        "A": 30,
        "B": 90
    })

    ws_conclusion["B9"].fill = yellow_fill
    ws_conclusion["B10"].fill = yellow_fill

    wb.save(output_path)
