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
        "risks_count": len(risks),
        "suppliers": amounts
    }

    history = load_history()
    history.append(record)
    save_history(history)
def get_history_analytics():
    history = load_history()

    if not history:
        return None

    total = len(history)
    avg_saving = sum(record.get("saving", 0) for record in history) / total
    avg_risks = sum(record.get("risks_count", 0) for record in history) / total

    winners = {}
    for record in history:
        winner = record.get("winner", "не определён")
        if winner and winner != "не определён":
            winners[winner] = winners.get(winner, 0) + 1

    winners_rating = sorted(
        winners.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return {
        "total": total,
        "avg_saving": avg_saving,
        "avg_risks": avg_risks,
        "winners_rating": winners_rating
    }
def get_supplier_statistics():
    history = load_history()

    stats = {}

    for record in history:
        winner = record.get("winner")

        for supplier_data in record.get("suppliers", []):
            supplier = supplier_data.get("supplier")

            if not supplier:
                continue

            if supplier not in stats:
                stats[supplier] = {
                    "participations": 0,
                    "wins": 0
                }

            stats[supplier]["participations"] += 1

            if supplier == winner:
                stats[supplier]["wins"] += 1

    result = []

    for supplier, data in stats.items():
        participations = data["participations"]
        wins = data["wins"]

        win_rate = 0

        if participations:
            win_rate = round(wins * 100 / participations, 1)

        result.append({
            "supplier": supplier,
            "participations": participations,
            "wins": wins,
            "win_rate": win_rate
        })

    result.sort(
        key=lambda x: x["wins"],
        reverse=True
    )

    return result