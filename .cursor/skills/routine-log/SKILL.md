---
name: routine-log
description: Records the owner's ordinary work outside Personal OS focus tasks: activities, minutes, and how much it distracted him. Use during an evening review or when a Telegram reply reports routine work.
---

# Routine work log

One calendar day (Europe/Moscow) = `routine/entries/YYYY-MM-DD.json`. Read `routine/work-routine.spec.json` and the existing day file before asking or writing.

This log is separate from:

- focus tasks and the «Фокус» board in Notion;
- the ritual transcript in `ritual/`;
- scores and substances in `journal/`.

## When this runs

| Trigger | What to do |
| --- | --- |
| `evening-review` | Include the routine block in the same ritual question as the focus recap. Do not send a third questionnaire. |
| `telegram-feedback` | Parse routine facts from the same reply, write the day file, and ask one compact clarification if the routine block was omitted or required fields are missing. |
| Ad-hoc in this repo | Fill or verify a named day from the owner's words. Do not message Telegram unless he asked. |

## What to ask

Use this block in the evening ritual:

```text
Отдельно про рабочую рутину вне фокуса: что делал по рабочим проектам и сколько минут или часов ушло на каждую часть? Насколько это отвлекло от фокус-задач — 1 почти не отвлекло, 2 заметно, 3 сильно. Если рутины не было — так и напиши.
```

The routine block belongs in the ritual message. The life-journal questionnaire remains a separate second message.

## Parse and write

1. Routine means ordinary work outside the Personal OS focus tasks tracked in Notion. Do not copy focus progress into this log unless the owner explicitly calls it routine work.
2. Preserve his project names and descriptions. `project` is optional; do not invent the names of his two work projects.
3. Convert exact hours to integer minutes. Do not round or estimate vague durations.
4. Each activity gets its own minutes when he supplied a breakdown.
5. If he described several activities but supplied only one total duration, store one combined activity. Do not invent a per-project split.
6. `totalMinutes` is the sum of all non-null activity minutes only when every activity has minutes; otherwise it is `null`.
7. `distraction` is one integer 1–3: how much the routine pulled him off focus. Do not ask how much strength it took. Do not infer the score from words such as «нормально» unless he tied the words to the scale anchors in the question. A second score («силы», «вымотало») is not stored. If he gives both and they differ, keep the one he tied to отвлекло; if neither number is labeled, ask once which is the distraction.
8. A new day is `specVersion` `1.1.0` and has no `energyDrain` key. A file that already has `energyDrain` stays as it was; do not strip it and do not ask for it again.
9. Merge into an existing file without duplicating activities or wiping earlier facts.
10. Set `source` to `telegram`, `voice`, or `chat`.

### Status

- `none`: he explicitly said there was no routine. Write `activities=[]`, `totalMinutes=0`, and `distraction` as `null`. Do not write `energyDrain`.
- `complete`: at least one activity has a description and minutes, `distraction` is present, and `totalMinutes` equals the activity sum.
- `partial`: some routine facts are usable but description, any activity's minutes, or `distraction` is missing.
- No routine answer at all: do not create a file or interpret silence as `none`; ask the full routine block once more in one compact clarification.

Write every usable fact even when the entry is partial. Then ask **one** clarification containing every missing routine field, not one message per field. Combine it with a pending ritual clarification when practical. Do not repeat the life-journal questionnaire.

Example:

```text
По рутине не хватает: времени на поддержку второго проекта; оценки, насколько всё отвлекло (1–3).
```

## Confirm

After a complete write, confirm briefly with human labels:

```text
Рутина записана: 210 минут, отвлекала на 2 из 3.
```

This may be part of the normal evening confirmation. Do not expose JSON field names in Telegram.

## Verify

Before saying the routine is written:

- JSON parses;
- filename date equals `date`, and `weekday` matches the Moscow calendar;
- `spec=work-routine`. A day written in this run is `specVersion` `1.1.0` and has no `energyDrain` key. An older file may stay `1.0.0` with `energyDrain`;
- minutes are positive integers for activities; `totalMinutes` equals their sum on a complete day;
- `distraction` is an integer in 1–3 on a complete day, and null when status is `none`;
- `none` appears only after an explicit no-routine answer;
- the file contains no focus-task or diary fields.

## Git

Routine entries are operational data, like ritual and life-journal entries. After a real write:

1. `git add routine/entries/` — nothing else.
2. Commit (`Routine YYYY-MM-DD recorded` or `Routine YYYY-MM-DD none`).
3. `git fetch origin master`.
4. Land the commit on `master` and `git push origin master`.
5. Do not wait for «ок». If the push fails, say so in the same reply.

If the same run writes `ritual/` or `journal/`, make separate commits. Do not mix skill, spec, catalog, or README changes into an operational routine-entry commit.

## Hard rules

- Do not invent work, project names, minutes, or ratings.
- Do not write routine work to Notion.
- Do not map routine distraction to life-journal `work`, `mood`, `energy.morning`, `energy.evening`, or any other diary score. Do not ask a second routine score for strength or fatigue.
- Do not send a separate routine questionnaire after the evening message.
