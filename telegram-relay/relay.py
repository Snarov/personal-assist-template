#!/usr/bin/env python3
"""Thin Telegram relay for Personal Assist.

Cursor agents POST here to write the owner in Telegram.
The owner's replies are queued and forwarded to a Cursor webhook automation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

TELEGRAM_API = "https://api.telegram.org"
MAX_TG = 3900
STATE_LOCK = threading.Lock()
DEFAULT_LAUNCH_COOLDOWN_SEC = 360
DEFAULT_SEND_DEDUPE_SEC = 900
DEFAULT_RITUAL_HOLD_SEC = 90 * 60
DEFAULT_INBOX_FRESH_SEC = 300
SEND_TELEGRAM_TIMEOUT = 50
OUTGOING_WAIT_SEC = 70
TRAILING_UPDATES_TIMEOUT_SEC = 8


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def allowed_chat_ids() -> set[str]:
    raw = env("TELEGRAM_ALLOWED_CHAT_IDS")
    return {part.strip() for part in raw.split(",") if part.strip()}


def default_chat_id() -> str:
    ids = sorted(allowed_chat_ids())
    if not ids:
        raise RuntimeError("TELEGRAM_ALLOWED_CHAT_IDS is empty")
    return ids[0]


def state_path() -> Path:
    path = Path(env("RELAY_STATE_PATH", "/var/lib/personal-assist/state.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_state() -> dict[str, Any]:
    path = state_path()
    if not path.exists():
        return {"offset": 0, "last_kind": None, "inbox": []}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"offset": 0, "last_kind": None, "inbox": []}
    data.setdefault("offset", 0)
    data.setdefault("last_kind", None)
    data.setdefault("inbox", [])
    data.setdefault("pending_archive", [])
    return data


def save_state(state: dict[str, Any]) -> None:
    path = state_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    tmp.replace(path)


def bearer_ok(header: str | None) -> bool:
    secret = env("RELAY_SECRET")
    if not secret or not header:
        return False
    prefix = "Bearer "
    if not header.startswith(prefix):
        return False
    given = header[len(prefix) :].strip()
    return secrets.compare_digest(given, secret)


def tg(method: str, payload: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    token = env("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
    url = f"{TELEGRAM_API}/bot{token}/{method}"
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method="POST" if body else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:500]
        raise RuntimeError(f"telegram {method} HTTP {exc.code}: {detail}") from exc


def split_text(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= MAX_TG:
        return [text]
    chunks: list[str] = []
    rest = text
    while rest:
        if len(rest) <= MAX_TG:
            chunks.append(rest)
            break
        cut = rest.rfind("\n", 0, MAX_TG)
        if cut < 200:
            cut = MAX_TG
        chunks.append(rest[:cut])
        rest = rest[cut:].lstrip("\n")
    return chunks


ACK_RECEIVED_EMOJI = "👀"
ACK_LAUNCHED_EMOJI = "⚡"
ACK_TEXT = "Принял."


def tg_chat_target(chat_id: str) -> int | str:
    target = str(chat_id)
    return int(target) if target.lstrip("-").isdigit() else target


def send_telegram(
    text: str,
    chat_id: str | None = None,
    reply_to_message_id: int | None = None,
) -> dict[str, Any]:
    target = str(chat_id or default_chat_id())
    if target not in allowed_chat_ids():
        raise RuntimeError("chat_id is not allowlisted")
    sent = []
    reply_to = int(reply_to_message_id) if reply_to_message_id is not None else None
    for chunk in split_text(text):
        payload: dict[str, Any] = {
            "chat_id": tg_chat_target(target),
            "text": chunk,
            "disable_web_page_preview": True,
        }
        if reply_to is not None:
            payload["reply_to_message_id"] = reply_to
            payload["allow_sending_without_reply"] = True
            reply_to = None
        result = tg("sendMessage", payload, timeout=SEND_TELEGRAM_TIMEOUT)
        if not result.get("ok"):
            raise RuntimeError(f"telegram send failed: {result}")
        sent.append(result.get("result") or {})
    return {"ok": True, "chat_id": target, "messages": len(sent)}


class _OutgoingSlot:
    def __init__(self) -> None:
        self.event = threading.Event()
        self.result: dict[str, Any] | None = None
        self.error: BaseException | None = None


_outgoing_inflight: dict[str, _OutgoingSlot] = {}
_outgoing_guard = threading.Lock()


def send_dedupe_sec() -> int:
    raw = env("RELAY_SEND_DEDUPE_SEC", str(DEFAULT_SEND_DEDUPE_SEC))
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_SEND_DEDUPE_SEC


def ritual_hold_sec() -> int:
    raw = env("RELAY_RITUAL_HOLD_SEC", str(DEFAULT_RITUAL_HOLD_SEC))
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_RITUAL_HOLD_SEC


def inbox_fresh_sec() -> int:
    raw = env("RELAY_INBOX_FRESH_SEC", str(DEFAULT_INBOX_FRESH_SEC))
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_INBOX_FRESH_SEC


def outgoing_fingerprint(chat_id: str, text: str) -> str:
    return hashlib.sha256(f"{chat_id}\n{text.strip()}".encode()).hexdigest()


def _recent_outgoing(state: dict[str, Any], fingerprint: str, now: float) -> dict[str, Any] | None:
    window = send_dedupe_sec()
    if window <= 0:
        return None
    for item in reversed(state.get("recent_sends") or []):
        if item.get("fp") != fingerprint or not item.get("ok"):
            continue
        try:
            at = float(item.get("at") or 0)
        except (TypeError, ValueError):
            continue
        if now - at <= window:
            return item
    return None


def _remember_outgoing(fingerprint: str, messages: int) -> None:
    window = send_dedupe_sec()
    if window <= 0:
        return
    now = time.time()
    with STATE_LOCK:
        state = load_state()
        kept: list[dict[str, Any]] = []
        for item in state.get("recent_sends") or []:
            try:
                at = float(item.get("at") or 0)
            except (TypeError, ValueError):
                continue
            if now - at <= window:
                kept.append(item)
        kept.append({"fp": fingerprint, "at": now, "ok": True, "messages": messages})
        state["recent_sends"] = kept[-40:]
        save_state(state)


def _duplicate_result(chat_id: str, messages: Any) -> dict[str, Any]:
    try:
        count = int(messages)
    except (TypeError, ValueError):
        count = 1
    return {"ok": True, "chat_id": chat_id, "messages": count, "duplicate": True}


def deliver_outgoing(text: str, chat_id: str | None = None) -> dict[str, Any]:
    """Send once. A same-text retry still in flight, or within the dedupe window, is not a second Telegram message.

    Diary posts often take about 30s. A 30s client timeout then retries the same body.
    On 2026-09-23 that retry landed a second morning questionnaire.
    """
    target = str(chat_id or default_chat_id())
    if target not in allowed_chat_ids():
        raise RuntimeError("chat_id is not allowlisted")
    cleaned = text.strip()
    if not cleaned:
        raise RuntimeError("text required")
    fingerprint = outgoing_fingerprint(target, cleaned)
    with STATE_LOCK:
        hit = _recent_outgoing(load_state(), fingerprint, time.time())
    if hit:
        return _duplicate_result(target, hit.get("messages"))

    with _outgoing_guard:
        slot = _outgoing_inflight.get(fingerprint)
        if slot is None:
            slot = _OutgoingSlot()
            _outgoing_inflight[fingerprint] = slot
            leader = True
        else:
            leader = False

    if not leader:
        if not slot.event.wait(OUTGOING_WAIT_SEC):
            raise RuntimeError("outgoing send still in flight")
        if slot.result and slot.result.get("ok"):
            return _duplicate_result(target, slot.result.get("messages"))
        if slot.error is not None:
            raise slot.error
        raise RuntimeError("outgoing send failed")

    try:
        with STATE_LOCK:
            hit = _recent_outgoing(load_state(), fingerprint, time.time())
        if hit:
            result = _duplicate_result(target, hit.get("messages"))
            slot.result = result
            return result
        result = send_telegram(cleaned, target)
        _remember_outgoing(fingerprint, int(result.get("messages") or 1))
        slot.result = result
        return result
    except Exception as exc:
        slot.error = exc
        raise
    finally:
        slot.event.set()
        with _outgoing_guard:
            if _outgoing_inflight.get(fingerprint) is slot:
                del _outgoing_inflight[fingerprint]


def confirm_key(ids: list[str]) -> str:
    return ",".join(sorted({item for item in ids if item}))


def _ids_marked(state: dict[str, Any], field: str, ids: list[str], now: float) -> bool:
    if not ids:
        return False
    window = send_dedupe_sec()
    if window <= 0:
        return False
    marked = state.get(field) or {}
    if not isinstance(marked, dict):
        return False
    for mid in ids:
        item = marked.get(mid)
        if not isinstance(item, dict):
            return False
        try:
            at = float(item.get("at") or 0)
        except (TypeError, ValueError):
            return False
        if now - at > window:
            return False
    return True


def _remember_ids(field: str, ids: list[str]) -> None:
    window = send_dedupe_sec()
    if window <= 0 or not ids:
        return
    now = time.time()
    with STATE_LOCK:
        state = load_state()
        marked = state.get(field) if isinstance(state.get(field), dict) else {}
        kept: dict[str, Any] = {}
        for mid, item in marked.items():
            if not isinstance(item, dict):
                continue
            try:
                at = float(item.get("at") or 0)
            except (TypeError, ValueError):
                continue
            if now - at <= window:
                kept[str(mid)] = item
        for mid in ids:
            kept[mid] = {"at": now}
        state[field] = kept
        save_state(state)


_confirm_inflight: dict[str, _OutgoingSlot] = {}
_confirm_guard = threading.Lock()


def _fresh_marks(marked: Any, now: float) -> bool:
    window = send_dedupe_sec()
    if window <= 0 or not isinstance(marked, dict):
        return False
    for item in marked.values():
        if not isinstance(item, dict):
            continue
        try:
            at = float(item.get("at") or 0)
        except (TypeError, ValueError):
            continue
        if now - at <= window:
            return True
    return False


def deliver_confirm(text: str, chat_id: str | None, ids: list[str]) -> dict[str, Any]:
    """One non-survey reply per inbox id set, even when the wording differs.

    On 2026-09-24 the morning run and a second telegram-feedback run each
    confirmed the same voice. The texts were the same answer, not the same
    string, so exact-text dedupe let both through about a minute apart.
    A confirm after ack has no unacked ids; a fresh confirm mark still blocks it.
    """
    cleaned_ids = [item for item in ids if item]
    if not cleaned_ids:
        target = str(chat_id or default_chat_id())
        with STATE_LOCK:
            if _fresh_marks(load_state().get("confirmed_inbox"), time.time()):
                return _duplicate_result(target, 1)
        result = deliver_outgoing(text, chat_id)
        if result.get("ok"):
            _remember_ids("confirmed_inbox", ["*"])
        return result
    key = confirm_key(cleaned_ids)
    target = str(chat_id or default_chat_id())
    with STATE_LOCK:
        if _ids_marked(load_state(), "confirmed_inbox", cleaned_ids, time.time()):
            return _duplicate_result(target, 1)

    with _confirm_guard:
        slot = _confirm_inflight.get(key)
        if slot is None:
            slot = _OutgoingSlot()
            _confirm_inflight[key] = slot
            leader = True
        else:
            leader = False

    if not leader:
        if not slot.event.wait(OUTGOING_WAIT_SEC):
            raise RuntimeError("confirm still in flight")
        if slot.result and slot.result.get("ok"):
            return _duplicate_result(target, slot.result.get("messages"))
        if slot.error is not None:
            raise slot.error
        raise RuntimeError("confirm failed")

    try:
        with STATE_LOCK:
            if _ids_marked(load_state(), "confirmed_inbox", cleaned_ids, time.time()):
                result = _duplicate_result(target, 1)
                slot.result = result
                return result
        result = deliver_outgoing(text, chat_id)
        if result.get("ok"):
            _remember_ids("confirmed_inbox", cleaned_ids)
        slot.result = result
        return result
    except Exception as exc:
        slot.error = exc
        raise
    finally:
        slot.event.set()
        with _confirm_guard:
            if _confirm_inflight.get(key) is slot:
                del _confirm_inflight[key]


def note_inbox_read() -> None:
    with STATE_LOCK:
        state = load_state()
        state["last_inbox_read_at"] = time.time()
        save_state(state)


def note_ritual_hold() -> None:
    window = ritual_hold_sec()
    if window <= 0:
        return
    with STATE_LOCK:
        state = load_state()
        state["ritual_hold_until"] = time.time() + window
        save_state(state)


def ritual_agent_is_draining(state: dict[str, Any]) -> bool:
    """Morning/evening already has this inbox. A second cloud agent doubles the confirm."""
    now = time.time()
    try:
        hold = float(state.get("ritual_hold_until") or 0)
        seen = float(state.get("last_inbox_read_at") or 0)
    except (TypeError, ValueError):
        return False
    fresh = inbox_fresh_sec()
    if fresh <= 0 or now >= hold:
        return False
    return now - seen <= fresh


def _as_message_id(message_id: Any) -> int | None:
    if message_id is None:
        return None
    raw = str(message_id).strip()
    if not raw.lstrip("-").isdigit():
        return None
    return int(raw)


def set_message_reaction(chat_id: str, message_id: int, emoji: str) -> None:
    tg(
        "setMessageReaction",
        {
            "chat_id": tg_chat_target(chat_id),
            "message_id": int(message_id),
            "reaction": [{"type": "emoji", "emoji": emoji}],
        },
        timeout=10,
    )


def send_chat_action(chat_id: str, action: str = "typing") -> None:
    tg(
        "sendChatAction",
        {"chat_id": tg_chat_target(chat_id), "action": action},
        timeout=10,
    )


def notify_received(chat_id: str, message_id: Any, source: str = "text") -> None:
    """Immediate UX before STT / cloud boot. Never raise — the message must still queue."""
    mid = _as_message_id(message_id)
    if mid is not None:
        try:
            set_message_reaction(chat_id, mid, ACK_RECEIVED_EMOJI)
        except Exception as exc:  # noqa: BLE001
            print(f"ack reaction failed: {exc}", file=sys.stderr)
    try:
        send_chat_action(chat_id, "record_voice" if source == "voice" else "typing")
    except Exception as exc:  # noqa: BLE001
        print(f"ack typing failed: {exc}", file=sys.stderr)
    try:
        send_telegram(ACK_TEXT, chat_id, reply_to_message_id=mid)
    except Exception as exc:  # noqa: BLE001
        print(f"ack text failed: {exc}", file=sys.stderr)


def notify_launched(chat_id: str, message_id: Any) -> None:
    mid = _as_message_id(message_id)
    if mid is None:
        return
    try:
        set_message_reaction(chat_id, mid, ACK_LAUNCHED_EMOJI)
    except Exception as exc:  # noqa: BLE001
        print(f"launch reaction failed: {exc}", file=sys.stderr)


CURSOR_API_URL = "https://api.cursor.com/v1/agents"
RITUAL_KINDS = {"morning", "evening"}
# A pace alert is an ordinary message. It must not take the one-confirm slot.
SEND_PURPOSES = {"survey", "confirm", "clarify", "alert"}
CONFIRM_PURPOSES = {"confirm", "clarify"}


def resolve_send(kind: str, purpose: str) -> tuple[str, str]:
    """Return (purpose, route). route is ``confirm`` or ``outgoing``.

    ``kind=pace`` and ``purpose=alert`` both go out as an ordinary message,
    including when an older relay would have rewritten an unknown purpose.
    """
    kind = (kind or "reply").strip() or "reply"
    purpose = (purpose or "").strip().lower()
    if purpose not in SEND_PURPOSES:
        if kind == "survey":
            purpose = "survey"
        elif kind == "reply":
            purpose = "confirm"
        elif kind == "pace":
            purpose = "alert"
        else:
            purpose = ""
    route = "confirm" if purpose in CONFIRM_PURPOSES else "outgoing"
    return purpose, route


# Cloud Agents API has no "source=automations" filter. Ritual chats use these titles.
DEFAULT_ARCHIVE_NEEDLES = (
    "telegram feedback",
    "morning check-in",
    "evening review",
)


def llm_proxy_url() -> str | None:
    """SOCKS URL for Cursor (and optional Whisper) hops from Belarus.

    Use socks5h so DNS is resolved through the proxy. socks5 (no h) resolves
    api2.cursor.sh locally, which is geo-blocked and makes the webhook look
    like it never started the cloud agent.
    """
    raw = env("HERMES_LLM_PROXY") or env("RELAY_LLM_PROXY")
    if not raw:
        return None
    if "://" in raw:
        if raw.startswith("socks5://") and not raw.startswith("socks5h://"):
            return "socks5h://" + raw[len("socks5://") :]
        return raw
    parts = raw.split(":", 3)
    if len(parts) >= 4:
        host, port, user, password = parts[0], parts[1], parts[2], parts[3]
        return (
            "socks5h://"
            + urllib.parse.quote(user, safe="")
            + ":"
            + urllib.parse.quote(password, safe="")
            + f"@{host}:{port}"
        )
    return None


def bearer_token(raw: str) -> str:
    token = raw.strip()
    while token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def record_launch(ok: bool, error: str = "") -> None:
    with STATE_LOCK:
        state = load_state()
        state["last_launch"] = {
            "ok": ok,
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "error": redact_secret(error)[:240] if error else "",
        }
        save_state(state)


def launch_cooldown_sec() -> int:
    raw = env("RELAY_LAUNCH_COOLDOWN_SEC", str(DEFAULT_LAUNCH_COOLDOWN_SEC))
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_LAUNCH_COOLDOWN_SEC


def last_ok_launch_age_sec(state: dict[str, Any]) -> float | None:
    last = state.get("last_launch") or {}
    if not last.get("ok"):
        return None
    at = last.get("at")
    if not at:
        return None
    try:
        launched = datetime.strptime(str(at), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return max(0.0, time.time() - launched.timestamp())


def unacked_inbox(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [x for x in state.get("inbox") or [] if not x.get("acked")]


def maybe_launch_feedback() -> bool:
    """Start at most one cloud agent per cooldown for the whole unacked inbox.

    Each voice message used to POST a new webhook immediately. Three voices
    in one burst started three agents; one of them re-sent an already-live
    diary survey. Queue everything, then launch once.
    """
    with STATE_LOCK:
        state = load_state()
        pending = unacked_inbox(state)
        if not pending:
            return False
        if ritual_agent_is_draining(state):
            print(
                f"skip cursor launch, ritual agent is draining inbox={len(pending)}",
                file=sys.stderr,
            )
            return False
        age = last_ok_launch_age_sec(state)
        cooldown = launch_cooldown_sec()
        if age is not None and age < cooldown:
            print(
                f"skip cursor launch, cooldown {age:.0f}s < {cooldown}s, inbox={len(pending)}",
                file=sys.stderr,
            )
            return False
        newest = pending[-1]
        payload = {
            "source": "telegram",
            "input": newest.get("source") or "text",
            "chat_id": newest.get("chat_id"),
            "text": newest.get("text"),
            "kind_hint": newest.get("kind_hint"),
            "received_at": newest.get("received_at"),
            "message_id": newest.get("id"),
            "inbox_count": len(pending),
        }
        reactions = [(x.get("chat_id"), x.get("tg_message_id")) for x in pending]
        chat_id = str(newest.get("chat_id") or default_chat_id())
    started = forward_cursor(payload)
    if started:
        for item_chat, mid in reactions:
            if item_chat:
                notify_launched(str(item_chat), mid)
        return True
    try:
        send_telegram(
            "Сообщение в очереди, но облачный ассистент не стартовал. "
            "Ответ всё равно разберёт следующий ритуал. Повтори текстом, если ответа нет.",
            chat_id,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"webhook-fail notice failed: {exc}", file=sys.stderr)
    return False


def curl_http(
    method: str,
    url: str,
    extra_headers: list[str],
    use_proxy: bool,
    timeout: int = 20,
    extra_args: list[str] | None = None,
    payload: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    dest = Path(f"/tmp/pa-wh-{uuid.uuid4().hex}")
    cmd = [
        "curl",
        "-sS",
        "-o",
        str(dest),
        "-w",
        "%{http_code}",
        "--max-time",
        str(timeout),
        "-X",
        method,
        url,
    ]
    if payload is not None:
        cmd.extend(
            [
                "-H",
                "Content-Type: application/json",
                "-d",
                json.dumps(payload, ensure_ascii=False),
            ]
        )
    if extra_args:
        cmd[1:1] = extra_args
    for header in extra_headers:
        cmd.extend(["-H", header])
    proxy = llm_proxy_url() if use_proxy else None
    if proxy:
        cmd[1:1] = ["--proxy", proxy]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5, check=False)
        code = (proc.stdout or "").strip()
        body = dest.read_text(errors="replace") if dest.exists() else ""
        if proc.returncode != 0 or not code.startswith("2"):
            detail = redact_secret((body or proc.stderr or "")[:180])
            return False, f"HTTP {code or proc.returncode} {detail}".strip()
        return True, body
    except Exception as exc:  # noqa: BLE001 — relay must keep polling
        return False, str(exc)
    finally:
        dest.unlink(missing_ok=True)


def curl_json_post(
    url: str,
    payload: dict[str, Any],
    extra_headers: list[str],
    use_proxy: bool,
    timeout: int = 20,
    extra_args: list[str] | None = None,
) -> tuple[bool, str]:
    return curl_http(
        "POST",
        url,
        extra_headers,
        use_proxy,
        timeout=timeout,
        extra_args=extra_args,
        payload=payload,
    )


def feedback_prompt(payload: dict[str, Any]) -> str:
    return (
        "Follow the telegram-feedback skill. "
        "If the text has an expense, income, transfer, debt, or account balance, "
        "also follow the econumo skill on that clause and do not copy it into Notion, "
        "the diary, routine, or notes.\n\n"
        "This is the owner's Telegram reply to the latest morning or evening check-in. "
        "Use kind_hint plus today's Planning status and the ritual miss list to classify. "
        "GET /inbox as well and handle every unacked message. "
        "One Notion write, one Telegram confirm via POST /send with kind=reply, "
        "then POST /inbox/ack.\n\n"
        "```json\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n```"
    )


def launch_attempts(use_proxy_first: bool) -> list[bool]:
    if use_proxy_first:
        return [True, False]
    return [False]


def launch_via_webhook(payload: dict[str, Any]) -> tuple[bool, str]:
    url = env("CURSOR_WEBHOOK_URL")
    if not url:
        return False, "CURSOR_WEBHOOK_URL is empty"
    headers: list[str] = []
    key = bearer_token(env("CURSOR_WEBHOOK_KEY"))
    if key:
        headers.append(f"Authorization: Bearer {key}")
    errors: list[str] = []
    proxy = llm_proxy_url()
    for use_proxy in launch_attempts(bool(proxy)):
        ok, detail = curl_json_post(url, payload, headers, use_proxy=use_proxy)
        if ok:
            remember_agent_id(extract_agent_id(detail))
            return True, ""
        errors.append(("proxy " if use_proxy else "direct ") + detail)
    return False, "; ".join(errors)


def launch_via_api(payload: dict[str, Any]) -> tuple[bool, str]:
    key = bearer_token(env("CURSOR_API_KEY"))
    if not key:
        return False, "CURSOR_API_KEY is empty"
    env_name = env("CURSOR_ENV_NAME")
    if not env_name:
        return False, "CURSOR_ENV_NAME is empty"
    body = {
        "prompt": {"text": feedback_prompt(payload)},
        "name": "Telegram feedback",
        "env": {"type": "cloud", "name": env_name},
    }
    extra_args = ["-u", f"{key}:"]
    errors: list[str] = []
    proxy = llm_proxy_url()
    for use_proxy in launch_attempts(bool(proxy)):
        ok, detail = curl_json_post(
            env("CURSOR_API_URL", CURSOR_API_URL) or CURSOR_API_URL,
            body,
            [],
            use_proxy=use_proxy,
            extra_args=extra_args,
        )
        if ok:
            remember_agent_id(extract_agent_id(detail))
            return True, ""
        errors.append(("proxy " if use_proxy else "direct ") + detail)
    return False, "; ".join(errors)


def forward_cursor(payload: dict[str, Any]) -> bool:
    """Start a telegram-feedback cloud agent. Prefer the webhook automation,
    then the Cloud Agents API. Retry through the proxy, then direct.
    """
    errors: list[str] = []
    if env("CURSOR_WEBHOOK_URL"):
        ok, detail = launch_via_webhook(payload)
        if ok:
            record_launch(True)
            kick_archive_sweep()
            return True
        errors.append(f"webhook: {detail}")
        print(f"cursor webhook failed: {redact_secret(detail)}", file=sys.stderr)
    else:
        errors.append("webhook: CURSOR_WEBHOOK_URL is empty")
    if env("CURSOR_API_KEY"):
        ok, detail = launch_via_api(payload)
        if ok:
            record_launch(True)
            kick_archive_sweep()
            return True
        errors.append(f"api: {detail}")
        print(f"cursor api launch failed: {redact_secret(detail)}", file=sys.stderr)
    else:
        errors.append("api: CURSOR_API_KEY is empty")
    record_launch(False, "; ".join(errors))
    return False


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def archive_idle_enabled() -> bool:
    raw = env("CURSOR_ARCHIVE_IDLE", "1").lower()
    return raw not in {"0", "false", "no", "off"}


def archive_needles() -> tuple[str, ...]:
    raw = env("CURSOR_ARCHIVE_NAME_SUBSTR")
    if not raw:
        return DEFAULT_ARCHIVE_NEEDLES
    parts = tuple(part.strip().casefold() for part in raw.split(",") if part.strip())
    return parts or DEFAULT_ARCHIVE_NEEDLES


def is_ritual_agent_name(name: str) -> bool:
    lowered = (name or "").casefold()
    return any(needle in lowered for needle in archive_needles())


def is_agent_id(value: Any) -> bool:
    text = str(value or "").strip()
    return text.startswith("bc-") or text.startswith("bc_")


def extract_agent_id(payload: Any) -> str | None:
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return text if is_agent_id(text) else None
    if not isinstance(payload, dict):
        return None
    candidates = [payload.get("id")]
    agent = payload.get("agent")
    if isinstance(agent, dict):
        candidates.append(agent.get("id"))
    for candidate in candidates:
        if is_agent_id(candidate):
            return str(candidate).strip()
    return None


def remember_agent_id(agent_id: str | None) -> None:
    if not agent_id or not is_agent_id(agent_id):
        return
    with STATE_LOCK:
        state = load_state()
        pending = [str(item) for item in state.get("pending_archive") or [] if item]
        if agent_id not in pending:
            pending.append(agent_id)
        state["pending_archive"] = pending[-80:]
        save_state(state)


def forget_agent_ids(agent_ids: set[str]) -> None:
    if not agent_ids:
        return
    with STATE_LOCK:
        state = load_state()
        state["pending_archive"] = [
            str(item)
            for item in state.get("pending_archive") or []
            if item and str(item) not in agent_ids
        ]
        save_state(state)


def pending_archive_ids() -> set[str]:
    with STATE_LOCK:
        return {str(item) for item in load_state().get("pending_archive") or [] if item}


def record_archive(result: dict[str, Any]) -> None:
    with STATE_LOCK:
        state = load_state()
        state["last_archive"] = result
        save_state(state)


def cursor_agents_url(suffix: str = "") -> str:
    base = (env("CURSOR_API_URL", CURSOR_API_URL) or CURSOR_API_URL).rstrip("/")
    if not suffix:
        return base
    if suffix.startswith("?"):
        return base + suffix
    return f"{base}/{suffix.lstrip('/')}"


def cursor_api_request(method: str, suffix: str, payload: dict[str, Any] | None = None) -> tuple[bool, str]:
    key = bearer_token(env("CURSOR_API_KEY"))
    if not key:
        return False, "CURSOR_API_KEY is empty"
    extra_args = ["-u", f"{key}:"]
    errors: list[str] = []
    proxy = llm_proxy_url()
    for use_proxy in launch_attempts(bool(proxy)):
        ok, detail = curl_http(
            method,
            cursor_agents_url(suffix),
            [],
            use_proxy=use_proxy,
            extra_args=extra_args,
            payload=payload,
        )
        if ok:
            return True, detail
        errors.append(("proxy " if use_proxy else "direct ") + detail)
    return False, "; ".join(errors)


def list_cursor_agents() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cursor = ""
    for _ in range(20):
        query = "includeArchived=false&limit=100"
        if cursor:
            query += "&cursor=" + urllib.parse.quote(cursor)
        ok, body = cursor_api_request("GET", "?" + query)
        if not ok:
            raise RuntimeError(body)
        try:
            data = json.loads(body or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"agents list is not json: {redact_secret(body[:160])}") from exc
        if not isinstance(data, dict):
            raise RuntimeError("agents list is not an object")
        batch = data.get("items") or []
        items.extend(item for item in batch if isinstance(item, dict))
        cursor = str(data.get("nextCursor") or "")
        if not cursor:
            break
    return items


def archive_cursor_agent(agent_id: str) -> tuple[bool, str]:
    return cursor_api_request("POST", f"{agent_id}/archive")


def should_archive_agent(item: dict[str, Any], tracked: set[str]) -> bool:
    if str(item.get("status") or "").upper() != "IDLE":
        return False
    agent_id = str(item.get("id") or "").strip()
    if agent_id in tracked:
        return True
    return is_ritual_agent_name(str(item.get("name") or ""))


def sweep_finished_ritual_agents() -> dict[str, Any]:
    """Archive finished ritual chats so they leave the Agents sidebar.

    Only IDLE agents. ACTIVE morning/evening waits stay visible until they finish.
    Internal cursor-cloud MCP can list but cannot archive; this uses Cloud Agents API.
    """
    at = utc_now()
    if not archive_idle_enabled():
        result = {"ok": True, "skipped": "disabled", "archived": 0, "error": "", "at": at}
        record_archive(result)
        return result
    if not bearer_token(env("CURSOR_API_KEY")):
        result = {"ok": True, "skipped": "no_api_key", "archived": 0, "error": "", "at": at}
        record_archive(result)
        return result
    tracked = pending_archive_ids()
    items = list_cursor_agents()
    archived: list[str] = []
    errors: list[str] = []
    for item in items:
        if not should_archive_agent(item, tracked):
            continue
        agent_id = str(item.get("id") or "").strip()
        if not is_agent_id(agent_id):
            continue
        ok, detail = archive_cursor_agent(agent_id)
        if ok:
            archived.append(agent_id)
        else:
            errors.append(f"{agent_id}: {redact_secret(detail)}")
    forget_agent_ids(set(archived))
    result = {
        "ok": not errors,
        "skipped": "",
        "archived": len(archived),
        "ids": archived[:20],
        "error": "; ".join(errors)[:240],
        "at": at,
    }
    record_archive(result)
    if archived:
        print(f"archived {len(archived)} ritual cloud agents", flush=True)
    return result


def _safe_archive_sweep() -> None:
    try:
        sweep_finished_ritual_agents()
    except Exception as exc:  # noqa: BLE001 — Telegram polling must not die
        print(f"archive sweep failed: {redact_secret(str(exc))}", file=sys.stderr)
        try:
            record_archive(
                {
                    "ok": False,
                    "skipped": "",
                    "archived": 0,
                    "error": redact_secret(str(exc))[:240],
                    "at": utc_now(),
                }
            )
        except Exception as persist_exc:  # noqa: BLE001
            print(f"archive status persist failed: {persist_exc}", file=sys.stderr)


def kick_archive_sweep() -> None:
    threading.Thread(target=_safe_archive_sweep, name="cursor-archive-once", daemon=True).start()


def archive_loop() -> None:
    raw = env("CURSOR_ARCHIVE_INTERVAL_SEC", "120") or "120"
    try:
        interval = max(30, int(raw))
    except ValueError:
        interval = 120
    time.sleep(min(20, interval))
    while True:
        _safe_archive_sweep()
        time.sleep(interval)


def download_telegram_file(file_id: str) -> Path:
    info = tg("getFile", {"file_id": file_id}, timeout=30)
    if not info.get("ok"):
        raise RuntimeError(f"getFile failed: {info}")
    file_path = str((info.get("result") or {}).get("file_path") or "")
    if not file_path:
        raise RuntimeError("getFile returned no path")
    ext = Path(file_path).suffix or ".ogg"
    dest = Path(f"/tmp/pa-voice-{uuid.uuid4().hex}{ext}")
    url = f"{TELEGRAM_API}/file/bot{env('TELEGRAM_BOT_TOKEN')}/{file_path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=60) as resp:
        dest.write_bytes(resp.read())
    return dest


_LOCAL_WHISPER = None


def redact_secret(text: str) -> str:
    return re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "sk-[redacted]", text)


def transcribe_local(path: Path) -> str:
    global _LOCAL_WHISPER
    from faster_whisper import WhisperModel

    model_name = env("STT_LOCAL_MODEL", "base") or "base"
    if _LOCAL_WHISPER is None:
        _LOCAL_WHISPER = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _info = _LOCAL_WHISPER.transcribe(str(path), language="ru", beam_size=5)
    text = " ".join(segment.text.strip() for segment in segments).strip()
    if not text:
        raise RuntimeError("empty local transcript")
    return text


def transcribe_openai(path: Path) -> str:
    key = env("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is missing")
    base = env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = env("STT_OPENAI_MODEL", "whisper-1") or "whisper-1"
    cmd = [
        "curl",
        "-sS",
        "--max-time",
        "90",
        "-H",
        f"Authorization: Bearer {key}",
        "-F",
        f"file=@{path};type=audio/ogg",
        "-F",
        f"model={model}",
        "-F",
        "language=ru",
        f"{base}/audio/transcriptions",
    ]
    proxy = llm_proxy_url()
    if proxy:
        cmd[1:1] = ["--proxy", proxy]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=95, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("whisper timed out") from exc
    if proc.returncode != 0:
        err = redact_secret((proc.stderr or proc.stdout or "curl failed")[:300])
        raise RuntimeError(err)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"whisper returned non-json: {redact_secret(proc.stdout[:200])}") from exc
    text = str(data.get("text") or "").strip()
    if not text:
        raise RuntimeError(str(data.get("error") or "empty transcript"))
    return text


def transcribe_audio(path: Path) -> str:
    errors: list[str] = []
    try:
        return transcribe_local(path)
    except Exception as exc:  # noqa: BLE001 — try cloud Whisper next
        errors.append(f"local: {redact_secret(str(exc))}")
    try:
        return transcribe_openai(path)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"openai: {redact_secret(str(exc))}")
    raise RuntimeError("; ".join(errors))


def extract_user_text(update: dict[str, Any]) -> dict[str, Any] | None:
    msg = update.get("message") or update.get("edited_message")
    if not isinstance(msg, dict):
        return None
    chat = msg.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    if chat_id not in allowed_chat_ids():
        return None
    caption = str(msg.get("caption") or "").strip()
    message_id = msg.get("message_id")
    media = msg.get("voice") or msg.get("audio") or msg.get("video_note")
    if isinstance(media, dict) and media.get("file_id"):
        return {
            "chat_id": chat_id,
            "text": caption,
            "source": "voice",
            "file_id": str(media["file_id"]),
            "message_id": message_id,
        }
    if msg.get("text"):
        return {
            "chat_id": chat_id,
            "text": str(msg["text"]).strip(),
            "source": "text",
            "message_id": message_id,
        }
    if caption:
        return {"chat_id": chat_id, "text": caption, "source": "text", "message_id": message_id}
    return None


def enqueue_user_message(
    chat_id: str,
    text: str,
    source: str,
    update_id: int,
    message_id: Any = None,
) -> dict[str, Any]:
    with STATE_LOCK:
        state = load_state()
        state["offset"] = max(int(state.get("offset") or 0), update_id + 1)
        item = {
            "id": f"{update_id}",
            "chat_id": chat_id,
            "text": text,
            "source": source,
            "kind_hint": state.get("last_kind"),
            "received_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "acked": False,
            "tg_message_id": message_id,
        }
        inbox = unacked_inbox(state)
        inbox.append(item)
        state["inbox"] = inbox[-50:]
        save_state(state)
    return item


def process_telegram_update(update: dict[str, Any]) -> bool:
    """Handle one Telegram update. Returns True if a user message was queued."""
    update_id = int(update.get("update_id") or 0)
    extracted = extract_user_text(update)
    with STATE_LOCK:
        state = load_state()
        state["offset"] = update_id + 1
        save_state(state)
    if extracted is None:
        return False
    chat_id = extracted["chat_id"]
    text = str(extracted.get("text") or "").strip()
    source = str(extracted.get("source") or "text")
    message_id = extracted.get("message_id")
    notify_received(chat_id, message_id, source)
    if extracted.get("file_id"):
        audio_path: Path | None = None
        try:
            send_chat_action(chat_id, "record_voice")
        except Exception as exc:  # noqa: BLE001
            print(f"stt typing failed: {exc}", file=sys.stderr)
        try:
            audio_path = download_telegram_file(str(extracted["file_id"]))
            transcript = transcribe_audio(audio_path)
            if text:
                text = f"{transcript}\n{text}"
            else:
                text = transcript
            source = "voice"
        except Exception as exc:  # noqa: BLE001
            print(f"stt error: {redact_secret(str(exc))}", file=sys.stderr)
            send_telegram(
                "Не разобрал голосовое. Повтори или напиши текстом.",
                chat_id,
            )
            return False
        finally:
            if audio_path is not None:
                try:
                    audio_path.unlink(missing_ok=True)
                except OSError:
                    pass
    if not text:
        return False
    enqueue_user_message(chat_id, text, source, update_id, message_id=message_id)
    return True


def poll_telegram_once(timeout: int) -> tuple[bool, list[dict[str, Any]]]:
    with STATE_LOCK:
        offset = int(load_state().get("offset") or 0)
    data = tg(
        "getUpdates",
        {
            "offset": offset,
            "timeout": timeout,
            "allowed_updates": ["message", "edited_message"],
        },
        timeout=timeout + 10,
    )
    if not data.get("ok"):
        return False, []
    result = data.get("result") or []
    return True, result if isinstance(result, list) else []


def poll_loop() -> None:
    while True:
        try:
            ok, updates = poll_telegram_once(50)
            if not ok:
                time.sleep(2)
                maybe_launch_feedback()
                continue
            enqueued = False
            for update in updates:
                if process_telegram_update(update):
                    enqueued = True
            if enqueued:
                # Voices that arrived while this batch was in STT.
                extra_ok, extra = poll_telegram_once(TRAILING_UPDATES_TIMEOUT_SEC)
                if extra_ok:
                    for update in extra:
                        process_telegram_update(update)
            maybe_launch_feedback()
        except Exception as exc:  # noqa: BLE001
            print(f"poll error: {exc}", file=sys.stderr)
            time.sleep(3)


def read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or "0")
    raw = handler.rfile.read(length) if length else b"{}"
    if not raw:
        return {}
    data = json.loads(raw.decode())
    if not isinstance(data, dict):
        raise ValueError("JSON object required")
    return data


def write_json(handler: BaseHTTPRequestHandler, code: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
        if path == "/health":
            with STATE_LOCK:
                state = load_state()
            write_json(
                self,
                200,
                {
                    "ok": True,
                    "last_launch": state.get("last_launch"),
                    "last_archive": state.get("last_archive"),
                    "last_kind": state.get("last_kind"),
                    "inbox": len([x for x in state.get("inbox") or [] if not x.get("acked")]),
                },
            )
            return
        if path == "/inbox":
            if not bearer_ok(self.headers.get("Authorization")):
                write_json(self, 401, {"ok": False, "error": "unauthorized"})
                return
            with STATE_LOCK:
                inbox = [x for x in load_state().get("inbox") or [] if not x.get("acked")]
            note_inbox_read()
            write_json(self, 200, {"ok": True, "messages": inbox})
            return
        write_json(self, 404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
        if path not in {"/send", "/inbox/ack"}:
            write_json(self, 404, {"ok": False, "error": "not found"})
            return
        if not bearer_ok(self.headers.get("Authorization")):
            write_json(self, 401, {"ok": False, "error": "unauthorized"})
            return
        try:
            payload = read_json(self)
        except (ValueError, json.JSONDecodeError):
            write_json(self, 400, {"ok": False, "error": "invalid json"})
            return
        if path == "/send":
            text = str(payload.get("text") or "").strip()
            if not text:
                write_json(self, 400, {"ok": False, "error": "text required"})
                return
            kind = str(payload.get("kind") or "reply").strip() or "reply"
            purpose, route = resolve_send(kind, str(payload.get("purpose") or ""))
            about = payload.get("about_ids")
            if isinstance(about, list) and about:
                ids = [str(item).strip() for item in about if str(item).strip()]
            else:
                with STATE_LOCK:
                    ids = [
                        str(item.get("id"))
                        for item in unacked_inbox(load_state())
                        if item.get("id")
                    ]
            try:
                if route == "confirm":
                    result = deliver_confirm(text, payload.get("chat_id"), ids)
                else:
                    result = deliver_outgoing(text, payload.get("chat_id"))
            except Exception as exc:  # noqa: BLE001
                write_json(self, 502, {"ok": False, "error": str(exc)})
                return
            if kind in RITUAL_KINDS and result.get("ok") and not result.get("duplicate"):
                note_ritual_hold()
            if kind in RITUAL_KINDS:
                with STATE_LOCK:
                    state = load_state()
                    state["last_kind"] = kind
                    save_state(state)
            write_json(self, 200, result)
            return
        message_id = str(payload.get("id") or "")
        with STATE_LOCK:
            state = load_state()
            for item in state.get("inbox") or []:
                if str(item.get("id")) == message_id:
                    item["acked"] = True
            save_state(state)
        write_json(self, 200, {"ok": True})


def main() -> int:
    if not env("TELEGRAM_BOT_TOKEN"):
        print("TELEGRAM_BOT_TOKEN is required", file=sys.stderr)
        return 1
    if not env("RELAY_SECRET"):
        print("RELAY_SECRET is required", file=sys.stderr)
        return 1
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        print("faster_whisper is missing in this Python; voice will fail", file=sys.stderr)
        return 1
    bind = env("RELAY_BIND", "127.0.0.1")
    port = int(env("RELAY_PORT", "8787") or "8787")
    threading.Thread(target=poll_loop, name="tg-poll", daemon=True).start()
    threading.Thread(target=archive_loop, name="cursor-archive", daemon=True).start()
    server = ThreadingHTTPServer((bind, port), Handler)
    print(f"personal-assist telegram relay on {bind}:{port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
