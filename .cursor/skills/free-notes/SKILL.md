---
name: free-notes
description: Saves the owner's free notes — ideas, experiences, views, and any other thought that is not task tracking, the health diary, or a note about how the day went. Use when a Telegram message or a chat in this repo contains such a thought, or when he asks to save a note.
---

# Free notes

One thought = `notes/entries/YYYY-MM-DD-HHMM.md` (Europe/Moscow). Read `notes/notes.spec.json` before writing.

This folder is not:

- task tracking (focus, minutes, progress, the «Фокус» board, a comment on a Задачи card);
- the health diary (`journal/`);
- the diary line «заметка о дне» (`journal` `notes`: how the day went);
- routine work (`routine/`);
- study (`study/` and the Notion database «Учёба»);
- the Notion database «Идеи».

## When this runs

| Trigger | What to do |
| --- | --- |
| `telegram-feedback` | Split the same reply. Save only the clauses that are free notes. Confirm in the reply he already gets. |
| `morning-checkin` / `evening-review` | Do not ask for a note. If an inbox reply contains one, follow this skill. |
| Ad-hoc in this repo | He said a free note, or asked to save one. Write the file. Do not message Telegram unless he asked to send it there. |

Sunday saves notes too. The day being diary-only does not drop a thought.

## Classify first

Go clause by clause. Each clause has one home. Do not copy it into a second one.

| The clause is | Home | Not a file in `notes/` |
| --- | --- | --- |
| Focus pick, minutes, progress, done, a task he asked to create, day-level «мешало» about the work | `telegram-feedback` | yes |
| A thought clearly about a task he named, or the one open focus card | Notion comment on that card | yes |
| Routine work, its minutes, distraction, «рутины не было» | `routine-log` | yes |
| Study: what he learned, study minutes, which goal, project, or task it applies to, «не учился» | `study-log` | yes |
| Sleep, energy, scores, mood, training, food, substances, what he read, watched, or listened to, any other health-diary item | `life-journal` | yes |
| How this day went: «день нормальный», «весь день тревожно», «закрытие сезона», the survey line «Заметка о дне» | `journal` `notes` | yes |
| An expense, income, transfer, debt, or account balance | `econumo` | yes |
| An idea, a recounted experience that is not "how today went", a view, a principle, an observation he is telling, anything of that kind | this folder | — |
| A decision on a due Notion idea («в задачу», «отложить» на дату, «отвергнуть», «это проект») | `telegram-feedback` → Idea decision | yes |
| A command («добавь», «трекай», «поменяй»), «ок», «пропустил», «потом», a greeting with no thought | nowhere | yes |

«Явно не относится» is the gate. Save when the clause is clearly outside task tracking, the health diary, and the day note. Do not save a clause that might still be one of those three.

A past experience or a lesson («когда жил один, понял…») is a note. A description of today is the day note.

Two possible task cards and the clause is about the work → ask which card, as `telegram-feedback` already does. Do not also file a note. If he then says it was just a thought, save it.

He asked to save it («запиши заметку», «заметка:», «сохрани мысль») → this folder, even if a task title is nearby. Do not also comment that text on the card unless he tied the thought to the task.

Do not ask «сохранить как заметку?». A clear thought is saved. A clear account is not.

## Write

1. One file per thought. Several unrelated thoughts in one message → several files. Several sentences of one thought → one file.
2. Time is Europe/Moscow, from `received_at` when the relay sent it, otherwise now. Name: `notes/entries/YYYY-MM-DD-HHMM.md`. If that file exists and the body differs, use `YYYY-MM-DD-HHMM-2.md`, then `-3`.
3. Quote him. Light STT cleanup only (`ну`, `вот`, `э` dropped when they carry nothing). Do not summarize into a nicer sentence. Do not add what he did not say.
4. The heading is a short Russian phrase from his point, not a second essay. If he named the note, use his name.
5. Same calendar day and the same body (whitespace and case folded) → do not write again.
6. Set `source` to `telegram` or `chat`, and `input` to `text` or `voice`.

```markdown
---
captured: 2000-01-01T12:00:00+03:00
source: telegram
input: voice
---

# Пример мысли

Короткая мысль своими словами.
```

Optional `messageId` when the relay gave one. Dedup is by the body, not by that id: one message may hold two notes.

## Examples

- «По задаче 30 минут, ещё не готово» → task only. No file.
- «День нормальный, закрывал сезон» → `journal` `notes` only.
- «Сон 7, качество 6, энергия 5» → diary only.
- «Сегодня слушал подкаст про сон» → diary `media` only.
- «По задаче 30 минут. Отдельно: занятость — это не работа» → 30 minutes on the task; the second sentence is a note. Do not put it on the task card.
- «Сегодня ничего. Просто думал: привычка важнее настроения» → focus «сегодня ничего». If a VPN task uniquely matches and he is talking about that work, comment on the card and do not file. If no card matches, file the thought. Do not ask which card.
- «Запиши заметку: привычка важнее настроения» → a note, even if a VPN task exists.
- «Ок» / «привет» / «добавь в дневник <вещество>» → no file.

## Confirm

Telegram, inside the reply he is already getting. One short clause, no path, no «репо»:

```text
Записал заметку: привычка важнее настроения.
```

Several: «Записал заметки: … и ….» A duplicate of a file already stored today: «Заметка уже есть: ….» If the write failed, say so in that same message.

In this chat, say that it was saved and name the file. Do not send Telegram unless he asked.

A note does not close a ritual slot and does not answer a diary item.

## Verify

Before saying it was saved:

- the file is under `notes/entries/`;
- the filename date and time match `captured` in Europe/Moscow;
- the heading and the body are his, not a paraphrase that adds meaning;
- the body is not a task recap, a diary score, or a how-the-day-went note;
- no second file today has the same body.

## Git

Note files are operational data, like ritual and the diary. After a real write:

1. `git add notes/entries/` — nothing else.
2. Commit (`Note YYYY-MM-DD-HHMM saved`).
3. `git fetch origin master`.
4. Land the commit on `master` and `git push origin master`.
5. Do not wait for «ок». If the push fails, say so in the same reply.

If the same run also wrote `ritual/`, `journal/`, or `routine/`, make a separate commit for the note. Do not mix skill, spec, catalog, or README edits into that commit.

## Hard rules

- Do not invent a thought he did not tell.
- Do not save task accounting, the health diary, or a note about how the day went into this folder.
- Do not copy a saved note into a Notion comment, into `journal` `notes`, or into `routine/`.
- Do not create a Notion page, an «Идеи» row, a project, or a task from a note.
- Do not ask a survey-style question in order to collect notes.
