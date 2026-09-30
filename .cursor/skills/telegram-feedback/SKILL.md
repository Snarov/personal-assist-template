---
name: telegram-feedback
description: Applies the owner's Telegram reply to focus tasks, the routine-work log, the life journal, free notes, Econumo finances, and Notion. Use when a Telegram relay webhook arrives or when he answers a check-in in chat. The owner is catalog.json → owner.
---

# Telegram feedback

Triggered by the relay webhook / Cloud Agents API (or `/inbox` if the launch payload is empty). One or more user messages in, Notion and local-log writes if needed, Telegram confirm and/or one diary questionnaire for the current wave.

The relay already reacts 👀 and replies «Принял.» the moment the message arrives — before STT and before this cloud run boots. Your `POST /send` is the result (focus titles / evening recap), not a second «принял».

Always `GET /inbox` and handle every unacked message, even if the webhook body already has `text`. Replies stay queued when Cursor fails to start. Voice answers often arrive as several messages about a minute apart; treat the whole unacked inbox as one burst.

## Fresh master

Cloud checkouts lag `origin/master`. Before reading `journal/survey.json`, `ritual/`, or deciding to send a diary questionnaire:

1. `git fetch origin master`
2. Read those files from `origin/master` (or reset/merge so HEAD matches).

Do not treat the snapshot's `survey.json` as truth. A stale `idle` re-sends a questionnaire that is already in the chat.

## One burst, then the open waves

1. `GET /inbox` first. Handle **every** unacked message (focus + diary + routine in the same burst) before any `/send`.
2. `GET /inbox` again immediately before sending a diary questionnaire. If anything new is there, handle it. Do not ask while unacked answers sit in the queue.
3. If `survey.json` on master is already `awaiting` for that `date`/`slot`, do **not** send that questionnaire again. Confirm ritual if needed; the list is already in the chat. A follow-up is allowed only after you parsed answers and some items of **that sent wave** are still missing — not a rebuilt `requiredOrder`.
4. After the first handle, subscribe `feedback-inbox` every 60s for up to 8 minutes. Each fire: `GET /inbox`; if unacked, handle. Then stop. This catches trailing voice messages from the same burst.
5. If other telegram-feedback runs are already on the same inbox, write answers. Do not send a second copy of an awaiting survey. Do not send a second ritual confirm: the relay keeps one confirm per inbox id for 15 minutes, including a reworded one, and answers `duplicate: true`.

## Tools

- Notion only through `notion-personal`.
- Task notes: `notion-create-comment` (page-level on the matched task). Then `notion-get-comments` to confirm the text is there.
- Ritual confirm and clarifications: `POST /send` with `kind=reply` and `purpose=confirm` (or `purpose=clarify`). One per inbox burst. A second confirm, even in different words, comes back `duplicate: true` — do not reword it.
- Diary questionnaire: `POST /send` with `kind=reply` and `purpose=survey`. That is not the confirm slot.
- Routine-work facts only through `routine-log` into `routine/entries/`.
- Study facts only through `study-log` into `study/entries/`. A topic is the only Notion write, one flat card in «Учёба».
- A free note (idea, experience, view — not task tracking, not the health diary, not how the day went) only through `free-notes` into `notes/entries/`.
- Then `POST /inbox/ack` with the message id when you handled it.

## Task trees

If this run changes `Статус` on a Задачи card, creates a task, or changes `Родительская задача`, `Горизонт`, or the task title, follow `task-trees` before the Telegram confirm. Rebuild the pages in Home → «Деревья». If the rebuild fails, say so in that confirm. Do not move the task card.

## Journal

Read `.cursor/rules/ritual-memory.mdc` and the matching `ritual/YYYY-MM-DD.md` files first.

After a successful handle (or an explicit skip), write his words into the day file. A focus pick, a no-focus evening reply, or a focus-day evening with per-task minutes or an explicit result becomes `answered`. «Пропустил» becomes `skipped`. A focus-day evening that is only a diary, a routine note, a study report, a free note, or «день нормальный» stays `sent` — do not remove a miss that is not actually closed. Remove a closed slot from `## Сейчас пропущено`. Commit **only** `ritual/` + the rule, then land that commit on `master` (see `.cursor/rules/ritual-memory.mdc` → Git). Do not wait for «ок». If he closes an older miss in the same message, write that day's file too. A no-focus day whose evening is still `missed` or stale `sent` is a day off: set that evening to `skipped` and drop it from the list, even when this message is about today.

## Classify

Sunday (Europe/Moscow): no focus pick, no evening check-in, no `ritual/` write, no `routine-log` unless he explicitly reported work, no `study-log` unless he explicitly reported study. Diary only via `life-journal`. A free note still goes through `free-notes`. An expense, income, transfer, debt, or balance still follows `econumo`.

Use `kind_hint` from the payload plus today's «Фокус» status, the miss list, and `journal/survey.json`:

- Morning / no focus yet / he names tasks → **focus pick**
- Evening / `Reviewing` / progress dump → **evening check-in**. On a focus day this closes the evening only with per-task minutes or an explicit result on those tasks (сделал / не делал / готово / по фокусу ничего). A diary voice, a day rating, routine notes, a study report, a free note, or «день нормальный» do not close it: leave вечер `sent`.
- Open miss + «пропустил» / не писал → **skip**: journal `skipped` only, no Notion invention
- Open miss + recap of that day → write that day's journal (and Notion if it is an evening recap with minutes); leftover task comments follow **Task comments** even on catch-up; do not guess
- Routine work outside focus tasks, its time, distraction, or «рутины не было» → also follow `routine-log` on the **same** text. A second score for strength or fatigue is not a field.
- Study: he studied or explicitly did not, minutes, what he learned, which goal or project, where he applied it or will apply it → also follow `study-log` on the **same** text. Do not invent a topic. Do not copy that clause into a task comment, a free note, the diary, or the day's «Фокус» card (`План`, `Итог`, `Корректировка`, `Порядок фокуса`, `Задачи`, `Фокус сегодня`). Study never becomes focus.
- Diary scores / answer to the awaiting survey / a mention of vitamins, cigarettes, nootropics, or another ordinary substance / «потом» / profile edit («трекай …», критерии work) → also follow `life-journal` on the **same** text. Do not invent scores if he only answered focus or minutes. Do not map routine impact scores to diary scores. Per-item diary comments stay in `journal` `comments`, not in Notion. A substance he names is not a clarifying question and not a new survey line. How the day went stays in `journal` `notes`. What he read, watched, or listened to on the diary line stays in `journal` `media`, not in study and not in a free note.
- A decision on a due idea («в задачу», «отложить» на дату, «отвергнуть», or «это проект») → **Idea decision** on the **same** text, whether or not the burst is also focus or evening. «По фокусу ничего» and «не делал задачу» are not a rejection of an idea. That decision is not a free note.
- He closes the research of an idea, or asks for the planned work after that research → **Consideration follow-up** on the **same** text. `Done` on that card closes only the review.
- A clause that is clearly not task tracking, not the health diary, not a note about how the day went, and not a decision on a due idea — an idea he is telling, an experience, a view, anything of that kind — → also follow `free-notes` on the **same** text. Do not invent a thought. Do not copy a task comment or a day note into `notes/`. Do not ask «сохранить?» when it is clearly a note. Do not create an «Идеи» row from it. A payment, a balance, a transfer, or a debt is not a free note.
- Money: an expense, income, transfer, debt, or account balance → also follow `econumo` on the **same** text. Do not copy that clause into Notion, `journal/`, `routine/`, or `notes/`. The confirm names what was written. An expense is not done until that skill has run the pace script; the script sends its own Telegram alert (`kind=pace`) when this expense pushed the budget line over the day's pace. Do not paste that alert into the confirm and do not send it again. Money does not close a ritual slot.
- A command to change how the assistant works («сделай правилом», «запиши в правила») is not a free note and not a focus pick. Write the rule. Do not invent focus or minutes from it.
- A goal level («у <цель из board.goals> высокий») → **Priorities** on the same text. The goal must be one of `catalog.json` → `board.goals`. It is not a focus pick and not a day-focus order. Do not invent the level.
- `survey.json` is `awaiting` → parse every labeled questionnaire answer for that `slot` (morning / evening / catch-up), even if the same blob is also a focus/evening reply.
- Ambiguous and **not** a survey answer → one clarifying Telegram question, then stop. Do not write guesses.

A focus reply without scores is not a diary skip. After writing focus, follow `life-journal`:

- `survey.json` is `idle` and yesterday is not complete → send yesterday's catch-up, then today's morning wave if that queue is still open (second `/send`; do not replace the yesterday pointer).
- `survey.json` is `awaiting` yesterday and today's morning was never sent → send today's morning without moving `survey.date` / `slot` / `missing`.
- `survey.json` is `idle`, yesterday is done, morning context, today's morning queue is still open → send today's morning wave.
- `survey.json` is `idle`, evening context, today is not complete → send today's evening wave. The wave is items still empty in the day file. Do not include a morning item that already has a usable value.
- `survey.json` is `awaiting` and this text answers the survey → write every usable field onto the date he named; if the **sent** wave is incomplete, send one follow-up containing only that wave's leftover `asked` / `missing` lines. Do not rebuild from `requiredOrder`.
- `survey.json` is `awaiting` and this text is only ritual → do **not** duplicate the questionnaire; it is already in the chat. Fetch master first so a stale snapshot cannot look like `idle`.
- After yesterday's catch-up closes in the morning, send today's morning wave if today's morning queue is still open and was never sent.
- Do not end with only `дневник без оценок` while a wave is still open.

## Focus pick

1. Match names to existing Tasks. If two could fit, ask which one.
2. «Продолжаем вчерашнее», «хвосты», «то же», «продолжи» without a new title → the open tails from the newest focus day in `morning-checkin` → **Tails**. Same cards. Do not create a card. Do not change `Горизонт`. Drop a tail whose project is `Paused`, `Done`, or `Cancelled` (see `catalog.json` → `board.paused`). Do not offer those tasks. If he names one of those cards himself, set the focus he named.
3. A phrase that resembles one open tail but is not its title → ask «это та же карточка?» Do not create until he says yes.
4. At most two focus tasks. If he says «сегодня ничего», clear `Фокус сегодня`, clear `Порядок фокуса`, and write that in `План`. Open tails stay open for the next morning. A **Пора** line is not a question to close. «Не беру», «не сейчас», and silence do not change that task's `Статус`, `Горизонт`, `Срок`, or `Приоритет`. Naming one of those tasks as today's focus is an ordinary focus pick.
5. Two tasks and he did not say which is first → ask «Что первым: … или …?» and stop the focus write. Do not check `Фокус сегодня`, do not link the cycle, do not mark утро `answered`. «A и B» is not an order. Explicit order: «сначала», «первым», «в первую очередь», «потом», «затем», «важнее», «раньше», or numbers 1 and 2. «Одинаково», «параллельно», «без разницы» means there is no first.
6. Uncheck `Фокус сегодня` on other tasks.
7. Check `Фокус сегодня` on the chosen ones and link them on today's «Фокус» cycle. If `Статус` is `Not started` or `Запланировано`, set `In progress`. Leave `Done` and `Archived`. In the same write, walk `Родительская задача` and apply `.cursor/rules/task-relations.mdc` → **Родитель в работе**: each ancestor that is `Not started`, `Запланировано`, or empty becomes `In progress`. Do not reopen `Done` or `Archived`. Do not change the ancestor's horizon, priority, срок, or focus. Re-fetch each ancestor. Unchecking `Фокус сегодня` does not move the status back. Do not set task `Приоритет` from the focus pick. Set it only when he named `Максимальный`, `Высокий`, `Средний`, or `Низкий` for that task. Two tasks: write `Порядок фокуса` as `1. <first title>` then `2. <second title>`, or `одинаково: <title>; <title>` when he said they are equal. One task: leave `Порядок фокуса` empty.
8. Write `План` in his words about the work focus tasks only. `Статус=Active`. A study clause in the same reply («учёба», «30 минут» учёбы, «задача по учёбе», a topic or exercise) does not go into `План`, `Итог`, `Корректировка`, `Порядок фокуса`, the cycle `Задачи` relation, the ritual `Фокус:` line, or `Фокус сегодня`. It goes only through `study-log`. If the plan already contains study, delete that part in this same run and leave the work sentences.
9. If the same reply has leftover task notes (see **Task comments**), comment those on the matched cards. Naming a focus task is not a note.
10. Apply **Idea decision** when this text decides a due idea, or when a due idea is still open.
11. Apply **Priorities** when this text names a goal level. A missing goal priority does not block the focus write.
12. Confirm titles only, no URLs. Plain Russian, one short message. Two tasks: «Сначала …, потом …» or «… и … одинаково». If this pick moved a card to `In progress`, one short clause that it is в работе. If an ancestor was lifted to `In progress`, one short clause naming that parent. If a comment was written, one short clause that the note landed on that task. If he continued a tail, one short clause that it is the same card. If an idea was decided or is still open, add the clause from **Idea decision** in that same message. If a goal priority was written, one short clause naming the goal and the level.
13. Journal today's утро as `answered` (фокус or «сегодня ничего») only after the focus write, including `Порядок фокуса` when there are two tasks. `Фокус:` is the title, or `1. <first>; 2. <second>`, or `одинаково: <title>; <title>`. Keep the morning's `Пора:` line; do not drop it and do not treat it as the focus.
14. Then `life-journal`: write any diary answers in the same text. If yesterday still needs a survey, send that catch-up, then today's morning wave if that queue is still open (second `/send`; do not replace the yesterday pointer). If yesterday is done and today's morning wave is open, send the morning wave. Separate git commit from the ritual journal.

## Evening check-in

1. Match each mentioned task. If the note does not match the title, ask before writing properties or comments.
2. Minutes are mandatory per updated task. Routine-work time does not count as a focus task's time. If he gave progress but no task minutes, ask «Сколько минут потратил на эту задачу?» and do not write `Факт (ч)` / Done / cycle `Итог` yet. Leftover task comments may still go through if the card is already matched (see **Task comments**).
3. Never invent `time_elapsed` / effort. No default 15/30/60.
4. Split the reply: minutes / progress / done stay in properties; leftover thoughts go to comments. Do not embellish either.
5. Add minutes / 60 to that task's `Факт (ч)` (keep prior hours, add today's).
6. Put the work recap in «Фокус» `Итог` (his words about those focus tasks, including work notes). Study clauses stay out of `Итог`, `План`, and `Корректировка`. Add `Корректировка` only if he stated a tomorrow plan for the work.
7. «Мешало» → text only. Day-level blocker stays in `Итог` / ritual. Task-specific blocker also becomes a comment on that card. Status `blocked` does not exist on Tasks; do not archive or Done unless he said the task is finished.
8. Done only if he said it is done. Then `Статус=Done` and uncheck `Фокус сегодня`. If he reported progress and did not say it is done, the confirm adds one short clause: «Карточка остаётся открытой, утром напомню.» Skip that clause when he said it is done, or when there was no task. If that Done card is the consideration of an idea, follow **Consideration follow-up** in the same run. `Done` closes only the review.
9. After writes, re-fetch the task and confirm the real Статус. After each comment, `notion-get-comments` and confirm the text is present. Do not say a note was saved until that read comes back.
10. If the cycle has results for the named work, set «Фокус» `Статус=Reviewed`.
11. Journal that day's вечер as `answered` only when the recap is real. On a focus day that means per-task minutes or an explicit result on those focus tasks (сделал / не делал / готово / по фокусу ничего), in his words (итог / мешало / минуты). A diary voice, a day rating, routine notes, a study report, a free note, or «день нормальный» do not close it: write the diary, the routine, the study log, and any free note, leave вечер `sent`, and ask the missing minutes once. On a no-focus day any evening reply closes it as `answered`. Catch-up for a missed evening uses that day's file and «Фокус» row, not today's. If he never answers a focus-day evening, the next ritual marks that stale `sent` as `missed`.
12. Then `routine-log`: write routine facts from the same text. If he omitted the routine block entirely, ask it once more in one compact clarification without interpreting silence as no routine. If he reported routine but omitted required parts, include every missing routine field in that one clarification. Use a separate operational-data commit.
13. Then `study-log` on a Mon–Fri evening: write study facts from the same text into `study/entries/`, including the carried due from **Balance**. If he omitted the study block entirely, ask it once more in that same compact clarification. Do not treat silence as no study and do not write a `none` file from it. A weekday that has already ended with no integer minutes still counts as 0 studied in the next morning's balance. If he reported study but omitted minutes, the topic, the goal, the project, or where it lands (an existing task, when, why), include every missing study field in that one clarification. Never ask project, parent, horizon, or priority there. A new study topic or «задача по учёбе» in the same text is a flat card in «Учёба», property `Тема` only, written in this same run, not a missing `create-task` field and not a second database. A separate operational-data commit for the day entry, and another for `study/topics.json` when a topic changed. Saturday and Sunday: write study only when he reported it; those minutes pay the carry down and do not add 30. Still write a topic he named.
14. Apply **Idea decision** when this text decides a due idea, or when a due idea is still open. The ritual confirm includes that clause in the same message as the evening recap.
15. Apply **Priorities** when this text names a goal level. A missing goal priority does not hold вечер `answered`. If a level was written, one short clause in that same confirm.
16. Then `life-journal`: write diary answers from the same text. If today still has empty evening items, send one evening-wave questionnaire with only those open lines. Do not include a morning item the day file already holds. A stale `missing` id that is already in `answered` is not a follow-up line. Separate git commit from the ritual journal, the routine log, and the study log.

## Idea decision

A due idea is a row in Идеи (`catalog.json` → `notion.ideasDataSourceUrl`) with `Статус` `Новая` or `Смотрим` and `Следующий просмотр` today or earlier (Europe/Moscow). Skip an empty date. Skip `Отложена`, `Стала проектом`, `Стала задачей`, and `Отвергнута`. The morning line does not close it and does not move `Новая` to `Смотрим`. Query live; do not trust the ritual file for the list.

A new idea row is `Статус=Новая`. Consideration has not started. Set `Смотрим` in this same run when he takes that idea as today's focus, or when a real discussion of it starts: he talks about whether or how to do it, or asks to look into it now (study a link, compare, draft). Capturing the card, «не поднимать», «отложим рассмотрение», and a later date alone stay `Новая`. The morning or evening line that only names the idea is not that discussion.

## Idea page body

Every new idea page uses this body. An existing page gets the callout the first time this run edits it. Keep notes that are already there; do not rewrite them into the template.

```
<callout icon="📅" color="gray_bg">
	**Дата:** <mention-date start="YYYY-MM-DD"/>
</callout>
## Суть
{his words, the same text as the Суть property}
## Заметки
```

`Дата` is the same day as `Следующий просмотр`. An empty review date is `**Дата:** —` with no mention. Do not add a second date property. Do not write the review date as a free sentence (`Напоминание: … Рассмотреть завтра.`). Links and research stay under `## Заметки`. The Notion connection cannot register this as a database New-menu template; write the body on create.

Match his words to one due idea. One due idea and he decides without repeating the title → that one. Two could fit, or he says «отложи» / «отвергни» while a focus task is also open and he did not say «идея» → ask which. Do not copy one answer onto every open idea.

Three outcomes. Do not invent a fourth. Do not delete the row, and do not move it to the scratch bin.

1. **В задачу.** «в задачу», «сделай задачей», «берём задачей».
   - The row is `create-task`. Do not write it from this section. He must name the project; two projects could fit → ask. Do not guess a project from `Суть`. Do not offer a `Paused`, `Done`, or `Cancelled` project (see `catalog.json` → `board.paused`). If he names one of those himself, use the one he named. Title is the idea title unless he names another. Page body is `Суть` when it is non-empty. This row is the short research of the idea, not the delivery. Its horizon is the consideration, not the month of the work he is imagining. When that review later finishes and he accepts the work, follow **Consideration follow-up**.
   - `create-task` asks in this same reply for any of project, parent task, horizon, and priority he did not name, and does not create the row yet. Priority is `Максимальный`, `Высокий`, `Средний`, or `Низкий`, his words. Until that row is on the board, leave the idea on its current status (`Новая` or `Смотрим`).
   - Search Задачи for that title first. If the card already exists, do not create a second one. Then set the idea to `Стала задачей`, set `Задача` to that card, and say the task was already there. Empty horizon, priority, project, or parent on that existing card: ask once whether to fill the empty ones. Do not overwrite a value that is already set. Do not invent `Приоритет`.
   - Only after `create-task` re-fetches a row with project, horizon, priority, and parent (or an explicit «без родителя»), set the idea `Статус=Стала задачей` and `Задача` to that page URL. If the `Задача` column is missing, add a one-way `ADD COLUMN "Задача" RELATION('<tasks data source id>')` on Идеи first (`catalog.json` → `notion.tasksDataSourceUrl`). Do not add a reverse column on Задачи. Show `Задача` in the Идеи table view. If the task write failed, leave the idea on its current status and say so. If the status is set and the relation write failed, say the link is missing.
   - «Это проект» / «стала проектом» is not a task. Search Проекты for the same theme first. Create a project only when he said it is a project, named the goal himself, and no card exists; then set the idea `Статус=Стала проектом`. If he did not name the goal, ask which goal and do not create the project. Do not guess the goal from `Суть`. A sketch with no tasks, or «сам поймёшь», stays an idea. A single deliverable stays a task.
2. **Отложить.** He names a date after today (Europe/Moscow), including «завтра», «в понедельник», «1 октября», «через неделю». Keep the current status (`Новая` stays `Новая`, `Смотрим` stays `Смотрим`) and set `Следующий просмотр` to that date. A postpone is not the start of consideration. It is asked again on that morning and that evening. «Потом» / «позже» without a day is not a date: ask once. Do not invent a date. A date of today or earlier is not a postpone: ask for a later day. Do not set `Отложена` for a dated postpone. Morning and evening skip `Отложена` entirely, so a date on that status never comes back. `Отложена` only when he says not to remind («насовсем», «не напоминай», «в долгий ящик»).
   - Same run, update the card body. Replace the `<mention-date>` inside the `**Дата:**` callout with the new day. If the callout is missing, insert it at the top and delete any line that starts with `Напоминание:`. Do not leave the old sentence. His extra words («раньше не поднимать») stay under `## Заметки`.
   - Same run, one page-level comment on that Идеи row, not on a task: `Рассмотрение перенесено на <mention-date start="NEW"/>. Было: <mention-date start="OLD"/>.`. If there was no previous date, omit «Было». This is the only comment an idea page gets.
   - Re-fetch the page and `notion-get-comments`. The `Дата` mention and the comment must both be there. If either write failed, say which one.
3. **Отвергнуть.** «отвергни», «отклони», «не надо» **about that idea** → `Статус=Отвергнута`. Leave the date as history. Leave the row.

If `Стала задачей` or `Отвергнута` is missing from the select, fetch the Идеи data source and add only the missing option before the property write. `ALTER COLUMN "Статус" SET SELECT(...)` must repeat every option already there (`Новая`, `Смотрим`, `Стала проектом`, `Отложена`, and whichever of the two new ones exists) plus the missing one. Do not drop an option. `Новая` is yellow, `Стала задачей` is green, `Отвергнута` is red. Leave the existing colors as they are.

Verify by re-fetching the idea page, not by the write response. Status and `Следующий просмотр` must match. `Дата` in the body must be that same day. When the outcome is a task, `Задача` must contain that task page. When the date moved, the comment must be on the page. Do not say the idea moved until that read is clean.

An open idea is not a ritual miss and does not go into `## Сейчас пропущено`. If this reply closes the morning or the evening and a due idea is still undecided, add one short line to the ritual confirm: the title, and «в задачу (какой проект), отложить на дату, или отвергнуть». Do not hold the evening `answered` for that. The next morning and the next evening ask again, because the card is still `Новая` or `Смотрим` with a date that has arrived.

Confirm in the same ritual reply what changed: task title and project, the new date, or that it was rejected. If a write failed, say the idea is still open.

## Consideration follow-up

The Задачи row an idea became is the research. He spends time on it. A spec and a preliminary plan written there are the outcome of that review.

When he says that review is finished («закрывай», «взяли», «спека готова», the research minutes and done) and the decision is to do the work, `Статус=Done` closes only the research. Do not leave that card as the delivery.

In the same run, create the follow-up rows through `create-task`. Parent is the bigger task this work is a piece of, or empty. The consideration card is not the parent. «Потом», «после исследования» and the next month are time order, not `Родительская задача`. Horizon, `Срок`, and priority are his words for those rows. One follow-up or several — only the cards he asked for. If horizon, the calendar box, or priority is still open, ask once and do not create that row.

Move the spec and the preliminary plan onto the follow-ups, in his words. Rename the consideration card so the title says it is the research when the delivery card needs the idea title. Horizon of the research is the short box he named for the review, or `День` when he called it a short research and named the longer horizon only for the follow-up. The research `Срок` is the day of the review when that day is already known; the delivery calendar box goes on the follow-up. The consideration body becomes a short recap plus a mention of the follow-up. The idea's `Задача` relation stays on the consideration card.

Re-fetch the research card and each follow-up before the confirm. Say the title, project, parent, horizon, and priority of each new card. If a write failed, say which card is missing. Then `task-trees`.

## Priorities

Full rule: `.cursor/rules/priorities.mdc`. Do not invent a level or a day order.

Goal `Приоритет` is only `Максимальный`, `Высокий`, `Средний`, or `Низкий`. `Максимальный` is above `Высокий`. The same four options are the task `Приоритет`.

- Create a Цели row only when he asked for that goal and named one of those three in the same reply. If the level is missing, ask once and do not create the row.
- On an existing goal, set `Приоритет` only when he named that goal and a level. «Обе высокие» sets both. «Важная» or «главная» without максимальный / высокий / средний / низкий is not a level: ask which of the four. «Сначала» on a focus task does not change the goal's priority.
- Re-fetch the goal and confirm the select matches. Do not say it was set until that read is clean.
- A goal that is still empty is not a ritual miss. If this reply closes the morning or the evening and an open goal still has no priority, add one short line: the titles, and «максимальный, высокий, средний или низкий».

Day order is `Порядок фокуса` on today's «Фокус» row, not task `Приоритет`. The focus-pick steps above own that write. Do not set task `Приоритет=Высокий` because a task is today's focus.

## Task relations

Implied parent-child links. Full rule: `.cursor/rules/task-relations.mdc`.

When this run creates a work task, follow `create-task`. That skill asks for the parent before the row exists. A study topic has no parent and does not enter this pass. The parent to propose is the bigger task this card is a smaller part of, already on the board. Same arc, a week or month goal, and «потом» do not set `Родительская задача`. A finished research card is not that parent. Two parents → ask which. Do not glue unrelated arcs. A parent is a task, not a new project. This is a relation write, not a page move.

Relink an already-existing card only when he asked, or when this run just created the child and the parent is unique.

## Task comments

Page-level Notion comments on **Задачи** are the running log of free thoughts about a task. Properties stay the structured facts. Comments are not a dump of the whole evening SMS.

### Split the reply first

Treat each clause as one of:

| Keep in properties / `Итог` only | Leftover → comment on the matched task |
| --- | --- |
| Minutes / hours (`30 минут`, `час`) | Intermediate notes (`сначала поправил конфиг`, `переставил шаги`) |
| Progress (`в процессе`, `75%`, `ещё не готово`) | Decisions, observations, how he did it |
| Result (`закончил`, `добил`, `ничего не делал`) | Task-specific «мешало» (`стенд не поднимается из-за …`) |
| Focus pick titles, «сегодня ничего», «сегодня отдыхаю» | Next micro-step about the work itself (`завтра начну с конфига WireGuard`) |
| Day-level «мешало» (`усталость`, `гости`) and diary scores | Free thoughts that are clearly about that task |

A clause that is only time, percent, status, or a yes/no result is **not** a comment. If after stripping those plus voice filler (`ну`, `вот`, `как бы`) nothing of his remains, skip the comment.

`Итог` / `План` still get his work recap, including leftover notes about those focus tasks. The comment is the per-task log, not a replacement for the day cycle. Study text does not go into `План` or `Итог`.

Diary `заметка`, diary `media` (what he read, watched, or listened to), and per-item `comments` from `life-journal` are not a task comment. Routine facts go to `routine-log`, never to a Notion comment. Study facts go to `study-log` (the day in git; a topic card in «Учёба»), never to a task comment and never into the day's «Фокус» card. The work task he names stays in the day file. An idea, an experience, or a view that is not about a matched task and not study goes to `free-notes`, never to a Notion comment and never to `journal` `notes`.

### Match, then write

1. Attach a leftover clause only to a task he named or that uniquely matches. Two possible cards → ask which one; do not guess.
2. Exactly one `Фокус сегодня` task and the leftover does not name another card → that focus task.
3. Two focus tasks and the leftover is not split → ask. Do not copy the same ambiguous note onto both.
4. One comment per task per handled message. Several leftovers for the same card → one comment, his wording, light STT cleanup only.
5. `notion-create-comment` with `page_id` = the task page and `markdown` only. No `discussion_id`, no `selection_with_ellipsis`, no comments on «Фокус» / Цели / Проекты, no body edits.
6. Comment shape — date mention, blank line, then his words. No agent preface (`заметка:`, `прогресс:`):

```text
<mention-date start="YYYY-MM-DD"/>

короткая мысль его словами
```

Use the ritual day (the missed evening's date on catch-up). Quote him. Do not invent or summarize into a nicer sentence.

### Examples

- «90 минут на задачу, ещё не готово, 50%» → hours + `Итог` only. No comment.
- «Обе закончил, на каждую по часу» → hours + Done + `Итог`. No comment.
- «По задаче 30 минут, 50%. Застрял на одном месте» → hours + `Итог`; comment on that task: `Застрял на одном месте`.
- «Сегодня ничего. Просто думал: привычка важнее настроения» → `План`/`Итог` as «сегодня ничего»; no hours. If a task uniquely matches and the thought is about that work, comment it there. If no card matches, it is a free note: follow `free-notes` and do not ask which card.
- Morning: «Фокус задача А и задача Б. С А сначала черновик» → focus properties; comment only on А: `сначала черновик`.

## Telegram replies

- Ritual confirm (focus titles / evening heard) may be one `kind=reply` message. If a task comment was written, add one short clause naming that task. If the comment write failed, say so in the same message. If an idea decision landed, one short clause naming the idea and the outcome. If a due idea is still open, one short line asking for the decision. If a free note was saved, add one short clause with its title (`Записал заметку: …`). A message that is only a note still gets that one confirm.
- A routine-log confirmation or clarification may be included in that ritual confirm. Do not send one routine question per activity or field.
- A study-log confirmation or clarification may be included in that same ritual confirm. Do not send one study question per field.
- The diary questionnaire is one **separate** `kind=reply` send composed from `journal/survey-script.json` for the current wave (morning / evening / catch-up). It contains that wave's open items. Never send one message per item.
- When the survey closes, one short human summary (`дневник 17.09: сон 23:40–07:10 (7,5 ч) / качество 6, последний приём пищи 21:30, компьютер до 22:10, энергия утро 5 вечер 4, настроение утром норм, вечером хорошее, медитация 15 мин, установки да, оценка дня 6, …`). No «эфф». Do not turn one night's meal time and computer time into a claimed effect on sleep.
- Then `POST /inbox/ack`.

## Telegram language

Phone, Russian, no jargon. Confirm what was written. If something failed, say it in words a person would use.

Never paste Notion/API fragments into chat. Forbidden: «архивированный предок», ancestor, cycle, «журнал в репо», raw error strings.

If a write fails, name the board and what that means:

- trash / archived parent → «не записал в Фокус: таблица или карточка дня в корзине»
- missing cycle → «нет карточки этого дня в Фокусе»
- journal only → «записал это в дневник, в Notion не попало»

Bad: «Цикл дня в Фокусе не обновил: страница с архивированным предком. Журнал в репо записан.»
Good: «Вечер услышал. 90 мин в задачу проставил. Итог дня в Фокусе не записался — таблица Фокус в корзине. Если вытащишь её оттуда, допишу.»

## Hard rules

- Do not use work Notion.
- Do not message anyone but `catalog.json` → `telegram.allowedChatId`.
- Do not create a new Задачи row unless he asked to add that exact title as a work task, or he decided a due idea becomes a task (**Idea decision**). A study topic, exercise, or «задача по учёбе» is not that row: `study-log` appends it as a flat card in «Учёба», title only, with the learning and links on the card. Do not ask project, parent, horizon, or priority for it. Continuing a tail reuses the open card. Do not change `Горизонт` for a tail. Every new Задачи row goes through `create-task`: project, parent task, horizon, and priority are his words, or one question, and the row waits. Project, parent, and horizon are determined only when he delegates, and the confirm says what was set. Task `Приоритет` is not invented.
- Voice arrives as a transcript (`input=voice`). Treat it as his words. Separate facts from filler. Do not embellish. If minutes are missing, ask.
- Do not move, archive, delete, restore, or reparent pages. Do not change icons, covers, views, or sidebar. Another agent owns workspace layout. Ritual writes: properties `План`, `Итог`, `Корректировка`, `Статус`, `Фокус сегодня`, `Факт (ч)`, `Порядок фокуса`, task `Приоритет` only when he named the level, goal `Приоритет` only when he named the level, cycle `Задачи`; plus page-level comments on matched **Задачи** as in **Task comments**. `Родительская задача` is a relation, not a page move: `create-task` sets it when he named the parent or delegated it, and on an existing card only when he asked or this run just created the child. An idea decision may also set Идеи `Статус`, `Следующий просмотр`, and the one-way `Задача` relation when the idea becomes a task, add a missing select option or that relation column on that data source, write the idea body (`Дата` callout, `## Суть`, `## Заметки`), replace the `Дата` mention and add one page comment on that Идеи row when the review date moves, and create one Задачи row only through `create-task`. A Проекты row from that decision only when he said it is a project and named the goal. Do not mint an empty project, and do not edit a goal page to announce one. `study-log` may create and update a flat card in «Учёба» (`Тема` only; the body is the learning, materials, and links). It does not create a day-log row, a second database, or a Задачи row for a study topic.
- If a Notion write fails (trash, archived parent, missing cycle, comment not visible on re-read), still send Telegram: the reply was heard, what was saved, what was not, in the language above. Still write the ritual journal. Do not try to restore the workspace.
- Diary scores are `life-journal`, not Notion. A failed Notion write does not skip a valid diary write, and the reverse.
- Routine work is `routine-log`, not Notion or `journal/`. A failed Notion or diary write does not skip a valid routine write, and the reverse.
- Study is `study-log`: `study/entries/` for the day, and a flat card in «Учёба» plus `study/topics.json` when he names a topic. It is not a task comment, not `journal` `notes`, and not `routine/`. A failed task or diary write does not skip a valid study write. A failed «Учёба» write does not skip the git file; say the board write failed.
- A free note is `free-notes` (`notes/entries/`), not Notion, not `journal` `notes`, and not `routine/`. A failed Notion, diary, or routine write does not skip a valid note, and the reverse. Do not file task accounting, diary scores, or how the day went as a note.
- Never map routine `distraction` to life-journal `work` / `mood` / `energy`. Do not store a second routine score. A file that already has `energyDrain` stays as it was.
- Do not probe other relay paths besides `/inbox`, `/send`, and `/inbox/ack`.
- Never send a diary questionnaire that `survey.json` on origin/master already has as `awaiting` for that date/slot. Fetch master first.
- Wait at least 90 seconds for a diary `/send`. A timeout, an empty body, or `duplicate: true` means that text is already in the chat. Do not send it again and do not reword it.
