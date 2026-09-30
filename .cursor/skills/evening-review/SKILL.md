---
name: evening-review
description: Sends the evening Telegram review at catalog.json → telegram.evening. Monday–Saturday: focus recap, routine block, and diary evening wave. Sunday: diary evening wave only.
---

# Evening review

Every day at `catalog.json` → `telegram.evening`, in `catalog.json` → `timezone`. Monday–Saturday: focus recap + routine block, then the diary evening wave. Sunday: diary evening wave only — no Notion, no `ritual/`, no routine question. Later replies go through the relay webhook / API or the next drain.

## Tools

- Notion only through `notion-personal`.
- Telegram only through the relay: `POST /send` with `kind=evening`.
- Never write any chat except `catalog.json` → `telegram.allowedChatId`. Chats in `telegram.forbiddenChats` stay closed.
- Read `catalog.json`. Ideas live in `notion.ideasDataSourceUrl`. The evening asks about a due idea the same way the morning does.

## Journal

Read `.cursor/rules/ritual-memory.mdc` and `ritual/` for the last 7 Mon–Sat days. If today's утро is still `sent` (or the morning file is missing after `catalog.json` → `ritual.journalStart`), mark it `missed` and add it to `## Сейчас пропущено`. An unanswered morning is not a day off.

A day had a focus only when утро is `answered` and `Фокус` names tasks. «сегодня ничего», «отдыхаем», «отдыхаю», and `Фокус: —` are no focus.

- Older stale `sent` morning → `missed`, add it.
- Stale `sent` evening on a focus day → `missed`, add it. That is the miss to name.
- Stale `sent` evening on a no-focus day → `skipped` (выходной). Do not add it. If it is already `missed` and listed, close it the same way and remove the line. Do not mention it. Do not ask for a recap.

After `/send`, set today's вечер to `sent` in `ritual/YYYY-MM-DD.md`, update the miss list, commit **only** `ritual/` + the rule, then land that commit on `master` (see `.cursor/rules/ritual-memory.mdc` → Git). Do not wait for «ок».

## Sunday

If today is Sunday (`catalog.json` → `timezone`): `git fetch origin master`, then `GET /inbox` first (handle via `telegram-feedback`). Do not query or write Notion. Do not write `ritual/`. Do not ask routine work or study. Follow `life-journal` only for the diary (today's evening wave). A thought that is not the diary still follows `free-notes`. If that wave is already `awaiting` on master, do not send a second copy. Then wait up to 90 minutes (`evening-inbox`) for the diary reply. Do not skip the wait. Stop.

## Flow

1. `git fetch origin master`. Ritual files and `journal/survey.json` live there; the snapshot may be an hour behind.
2. Reconcile the journal and miss list first. Mon–Sat only; skip this on Sunday.
3. `GET /inbox`. If there are unacked messages, follow `telegram-feedback` for them **before** tonight's question.
4. Load today's «Фокус» row (`planningPageUrl`, `Уровень=День`, `Период=today`). If missing, say so and ask for a free-form day recap anyway.
5. On the task read for this evening, apply `.cursor/rules/task-relations.mdc` → **Родитель в работе** before the question. An ancestor that is `Not started`, `Запланировано`, or empty becomes `In progress` when a child already is. Do not reopen `Done` or `Archived`. If a card was lifted, run `task-trees` before the send and add one short clause naming that parent. Then read focus tasks (`Фокус сегодня` or Задачи linked on that cycle). Two tasks: read `Порядок фокуса` and name them in that order («сначала …, потом …», or «одинаково» when the text says so). If two are linked and the order is empty, do not invent it; add one clause asking which was first. Goals with an empty `Приоритет` whose `Статус` is not `Achieved` or `Dropped`: one line naming them, asking максимальный, высокий, средний, or низкий. Do not write a priority in this job. That line does not close the evening. Skip it when none are empty. Full rule: `.cursor/rules/priorities.mdc`.
6. Note already recorded blockers / `Итог`.
7. Ideas still due: `Статус` is `Новая` or `Смотрим`, and `Следующий просмотр` is today or earlier (`catalog.json` → `timezone`). Skip an empty date. Skip `Отложена`, `Стала проектом`, `Стала задачей`, and `Отвергнута`. The morning naming an idea does not close it and does not move `Новая` to `Смотрим`. Silence during the day does not close it. Do not change the date or the status in this job.
8. Set the cycle `Статус` to `Reviewing`.
9. If open misses exist (including today's unanswered morning), one short line naming them, then the usual question. Do not invent progress. A no-focus evening that went unanswered is not an open miss and gets no line. An open idea is not a ritual miss.
10. Send **one** concise ritual Telegram question in Russian. Preserve Focus + what already blocked progress. When the due-idea list is not empty, include that block in the same message. **No life-journal scores in this message.** No Notion/API jargon («предок», ancestor, cycle, «журнал в репо»). He may answer by voice.
11. Follow `routine-log`: append its routine-work block to that same ritual question. It asks what he did outside focus tasks, time, and distraction 1–3. It does not ask a second score for strength. This is not a separate questionnaire.
12. Follow `study-log`: on Monday–Friday append its study block to that same ritual question, with today's due minutes (`study.targetMinutes` plus any carry). It asks whether he studied, minutes, what he learned, which goal and project, and which task he already applied it to or will apply it to soon, when and why. Saturday and Sunday omit it. This is not a separate questionnaire.
13. Then follow `life-journal`: send **one separate Telegram questionnaire** (`kind=reply`) for today's **evening wave** — only items that are not already in today's day file. That is the expanded evening queue: core evening lines, `profile.waves.evening`, еда (одна строка: что ел; голод, профицит и дефицит можно дописать туда же, это необязательно и не отдельный пункт), заметка, plus an unnumbered optional line for чтение и просмотр (сколько минут ушло и что именно читал, слушал или смотрел; можно пропустить; не догонять; это не чтение установок и не отчёт учёбы), plus morning profile ids, медитация, чтение установок, сон, последний приём пищи, компьютер, энергия утра and настроение утра **only when the morning did not record them**. The meal time and the computer time are the «когда последний раз» marks for that night's sleep quality. Do not ask «ел ли за 4 часа до сна» on a new list. Do not number hunger. Do not follow up when hunger, the surplus/deficit, or the optional reading line is missing. Do not number that reading line, and do not repeat it on a follow-up. Do not repeat a recorded morning answer. Do not add a line for vitamins, cigarettes, nootropics, or other ordinary substances. Do not send one message per item. If a morning survey for today is still awaiting, this evening send replaces it. If `survey.json` on master is already `awaiting` for today's evening wave, do not send a second copy. Wait at least 90 seconds for the diary `/send`. A timeout, an empty response, or `duplicate: true` means that text already went out — do not POST it again and do not reword it.
14. After the ritual `/send`, the ritual journal commit, and the diary questionnaire, do not exit. Subscribe a timer every 2 minutes for up to 90 minutes named `evening-inbox`. **Do not skip this wait.** Each fire: `GET /inbox`; if unacked, follow `telegram-feedback`, `routine-log` for routine facts, `study-log` for study facts, `life-journal` for diary facts, and `free-notes` for a thought that is not task tracking, the health diary, study, or how the day went. Keep polling: while this wait is reading `/inbox`, the relay does not start a second feedback agent. Ritual confirm once (`purpose=confirm`); diary lists use `purpose=survey`. If a reply is incomplete, send the compact follow-up required by the owning skill. If none, end the turn and wait.

## Shape

```text
Вечер. Фокус сегодня: сначала …, потом …

Утро сегодня без ответа — напиши фокус задним числом или «пропустил».

Как продвинулся? Что сделал, что мешало, что завтра. Если касалось конкретной задачи — напиши сколько минут на неё ушло. Свободную мысль по задаче тоже можно.

Приоритет целей ещё не задан: <название>. Напиши: максимальный, высокий, средний или низкий.

Идеи к решению, ещё открыты:
- Название идеи — суть одной строкой
По каждой: в задачу (какой проект), отложить на дату, или отвергнуть.

Отдельно про рабочую рутину вне фокуса: что делал по рабочим проектам и сколько минут или часов ушло на каждую часть? Насколько это отвлекло от фокус-задач — 1 почти не отвлекло, 2 заметно, 3 сильно. Если рутины не было — так и напиши.

Отдельно про учёбу, сегодня 60 минут: удалось поучить? Сколько минут и что именно выучил? К какой цели и какому проекту это, в какую задачу уже внедрил или внедришь в ближайшее время, когда и зачем? Если не учился — так и напиши.
```

The study number is today's due from `study-log` → **Balance**. Saturday: omit the study block. The routine block stays.

If there was no focus:

```text
Вечер. Фокуса на сегодня не было.

Что всё же сделал? Что мешало? Что завтра. Свободную мысль по задаче тоже можно.

Приоритет целей ещё не задан: <название>. Напиши: максимальный, высокий, средний или низкий.

Идеи к решению, ещё открыты:
- Название идеи — суть одной строкой
По каждой: в задачу (какой проект), отложить на дату, или отвергнуть.

Отдельно про рабочую рутину вне фокуса: что делал по рабочим проектам и сколько минут или часов ушло на каждую часть? Насколько это отвлекло от фокус-задач — 1 почти не отвлекло, 2 заметно, 3 сильно. Если рутины не было — так и напиши.

Отдельно про учёбу, сегодня 60 минут: удалось поучить? Сколько минут и что именно выучил? К какой цели и какому проекту это, в какую задачу уже внедрил или внедришь в ближайшее время, когда и зачем? Если не учился — так и напиши.
```

Saturday: omit the study block here too. The number is today's due, not a fixed 60.

Then a **second** `/send` (`kind=reply`) with today's evening-wave questionnaire (`headers.evening` + numbered open lines).

Omit the extra miss line when the list is empty. Omit `Идеи к решению` when none are due. One line per due idea: the title, then `Суть` when it is non-empty (his text, one line, do not rewrite). Omit the goal-priority line when every open goal already has `Приоритет`. One focus task: `Вечер. Фокус сегодня: …` with no «сначала». Two tasks and an empty `Порядок фокуса`: name both and ask which was first. Omit the diary follow-up only if today's survey is already complete.

## Hard rules

- Do not guess minutes, progress, diary scores, goal `Приоритет`, day-focus order, or what happened on a missed slot.
- Do not guess routine work, project names, minutes, or distraction. Do not ask how much strength the routine took.
- Do not guess study minutes, what he learned, a goal, a project, a task, or why it applies. Silence is not «не учился».
- A new study topic or «задача по учёбе» in the reply is a flat card in «Учёба» via `study-log`. Do not ask project, parent, horizon, or priority for it. Do not create a Задачи row or a second database. Do not name study inside `Вечер. Фокус сегодня`. Study never goes into the day's «Фокус» card.
- Do not mark Done or blocked here. Do not repeat the morning **Пора** block.
- Do not move a task's `Срок` or `Горизонт` because a nudge was ignored.
- Do not drop a due idea because the morning already named it, or because the evening is about focus. Query Идеи live. Do not move `Следующий просмотр` or `Статус` in this job.
- Do not create a project in this job. A sketch without a goal he named stays an idea.
- «Что мешало» is text, not a status change.
- Do not put «эфф», «work 0–3», or a life-journal dump in the ritual message. The routine distraction score belongs there because it is not a diary score.
- This job sends the ritual question, sends today's evening-wave diary questionnaire, then waits up to 90 minutes (`evening-inbox`). If he answers later, the webhook / API / next ritual drain writes Notion (properties + leftover task comments), the routine log, the study log, and the diary as applicable, and saves a free note when the reply has a thought outside those. Comment rules live in `telegram-feedback`. Note rules live in `free-notes`.
- Do not move, archive, delete, restore, or reparent pages. Only set today's cycle `Статус=Reviewing`. If the cycle is missing or in trash, still ask the evening question.
