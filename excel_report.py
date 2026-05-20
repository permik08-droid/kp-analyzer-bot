import re
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side


def get_position_key(name: str) -> str:
    name = str(name).upper()

    patterns = [
        r"СКВ\d[-\w]+",
        r"BT\d+[-\w]+",
        r"RDH[-\w]+",
        r"[A-ZА-Я]{2,}\d+[-\w]+"
    ]

    for pattern in patterns:
        match = re.search(pattern, name)
        if match:
            return match.group(0)

    return name.strip()


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
            item.get("comment", "")
        ])

    style_sheet(ws, {
        "A": 6,
        "B": 30,
        "C": 18,
        "D": 15,
        "E": 35,
        "F": 25,
        "G": 45
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

        if supplier not in supplier_stats:
            supplier_stats[supplier] = {
                "wins": 0,
                "sum_wins": 0,
                "positions": 0
            }

        for position in item.get("items", []):
            name = position.get("name", "не указано")
            key = get_position_key(name)

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

        if supplier not in suppliers:
            suppliers.append(supplier)

        for position in item.get("items", []):
            name = position.get("name", "не указано")
            key = get_position_key(name)
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
            ws_map.cell(row=row_idx, column=min_col).fill = green_fill

    # Лист 4 — Итоги по поставщикам
    ws_summary = wb.create_sheet("Итоги поставщиков")

    ws_summary.append([
        "Поставщик",
        "Всего позиций в КП",
        "Позиций выиграно",
        "Сумма выигранных позиций",
        "Комментарий"
    ])

    best_supplier = None
    best_wins = -1

    for supplier, stat in supplier_stats.items():
        wins = stat.get("wins", 0)

        if wins > best_wins:
            best_wins = wins
            best_supplier = supplier

        comment = "Лидер по количеству минимальных цен" if wins > 0 else "Нет выигранных позиций"

        ws_summary.append([
            supplier,
            stat.get("positions", 0),
            wins,
            stat.get("sum_wins", 0),
            comment
        ])

    style_sheet(ws_summary, {
        "A": 35,
        "B": 20,
        "C": 20,
        "D": 25,
        "E": 45
    })

    for row_idx in range(2, ws_summary.max_row + 1):
        if ws_summary.cell(row=row_idx, column=1).value == best_supplier:
            for col_idx in range(1, 6):
                ws_summary.cell(row=row_idx, column=col_idx).fill = green_fill

    # Лист 5 — Заключение
    ws_conclusion = wb.create_sheet("Заключение")

    total_positions = len(position_data)

    ws_conclusion.append(["Параметр", "Значение"])
    ws_conclusion.append(["Всего КП", len(items)])
    ws_conclusion.append(["Всего уникальных позиций", total_positions])
    ws_conclusion.append(["Лидер по минимальным ценам", best_supplier or "не определён"])
    ws_conclusion.append(["Потенциальная экономия", total_saving])

    ws_conclusion.append(["", ""])
    ws_conclusion.append(["Рекомендация", ""])

    if best_supplier:
        recommendation = (
            f"По результатам анализа коммерческих предложений лидер по количеству "
            f"минимальных цен — {best_supplier}. Рекомендуется дополнительно проверить "
            f"сроки поставки, условия оплаты, наличие товара, гарантию и включение доставки."
        )
    else:
        recommendation = (
            "Победитель не определён. Рекомендуется проверить корректность цен и наименований позиций."
        )

    ws_conclusion.append(["Текст заключения", recommendation])

    style_sheet(ws_conclusion, {
        "A": 30,
        "B": 90
    })

    ws_conclusion["B8"].fill = yellow_fill

    wb.save(output_path)
