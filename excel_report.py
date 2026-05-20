from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter


def create_procurement_report(items: list, output_path: str):
    wb = Workbook()
    ws = wb.active
    ws.title = "Сравнение КП"

    headers = [
        "№",
        "Поставщик",
        "Сумма",
        "НДС",
        "Доставка",
        "Срок поставки",
        "Комментарий"
    ]

    ws.append(headers)

    header_fill = PatternFill("solid", fgColor="D9EAF7")
    thin = Side(border_style="thin", color="999999")

    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = Border(top=thin, bottom=thin, left=thin, right=thin)

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

    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = Border(top=thin, bottom=thin, left=thin, right=thin)

    widths = {
        "A": 6,
        "B": 30,
        "C": 18,
        "D": 15,
        "E": 35,
        "F": 25,
        "G": 45
    }

    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    wb.save(output_path)
    