#!/usr/bin/env python3
"""Spending pace against the budget in catalog.json → econumo.budget.name.

Pace for today (catalog.json → timezone) is budget × day / days in the month.
Day is today's date: on 29 September the pace is 29/30 of the envelope budget.

The limit lives on the envelope (Еда), not on a child category. An expense
in «Еда (Кофе)» counts toward Еда.

After an expense, pass that category, amount, and currency. The script
sends a Telegram alert only when this expense pushed the envelope from
at or under the pace to over it. A later expense in an envelope that is
already over does not send again.

  python3 spending_pace.py --category "Еда (Кофе)" --amount 4.50 --currency BYN
  python3 spending_pace.py
  python3 spending_pace.py --self-test

Credentials: ECONUMO_BASE_URL, ECONUMO_USERNAME, ECONUMO_PASSWORD.
The alert uses TELEGRAM_RELAY_SECRET. The script never prints those values.
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

MONEY = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def money_text(value: Decimal) -> str:
    text = format(money(value), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def parse_decimal(raw) -> Decimal | None:
    if raw is None:
        return None
    text = str(raw).replace("\u00a0", "").replace(" ", "").replace(",", ".").strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def expected_pace(budget: Decimal, day: int, days: int) -> Decimal:
    if days <= 0 or day <= 0:
        raise ValueError("day and days must be positive")
    return budget * Decimal(day) / Decimal(days)


def crossed_pace(spent: Decimal, amount_in_budget: Decimal, pace: Decimal) -> bool:
    """True when this expense is what moved the envelope over the pace.

    Equal to the pace is not over. An envelope that was already over stays quiet.
    """
    before = spent - amount_in_budget
    return before <= pace < spent


def convert_amount(amount: Decimal, source_rate: Decimal, target_rate: Decimal) -> Decimal:
    """Rates are units of that currency per 1 USD."""
    if source_rate <= 0 or target_rate <= 0:
        raise ValueError("rate must be positive")
    return money(amount * target_rate / source_rate)


def alert_text(
    envelope: str,
    category: str,
    spent: Decimal,
    pace: Decimal,
    planned: Decimal,
    code: str,
    day: int,
    days: int,
) -> str:
    via = ""
    if category.casefold().strip() != envelope.casefold().strip():
        via = f" из-за «{category}»"
    return (
        f"{envelope} выше темпа{via}: {money_text(spent)} {code} "
        f"при темпе {money_text(pace)} "
        f"(бюджет {money_text(planned)}, день {day} из {days})."
    )


def budget_name() -> str:
    return str(catalog()["econumo"]["budget"]["name"])


def default_currency() -> str:
    return str(catalog()["econumo"].get("currency") or "BYN")


def zone() -> ZoneInfo:
    return ZoneInfo(str(catalog().get("timezone") or "UTC"))


def local_today() -> date:
    return datetime.now(zone()).date()


def month_span(day: date) -> tuple[int, int, str]:
    days = calendar.monthrange(day.year, day.month)[1]
    return day.day, days, day.strftime("%Y-%m-01")


class Api:
    def __init__(self, base: str, token: str) -> None:
        self.base = base.rstrip("/")
        self.token = token

    def get(self, path: str) -> dict:
        req = urllib.request.Request(
            self.base + path,
            headers={"Authorization": "Bearer " + self.token},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                body = json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"HTTP {exc.code} {detail}") from exc
        if isinstance(body, dict) and body.get("success") is False:
            raise RuntimeError(json.dumps(body, ensure_ascii=False)[:300])
        return body


def login() -> Api:
    missing = [key for key in ("ECONUMO_BASE_URL", "ECONUMO_USERNAME", "ECONUMO_PASSWORD") if not os.environ.get(key)]
    if missing:
        raise RuntimeError("missing " + ", ".join(missing))
    base = os.environ["ECONUMO_BASE_URL"].rstrip("/")
    payload = json.dumps(
        {
            "username": os.environ["ECONUMO_USERNAME"],
            "password": os.environ["ECONUMO_PASSWORD"],
        }
    ).encode()
    req = urllib.request.Request(
        base + "/api/v1/user/login-user",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        token = json.loads(response.read())["token"]
    return Api(base, token)


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for folder in [here.parent, *here.parents]:
        if (folder / "catalog.json").is_file():
            return folder
    raise RuntimeError("catalog.json not found")


def catalog() -> dict:
    return json.loads((repo_root() / "catalog.json").read_text(encoding="utf-8"))


def send_alert(text: str) -> dict:
    secret = os.environ.get("TELEGRAM_RELAY_SECRET") or ""
    if not secret:
        raise RuntimeError("missing TELEGRAM_RELAY_SECRET")
    data = catalog()
    relay = str(data["telegram"]["relayUrl"]).rstrip("/")
    chat_id = str(data["telegram"]["allowedChatId"])
    payload = json.dumps(
        {
            "text": text,
            "kind": "pace",
            "purpose": "alert",
            "chat_id": chat_id,
        },
        ensure_ascii=False,
    ).encode()
    req = urllib.request.Request(
        relay + "/send",
        data=payload,
        headers={
            "Authorization": "Bearer " + secret,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            body = json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"telegram HTTP {exc.code} {detail}") from exc
    if not isinstance(body, dict) or not body.get("ok"):
        raise RuntimeError("telegram send failed")
    return {"ok": True, "duplicate": bool(body.get("duplicate"))}


def _cell(element: dict) -> tuple[Decimal | None, Decimal]:
    cells = element.get("cells") or []
    if not cells:
        return None, Decimal(0)
    planned = parse_decimal(cells[0].get("planned"))
    actual = parse_decimal(cells[0].get("actual")) or Decimal(0)
    return planned, actual


def _names(element: dict) -> set[str]:
    found = {str(element.get("name") or "").casefold().strip()}
    for child in element.get("children") or []:
        found.add(str(child.get("name") or "").casefold().strip())
    return {name for name in found if name}


def _ids(element: dict) -> set[str]:
    found = {str(element.get("id") or "")}
    for child in element.get("children") or []:
        found.add(str(child.get("id") or ""))
    return {item for item in found if item}


def budget_lines(elements: list[dict]) -> list[dict]:
    lines = []
    for element in elements:
        if element.get("isArchived"):
            continue
        planned, spent = _cell(element)
        if planned is None or planned <= 0:
            continue
        lines.append(
            {
                "id": element.get("id"),
                "name": element.get("name") or "",
                "currencyId": element.get("currencyId") or "",
                "planned": planned,
                "spent": spent,
                "names": _names(element),
                "ids": _ids(element),
            }
        )
    return lines


def match_lines(lines: list[dict], category: str) -> list[dict]:
    needle = category.casefold().strip()
    return [line for line in lines if needle in line["names"] or category in line["ids"]]


def currency_maps(api: Api) -> tuple[dict[str, str], dict[str, Decimal], str]:
    listed = api.get("/api/v1/currency/get-currency-list")
    rates = api.get("/api/v1/currency/get-currency-rate-list")
    codes: dict[str, str] = {}
    usd_id = ""
    for item in (listed.get("data") or {}).get("items") or []:
        codes[item["id"]] = item.get("code") or ""
        if item.get("code") == "USD":
            usd_id = item["id"]
    by_id: dict[str, Decimal] = {}
    for item in (rates.get("data") or {}).get("items") or []:
        parsed = parse_decimal(item.get("rate"))
        if parsed is not None and parsed > 0:
            by_id[item["currencyId"]] = parsed
    if usd_id:
        by_id.setdefault(usd_id, Decimal(1))
    return codes, by_id, usd_id


def amount_in_currency(
    amount: Decimal,
    source_code: str,
    target_id: str,
    codes: dict[str, str],
    rates: dict[str, Decimal],
) -> Decimal:
    target_code = codes.get(target_id) or ""
    if source_code == target_code:
        return money(amount)
    code_to_id = {code: cid for cid, code in codes.items()}
    source_id = code_to_id.get(source_code)
    if not source_id or source_id not in rates or target_id not in rates:
        raise RuntimeError(f"rate missing for {source_code} → {target_code or target_id}")
    return convert_amount(amount, rates[source_id], rates[target_id])


def line_result(
    line: dict,
    day: int,
    days: int,
    code: str,
    amount_in_budget: Decimal | None,
    category: str,
) -> dict:
    pace = expected_pace(line["planned"], day, days)
    over = line["spent"] > pace
    did_cross = False
    if amount_in_budget is not None:
        did_cross = crossed_pace(line["spent"], amount_in_budget, pace)
    text = None
    if did_cross:
        text = alert_text(line["name"], category, line["spent"], pace, line["planned"], code, day, days)
    return {
        "envelope": line["name"],
        "currency": code,
        "spent": money_text(line["spent"]),
        "planned": money_text(line["planned"]),
        "pace": money_text(pace),
        "over": over,
        "crossed": did_cross,
        "alert": text,
    }


def load_plan(api: Api, month_start: str) -> tuple[str, list[dict]]:
    listed = api.get("/api/v1/budget/get-budget-list")
    items = (listed.get("data") or {}).get("items") or []
    name = budget_name()
    budget = next((item for item in items if item.get("name") == name and not item.get("isArchived")), None)
    if budget is None:
        raise RuntimeError(f"budget {name} not found")
    plan = api.get(
        "/api/v1/budget/get-budget-plan?id="
        + budget["id"]
        + "&from="
        + month_start
        + "&months=1"
    )
    item = (plan.get("data") or {}).get("item") or {}
    elements = ((item.get("structure") or {}).get("elements")) or []
    return budget["name"], budget_lines(elements)


def evaluate(args: argparse.Namespace) -> dict:
    today = local_today()
    expense_day = today
    if args.date:
        expense_day = datetime.strptime(args.date, "%Y-%m-%d").date()
    day_num, days, month_start = month_span(today)
    report: dict = {
        "ok": True,
        "date": today.isoformat(),
        "day": day_num,
        "days": days,
        "budget": budget_name(),
    }
    if expense_day.year != today.year or expense_day.month != today.month:
        report.update(
            {
                "in_month": False,
                "expense_date": expense_day.isoformat(),
                "notified": False,
                "alert": None,
            }
        )
        return report

    api = login()
    _, lines = load_plan(api, month_start)
    codes, rates, _usd = currency_maps(api)

    if not args.category:
        rows = []
        for line in lines:
            code = codes.get(line["currencyId"]) or ""
            rows.append(line_result(line, day_num, days, code, None, line["name"]))
        report["lines"] = rows
        report["notified"] = False
        return report

    matched = match_lines(lines, args.category)
    if not matched:
        report.update(
            {
                "in_month": True,
                "category": args.category,
                "matched": False,
                "notified": False,
                "alert": None,
            }
        )
        return report

    if args.amount is None:
        raise RuntimeError("--amount is required with --category")
    amount = parse_decimal(args.amount)
    if amount is None or amount < 0:
        raise RuntimeError("bad amount")
    source = (args.currency or default_currency()).strip().upper()

    rows = []
    alerts = []
    for line in matched:
        code = codes.get(line["currencyId"]) or ""
        converted = amount_in_currency(amount, source, line["currencyId"], codes, rates)
        row = line_result(line, day_num, days, code, converted, args.category)
        row["amount"] = money_text(converted)
        rows.append(row)
        if row["alert"]:
            alerts.append(row["alert"])

    text = "\n".join(alerts) if alerts else None
    notified = False
    duplicate = False
    if text and not args.no_notify:
        sent = send_alert(text)
        notified = True
        duplicate = sent["duplicate"]
    report.update(
        {
            "in_month": True,
            "category": args.category,
            "matched": True,
            "lines": rows,
            "alert": text,
            "notified": notified,
            "duplicate": duplicate,
        }
    )
    return report


def self_test() -> int:
    pace = expected_pace(Decimal(3000), 29, 30)
    assert pace == Decimal(2900), pace
    assert expected_pace(Decimal(310), 1, 31) == Decimal(10)
    assert crossed_pace(Decimal("2910"), Decimal("20"), Decimal(2900))
    assert not crossed_pace(Decimal(3000), Decimal(10), Decimal(2900))
    assert not crossed_pace(Decimal(2900), Decimal(10), Decimal(2900))
    assert not crossed_pace(Decimal(100), Decimal(50), Decimal(2900))
    converted = convert_amount(Decimal(100), Decimal("84.58025"), Decimal("3.0316"))
    assert converted == money(Decimal(100) * Decimal("3.0316") / Decimal("84.58025"))
    same = convert_amount(Decimal("4.5"), Decimal(1), Decimal(1))
    assert same == Decimal("4.50")
    text = alert_text("Еда", "Еда (Кофе)", Decimal(3100), Decimal(2900), Decimal(3000), "BYN", 29, 30)
    assert text.startswith("Еда выше темпа из-за «Еда (Кофе)»")
    assert "3100 BYN" in text and "день 29 из 30" in text
    plain = alert_text("Еда", "Еда", Decimal(3100), Decimal(2900), Decimal(3000), "BYN", 29, 30)
    assert "из-за" not in plain
    elements = [
        {
            "id": "env",
            "name": "Еда",
            "isArchived": 0,
            "currencyId": "byn",
            "cells": [{"planned": "3000", "actual": "835"}],
            "children": [{"id": "coffee", "name": "Еда (Кофе)"}],
        },
        {
            "id": "gift",
            "name": "Подарки",
            "isArchived": 0,
            "currencyId": "byn",
            "cells": [{"planned": "", "actual": "10"}],
            "children": [],
        },
    ]
    lines = budget_lines(elements)
    assert len(lines) == 1
    assert match_lines(lines, "Еда (Кофе)")[0]["name"] == "Еда"
    assert match_lines(lines, "coffee")[0]["name"] == "Еда"
    assert match_lines(lines, "Подарки") == []
    assert budget_name()
    assert zone()
    print("self-test ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Spending pace vs the budget in catalog.json")
    parser.add_argument("--category", help="Category or envelope just spent, name or id")
    parser.add_argument("--amount", help="Expense amount in the account currency")
    parser.add_argument("--currency", default=None, help="Account currency code; default is catalog.json → econumo.currency")
    parser.add_argument("--date", help="Expense date Y-m-d. Pace still uses today in catalog.json timezone")
    parser.add_argument("--no-notify", action="store_true", help="Print only. Do not use after a real expense")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    try:
        report = evaluate(args)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
