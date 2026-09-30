# Telegram feedback (webhook automation)

Automation id: `catalog.json` → `telegram.feedbackAutomationId`. Trigger: **Webhook**. Repository: `catalog.json` → `github.repo`, environment **Personal Assist**.

The relay acks the owner immediately (👀 + «Принял.»), then POSTs here so a new cloud run can write Notion. If this webhook URL or auth is missing on the host, the relay falls back to `CURSOR_API_KEY` (`POST https://api.cursor.com/v1/agents`). If both fail, the bot says the assistant did not start and the reply stays in `/inbox`.

The same API key also archives finished ritual agents (`POST /v1/agents/{id}/archive`) so morning / evening / telegram-feedback chats leave the Agents sidebar. The in-agent `cursor-cloud` tools can list runs but cannot archive them. Only `IDLE` chats matching those titles are archived; a still-running 90-minute wait is left alone.

Webhook URL and auth header live in `relay.env` on the host from `catalog.json` → `deploy`:

```
CURSOR_WEBHOOK_URL=https://api2.cursor.sh/automations/webhook/<id>
CURSOR_WEBHOOK_KEY=crsr_...
```

After changing `relay.py`: `./telegram-relay/deploy.sh`. Egress: `catalog.json` → `deploy.egressNote`.

## Prompt

```text
Follow the telegram-feedback skill. If the text has ordinary work outside focus tasks, routine time, a distraction rating, or «рутины не было», also follow routine-log. If the text reports study, study minutes, what he learned, where it applies, or «не учился», also follow study-log: write study/entries and a row in the Notion database «Учёба», linked to the goal, project, and task he named. Do not copy that clause into a task comment or a free note. If the text has diary answers, an answer to the awaiting survey, or a journal-profile change, also follow life-journal. If a clause is clearly not task tracking, not the health diary, not study, and not a note about how the day went — an idea, an experience, a view, anything of that kind — also follow free-notes and save it under notes/entries. Do not copy that clause into a task comment or into journal notes. If a clause is an expense, income, transfer, debt, or account balance, also follow the econumo skill and write it in Econumo. Do not copy that clause into Notion, the diary, routine, or notes. Confirm the account, amount, and category in the same reply.

The webhook JSON is the owner's Telegram reply (fields: text, input, kind_hint, chat_id, message_id, received_at, inbox_count). `git fetch origin master` before reading journal/survey.json. GET /inbox and handle every unacked message as one burst — voice answers often arrive as several messages. Notion write if needed. Write routine facts to routine/entries, never Notion or journal. Ritual and routine confirmation via POST /send with kind=reply and purpose=confirm. One confirm per inbox burst: a reworded second confirm returns duplicate:true, do not send it again. A diary request is one separate /send with purpose=survey from journal/survey-script.json for the current wave (morning / evening / catch-up) containing that wave's open items. Follow-up only the items from the list already sent for that date (`asked` / `survey.missing`), never a rebuilt requiredOrder. Today's morning may be a second /send while yesterday is still awaiting; do not move the awaiting pointer off yesterday. Never send one message per item; never use «эфф». If survey.json on master is already awaiting for that date/slot, do not send the list again. Wait at least 90 seconds for a diary /send. A timeout, an empty body, or duplicate:true means that text is already in the chat — do not send it again and do not reword it. GET /inbox again before any diary send. Then POST /inbox/ack. After the first handle, wait up to 8 minutes (feedback-inbox, every 60s) for trailing voices.

The relay already sent «Принял.» — your /send is the result, not a second ack.

Do not invent minutes, routine work, project names, ratings, or free notes. Do not map routine ratings to diary scores. Do not mark Done unless he said the task is finished. Leftover task notes (not minutes / progress / result) go to a page-level Notion comment on the matched task. A thought that is not about a matched task, not a diary item, and not how the day went goes to notes/entries, not to Notion. When creating a task, set Родительская задача only when the new card is a smaller part of a bigger task already on the board. A time sequence («потом», «после исследования», the next month) is not a parent. A finished research card is not the parent of the work that follows it. Use only notion-personal.
```
