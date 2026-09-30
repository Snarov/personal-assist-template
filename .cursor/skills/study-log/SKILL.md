---
name: study-log
description: Records the owner's weekday study and the carried minute debt, plus a flat list of study topics. One topic card is one theme or exercise, title only, with the learning and links on the card. Use on morning check-in, evening review, and when a Telegram reply reports study or names a study topic. Goals and projects come from catalog.json → board.
---

# Study log

One calendar day (Europe/Moscow) = `study/entries/YYYY-MM-DD.json`. Notion «Учёба» is the flat list of topic cards, not a row per day. Read `study/study.spec.json`, `catalog.json` → `study`, and the existing day file before asking or writing.

The obligation is Monday–Friday. Each of those days adds `study.targetMinutes` (30). Minutes he did not study carry to the next weekday. Saturday and Sunday add nothing and are not asked. Do not backfill days before `study.askFrom`. Days before `study.accrueFrom` are not debt.

This log is separate from:

- focus tasks and the day board «Фокус» in Notion (a study day can name an existing task; it does not replace minutes on that task, and it does not become a card);
- the ritual transcript in `ritual/`;
- scores in `journal/`, including the evening diary line about reading, podcasts, audiobooks, and videos (`media`). That line is not «учился» and is not copied here unless the same reply also reports study;
- ordinary work in `routine/`;
- free notes in `notes/`.

## When this runs

| Trigger | What to do |
| --- | --- |
| `morning-checkin` | Mon–Fri: one reminder line with today's due minutes. Do not ask what he will study. Do not write a file. Saturday and Sunday: omit the line. |
| `evening-review` | Mon–Fri: the study block in the same ritual question, naming today's due minutes. Do not send another questionnaire. Saturday and Sunday: omit it. |
| `telegram-feedback` | Parse study facts from the same reply, write git and Notion, and on Mon–Fri ask one compact clarification if the block was omitted or required fields are missing. Saturday and Sunday: write only what he volunteered, and do not ask. A new study topic in that reply is **Study topics**, written in the same run. |
| Ad-hoc in this repo | Fill or verify a named day from his words, or append a study topic he named. Do not message Telegram unless he asked. |

## Balance

Read every `study/entries/` file from `study.accrueFrom` through the day before the date being asked or written. Europe/Moscow. `study.targetMinutes` is the daily add (30), not the number to say when debt has piled up.

`carry` starts at 0. Walk the dates in order:

- Saturday or Sunday: do not add 30. If that file has an integer `totalMinutes`, `carry = max(0, carry - totalMinutes)`. A missing file or null minutes changes nothing.
- Monday–Friday: add 30. `studied` is `totalMinutes` when that file has an integer, otherwise 0. `carry = max(0, carry + 30 - studied)`. A missing file and a file with null minutes are both 0 studied. The day already ended, so the unpaid 30 stays in the debt. Do not create a file only to store that zero.

That `carry` is `carryIn` for the date in question. `accruedMinutes` is 30 on a Monday–Friday on or after `accrueFrom`, otherwise 0. `dueMinutes` = `carryIn + accruedMinutes`. On Saturday and Sunday `dueMinutes` equals `carryIn`: nothing new is owed, and minutes he volunteers pay the debt down.

`carryOut` = `max(0, dueMinutes - totalMinutes)` when `totalMinutes` is an integer, otherwise null. Minutes above the due do not become a credit. When `carryOut` is 0, the next weekday is 30 again.

A file before `accrueFrom` is not part of this walk, even when `metTarget` is false. Do not rewrite it. A file inside the window at `specVersion` 1.0.0 still counts through `totalMinutes`. Do not migrate it only to add carry fields.

The next reminder day is the next Monday–Friday after the day just written. Its number is `carryOut + 30`. Say «Завтра N минут» when that day is tomorrow. Say «В понедельник N минут» on Friday, Saturday, and Sunday. When that number is 30, say «снова 30».

Worked example, debt empty at the start of Tuesday: he skips Tuesday, or the day ends with no minutes at all → Wednesday is 60. He studies all 60 on Wednesday → Thursday is 30. He skips Friday → Saturday and Sunday add nothing and are not asked → Monday is 60. He studies 30 on Saturday of his own accord → Monday is 30.

A Tuesday that ended with no recorded minutes means the next weekday morning owes 60. A same-evening silence is not a `none` file. It still counts as unpaid once that weekday is over.

## Morning line

Compute today's due first. Monday–Friday only, in the ritual message after the focus question. No debt:

```text
Учёба: сегодня 30 минут. Вечером спрошу, что выучил и в какую задачу это пойдёт.
```

With debt (`carryIn` 30, due 60):

```text
Учёба: сегодня 60 минут, из них 30 перешло. Вечером спрошу, что выучил и в какую задачу это пойдёт.
```

Use the computed numbers. The line does not need an answer. A morning reply that only accepts the reminder does not create a study file.

Mon–Fri: `morning-checkin` must not send the ritual message without this line and today's due. If the draft lacks it, insert it first. Saturday and Sunday: omit the line.

## Evening block

Monday–Friday only. Name today's due:

```text
Отдельно про учёбу, сегодня 60 минут: удалось поучить? Сколько минут и что именно выучил? К какой цели и какому проекту это, в какую задачу уже внедрил или внедришь в ближайшее время, когда и зачем? Если не учился — так и напиши.
```

When `carryIn` is 0 the number is 30. Saturday and Sunday: do not append this block.

## Parse and write

1. Study is learning he names as учёба / выучил / прочитал / разобрал материал. Focus-task progress and routine work are not study unless he says he was learning.
2. Preserve his words for what he learned, where it goes, and why. Light STT cleanup only.
3. Convert exact hours to integer minutes (`полчаса` = 30, `час` = 60). Do not round «около часа» or any vague duration; ask.
4. Several topics with one total duration stay one item. Do not invent a split.
5. `totalMinutes` is the sum of item minutes only when every item has minutes; otherwise `null`. Before writing, compute **Balance** for this date. Set `accruedMinutes`, `carryIn`, `dueMinutes`, and `targetMinutes` (`targetMinutes` equals `dueMinutes`). `carryOut` is null while `totalMinutes` is null. `metTarget` is `true` only when `totalMinutes` ≥ `dueMinutes`, `false` when the sum is known and below the due, `null` when minutes are missing. A day under the due can still be `complete`. `specVersion` on a new or updated day on or after `accrueFrom` is `1.1.0`.
6. Goals are only `catalog.json` → `board.goals`. Match the one he named. A phrase in `board.goalAliases` matches that goal when it is the only goal those words fit. Silence is not a goal. Two goals could fit → ask.
7. Match `Проект` in live Проекты. Do not offer a `Paused`, `Done`, or `Cancelled` project (see `board.paused`). If he names one of those, use it. Two projects could fit → ask. Do not create a project.
8. Match `Задачи` he named, under that project when he named one. Two cards could fit → ask. Link every task he named. Do not check `Фокус сегодня`, do not change `Горизонт`, and do not set `Приоритет` on an existing task.
9. A new study topic or exercise («задача по учёбе», «тема», «упражнение», or he asks to add one for study) is **Study topics**. Write that card in this same run. Do not call `create-task`. Do not ask project, parent, horizon, or priority. Do not put it on «Фокус сегодня». It is not a row in Задачи. Do not write it into the day's «Фокус» `План`, `Итог`, `Корректировка`, `Порядок фокуса`, or `Задачи`. Study never becomes focus.
10. Linking what he learned to work is only an existing Задачи card he named. Do not create a Задачи row because he studied or because he named a study topic. If that card is missing from the evening answer, the clarification asks which existing task, or he can say there is none. It never asks project, parent, horizon, or priority.
11. `application` is his words for when and where. `applicationWhen` is `implemented` when he said he already applied it, `willImplement` when he said he will soon. Do not pick one from silence.
12. `purpose` is his «зачем». Do not infer it from the task title.
13. `tasksDeclined` is `true` only when he says not to attach a work task («задачу не заводи», «пока без задачи»). A study-topic card is not that decline and not that attachment. Otherwise a missing work task stays a question, without the four `create-task` fields.
14. Merge into the existing day file. The same `what` (case and whitespace folded) updates that item. A day item is not a Notion card.
15. Set `source` to `telegram`, `voice`, or `chat`.

### Status

- `none`: he explicitly said he did not study. `items=[]`, `totalMinutes=0`. `metTarget` is false when `dueMinutes` > 0 and true when nothing was owed. No topic card for that answer. `carryOut` equals `dueMinutes`.
- `complete`: every item has `what`, minutes, one goal URL, one project URL, either at least one task URL or `tasksDeclined=true`, `application`, `applicationWhen`, and `purpose`. `notionPageUrl` stays null. `totalMinutes` equals the sum.
- `partial`: some facts are usable but a required field is missing.
- No study answer at all, on a Mon–Fri evening: do not create a file and do not treat silence as `none`. Ask the full block once, in one clarification. Saturday and Sunday silence stays silence. The next morning still counts that closed weekday as 0 studied.

Write every usable fact even when the entry is partial. Then one clarification with every missing field, combined with a pending ritual or routine clarification. Do not send one question per field.

```text
По учёбе не хватает: минут; к какой цели и проекту; в какую уже существующую задачу внедрил или внедришь, когда и зачем.
```

That question is about an existing work card. It is not an offer to create one. A study topic he named in the same reply is already the flat card; do not add it to this clarification.

## Study topics

A study topic is a flat card in the one database «Учёба», `catalog.json` → `study.notionDataSourceUrl`. There is no second database. Do not create «Темы учёбы». Git list: `study/topics.json`. Array order is the sequence.

One card is one topic or one exercise. The only property is `Тема`, his title. No priority, parent, horizon, project, goal, status, date, or minutes. Do not ask for those. Do not propose a parent. Do not group cards. Do not add columns. Hierarchy waits until he asks.

The page body is the learning that belongs to that card: his description, the materials, and every link he gave. Do not split that into Задачи, a task comment, a free note, `journal`, or `routine`. Do not invent links or a description he did not give.

Study is one topic a day, taken in this list order. Do not rank the list and do not pick a later card ahead of an earlier one.

Append in the order he names them. Several topics in one message stay in that spoken order. The same title (case and whitespace folded) updates that card's body. Do not add a second card.

Write:

1. Read `study/topics.json`. Append or update the item: `title`, `body`, `notionPageUrl`, `added` (Europe/Moscow date). `spec` is `study-topics`, `specVersion` is `1.0.0`.
2. `notion-create-pages` on `study.notionDataSourceUrl`. Property `Тема` only. Content is `body`. On a later addition to the same topic, `notion-update-page` that page.
3. Re-fetch the page. The parent database is «Учёба». `Тема` and the body must match. The data source schema is still only `Тема`. Copy that page URL into `notionPageUrl`. Do not say the card is saved until that read matches. A failed Notion write still keeps the git row; say the board write failed.

Confirm in one clause: `Тема учёбы: «Название темы». В учёбе.` This does not run `task-trees`. It is not today's focus.

Naming a topic does not by itself write `study/entries/`. A day entry is what he already studied. A topic he wants next is only the list.

## Notion

«Учёба» is only the flat topic list above. A day's study report does not create a row. Minutes, goal, project, task, application, and purpose stay in `study/entries/`. `notionPageUrl` on a day item stays null.

Do not add columns. Do not recreate «Темы учёбы». Do not put study text in a task comment, and do not edit a goal page or a project page. The work task he names stays in the day file.

## Confirm

After a write, one short clause in the ritual confirm:

```text
Учёба записана: 40 минут из 60. «что выучено», цель / проект, задача «название», внедришь завтра. Завтра 50 минут.
```

Name the gap against today's due, then the next reminder: `20 минут из 60. Завтра 70 минут.` No study on a day that owed minutes: `Учёбы сегодня не было. Завтра 60 минут.` The due was met and nothing carries: `Учёба записана: 60 минут. Завтра снова 30.` Friday with a shortfall: `Учёбы сегодня не было. В понедельник 60 минут.` A new topic in the same reply is its own clause: `Тема учёбы: «Название темы». В учёбе.` If Notion did not stick, say so in the same clause. No JSON names, no URLs. Do not name the next total while `carryOut` is null.

A study report does not close a focus-day evening. Minutes on a focus task are still required for that slot.

## Verify

Before saying study is written:

- JSON parses; filename date equals `date`; `weekday` matches Moscow.
- `spec=study` and `specVersion` is `1.1.0` on a day on or after `accrueFrom` written in this run.
- `accruedMinutes` is 30 on Mon–Fri and 0 on Sat–Sun. `targetMinutes` equals `dueMinutes`. `dueMinutes` equals `carryIn + accruedMinutes`. With integer `totalMinutes`, `carryOut` equals `max(0, dueMinutes - totalMinutes)`. The walk in **Balance** produces the same `carryIn`.
- `none` only after an explicit no-study answer, and no topic card was created for it.
- On `complete`, every item has the fields in **Status**, `notionPageUrl` is null, and `totalMinutes` is the sum.
- A topic write: `study/topics.json` parses, `spec` is `study-topics`, the new title is last unless it updated an existing one, and the re-fetched page is in «Учёба» with that `Тема` and the same body. The data source schema is still only `Тема`. «Темы учёбы» was not created.

## Git

Study entries are operational data. After a real write:

1. `git add study/entries/` — nothing else.
2. Commit (`Study YYYY-MM-DD recorded` or `Study YYYY-MM-DD none`).
3. `git fetch origin master`.
4. Land the commit on `master` and `git push origin master`.
5. Do not wait for «ок». If the push fails, say so in the same reply.

If the same run writes `ritual/`, `journal/`, `routine/`, or `notes/`, make a separate commit. Do not mix skill, spec, catalog, or README changes into a study-entry commit.

A topic-list write is its own operational commit when it is the only change:

1. `git add study/topics.json` — nothing else.
2. Commit (`Study topic «…»`).
3. `git fetch origin master`.
4. Land that commit on `master` and `git push origin master`.
5. Do not wait for «ок». If the push fails, say so. Do not mix it into a day-entry commit or into a skill commit.

## Hard rules

- Do not invent minutes, topics, goals, projects, tasks, or a purpose.
- Do not create a Задачи row for a study topic. Do not ask project, parent, horizon, or priority for one.
- Do not create a second study database. Do not add properties to «Учёба». A day report is not a card.
- Do not mark a focus task Done because he studied for it.
- Do not file study as a free note, a diary line, or routine work.
- Do not send a separate study questionnaire after the evening message.
- Saturday and Sunday: do not ask. Record only what he volunteered, and let those minutes pay the carry down. Do not add 30.
- Do not write `none` from silence on the same evening. Once that weekday is over, **Balance** counts it as 0 studied. Do not pull days before `accrueFrom` into the debt.
