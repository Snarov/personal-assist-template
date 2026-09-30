#!/usr/bin/env python3
"""Unit tests for Cursor launch helpers. No network."""

from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ["TELEGRAM_ALLOWED_CHAT_IDS"] = "424242"

import relay


class ProxyTests(unittest.TestCase):
    def test_host_port_user_pass_uses_socks5h(self) -> None:
        with mock.patch.dict(os.environ, {"HERMES_LLM_PROXY": "127.0.0.1:1080:user:p@ss"}, clear=False):
            os.environ["HERMES_LLM_PROXY"] = "127.0.0.1:1080:user:p@ss"
            os.environ.pop("RELAY_LLM_PROXY", None)
            url = relay.llm_proxy_url()
        self.assertIsNotNone(url)
        assert url is not None
        self.assertTrue(url.startswith("socks5h://"))
        self.assertIn("127.0.0.1:1080", url)
        self.assertIn("p%40ss", url)

    def test_socks5_scheme_upgraded_to_socks5h(self) -> None:
        os.environ["HERMES_LLM_PROXY"] = "socks5://u:p@127.0.0.1:1080"
        os.environ.pop("RELAY_LLM_PROXY", None)
        self.assertEqual(relay.llm_proxy_url(), "socks5h://u:p@127.0.0.1:1080")

    def test_socks5h_left_alone(self) -> None:
        os.environ["HERMES_LLM_PROXY"] = "socks5h://u:p@127.0.0.1:1080"
        os.environ.pop("RELAY_LLM_PROXY", None)
        self.assertEqual(relay.llm_proxy_url(), "socks5h://u:p@127.0.0.1:1080")


class BearerTests(unittest.TestCase):
    def test_strips_duplicate_bearer(self) -> None:
        self.assertEqual(relay.bearer_token("Bearer Bearer crsr_abc"), "crsr_abc")
        self.assertEqual(relay.bearer_token("crsr_abc"), "crsr_abc")


class LaunchTests(unittest.TestCase):
    def tearDown(self) -> None:
        for key in (
            "CURSOR_WEBHOOK_URL",
            "CURSOR_WEBHOOK_KEY",
            "CURSOR_API_KEY",
            "HERMES_LLM_PROXY",
            "RELAY_LLM_PROXY",
        ):
            os.environ.pop(key, None)

    def test_empty_config_fails(self) -> None:
        os.environ.pop("CURSOR_WEBHOOK_URL", None)
        os.environ.pop("CURSOR_API_KEY", None)
        with mock.patch.object(relay, "record_launch"):
            self.assertFalse(relay.forward_cursor({"text": "hi"}))

    def test_webhook_success_skips_api(self) -> None:
        os.environ["CURSOR_WEBHOOK_URL"] = "https://api2.cursor.sh/automations/webhook/x"
        os.environ["CURSOR_API_KEY"] = "should-not-be-used"
        with mock.patch.object(relay, "launch_via_webhook", return_value=(True, "")):
            with mock.patch.object(relay, "launch_via_api") as api:
                with mock.patch.object(relay, "record_launch"):
                    with mock.patch.object(relay, "kick_archive_sweep") as sweep:
                        self.assertTrue(relay.forward_cursor({"text": "hi"}))
                api.assert_not_called()
                sweep.assert_called_once()

    def test_ritual_kinds_are_only_morning_and_evening(self) -> None:
        self.assertEqual(relay.RITUAL_KINDS, {"morning", "evening"})
        self.assertNotIn("reply", relay.RITUAL_KINDS)

    def test_api_fallback_when_webhook_fails(self) -> None:
        os.environ["CURSOR_WEBHOOK_URL"] = "https://api2.cursor.sh/automations/webhook/x"
        os.environ["CURSOR_API_KEY"] = "k"
        with mock.patch.object(relay, "launch_via_webhook", return_value=(False, "HTTP 401")):
            with mock.patch.object(relay, "launch_via_api", return_value=(True, "")):
                with mock.patch.object(relay, "record_launch"):
                    with mock.patch.object(relay, "kick_archive_sweep") as sweep:
                        self.assertTrue(relay.forward_cursor({"text": "hi"}))
                    sweep.assert_called_once()


class ExtractTests(unittest.TestCase):
    def test_text_includes_message_id(self) -> None:
        got = relay.extract_user_text(
            {
                "message": {
                    "message_id": 77,
                    "chat": {"id": 424242},
                    "text": "сегодня ничего",
                }
            }
        )
        self.assertIsNotNone(got)
        assert got is not None
        self.assertEqual(got["text"], "сегодня ничего")
        self.assertEqual(got["source"], "text")
        self.assertEqual(got["message_id"], 77)

    def test_voice_includes_file_and_message_id(self) -> None:
        got = relay.extract_user_text(
            {
                "message": {
                    "message_id": 88,
                    "chat": {"id": 424242},
                    "voice": {"file_id": "AwAAA"},
                }
            }
        )
        self.assertIsNotNone(got)
        assert got is not None
        self.assertEqual(got["source"], "voice")
        self.assertEqual(got["file_id"], "AwAAA")
        self.assertEqual(got["message_id"], 88)

    def test_foreign_chat_ignored(self) -> None:
        self.assertIsNone(
            relay.extract_user_text(
                {"message": {"message_id": 1, "chat": {"id": 1}, "text": "hi"}}
            )
        )


class AckTests(unittest.TestCase):
    def test_notify_received_reacts_types_and_replies(self) -> None:
        with mock.patch.object(relay, "set_message_reaction") as react:
            with mock.patch.object(relay, "send_chat_action") as action:
                with mock.patch.object(relay, "send_telegram") as send:
                    relay.notify_received("424242", 42, "voice")
        react.assert_called_once_with("424242", 42, "👀")
        action.assert_called_once_with("424242", "record_voice")
        send.assert_called_once_with("Принял.", "424242", reply_to_message_id=42)

    def test_notify_received_swallows_errors(self) -> None:
        with mock.patch.object(relay, "set_message_reaction", side_effect=RuntimeError("nope")):
            with mock.patch.object(relay, "send_chat_action", side_effect=RuntimeError("nope")):
                with mock.patch.object(relay, "send_telegram", side_effect=RuntimeError("nope")):
                    relay.notify_received("424242", 1, "text")

    def test_notify_launched_changes_reaction(self) -> None:
        with mock.patch.object(relay, "set_message_reaction") as react:
            relay.notify_launched("424242", 42)
        react.assert_called_once_with("424242", 42, "⚡")

    def test_send_telegram_reply_to(self) -> None:
        with mock.patch.object(relay, "tg", return_value={"ok": True, "result": {}}) as tg_call:
            relay.send_telegram("Принял.", "424242", reply_to_message_id=9)
        payload = tg_call.call_args[0][1]
        self.assertEqual(payload["reply_to_message_id"], 9)
        self.assertTrue(payload["allow_sending_without_reply"])


class CoalesceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.state_file = Path(self.tmp.name) / "state.json"
        os.environ["RELAY_STATE_PATH"] = str(self.state_file)
        os.environ["RELAY_LAUNCH_COOLDOWN_SEC"] = "360"

    def tearDown(self) -> None:
        self.tmp.cleanup()
        os.environ.pop("RELAY_STATE_PATH", None)
        os.environ.pop("RELAY_LAUNCH_COOLDOWN_SEC", None)

    def _inbox_item(self, update_id: str, text: str, acked: bool = False) -> dict:
        return {
            "id": update_id,
            "chat_id": "424242",
            "text": text,
            "source": "voice",
            "kind_hint": "morning",
            "received_at": "2026-09-21T06:06:15Z",
            "acked": acked,
            "tg_message_id": int(update_id[-2:]),
        }

    def test_enqueue_does_not_launch(self) -> None:
        with mock.patch.object(relay, "forward_cursor") as launch:
            item = relay.enqueue_user_message(
                "424242",
                "сегодня ничего",
                "voice",
                151050078,
                message_id=42,
            )
        launch.assert_not_called()
        self.assertEqual(item["id"], "151050078")
        self.assertEqual(item["tg_message_id"], 42)
        self.assertFalse(item["acked"])
        state = relay.load_state()
        self.assertEqual(len(state["inbox"]), 1)

    def test_maybe_launch_empty_inbox(self) -> None:
        relay.save_state({"offset": 0, "last_kind": None, "inbox": []})
        with mock.patch.object(relay, "forward_cursor") as launch:
            self.assertFalse(relay.maybe_launch_feedback())
        launch.assert_not_called()

    def test_maybe_launch_once_for_burst(self) -> None:
        relay.save_state(
            {
                "offset": 3,
                "last_kind": "morning",
                "inbox": [
                    self._inbox_item("151050078", "сегодня ничего"),
                    self._inbox_item("151050079", "оценка 5"),
                    self._inbox_item("151050080", "кофе 2"),
                ],
            }
        )
        with mock.patch.object(relay, "forward_cursor", return_value=True) as launch:
            with mock.patch.object(relay, "notify_launched") as notify:
                self.assertTrue(relay.maybe_launch_feedback())
        launch.assert_called_once()
        payload = launch.call_args[0][0]
        self.assertEqual(payload["inbox_count"], 3)
        self.assertEqual(payload["text"], "кофе 2")
        self.assertEqual(notify.call_count, 3)

    def test_maybe_launch_skips_during_cooldown(self) -> None:
        relay.save_state(
            {
                "offset": 1,
                "last_kind": "morning",
                "inbox": [self._inbox_item("151050079", "оценка 5")],
                "last_launch": {"ok": True, "at": "2099-01-01T00:00:00Z", "error": ""},
            }
        )
        with mock.patch.object(relay, "forward_cursor") as launch:
            self.assertFalse(relay.maybe_launch_feedback())
        launch.assert_not_called()

    def test_maybe_launch_after_cooldown(self) -> None:
        relay.save_state(
            {
                "offset": 1,
                "last_kind": "morning",
                "inbox": [self._inbox_item("151050079", "оценка 5")],
                "last_launch": {"ok": True, "at": "2020-01-01T00:00:00Z", "error": ""},
            }
        )
        with mock.patch.object(relay, "forward_cursor", return_value=True) as launch:
            with mock.patch.object(relay, "notify_launched"):
                self.assertTrue(relay.maybe_launch_feedback())
        launch.assert_called_once()

    def test_failed_launch_does_not_block_retry(self) -> None:
        relay.save_state(
            {
                "offset": 1,
                "last_kind": "morning",
                "inbox": [self._inbox_item("151050079", "оценка 5")],
                "last_launch": {
                    "ok": False,
                    "at": "2099-01-01T00:00:00Z",
                    "error": "HTTP 401",
                },
            }
        )
        with mock.patch.object(relay, "forward_cursor", return_value=True) as launch:
            with mock.patch.object(relay, "notify_launched"):
                self.assertTrue(relay.maybe_launch_feedback())
        launch.assert_called_once()

    def test_last_ok_launch_age_none_when_failed(self) -> None:
        age = relay.last_ok_launch_age_sec(
            {"last_launch": {"ok": False, "at": "2026-09-21T06:06:15Z"}}
        )
        self.assertIsNone(age)

    def test_maybe_launch_skips_while_ritual_is_draining(self) -> None:
        now = time.time()
        relay.save_state(
            {
                "offset": 1,
                "last_kind": "morning",
                "inbox": [self._inbox_item("151050097", "фокус задача")],
                "ritual_hold_until": now + 3600,
                "last_inbox_read_at": now,
            }
        )
        with mock.patch.object(relay, "forward_cursor") as launch:
            self.assertFalse(relay.maybe_launch_feedback())
        launch.assert_not_called()

    def test_maybe_launch_when_ritual_stopped_reading(self) -> None:
        now = time.time()
        relay.save_state(
            {
                "offset": 1,
                "last_kind": "morning",
                "inbox": [self._inbox_item("151050097", "фокус задача")],
                "ritual_hold_until": now + 3600,
                "last_inbox_read_at": now - relay.DEFAULT_INBOX_FRESH_SEC - 5,
            }
        )
        with mock.patch.object(relay, "forward_cursor", return_value=True) as launch:
            with mock.patch.object(relay, "notify_launched"):
                self.assertTrue(relay.maybe_launch_feedback())
        launch.assert_called_once()


class RitualNameTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("CURSOR_ARCHIVE_NAME_SUBSTR", None)

    def test_matches_automation_titles(self) -> None:
        self.assertTrue(relay.is_ritual_agent_name("Personal assist telegram feedback"))
        self.assertTrue(relay.is_ritual_agent_name("Personal assist morning check-in"))
        self.assertTrue(relay.is_ritual_agent_name("Personal assist evening review"))
        self.assertTrue(relay.is_ritual_agent_name("Telegram feedback"))

    def test_ignores_manual_chats(self) -> None:
        self.assertFalse(relay.is_ritual_agent_name("Автоматическая архивация чатов агентов"))
        self.assertFalse(relay.is_ritual_agent_name("Fix Notion layout"))
        self.assertFalse(relay.is_ritual_agent_name(""))


class ExtractAgentIdTests(unittest.TestCase):
    def test_v1_create_envelope(self) -> None:
        self.assertEqual(
            relay.extract_agent_id('{"agent":{"id":"bc-00000000-0000-0000-0000-000000000001"}}'),
            "bc-00000000-0000-0000-0000-000000000001",
        )

    def test_top_level_id(self) -> None:
        self.assertEqual(relay.extract_agent_id({"id": "bc_abc123"}), "bc_abc123")

    def test_non_agent_json_ignored(self) -> None:
        self.assertIsNone(relay.extract_agent_id('{"ok":true}'))
        self.assertIsNone(relay.extract_agent_id("not-json"))


class ArchiveSweepTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        state = Path(self._tmp.name) / "state.json"
        self._env = mock.patch.dict(
            os.environ,
            {
                "CURSOR_API_KEY": "k",
                "CURSOR_ARCHIVE_IDLE": "1",
                "RELAY_STATE_PATH": str(state),
            },
            clear=False,
        )
        self._env.start()

    def tearDown(self) -> None:
        self._env.stop()
        os.environ.pop("CURSOR_ARCHIVE_IDLE", None)
        os.environ.pop("CURSOR_API_KEY", None)
        self._tmp.cleanup()

    def test_skip_without_key(self) -> None:
        os.environ.pop("CURSOR_API_KEY", None)
        with mock.patch.object(relay, "list_cursor_agents") as listed:
            result = relay.sweep_finished_ritual_agents()
        listed.assert_not_called()
        self.assertEqual(result["skipped"], "no_api_key")
        self.assertEqual(result["archived"], 0)

    def test_skip_when_disabled(self) -> None:
        os.environ["CURSOR_ARCHIVE_IDLE"] = "0"
        with mock.patch.object(relay, "list_cursor_agents") as listed:
            result = relay.sweep_finished_ritual_agents()
        listed.assert_not_called()
        self.assertEqual(result["skipped"], "disabled")

    def test_archives_idle_ritual_only(self) -> None:
        items = [
            {"id": "bc-idle-ritual", "name": "Personal assist telegram feedback", "status": "IDLE"},
            {"id": "bc-active-ritual", "name": "Personal assist morning check-in", "status": "ACTIVE"},
            {"id": "bc-idle-manual", "name": "Rewrite catalog", "status": "IDLE"},
        ]
        archived: list[str] = []

        def fake_archive(agent_id: str) -> tuple[bool, str]:
            archived.append(agent_id)
            return True, "{}"

        with mock.patch.object(relay, "list_cursor_agents", return_value=items):
            with mock.patch.object(relay, "archive_cursor_agent", side_effect=fake_archive):
                result = relay.sweep_finished_ritual_agents()
        self.assertEqual(archived, ["bc-idle-ritual"])
        self.assertEqual(result["archived"], 1)
        self.assertTrue(result["ok"])

    def test_archives_tracked_id_even_if_name_unknown(self) -> None:
        relay.remember_agent_id("bc-tracked")
        items = [{"id": "bc-tracked", "name": "Custom webhook title", "status": "IDLE"}]
        with mock.patch.object(relay, "list_cursor_agents", return_value=items):
            with mock.patch.object(relay, "archive_cursor_agent", return_value=(True, "{}")) as archive:
                result = relay.sweep_finished_ritual_agents()
        archive.assert_called_once_with("bc-tracked")
        self.assertEqual(result["archived"], 1)
        self.assertNotIn("bc-tracked", relay.pending_archive_ids())


class OutgoingDedupeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["RELAY_STATE_PATH"] = str(Path(self.tmp.name) / "state.json")
        os.environ.pop("RELAY_SEND_DEDUPE_SEC", None)
        relay._outgoing_inflight.clear()
        relay.save_state({"offset": 0, "last_kind": None, "inbox": []})

    def tearDown(self) -> None:
        relay._outgoing_inflight.clear()
        self.tmp.cleanup()
        os.environ.pop("RELAY_STATE_PATH", None)
        os.environ.pop("RELAY_SEND_DEDUPE_SEC", None)

    def test_identical_retry_does_not_send_again(self) -> None:
        sent = {"ok": True, "chat_id": "424242", "messages": 1}
        with mock.patch.object(relay, "send_telegram", return_value=sent) as send:
            first = relay.deliver_outgoing("Дневник утро 23.09", "424242")
            second = relay.deliver_outgoing("  Дневник утро 23.09  ", "424242")
        self.assertEqual(send.call_count, 1)
        self.assertFalse(first.get("duplicate"))
        self.assertTrue(second.get("duplicate"))
        self.assertEqual(second["messages"], 1)

    def test_different_text_still_sends(self) -> None:
        sent = {"ok": True, "chat_id": "424242", "messages": 1}
        with mock.patch.object(relay, "send_telegram", return_value=sent) as send:
            relay.deliver_outgoing("Утро.", "424242")
            relay.deliver_outgoing("Дневник утро 23.09", "424242")
        self.assertEqual(send.call_count, 2)

    def test_failed_send_can_be_retried(self) -> None:
        with mock.patch.object(
            relay,
            "send_telegram",
            side_effect=[RuntimeError("timeout"), {"ok": True, "chat_id": "424242", "messages": 1}],
        ) as send:
            with self.assertRaises(RuntimeError):
                relay.deliver_outgoing("Дневник утро 23.09", "424242")
            again = relay.deliver_outgoing("Дневник утро 23.09", "424242")
        self.assertEqual(send.call_count, 2)
        self.assertFalse(again.get("duplicate"))

    def test_same_text_sends_again_after_the_window(self) -> None:
        clock = {"now": 1_000_000.0}

        def fake_time() -> float:
            return clock["now"]

        sent = {"ok": True, "chat_id": "424242", "messages": 1}
        with mock.patch.object(relay.time, "time", side_effect=fake_time):
            with mock.patch.object(relay, "send_telegram", return_value=sent) as send:
                relay.deliver_outgoing("Дневник утро 23.09", "424242")
                clock["now"] += relay.DEFAULT_SEND_DEDUPE_SEC + 1
                again = relay.deliver_outgoing("Дневник утро 23.09", "424242")
        self.assertEqual(send.call_count, 2)
        self.assertFalse(again.get("duplicate"))

    def test_inflight_retry_shares_one_telegram_call(self) -> None:
        started = threading.Event()
        release = threading.Event()

        def slow(text: str, chat_id: str | None = None, reply_to_message_id: int | None = None) -> dict:
            started.set()
            self.assertTrue(release.wait(2))
            return {"ok": True, "chat_id": chat_id or "424242", "messages": 1}

        results: list[dict] = []
        errors: list[BaseException] = []

        def call() -> None:
            try:
                results.append(relay.deliver_outgoing("Дневник утро 23.09", "424242"))
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        with mock.patch.object(relay, "send_telegram", side_effect=slow) as send:
            leader = threading.Thread(target=call)
            follower = threading.Thread(target=call)
            leader.start()
            self.assertTrue(started.wait(2))
            follower.start()
            follower.join(0.2)
            release.set()
            leader.join(3)
            follower.join(3)
        self.assertEqual(errors, [])
        self.assertEqual(send.call_count, 1)
        self.assertEqual(len(results), 2)
        self.assertEqual(sum(1 for item in results if item.get("duplicate")), 1)


class ConfirmSlotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["RELAY_STATE_PATH"] = str(Path(self.tmp.name) / "state.json")
        os.environ.pop("RELAY_SEND_DEDUPE_SEC", None)
        relay._outgoing_inflight.clear()
        relay._confirm_inflight.clear()
        relay.save_state({"offset": 0, "last_kind": None, "inbox": []})

    def tearDown(self) -> None:
        relay._outgoing_inflight.clear()
        relay._confirm_inflight.clear()
        self.tmp.cleanup()
        os.environ.pop("RELAY_STATE_PATH", None)

    def test_reworded_confirm_for_same_inbox_is_not_sent(self) -> None:
        sent = {"ok": True, "chat_id": "424242", "messages": 1}
        with mock.patch.object(relay, "send_telegram", return_value=sent) as send:
            first = relay.deliver_confirm("Фокус: задача А и задача Б.", "424242", ["151050097"])
            second = relay.deliver_confirm(
                "Фокус на сегодня:\n- Задача А\n- Задача Б",
                "424242",
                ["151050097"],
            )
        self.assertEqual(send.call_count, 1)
        self.assertFalse(first.get("duplicate"))
        self.assertTrue(second.get("duplicate"))

    def test_confirm_after_ack_is_not_sent_again(self) -> None:
        sent = {"ok": True, "chat_id": "424242", "messages": 1}
        with mock.patch.object(relay, "send_telegram", return_value=sent) as send:
            relay.deliver_confirm("Фокус: задача А.", "424242", ["151050097"])
            again = relay.deliver_confirm("Фокус:\n• задача А\n• задача Б", "424242", [])
        self.assertEqual(send.call_count, 1)
        self.assertTrue(again.get("duplicate"))

    def test_new_inbox_id_still_confirms(self) -> None:
        sent = {"ok": True, "chat_id": "424242", "messages": 1}
        with mock.patch.object(relay, "send_telegram", return_value=sent) as send:
            relay.deliver_confirm("Фокус: задача А.", "424242", ["151050097"])
            again = relay.deliver_confirm("Дописал: дневник потом.", "424242", ["151050098"])
        self.assertEqual(send.call_count, 2)
        self.assertFalse(again.get("duplicate"))

    def test_survey_text_is_not_a_confirm_slot(self) -> None:
        sent = {"ok": True, "chat_id": "424242", "messages": 1}
        with mock.patch.object(relay, "send_telegram", return_value=sent) as send:
            relay.deliver_confirm("Фокус: задача А.", "424242", ["151050097"])
            diary = relay.deliver_outgoing("Дневник утро 24.09", "424242")
        self.assertEqual(send.call_count, 2)
        self.assertFalse(diary.get("duplicate"))


class ResolveSendTests(unittest.TestCase):
    def test_reply_without_purpose_is_a_confirm(self) -> None:
        purpose, route = relay.resolve_send("reply", "")
        self.assertEqual((purpose, route), ("confirm", "confirm"))

    def test_survey_stays_outgoing(self) -> None:
        purpose, route = relay.resolve_send("reply", "survey")
        self.assertEqual((purpose, route), ("survey", "outgoing"))

    def test_pace_alert_does_not_take_the_confirm_slot(self) -> None:
        self.assertEqual(relay.resolve_send("pace", "alert"), ("alert", "outgoing"))
        self.assertEqual(relay.resolve_send("pace", ""), ("alert", "outgoing"))
        self.assertEqual(relay.resolve_send("reply", "alert"), ("alert", "outgoing"))

    def test_morning_is_not_rewritten_into_a_confirm(self) -> None:
        purpose, route = relay.resolve_send("morning", "")
        self.assertEqual((purpose, route), ("", "outgoing"))


if __name__ == "__main__":
    unittest.main()
