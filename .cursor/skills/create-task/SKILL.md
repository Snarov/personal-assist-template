---
name: create-task
description: Creates a row in the owner's personal Задачи only after project, parent task, horizon, and priority are collected or, if he delegates, determined. Use on every path that creates a work task, including an idea becoming a task, morning, and reclassifying a project into a task. A study topic or exercise is not this skill.
---

# Create task

The only way to add a row to Задачи (`catalog.json` → `notion.tasksDataSourceUrl`). Notion only through `notion-personal`. Another skill that needs a new work task follows this one and does not write the row itself.

A study topic, exercise, or «задача по учёбе» is not a row here. `study-log` writes it as a flat card in «Учёба»: the title only, and the learning, materials, and links on the card. No project, parent, horizon, or priority. Do not ask those fields. Do not create the Задачи row.

Do not create a task he did not ask for. An idea becomes a task only when he said so and named the project. A tail reuses the open card.

## Required on the card

The row is created only when all of these are resolved. A silent default is not resolved.

| Field | Resolved when |
| --- | --- |
| `Задача` | He named the title, or the idea title when he did not name another |
| `Проект` | He named one existing project |
| `Родительская задача` | He named the parent, or he said there is none («без родителя», «верхняя», «сама по себе») |
| `Горизонт` | He named Год, Квартал, Месяц, Неделя, or День |
| `Приоритет` | He named `Максимальный`, `Высокий`, `Средний`, or `Низкий`. `Максимальный` is above `Высокий`. «Важная» and «главная» are not a level |

Also set, without a separate question:

- `Статус=Not started`, unless he named another status in this same decision. If this same reply also picks the task as today's focus, `Статус=In progress`. When the new row is `In progress`, the same write applies `.cursor/rules/task-relations.mdc` → **Родитель в работе**: every ancestor that is `Not started`, `Запланировано`, or empty becomes `In progress`. Do not reopen `Done` or `Archived`. Do not change the ancestor's horizon, priority, срок, or focus. Re-fetch each ancestor and say which parent stayed unchanged if a write failed.
- `Фокус сегодня` checked only when this same reply picks the task as today's focus. A study topic is not this skill and is never today's focus.
- Page body is his words: the idea `Суть` when that is the source, otherwise the sentence he gave. Nothing else.
- Set `Срок` when he named a calendar box. The map is `.cursor/rules/task-nudges.mdc` → **Срок при создании**. «На октябрь» is that box: the month range, and `Горизонт=Месяц` when he did not name another horizon. A bare «месяц» / «неделя» / «квартал» / «год» does not set `Срок`. Do not overwrite a `Срок` that is already set. Do not set `Оценка (ч)`, `Декомпозиция`, `Порядок`, `Исполнитель`, or `Уровень периода` unless he named them. `Горизонт` is the only horizon. `Проект` is exactly one project, the nearest he named. If that project has `Родительский проект`, do not also add the ancestor. The tasks roadmap nests by `Родительская задача` and does not group by `Проект`; a second project link repeats the card.

Search Задачи for that title first. If the card already exists, do not create a second one. Leave a filled `Горизонт`, `Приоритет`, `Проект`, or `Родительская задача` as it is. If one of those four is empty on that card, ask once whether to fill the empty ones. Do not overwrite a value that is already there.

## Collect

Read what he already said in this decision. Do not ask again for a field he named. A named month, week, or quarter answers `Горизонт` as in `.cursor/rules/task-nudges.mdc` → **Срок при создании**, and that same create writes `Срок`. Do not ask the horizon line again. A single date does not answer horizon.

Anything still open is one question, in the same Telegram or chat reply, listing only the gaps. Do not create the row in that turn. Do not send one message per field.

```text
Задачу ещё не завожу.
Проект — <проект из catalog.json → board.projects>.
Родитель: «<предложенная задача>» или без родителя?
Горизонт: год, квартал, месяц, неделя, день?
Приоритет: максимальный, высокий, средний, низкий?
```

Drop a line he already answered. If no parent is proposed, ask «Какая родительская задача, или без родителя?» If the project is missing, ask which project and do not offer a `Paused`, `Done`, or `Cancelled` project (see `catalog.json` → `board.paused`). If he names one of those himself, use it. Two projects could fit → ask. Do not guess a project from `Суть`.

Before the question, run `.cursor/rules/task-relations.mdc`. One obvious decomposition parent — this card is a smaller part of a bigger task already on the board — is named in the question as the proposal. Two parents that both fit → ask which, with no proposal. Not a piece of a bigger task → ask «без родителя или какая задача?». A time sequence and a finished research card are not that parent. Do not write `Родительская задача` until he picks or delegates.

An idea stays on its current status until this skill has created the row. A study row stays without that task link until then. A project card is not deleted until the replacement task is on the board.

## Worst case: determine

Only when he delegates the missing fields («сам», «как считаешь», «поставь», «неважно», «на твоё») or tells you to create the card anyway without answering them. Still refuse to pick between two real options: ask that one field.

- **Проект.** The one project this decision already named. If he delegated and exactly one live project is what the conversation is about, use it. Two projects → ask. Never from `Суть` alone.
- **Родительская задача.** The one decomposition parent from task-relations. Not a piece of a bigger task → leave it empty and treat that as «без родителя». Two possible parents → ask. Do not hang the card on a finished research task or on the previous step in time.
- **Горизонт.** A named calendar box already resolved it (`.cursor/rules/task-nudges.mdc` → **Срок при создании**), including a future month. Otherwise the parent's horizon when the parent is set. Otherwise `Год`. `Месяц` only when he put this task on a month, or the parent is already `Месяц`. Do not infer `Месяц` from `In progress`.
- **Приоритет.** Do not invent a level. Full rule: `.cursor/rules/priorities.mdc`. If he delegated and the parent already has a `Приоритет` he set, copy that level and say so. If the parent has none, still ask which of the four and do not create the row. Never set `Высокий` or `Максимальный` because the task is today's focus.

Say in the confirm which fields were his and which were determined. He can correct them in the next reply; until then the card holds these values.

## Write

1. Create the row with the resolved properties and the body above. `Родительская задача` is a relation on the new page, not a move. `Проект` is that one project URL, not the project plus its ancestors.
2. Re-fetch the row. Title, project, horizon, priority, and status must match. `Проект` is one URL. Parent must match, or be empty only when the resolution was «без родителя».
3. Run `task-trees` before the reply.
4. If this task came from an idea, set that idea `Статус=Стала задачей` and `Задача` to this page only after the re-fetch is clean. Follow **Idea decision** in `telegram-feedback` for the rest of the idea write. That row is the consideration, not the delivery. Do not put the delivery horizon on it.

## Idea research, then the work

A row created because an idea became a task is the short research. `Done` on it means the review finished.

When he says that review is done and the accepted work should be planned, keep that card as the research. If the delivery needs the idea title, rename the research so the title says it is the research. Horizon of the research is the short box he named, or `День` when he called the review short and named the longer horizon only for the follow-up. When the calendar box he named belongs to the follow-up, put `Срок` there. The research keeps the day of the review when that day is already known from the card or the journal.

Create each follow-up through this skill. Parent is the bigger task this follow-up is a piece of, when that bigger task is already on the board. The consideration card is not the parent: work created after the research is finished does not hang on the research. A later step in time is not a parent. If he did not name a parent and the follow-up is not a piece of a bigger task, leave `Родительская задача` empty. Body of the follow-up is the spec and plan already written, in his words. Body of the consideration card becomes the short recap plus a mention of the follow-up. The idea's `Задача` relation stays on the consideration card. Do not create a follow-up while its horizon, calendar box, or priority is still open: ask once.

Confirm in his language: title, project, parent or «без родителя», horizon, priority. If a write failed, say the task was not created and leave the idea on its current status.
