---
name: morning-checkin
description: Sends the morning Telegram check-in at catalog.json → telegram.morning. Monday–Saturday: focus pick from Notion, a short Пора nudge for task windows, plus the diary morning wave. Sunday: diary morning wave only.
---

# Morning check-in

Every day at `catalog.json` → `telegram.morning`, in `catalog.json` → `timezone`. Monday–Saturday: Notion brief + focus pick, then the diary morning wave. Sunday: diary wave only — no Notion, no `ritual/`, no focus question. The owner answers later through the relay.

## Tools

- Notion only through `notion-personal`. Stop if that server is missing or bound to a work workspace.
- Telegram only through the Personal Assist relay in `catalog.json` (`telegram.relayUrl`). `POST /send` with `Authorization: Bearer $TELEGRAM_RELAY_SECRET` and `{"text":"...","kind":"morning"}`.
- Never write a chat in `catalog.json` → `telegram.forbiddenChats`, or any chat other than `telegram.allowedChatId`.

## Notion sources

Read `catalog.json`. Query Цели, Проекты, Задачи, «Фокус» (`planningPageUrl` / `planningDataSourceUrl`, `Уровень=День`, today's `Период`), and Идеи (`notion.ideasDataSourceUrl`). The day board is titled «Фокус».

Goals are only the names in `catalog.json` → `board.goals`.
Projects hang under them: `catalog.json` → `board.projects`. A project with `parent` is a child of that project; a task belongs to the nearest project only. Do not brief a project in `board.paused` or any of its tasks; `until` is how long that pause stands. Household work toward a goal is the project whose `role` is `household`. A single deliverable is a task, not a project — see `.cursor/rules/notion-workspace-hygiene.mdc`.

Идеи is a separate database, not projects and not tasks. It holds things that might become projects and that we review against the goals, plus ways of working (behavior, development, lifestyle, work style). A new row is `Статус=Новая` until he takes it as the day's focus or a real discussion of it starts; then it is `Смотрим`. Do not create a project or task from an idea unless he says it became one.

## Journal

Read `.cursor/rules/ritual-memory.mdc` and `ritual/` for the last 7 Mon–Sat days (journal starts at `catalog.json` → `ritual.journalStart`). Do not invent misses before the start date.

Reconcile stale slots before the brief. A day had a focus only when утро is `answered` and `Фокус` names tasks. «сегодня ничего», «отдыхаем», «отдыхаю», and `Фокус: —` are no focus.

- Stale `sent` morning → `missed`, add it to `## Сейчас пропущено`. An unanswered morning is not a day off.
- Stale `sent` evening on a focus day → `missed`, add it. That is the miss to name.
- Stale `sent` evening on a no-focus day → `skipped` (выходной). Do not add it. If it is already `missed` and listed, close it the same way and remove the line. Do not mention it. Do not ask for a recap.

Day file `ritual/YYYY-MM-DD.md`:

```markdown
# YYYY-MM-DD

## Утро
- Статус: sent | answered | skipped | missed
- Отправлено: …
- Ответ: —
- Фокус: —
- Пора: —

## Вечер
- Статус: …
- Отправлено: —
- Ответ: —
- Итог: —
- Мешало: —
```

After `/send`, set today's утро to `sent`, write `Пора:` with the lines actually sent (or `—`, or `не считал` when the task read failed), update the miss list, commit **only** `ritual/` + the rule, then land that commit on `master` (see `.cursor/rules/ritual-memory.mdc` → Git). Do not wait for «ок». The `Пора` line is not a miss.

## Sunday

If today is Sunday (`catalog.json` → `timezone`): `git fetch origin master`, then `GET /inbox` first (handle via `telegram-feedback`). Do not query or write Notion. Do not write `ritual/`. Do not ask focus. Follow `life-journal` only for the diary (yesterday catch-up if that day is open, then today's morning wave if that queue is open). A thought that is not the diary still follows `free-notes`. If a given date/slot is already `awaiting` on master, do not send a second copy of that list. Then wait up to 90 minutes (`morning-inbox`) for the diary reply. Do not skip the wait. Stop.

## Flow

1. `git fetch origin master`. Ritual files and `journal/survey.json` live there; the snapshot may be an hour behind.
2. Reconcile the journal and miss list first. Mon–Sat only; skip this on Sunday.
3. `GET /inbox`. If there are unacked messages, follow `telegram-feedback` for them **before** today's brief. The relay queues replies when the cloud agent fails to start.
4. Find or create today's «Фокус» row: title `YYYY-MM-DD`, `Уровень=День`, `Период=today`, `Статус=Active`.
5. Collect tails **before** clearing `Фокус сегодня`. Rules in **Tails** below.
6. Clear stale `Фокус сегодня` on tasks that are not linked to today's cycle, unless the owner already confirmed them today. Clearing the checkbox does not change `Статус`.
7. Build **Пора** from `.cursor/rules/task-nudges.mdc`. Query open tasks once; the brief below uses that same list. Walk the rows; do not paste the board into the nudge. A future window stays silent: if the window starts after today (`catalog.json` → `timezone`), do not name the task, including on the last day of the current month. An empty `Срок` is not a deadline and is not `срок закрывается`. A `старт` line says the planned period has begun and offers the task for today or the nearest plans; it does not say the deadline is ending. Do not repeat a journal phase the fresh calculation does not still give. Do not write `Статус`, `Горизонт`, `Срок`, `Приоритет`, or `Фокус сегодня` for a nudge. The block does not pick focus and does not close the morning. On that same read, before the brief, apply `.cursor/rules/task-relations.mdc` → **Родитель в работе**. That lift is not a nudge: an ancestor that is `Not started`, `Запланировано`, or empty becomes `In progress` when a child already is. Do not reopen `Done` or `Archived`. If a card was lifted, run `task-trees` before the send and add one short clause naming that parent.
8. Build a short brief from live Notion data, grouped **parent → children**:
   - Goals that are In progress, higher `Приоритет` first (`Максимальный`, then `Высокий`, then `Средний`, then `Низкий`, empty last). When the priority is set, put that word on the goal line. Do not invent one.
   - Their projects whose `Статус` is `In progress`, `Planning`, or `Backlog`. Skip `Paused`, `Done`, and `Cancelled`, including every project in `board.paused`.
   - Open tasks (`Not started` / `In progress`) of those projects only, `Максимальный` first, then `Высокий`, `Средний`, `Низкий`, empty last. Do not list or propose a task whose project is `Paused`, `Done`, or `Cancelled`.
   - Goals with an empty `Приоритет` whose `Статус` is not `Achieved` or `Dropped`: one line in the same message, naming each, asking максимальный, высокий, средний, or низкий. Do not write a priority in this job. The line does not close the morning and is not a ritual miss. Skip the line when none are empty. Full rule: `.cursor/rules/priorities.mdc`.
9. Ideas due for a decision: `Статус` is `Новая` or `Смотрим`, and `Следующий просмотр` is today or earlier (`catalog.json` → `timezone`). Skip an empty date. Skip `Отложена`, `Стала проектом`, `Стала задачей`, and `Отвергнута`. Naming the line does not start consideration and does not close the idea. Do not change the date or the status in this job. Do not turn the row into a task or a project here. If he answers during `morning-inbox`, `telegram-feedback` → **Idea decision** applies it, including the move `Новая` → `Смотрим` when he takes it as today's focus or a real discussion of it starts.
10. If today's cycle already has 1–2 focus tasks, say they are already set and ask whether to keep or replace them. Two tasks: name them in `Порядок фокуса` order («сначала …, потом …», or «одинаково» when that text says so). If two are linked and `Порядок фокуса` is empty, do not invent an order; ask which is first.
11. If no focus yet, ask him to name 1–2 tasks (or «сегодня ничего»). When the tail list is not empty, ask him to continue a tail on the same card or pick something else. When he might name two, ask which is first. Do not pick the order.
12. If the miss list is not empty, add **one** line: name the open slots, ask for a recap or «пропустил». Then today's brief. Do not invent yesterday's work. A no-focus evening that went unanswered is not on that list and gets no line.
13. Follow `study-log`: on Monday–Friday add its one-line reminder to that same ritual message. The line names today's due minutes (30 plus any carry). It is not a question and does not write a file. Saturday and Sunday omit the line. Sunday omits the rest of the ritual too.
14. Send **one** ritual Telegram message. Russian. No IDs, no ISO period keys, no lecture, **no diary scores**, no Notion/API jargon («предок», ancestor, cycle, «журнал в репо»). He may answer by voice.
15. Then follow `life-journal`. Diary `/send`s (`kind=reply`): if yesterday is not survey-done, send that catch-up (skip if it is already `awaiting`). Then, if today's morning queue is still open, send today's **morning wave** (the expanded `morningOrder`: core lines plus `profile.waves`) as a **separate** message. The meal time and the computer time are recorded so later statistics can relate a late meal and late computer work to that night's sleep quality. Do not add a line for vitamins, cigarettes, nootropics, or other ordinary substances. Do not send one message per item. Do not wait until evening to ask today's sleep, last meal, computer time, morning energy, or morning mood. Do not put yesterday and today in the same questionnaire. Do not move `survey.date` / `slot` / `missing` off yesterday when sending today. If `survey.json` on master is already `awaiting` for that exact date/slot, do not send a second copy of that list. Wait at least 90 seconds for each diary `/send`. A timeout, an empty response, or `duplicate: true` means that text already went out — do not POST it again and do not reword it.
16. After the `/send`s, do not exit immediately. Subscribe a timer every 2 minutes for up to 90 minutes named `morning-inbox`. **Do not skip this wait.** Each fire: `GET /inbox`; if unacked, follow `telegram-feedback` (it will write ritual and/or the diary, `study-log` when the reply reports study, and `free-notes` when the reply contains a thought that is not task tracking, the health diary, study, or how the day went). Keep polling: while this wait is reading `/inbox`, the relay does not start a second feedback agent for the same reply. Send the ritual confirm once (`purpose=confirm`). Diary lists use `purpose=survey`. If the diary reply is incomplete, send one follow-up containing all missing items of **that wave**. If none, end the turn and wait.

## After he answers

If the reply arrives while this session is still waiting on `morning-inbox`, handle it here via `telegram-feedback` (and `life-journal` for the survey, `free-notes` for a thought that is not a task, a diary item, or how the day went). Otherwise the telegram-feedback run (webhook / API / next ritual drain) writes Notion (focus properties + leftover task comments), saves a free note when the reply has one, and continues the survey.

## Hard rules

- Do not invent focus, progress, minutes, next steps, goal `Приоритет`, day-focus order, or what happened on a missed slot. **Пора** suggests tasks; it does not choose focus. Ignoring it does not change the card and is not a miss.
- Do not offer a `Paused`, `Done`, or `Cancelled` project, or any of its tasks, as focus or in the brief. Projects in `catalog.json` → `board.paused` stay paused until their `until`. Household work toward a goal is the project in `board.projects` whose `role` is `household`.
- Do not create tasks unless he asked to add one by name. A tail continues on the same card. If this job must create one, follow `create-task`. If project, parent, horizon, or priority is still open, ask once and do not create the row in this send. A study topic or «задача по учёбе» is not that row: `study-log` appends it as a flat card in «Учёба» and does not ask those four fields.
- Do not create a project in this job, including from «создай проект» when he did not name the goal. A sketch is an idea, not a Проекты row. Do not create a project or task from an idea in this job. Do not move `Следующий просмотр` until he has looked at it and named a date, a task, or a rejection. That write is `telegram-feedback` → **Idea decision**, not the morning send.
- Do not mark Done or blocked.
- Do not change `Горизонт` when carrying a tail forward.
- Keep the **ritual** message short enough to read on a phone.
- Do not put «эфф», «work 0–3», or a diary dump in the ritual message.
- A 1.6.0 morning file that still lacks bedtime, wake time, numeric sleep quality, the last meal time, the time he finished computer work, morning energy, or morning mood is an open morning queue. Send that gap. Do not treat the file as done because other morning fields are filled. A legacy file with sleep hours and numeric quality is closed for sleep without clock times. A sent list that never numbered the computer line is not reopened for it.
- Do not move, archive, delete, restore, or reparent pages. Do not change icons, covers, views, or sidebar. Only today's Day cycle and stale `Фокус сегодня`. If Notion is missing or in trash, still POST Telegram and say the board was unavailable.

## Tails

A tail is an unfinished focus task from a recent working day. Show it so he can continue that card instead of opening a new one.

Day card: the «Фокус» row whose title is exactly `YYYY-MM-DD` and `Уровень=День`. One date, one card. Ignore any other row with the same `Период`, including titles that start with `ТЕСТ`. If that title row is missing, that date has no tails.

Focus day: that card's `Задачи` is non-empty, and neither `План` nor the ritual file says «сегодня ничего» / «отдыхаем» / no focus. A ritual answer of nothing wins over a stray link. If the ritual names focus titles and `Задачи` is empty, match those titles to existing tasks.

Window: start at yesterday. Skip Sunday. Skip days that are not focus days. Take the 3 most recent focus days. Do not look earlier than 7 Mon–Sat days.

Tail: a task linked on one of those days whose `Статус` is `Not started` or `In progress`, and whose project is not `Paused`, `Done`, or `Cancelled`. `Done` and `Archived` tasks are not tails. A paused project's open tasks are not tails. Dedup. Keep the newest day. Order newest first.

Percent only if that newest day's `Итог` states one. «Перенос» only if that day's `Итог` or `Корректировка` states a transfer. Do not invent either. Do not change `Горизонт`.

Collect this list before clearing `Фокус сегодня`. The checkbox is not the source.

Omit the tail block when the list is empty. Do not put an open task here only because it is High or `Горизонт=Месяц` and was never a focus.

## Shape

```text
Утро.

Пропуски: вчера вечер. Напиши итог или «пропустил».

Хвосты, ещё открыты:
- Название задачи — 75%, ещё не готово
- Название задачи — перенос, карточка та же

Пора:
- Название задачи — октябрь открылся
Период, на который они запланированы, начался. Взять в работу сегодня или поставить в ближайшие планы?

<цель из board.goals> — высокий
- …
<цель без приоритета>
- …

Приоритет целей ещё не задан: <название>. Напиши: максимальный, высокий, средний или низкий.

Идеи к решению:
- Название идеи — суть одной строкой
По каждой: в задачу (какой проект), отложить на дату, или отвергнуть.

Продолжить хвост на той же карточке или выбрать другое. 1–2 задачи, или «сегодня ничего». Если две — напиши, какая первая.

Учёба: сегодня 60 минут, из них 30 перешло. Вечером спрошу, что выучил и в какую задачу это пойдёт.
```

The numbers come from `study-log` → **Balance**. With no debt the line is `Учёба: сегодня 30 минут. Вечером спрошу, что выучил и в какую задачу это пойдёт.`

Mon–Fri: do not `POST /send` the morning ritual until that учёба line is in the text with today's due. If it is missing, insert it and only then send. This is not optional and not a tail. Saturday and Sunday: omit the line. The line is Telegram only. Do not copy it into the day's «Фокус» `План`, `Итог`, `Порядок фокуса`, or `Задачи`, and do not check `Фокус сегодня` for a study topic. Study never becomes the day's focus.

Omit the `Хвосты` block when there are none. Omit `Пора` when no task is due (the day file still gets `Пора: —`). The period-started line under `Пора` is only when the block has a `старт` row. With no start row, the line under the list is `Это не фокус, пока сам не выберешь.` The day file stores `Название — фраза` only, not that line. Omit `Идеи к решению` when none are due. One line per due idea: the title, then `Суть` when it is non-empty (his text, one line, do not rewrite). Then one decision line for the block. Then the question is: `Фокус ещё не выбран. Напиши 1–2 задачи на сегодня или «сегодня ничего». Если две — какая первая.` When focus is already set, ask whether to keep or replace it, name two tasks in the stored order, and still show the tails above the goals. Omit the priority line when every open goal already has `Приоритет`. A goal line shows the priority word only when it is set.

Then diary `/send`s (`kind=reply`): yesterday's catch-up if that day is still open (unless already `awaiting`), then today's morning wave if that queue is still open (`headers.morning` + numbered `morningOrder` lines from `journal/survey-script.json`). Two dates = two messages.

Omit the `Пропуски:` line when the miss list is empty. Omit diary sends only when yesterday is done **and** today's morning queue is empty (bedtime, wake, numeric `sleep.quality`, last meal, computer time, `energy.morning`, and `mood.morning` already recorded — or that morning was already closed under an older list).
