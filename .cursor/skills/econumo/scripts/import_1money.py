#!/usr/bin/env python3
"""Load a 1Money CSV into the Econumo shelf in catalog.json.

Expenses and income keep their categories. Transfers stay transfers.
Accounts that are not on the live shelf are created in
catalog.json → econumo.deletedFolder, with econumo.deletedSuffix in the
name, so the operations remain. Live names and currencies come from
econumo.accounts, debtAccounts, importNames, aliases, and debtNameStoredAs.
A second run matches date, accounts, amount, category, and note:
Econumo stores its own id, not the id sent in the request.

Credentials: ECONUMO_BASE_URL, ECONUMO_USERNAME, ECONUMO_PASSWORD.
The script never prints the password or the session token.

Usage:
  python3 import_1money.py /path/to/1Money.csv
  python3 import_1money.py --self-test
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation
from pathlib import Path

NS = uuid.UUID("8f3e2c10-6a4b-4d1e-9c77-1b0e5a9d4c21")
ICON = "account_balance_wallet"
CATEGORY_ICON = "local_offer"
TYPES = {"Расход": "expense", "Доход": "income", "Перевод": "transfer"}

_LIVE: dict[str, tuple[str, str]] | None = None


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for folder in [here.parent, *here.parents]:
        if (folder / "catalog.json").is_file():
            return folder
    raise RuntimeError("catalog.json not found")


def catalog() -> dict:
    return json.loads((repo_root() / "catalog.json").read_text(encoding="utf-8"))


def econumo() -> dict:
    return catalog()["econumo"]


def deleted_folder() -> str:
    return str(econumo().get("deletedFolder") or "Удалённые")


def deleted_suffix() -> str:
    return str(econumo().get("deletedSuffix") or "· удалён").strip()


def uncategorized() -> str:
    return str(econumo().get("uncategorized") or "Без категории")


def live_map() -> dict[str, tuple[str, str]]:
    """CSV name -> (live Econumo name, currency).

    A row in another currency does not land on that card; it gets a deleted
    stub in the row currency. Built from catalog.json → econumo.
    """
    global _LIVE
    if _LIVE is not None:
        return _LIVE
    data = econumo()
    default_currency = str(data.get("currency") or "BYN")
    stored_as = data.get("debtNameStoredAs") or {}
    import_names = data.get("importNames") or {}
    mapping: dict[str, tuple[str, str]] = {}

    def bind(csv_name: str, live_name: str, code: str) -> None:
        mapping[csv_name] = (live_name, code)

    for account in data.get("accounts") or []:
        name = str(account["name"])
        code = str(account.get("currency") or default_currency)
        bind(name, name, code)
        for alias in import_names.get(name) or []:
            bind(str(alias), name, code)
    for debt in data.get("debtAccounts") or []:
        debt_name = str(debt)
        live = str(stored_as.get(debt_name, debt_name))
        bind(debt_name, live, default_currency)
        bind(live, live, default_currency)
        for alias in import_names.get(debt_name) or []:
            bind(str(alias), live, default_currency)
    for alias, target in (data.get("aliases") or {}).items():
        target_name = str(target)
        if target_name in mapping:
            bind(str(alias), mapping[target_name][0], mapping[target_name][1])
        else:
            live = str(stored_as.get(target_name, target_name))
            bind(str(alias), live, default_currency)
    _LIVE = mapping
    return mapping


class Api:
    def __init__(self, base: str, token: str) -> None:
        self.base = base.rstrip("/")
        self.token = token

    def call(self, method: str, path: str, payload: dict | None = None, tries: int = 5):
        data = None if payload is None else json.dumps(payload).encode()
        headers = {"Authorization": "Bearer " + self.token}
        if data is not None:
            headers["Content-Type"] = "application/json"
        last = "request failed"
        for attempt in range(tries):
            req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=60) as response:
                    body = response.read()
                    return json.loads(body) if body else {}
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:500]
                last = f"HTTP {exc.code} {detail}"
                retryable = exc.code in {429, 500, 502, 503, 504} or "locked" in detail.lower() or "busy" in detail.lower()
                if not retryable or attempt == tries - 1:
                    raise RuntimeError(last) from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last = str(exc)
                if attempt == tries - 1:
                    raise RuntimeError(last) from exc
            time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(last)

    def get(self, path: str):
        return self.call("GET", path)

    def post(self, path: str, payload: dict):
        body = self.call("POST", path, payload)
        if isinstance(body, dict) and body.get("success") is False:
            raise RuntimeError(json.dumps(body, ensure_ascii=False)[:500])
        return body


def login() -> Api:
    base = os.environ["ECONUMO_BASE_URL"].rstrip("/")
    body = json.dumps(
        {
            "username": os.environ["ECONUMO_USERNAME"],
            "password": os.environ["ECONUMO_PASSWORD"],
        }
    ).encode()
    req = urllib.request.Request(
        base + "/api/v1/user/login-user",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        token = json.loads(response.read())["token"]
    return Api(base, token)


def money(raw: str) -> Decimal:
    text = (raw or "").replace("\u00a0", "").replace(" ", "").replace(",", ".").strip()
    if not text:
        raise InvalidOperation("empty amount")
    return Decimal(text)


def money_str(value: Decimal) -> str:
    return format(abs(value), "f")


def canon_amount(value) -> str:
    text = format(abs(Decimal(str(value))), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def parse_date(raw: str) -> str:
    text = (raw or "").strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = time.strptime(text, fmt)
        except ValueError:
            continue
        if fmt.endswith("%S"):
            return time.strftime("%Y-%m-%d %H:%M:%S", parsed)
        return time.strftime("%Y-%m-%d 12:00:00", parsed)
    raise ValueError(f"bad date {text!r}")


def category_name(raw: str) -> str:
    name = (raw or "").strip()
    if len(name) >= 2 and name[0] == "(" and name[-1] == ")" and name.count("(") == 1:
        name = name[1:-1].strip()
    return name


def resolved_category(row: dict) -> str:
    return category_name(row["dst"]) or uncategorized()


def stub_name(original: str, currency: str, needs_code: bool) -> str:
    suffix = " " + deleted_suffix() + (f" · {currency}" if needs_code else "")
    room = 64 - len(suffix)
    base = original.strip() or "счёт"
    if len(base) < 3 and not needs_code:
        base = (base + "...").strip(".")
        base = (base + "...")[:3]
    if len(base) > room:
        base = base[:room].rstrip()
    name = f"{base}{suffix}"
    if len(name) < 3:
        name = (name + "...")[:64]
    return name[:64]


def load_rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    rows = []
    reader = csv.DictReader(text.splitlines())
    for raw in reader:
        kind = (raw.get("ТИП") or "").strip()
        if kind not in TYPES:
            continue
        src = (raw.get("СО СЧЁТА") or "").strip()
        dst = (raw.get("НА СЧЁТ/НА КАТЕГОРИЮ") or "").strip()
        rows.append(
            {
                "date": parse_date(raw.get("ДАТА") or ""),
                "kind": TYPES[kind],
                "src": src,
                "dst": dst,
                "amount": money(raw.get("СУММА") or ""),
                "currency": (raw.get("ВАЛЮТА") or "").strip().upper(),
                "amount2": (raw.get("СУММА 2") or "").strip(),
                "currency2": (raw.get("ВАЛЮТА 2") or "").strip().upper(),
                "notes": (raw.get("ЗАМЕТКИ") or "").strip(),
            }
        )
    stamp_ids(rows)
    return rows


def canonical(row: dict) -> str:
    return json.dumps(
        {
            "date": row["date"],
            "kind": row["kind"],
            "src": row["src"],
            "dst": row["dst"],
            "amount": money_str(row["amount"]),
            "currency": row["currency"],
            "amount2": row["amount2"],
            "currency2": row["currency2"],
            "notes": row["notes"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def row_id(row: dict, occurrence: int = 0) -> str:
    return str(uuid.uuid5(NS, canonical(row) + f"\n{occurrence}"))


def stamp_ids(rows: list[dict]) -> None:
    seen: Counter = Counter()
    for row in rows:
        key = canonical(row)
        occurrence = seen[key]
        seen[key] += 1
        row["occurrence"] = occurrence
        row["id"] = row_id(row, occurrence)


def second_amount(row: dict) -> tuple[Decimal, str]:
    if row["amount2"]:
        return money(row["amount2"]), row["currency2"] or row["currency"]
    return row["amount"], row["currency"]


def account_key(name: str, currency: str) -> tuple[str, str]:
    live = live_map().get(name)
    if live and live[1] == currency:
        return ("live", live[0])
    return ("stub", name)


def plan_accounts(rows: list[dict]) -> dict[tuple[str, str], str]:
    """Map (shelf, csv-or-live name) is not enough: return currency-aware targets.

    Key is (role, display name, currency) -> not used.
    Returns {(csv_name, currency): econumo account name}.
    """
    pairs: set[tuple[str, str]] = set()
    for row in rows:
        if row["src"] and row["currency"]:
            pairs.add((row["src"], row["currency"]))
        if row["kind"] == "transfer" and row["dst"]:
            amount2, currency2 = second_amount(row)
            if currency2:
                pairs.add((row["dst"], currency2))
    by_original: dict[str, set[str]] = {}
    for name, currency in pairs:
        if account_key(name, currency)[0] == "stub":
            by_original.setdefault(name, set()).add(currency)
    planned: dict[tuple[str, str], str] = {}
    for name, currency in pairs:
        role, live_name = account_key(name, currency)
        if role == "live":
            planned[(name, currency)] = live_name
        else:
            planned[(name, currency)] = stub_name(name, currency, len(by_original.get(name, set())) > 1)
    return planned


def self_test() -> None:
    sample = (
        '"ДАТА","ТИП","СО СЧЁТА","НА СЧЁТ/НА КАТЕГОРИЮ","СУММА","ВАЛЮТА","СУММА 2","ВАЛЮТА 2","МЕТКИ","ЗАМЕТКИ"\n'
        '"20.08.2026","Расход","Карта","Транспорт (Автомобиль)","7","BYN","7","BYN","",""\n'
        '"20.08.2026","Расход","Карта"," (Золотой слон)","1","BYN","1","BYN","",""\n'
        '"19.08.2026","Перевод","Кошелек","Карта Prior","10","BYN","10","BYN","","на карту"\n'
        '"01.01.2022","Перевод","Старый кошелёк","Другая карта","370.45","BYN","14500","RUB","",""\n'
        '"НАЗВАНИЕ","БАЛАНС","ВАЛЮТА"\n'
    )
    path = Path("/tmp/econumo-import-sample.csv")
    path.write_text(sample, encoding="utf-8")
    rows = load_rows(path)
    assert len(rows) == 4, len(rows)
    assert rows[0]["date"] == "2026-08-20 12:00:00"
    assert category_name(rows[1]["dst"]) == "Золотой слон"
    assert category_name(rows[0]["dst"]) == "Транспорт (Автомобиль)"
    planned = plan_accounts(rows)
    assert planned[("Карта", "BYN")].endswith("удалён")
    assert planned[("Кошелек", "BYN")].endswith("удалён")
    assert planned[("Карта Prior", "BYN")].endswith("удалён")
    assert planned[("Другая карта", "RUB")].endswith("удалён")
    two = plan_accounts(
        rows
        + [
            {
                "date": "2022-01-02 12:00:00",
                "kind": "expense",
                "src": "Старый кошелёк",
                "dst": "Еда",
                "amount": Decimal("1"),
                "currency": "RUB",
                "amount2": "",
                "currency2": "",
                "notes": "",
            },
            {
                "date": "2022-01-03 12:00:00",
                "kind": "expense",
                "src": "Старый кошелёк",
                "dst": "Еда",
                "amount": Decimal("1"),
                "currency": "USD",
                "amount2": "",
                "currency2": "",
                "notes": "",
            },
        ]
    )
    assert "RUB" in two[("Старый кошелёк", "RUB")]
    assert "USD" in two[("Старый кошелёк", "USD")]
    assert row_id(rows[0], 0) == rows[0]["id"]
    assert row_id(rows[0], 0) != row_id(rows[0], 1)
    assert operation_key(rows[0], planned) == operation_key(rows[0], planned)
    assert canon_amount("7.00") == canon_amount(7) == "7"
    assert canon_amount("-11.24") == "11.24"
    assert resolved_category({"dst": ""}) == uncategorized()
    assert resolved_category(rows[1]) == "Золотой слон"
    assert len(stub_name("Очень длинное название счёта которое точно не влезает в лимит", "BYN", False)) <= 64
    print("self-test ok", len(rows))


def items(payload: dict) -> list:
    data = payload.get("data") or {}
    return data.get("items") or []


def ensure_folder(api: Api, folders: dict[str, str]) -> str:
    name = deleted_folder()
    if name in folders:
        return folders[name]
    api.post("/api/v1/account/create-folder", {"name": name})
    fresh = {item["name"]: item["id"] for item in items(api.get("/api/v1/account/get-folder-list"))}
    if name not in fresh:
        raise RuntimeError(f"folder {name} was not created")
    return fresh[name]


def ensure_accounts(api: Api, planned: dict[tuple[str, str], str], currencies: dict[str, str]) -> dict[str, dict]:
    accounts = {item["name"]: item for item in items(api.get("/api/v1/account/get-account-list"))}
    folders = {item["name"]: item["id"] for item in items(api.get("/api/v1/account/get-folder-list"))}
    folder_id = None
    wanted = {}
    for (csv_name, currency), econ_name in planned.items():
        wanted.setdefault(econ_name, currency)
    for name, currency in sorted(wanted.items()):
        if name in accounts:
            have = accounts[name]["currency"]["code"]
            if have != currency:
                raise RuntimeError(f"{name} is {have}, import needs {currency}")
            continue
        if currency not in currencies:
            raise RuntimeError(f"no currency {currency} for account {name}")
        if folder_id is None:
            folder_id = ensure_folder(api, folders)
        api.post(
            "/api/v1/account/create-account",
            {
                "id": str(uuid.uuid4()),
                "name": name,
                "currencyId": currencies[currency],
                "folderId": folder_id,
                "balance": "0.00",
                "icon": ICON,
            },
        )
        print("account", name, currency, flush=True)
    accounts = {item["name"]: item for item in items(api.get("/api/v1/account/get-account-list"))}
    missing = [name for name in wanted if name not in accounts]
    if missing:
        raise RuntimeError("accounts missing after create: " + ", ".join(missing))
    return accounts


def ensure_categories(api: Api, rows: list[dict]) -> dict[tuple[str, str], str]:
    have = {(item["type"], item["name"]): item["id"] for item in items(api.get("/api/v1/category/get-category-list"))}
    needed = set()
    for row in rows:
        if row["kind"] == "transfer":
            continue
        needed.add((row["kind"], resolved_category(row)))
    for key in sorted(needed):
        if key in have:
            continue
        kind, name = key
        api.post(
            "/api/v1/category/create-category",
            {"id": str(uuid.uuid4()), "name": name, "type": kind, "icon": CATEGORY_ICON},
        )
        print("category", kind, name, flush=True)
    if needed - set(have):
        have = {(item["type"], item["name"]): item["id"] for item in items(api.get("/api/v1/category/get-category-list"))}
    missing = [f"{kind}:{name}" for kind, name in needed if (kind, name) not in have]
    if missing:
        raise RuntimeError("categories missing: " + ", ".join(missing[:20]))
    return have


def transaction_list(api: Api) -> list:
    payload = api.get(
        "/api/v1/transaction/get-transaction-list?periodStart=2000-01-01%2000:00:00&periodEnd=2027-01-01%2000:00:00"
    )
    return items(payload)


def clear_balance_adjustments(api: Api) -> int:
    """Remove the zeroing corrections from the empty-shelf setup.

    Each account's adjustments must net to zero. A non-zero net is left
    in place and stops the import, so a real balance is not deleted.
    """
    found = [
        item
        for item in transaction_list(api)
        if (item.get("description") or "") == "Balance adjustment" and str(item.get("date") or "").startswith("2026-08-31")
    ]
    if not found:
        print("balance adjustments 0", flush=True)
        return 0
    nets: dict[str, Decimal] = {}
    for item in found:
        kind = item.get("type")
        if kind == "income":
            sign = Decimal(1)
        elif kind == "expense":
            sign = Decimal(-1)
        else:
            raise RuntimeError(f"unexpected balance adjustment {item.get('id')} type {kind}")
        account_id = item["accountId"]
        nets[account_id] = nets.get(account_id, Decimal(0)) + sign * Decimal(str(item["amount"]))
    bad = {account_id: str(net) for account_id, net in nets.items() if net != 0}
    if bad:
        raise RuntimeError("balance adjustments do not net to zero: " + json.dumps(bad))
    for item in found:
        api.post("/api/v1/transaction/delete-transaction", {"id": item["id"]})
    print("deleted balance adjustments", len(found), flush=True)
    return len(found)


def operation_key(row: dict, planned) -> tuple:
    """Identity Econumo actually keeps. The server replaces the request id."""
    src_name = planned[(row["src"], row["currency"])]
    notes = row["notes"][:500]
    if row["kind"] == "transfer":
        amount2, currency2 = second_amount(row)
        dst_name = planned[(row["dst"], currency2)]
        return (
            row["date"],
            "transfer",
            src_name,
            canon_amount(row["amount"]),
            dst_name,
            canon_amount(amount2),
            notes,
        )
    return (
        row["date"],
        row["kind"],
        src_name,
        canon_amount(row["amount"]),
        resolved_category(row),
        notes,
    )


def server_operation_key(item: dict, accounts_by_id: dict, category_names: dict) -> tuple:
    src = accounts_by_id[item["accountId"]]["name"]
    notes = (item.get("description") or "")[:500]
    if item.get("type") == "transfer":
        dst = accounts_by_id.get(item.get("accountRecipientId") or "", {}).get("name", "")
        return (
            item.get("date"),
            "transfer",
            src,
            canon_amount(item.get("amount") or 0),
            dst,
            canon_amount(item.get("amountRecipient") or 0),
            notes,
        )
    return (
        item.get("date"),
        item.get("type"),
        src,
        canon_amount(item.get("amount") or 0),
        category_names.get(item.get("categoryId") or "", ""),
        notes,
    )


def build_body(row: dict, accounts: dict[str, dict], categories, planned) -> dict:
    src_name = planned[(row["src"], row["currency"])]
    body = {
        "id": row["id"],
        "type": row["kind"],
        "accountId": accounts[src_name]["id"],
        "amount": money_str(row["amount"]),
        "date": row["date"],
        "description": row["notes"][:500],
    }
    if row["kind"] == "transfer":
        amount2, currency2 = second_amount(row)
        dst_name = planned[(row["dst"], currency2)]
        body["accountRecipientId"] = accounts[dst_name]["id"]
        body["amountRecipient"] = money_str(amount2)
    else:
        body["categoryId"] = categories[(row["kind"], resolved_category(row))]
    return body


def import_rows(api: Api, rows: list[dict], accounts: dict[str, dict], categories, planned, workers: int, dry_run: bool) -> Counter:
    accounts_by_id = {item["id"]: item for item in accounts.values()}
    category_names = {category_id: name for (_kind, name), category_id in categories.items()}
    have: Counter = Counter()
    for item in transaction_list(api):
        if item.get("accountId") not in accounts_by_id:
            continue
        have[server_operation_key(item, accounts_by_id, category_names)] += 1
    stats: Counter = Counter()
    pending = []
    for index, row in enumerate(rows, start=1):
        key = operation_key(row, planned)
        if have[key] > 0:
            have[key] -= 1
            stats["already"] += 1
            continue
        pending.append((index, row))
    print(f"to create {len(pending)} already {stats['already']}", flush=True)
    if dry_run:
        return stats
    lock = threading.Lock()
    finished = 0

    def one(item: tuple[int, dict]) -> None:
        nonlocal finished
        index, row = item
        try:
            api.post("/api/v1/transaction/create-transaction", build_body(row, accounts, categories, planned))
            key = row["kind"]
        except Exception as exc:  # noqa: BLE001 — keep going and report the row
            text = str(exc)
            if "already" in text.lower() or "exist" in text.lower() or "duplicate" in text.lower():
                key = "already"
            else:
                key = "failed"
                print(
                    f"fail row {index} {row['date']} {row['kind']} {row['src']} -> {row['dst']}: {text[:240]}",
                    flush=True,
                )
        with lock:
            stats[key] += 1
            finished += 1
            if finished % 200 == 0 or finished == len(pending):
                print(f"progress {finished}/{len(pending)} {dict(stats)}", flush=True)

    if workers <= 1 or len(pending) <= 1:
        for item in pending:
            one(item)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(one, pending))
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", nargs="?")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.csv_path:
        print("need the 1Money csv path", file=sys.stderr)
        return 2
    rows = load_rows(Path(args.csv_path))
    print("rows", len(rows), dict(Counter(row["kind"] for row in rows)), "ids", len({row["id"] for row in rows}))
    planned = plan_accounts(rows)
    api = login()
    clear_balance_adjustments(api)
    currencies = {item["code"]: item["id"] for item in items(api.get("/api/v1/currency/get-currency-list"))}
    accounts = ensure_accounts(api, planned, currencies)
    categories = ensure_categories(api, rows)
    started = time.time()
    stats = import_rows(api, rows, accounts, categories, planned, max(1, args.workers), args.dry_run)
    print("elapsed", round(time.time() - started), flush=True)
    print("done", dict(stats))
    check = api.get(
        "/api/v1/transaction/get-transaction-list?periodStart=2000-01-01%2000:00:00&periodEnd=2027-01-01%2000:00:00"
    )
    listed = items(check)
    real = [item for item in listed if (item.get("description") or "") != "Balance adjustment"]
    print("listed", len(listed), "without balance adjustments", len(real))
    by_type = Counter(item["type"] for item in real)
    print("by type", dict(by_type))
    return 1 if stats["failed"] else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        raise SystemExit(0)
