import json
from datetime import datetime
from pathlib import Path

from procurement_risks import analyze_procurement_risks


HISTORY_FILE = Path("history.json")


def to_number(value):
    if value is None:
        return None

    text = str(value)
    text = text.replace(" ", "")
    text = text.replace(",", ".")

    digits = ""
    for char in text:
        if char.isdigit() or char == ".":
            digits += char

    if not digits:
        return None

    try:
        return float(digits)
    except ValueError:
        return None


def load_history():
    if not HISTORY_FILE.exists():
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return []


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=2)


def add_history_record(items):
    amounts = []

    for item in items:
        amount = to_number(item.get("total_amount"))
        if amount is not None:
            amounts.append({
                "supplier": item.get("supplier", "не указано"),
                "amount": amount
            })

    amounts = sorted(amounts, key=lambda x: x["amount"])

    winner = "не определён"
    saving = 0

    if len(amounts) >= 1:
        winner = amounts[0]["supplier"]

    if len(amounts) >= 2:
        saving = round(
            amounts[1]["amount"] - amounts[0]["amount"],
            2
        )

    risks = analyze_procurement_risks(items)

    record = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "kp_count": len(items),
        "winner": winner,
        "saving": saving,
        "risks_count": len(risks)
    }

    history = load_history()
    history.append(record)
    save_history(history)