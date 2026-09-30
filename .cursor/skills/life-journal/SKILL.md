---
name: life-journal
description: Fills, verifies, and profiles the owner's daily life-control journal (оценки, сон, питание, вещества). Use during morning/evening check-ins, on a Telegram reply that includes scores, or whenever he asks about the дневник, журнал, профиль дневника, or to fill/check a day. The stack to ask is journal/profile.json, not this file.
---

# Life journal

Daily observation from `journal/life-control.spec.json`. Not the ritual MD in `ritual/`, not Notion tasks.

One calendar day (Europe/Moscow) = `journal/entries/YYYY-MM-DD.json`. Month extras = `journal/months/YYYY-MM.json`. What to ask = `journal/profile.json`. **How to ask** = `journal/survey-script.json`. **Where we are** = `journal/survey.json`.

Read the spec + profile + script + survey state + the day file **before** asking or writing. Do not copy `sourceTemplate` (чужой стек).

`git fetch origin master` first and read `journal/survey.json` / day files from there. Cloud snapshots lag the last ritual write.

## Do not duplicate a live survey

If `survey.json` on master is `awaiting` and `date`/`slot` match the wave you were about to send, do not `POST /send` that questionnaire again. It is already in the chat. A `/send` that times out or returns no body may already be in Telegram: the relay often needs about 30 seconds, and a 30-second client gives up at the same moment. Do not POST that same text again and do not reword it to force another copy. Wait at least 90 seconds for the call. Within 15 minutes the relay answers an identical retry with `duplicate: true` and does not create a second message. Treat that as delivered. Only send:

- a missing-items follow-up after parsing a reply that left gaps of **that same sent list**, or
- today's morning wave as a **second** `/send` while yesterday's catch-up is already awaiting (do not replace `survey.date` / `slot` / `missing`), or
- a new wave after the previous one closed.

A ritual-only reply while awaiting is not a send trigger. Trailing voice messages for the same wave go into the day file, not into a second copy of the list.

## What this is

Two Telegram waves per day, each one numbered questionnaire answered in one message:

- **Утро** — ночь, последний приём пищи и компьютер перед этим сном, энергия и настроение в начале дня и то, что уже было с утра: ядро из `morningOrder` плюс пункты `journal/profile.json` → `waves.morningEarly` и `waves.morningLate`. Часы сна считает агент.
- **Вечер** — энергия и настроение в конце дня и пункты, которых ещё нет в записи дня: оценка дня, работа, тренировка, люди (были ли, кто и как повлияли: раздражали, нейтрально или вдохновляли), пункты `waves.evening`, еда, заметка. Голод, профицит и дефицит — не отдельные пункты: их можно дописать в ответ про еду. Чтение и просмотр — необязательная строка без номера: сколько минут ушло и что именно читал, слушал или смотрел. Пропуск не догоняется. Утренние пункты профиля, медитация, чтение установок, сон, последний приём пищи, компьютер, энергия утра и настроение утра — только если утро их не закрыло. Уже записанный утренний ответ вечером не повторять. Витамины, сигареты, ноотропы и прочие обычные вещества не входят ни в одну волну.

Sleep happens at night, so it is asked in the morning: bedtime, wake time, and quality 1–10. The agent writes the hours; he does not. The last meal before that sleep and the time he finished computer work before that sleep are the next morning lines, both clock times. They are recorded so later statistics can relate a late meal and late computer work to that night's sleep quality. Do not invent that link while writing the day. Morning energy and morning mood are how he feels at the start of the day; evening energy and evening mood are the end-of-day readings. Mood uses the same 0–4 scale at both ends. Оценка дня, работа, тренировка, люди (who and how they affected him, see **Люди**), the ids in `waves.evening`, еда, заметка are the lived day, so they wait for the evening. Чтение и просмотр is an optional unnumbered evening line: minutes and what he read, listened to, or watched. Skipping it does not reopen the survey. It is not the attitudes line and not the study report. Hunger, surplus, and deficit ride inside the food answer and are not their own lines. Profile items on the morning waves, plus медитация and чтение установок, are asked in the morning for what already happened. A usable answer closes them. The evening asks one of these only when the morning left it empty. A new value he states later overwrites the morning one.

If he misses fields, send one follow-up containing **all** still-missing lines of **that sent wave**. Never send one Telegram message per item. Never mix yesterday and today in one questionnaire. Never add items that were not numbered in a questionnaire already sent for that date.

No spreadsheet jargon: never «эфф», «work 0–3», «tr», «soc», «Sle», «Пустое ≠ 0».

The old one-liners are forbidden. Do not send them:

```text
Дневник: вчера без эфф или сна. Напиши оценки или «потом».
Дневник: эфф 1–10, work 0–3, mood 0–3, tr 0–2, soc нет/было/круто.
```

## When this runs

| Trigger | What to do |
| --- | --- |
| `morning-checkin` | Ritual message has **no** diary scores. After the brief: if yesterday is not survey-done, send yesterday's catch-up (or skip if that list is already `awaiting`). Then, if today's morning queue is still open, send today's morning wave as a separate `/send`. The queue is open when `sleep` (bedtime, wake, and numeric quality), `lastMeal`, `lastComputer`, `energy.morning`, or `mood.morning` has no usable value, unless that date was already closed under an older list. Two dates = two messages. Do not replace an awaiting yesterday pointer with today. |
| `evening-review` | Ritual message has **no** diary scores. After the progress `/send`, send today's evening wave. |
| `telegram-feedback` | Same reply may contain focus/minutes **and** diary. Split them. A burst may fill yesterday and today. If a survey is `awaiting`, parse every listed answer onto the date he named. Write what is usable. Follow-up only the primary awaiting wave, using that wave's sent items — not a rebuilt `requiredOrder`. If a catch-up closes in the morning and today's morning queue is still open and was never sent, send today's morning wave. |
| Ad-hoc in this repo | Fill a named day (default: today Moscow), verify recent files, or edit the profile. He may speak in chat, not Telegram. Do not spam Telegram unless he asked to send the survey there. |

Diary waves run **every day**, including Sunday. The Notion/focus ritual does not: on Sunday `morning-checkin` and `evening-review` skip Notion, `ritual/`, and `routine-log`, and only send the diary wave.

Do not backfill days before `catalog.json` → `lifeControl.askFrom`. Do not mark those days missed.

## Tools

- Files: `journal/`. No Excel, no Notion database for this diary.
- Telegram only through the ritual skill that called you (`kind=morning|evening|reply`). Survey follow-ups: `kind=reply` (do not change `last_kind`).
- One `/send` per wave. Never split its items across Telegram messages.

## Survey state (`journal/survey.json`)

```json
{
  "status": "idle" | "awaiting" | "paused",
  "date": "YYYY-MM-DD" | null,
  "slot": "morning" | "evening" | "catch-up" | null,
  "missing": [],
  "paused": false,
  "days": {
    "YYYY-MM-DD": {
      "asked": [],
      "answered": [],
      "cleared": [],
      "complete": false
    }
  }
}
```

- `idle` — nothing in flight.
- `awaiting` — the **primary** questionnaire (`date` / `slot`) is in the chat. `missing` is exactly the unanswered ids from **that sent list**, in the order they were numbered. This is the follow-up contract. Do not rebuild it from the current `requiredOrder`.
- `paused` — he said «потом» / «не пиши дневник» this slot. Do not nag again **in this slot**. Next morning/evening may resume with the wave due then.
- `days[date].asked` — union of item ids numbered in questionnaires already sent for that date. Write it when you send. A follow-up never adds new ids here.
- `days[date].answered` / `cleared` — day-final answers (value / explicit «нет»). `complete=true` when every id in `asked` is in one of them. If `asked` is missing (legacy day), fall back to `requiredOrder`. Keep the latest 31 days.

`survey.date` / `slot` / `missing` is one primary pointer — usually the oldest open day. Today's morning wave may already be in the chat at the same time: record it on `days[today].asked` and do **not** move the pointer off yesterday. An evening send for today replaces a still-awaiting morning survey **for today only**.

Commit `survey.json` with the journal write (same commit as the day file). If you only asked the questionnaire and wrote no answers, still commit `survey.json` with the journal git ritual (`Journal YYYY-MM-DD survey sent`).

## Queue

Required items, in this order, from `survey-script.json` → `requiredOrder`:

1. сон (`sleep`) — время отхода, время подъёма **и** качество 1–10. Часы пишет агент
2. последний приём пищи (`lastMeal` → `nutrition.lastMealAt`) — во сколько перед этим сном
3. компьютер (`lastComputer` → `sleep.lastComputerAt`) — во сколько закончил работу за компьютером перед этим сном
4. энергия утром (`energyMorning` → `energy.morning`)
5. настроение утром (`moodMorning` → `mood.morning`)
6. энергия вечером (`energyEvening` → `energy.evening`)
7. настроение вечером (`moodEvening` → `mood.evening`)
8. оценка дня (`effectiveness`)
9. работа (`work`)
10. тренировка (`training`)
11. `@profile.morningEarly` — ids from `journal/profile.json` → `waves.morningEarly`, in that order
12. медитация (`meditation` → `meditation.minutes`)
13. чтение установок (`attitudes` → `attitudesRead`)
14. люди (`social`)
15. `@profile.morningLate` — ids from `waves.morningLate`, in that order
16. `@profile.evening` — ids from `waves.evening`, in that order
17. еда (`food` → `nutrition.what`; голод, профицит и дефицит в том же ответе необязательны и не нумеруются)
18. заметка (`notes`, «нет» is a valid answer)

Expand every `@profile.*` token before numbering the Telegram list. The `line`, `accept`, and `reject` for those ids live on the matching `customSlot` or `intake`. Core items stay in `survey-script.json` → `items`. Do not hardcode the profile labels in the questionnaire.

`lastMeal` and `lastComputer` are the «когда последний раз» marks. Both sit on the same night as `sleep.quality` so a later pass can relate a late meal and late computer work to that sleep. The morning header states this once. Do not write the purpose into `notes` or `comments` unless he said it himself.

`mood` and `ateBeforeSleep` are not in this order. Their lines stay in `survey-script.json` → `items` only for a follow-up of a list that already numbered them. Do not put either id on a new questionnaire.

`oneOffSubstances` is not in this queue. Do not number it, do not add it to `morningOrder` / `requiredOrder` / `asked` / `missing`, and do not follow up for it.

`media` is not in this queue. On the first evening send and the first catch-up send, append `items.media.line` once, unnumbered, after the numbered list and before the footer. Do not add it to `asked` or `missing`. Do not append it to a follow-up, to the morning wave, or to a message sent only because this line is empty. If the day file already holds `media`, omit the line. Silence is not «нет» and is not chased.

| Wave | Queue |
| --- | --- |
| morning (today) | `morningOrder`, minus items already in `answered`/`cleared` for today |
| evening (today) | `requiredOrder`, minus items that already have a usable value in the day file. A morning value counts. The day file wins over an `answered` array that forgot to list it. |
| catch-up, first send | `requiredOrder`, minus items that already have a usable value in that day's file; then copy that queue into `asked` |
| follow-up of any wave | `days[date].asked` (or current `survey.missing` if `asked` is empty), minus items now in `answered`/`cleared` and minus items the day file already holds. Do not grow `asked` |

**A usable morning value closes the item.** Write it to the day file and add the id to `answered`. That includes every profile id on the morning waves, медитация, чтение установок, `sleep` (bedtime, wake, and numeric quality), `lastMeal`, `lastComputer`, `energyMorning`, and `moodMorning`. The evening wave does not ask a closed item again. Morning «нет» / «не было» / «не пил» / «не принимал» for медитация and for a profile item with `closeOnMorningNo: false` means not yet: do not add the id to `answered` or `cleared`, and do ask it in the evening. A profile item with `closeOnMorningNo: true` closes on that «нет». Attitudes «нет» / «не читал» writes `attitudesRead: false` and closes `attitudes`. Morning «не ел» for the last meal writes `nutrition.within4hOfSleep: false`, omits `lastMealAt`, and closes `lastMeal`. Morning «не работал» / «не сидел» for the computer writes `sleep.lastComputerAt: null` (the key is present) and closes `lastComputer`. A missing key is not that answer.

If he later names a new value for a closed item, write that value over the morning one. Do not put the item on the evening questionnaire just to offer the overwrite.

A sleep comment without bedtime, wake, and a numeric quality does not close `sleep`. The next diary send asks only that gap, quoting the comment: «Сон: утром было «…». Напиши, во сколько лёг и во сколько встал, и качество от 1 до 10.» Do not use the generic start-of-day sleep line, and do not attach the rest of the morning list to that gap. If that date's sent line still asked for hours, keep the old gap text («Напиши часы (шаг полчаса) и качество от 1 до 10») and accept hours without clock times.

A day file that exists is not a closed morning wave. On a 1.6.0 day, if bedtime, wake, or numeric `sleep.quality` is missing, or `lastMeal` / `lastComputer` / `energy.morning` / `mood.morning` is missing, that item is still open. A day whose `asked` never included `lastComputer` can stay complete without it. Send the gap when yesterday's catch-up closes, or on the evening wave if no earlier send happened. Do not skip it because other morning fields are already filled. A day below 1.6.0 that already has `sleep.hours` and a numeric quality is closed for `sleep` even without clock times. A legacy integer `mood` closes the old single mood and does not open `moodMorning` or `moodEvening`. A stored `nutrition.within4hOfSleep` without `lastMealAt` closes the old pre-sleep line and does not open `lastMeal`.

An item is answered when the day file has a usable value: on 1.6.0, `sleep.bedtime` **and** `sleep.wake` **and** computed `sleep.hours` **and** a numeric `sleep.quality` 1–10; on an older file, `sleep.hours` and a numeric `sleep.quality` (legacy `ok`/`poor` on already-complete days counts, do not re-ask); `nutrition.lastMealAt` as `ЧЧ:ММ`, or an explicit «не ел» stored as `within4hOfSleep: false` without `lastMealAt`; `sleep.lastComputerAt` as `ЧЧ:ММ` or an explicit `null`; non-null `energy.morning` / `energy.evening` / `mood.morning` / `mood.evening` / `effectiveness` / `work` / `training` / `attitudesRead`; `social` as in **Люди** (a day below 1.7.0, or an in-flight list whose line was «нет / было / было и круто», closes on `happened`; on the 1.7.0 line, `happened: false` closes it, and `happened: true` closes it only with who and an effect); a legacy integer `mood` for the old `mood` id only; a `meditation.minutes` integer, a stored custom-slot value, an intake object, non-empty `nutrition.what`, or `notes` text. A comment never completes an item. `comments.social` does not close `social`. `nutrition.balance` and `nutrition.hungry` never complete or reopen `food`, and neither is its own survey id. A `media` object never completes or reopens the survey, and it is not its own required id. `nutrition.within4hOfSleep` computed from the two clock times is not its own survey id. For медитация, each profile id, and заметка, evening or catch-up «нет» is an answer: omit the value and add the id to `cleared`; never ask it again for that date. For чтение установок evening/catch-up «нет» writes `attitudesRead: false` and adds `attitudes` to `answered`. For еда, «нет» / «не ел» / «ничего» writes that phrase into `nutrition.what` and adds `food` to `answered`. For a follow-up that still lists `ateBeforeSleep`, «нет» writes `within4hOfSleep: false`. A day whose `asked` already contains `hunger` from the 2026-09-23 evening keeps that id until it is answered; do not add `hunger` to any new list.

## How to send the questionnaire

1. Pick the wave (see **When this runs**). Before an evening or catch-up queue, close every id the day file already holds (add it to `answered` or `cleared`). Then build the queue from what is still empty. Do not list a closed morning item.
2. If the queue is empty: for a morning wave, nothing to send. For evening / catch-up, set `days[date].complete=true`, state idle if nothing else is awaiting, and confirm the day in one short human clause.
3. Compose one message: `headers[slot]` (or `headers.missing` on a follow-up), blank line, the queue items numbered from 1 using each item's `line`, blank line, then — only on a first evening send or a first catch-up, and only when `media` is still absent — the unnumbered `items.media.line`, blank line, `footer`. Do not number that line. Do not put it on a follow-up or on the morning wave. Replace `{date}` with `D.MM` (17.09). If `sleep` is open only because a time or quality is missing and `comments.sleep` is set, use the quoted gap line («Сон: утром было «…». Напиши, во сколько лёг…») instead of `items.sleep.line`. On a follow-up of the old hours line, keep asking hours. If only quality is missing and both times (or legacy hours) are already stored, ask quality only. If `social` is open only because who or the effect is missing, use the gap line from **Люди** instead of `items.social.line`. On a follow-up of the old «нет / было / было и круто» line, keep that old line.
4. `POST /send` that text once with `purpose=survey`. Wait at least 90 seconds. `kind=reply` if the ritual message already went out; `kind=morning|evening` only for the ritual brief itself. `purpose=survey` is required so a diary list is not swallowed as a second focus confirm. If the call times out or returns `duplicate: true`, stop. The questionnaire is already in the chat. Do not send it again in different words.
5. Union the numbered ids into `days[date].asked`. Do not add `media`. If this is the primary wave (yesterday catch-up, or today when yesterday is already done), set `{status: "awaiting", date, slot, missing: [queue], paused: false}`. If this is today's morning while yesterday is still the primary `awaiting`, leave `survey.date` / `slot` / `missing` on yesterday.
6. Do not send each line separately. Today's morning wave may follow yesterday's catch-up as a second `/send` in the same run — two messages, two dates. Do not put both dates in one questionnaire.

## After he answers

Same message may contain focus/minutes **and** diary. Split them. Ritual Notion write stays in `telegram-feedback`. Diary write is this skill.

Parse:

1. If `survey.status=awaiting`, parse every labeled/numbered line he answered. An unlabeled run of numbers maps by position onto `survey.missing` only if it clearly follows that list. If he named a date («это за 21», «теперь за 22») or sent two voices, write each blob onto that date; do not store yesterday's scores on today.
2. Unusable (`оценка нормально`, a profile intake `да`, substance `принимал` without quantity, food `да` / `ел` without what he ate, last meal `да` / `ел` without a clock time, computer `да` / `работал` without a clock time) stays missing. Do not guess. A bare «да» / «читал» / «смотрел» / «слушал» on the optional media line writes nothing and is not chased. Extra «нет» / «не пил» / «не было» / «не принимал» right after a labeled intake map in order onto the next still-missing profile intakes of **that wave**, in `waves` order. Do not map them onto сон / последний приём пищи / компьютер / энергия / настроение / оценка дня / еда / чтение и просмотр. Do not read a routine-log clock or the evening work score as `lastComputer`. A line that names vitamins, cigarettes, nootropics, or another ordinary substance is not a positional answer to the next intake.
3. Usable → merge into the day file. Never wipe fields he already gave. If he names a new value for медитация, чтение установок, or a profile id, that value replaces the morning one. Quote him. Unknown → `null` / omit. If he added a comment to an item, merge it into `comments.<id>` without touching `notes`.
4. «потом» / «не пиши дневник» → leave fields as-is, `survey.json` = `{status: "paused", date, slot, missing: [...], paused: true}`. Do not nag again in **this** slot.
5. «сегодня ничего» is a **focus** answer, not an empty diary. Continue the survey after handling focus.
6. Write every usable answer. An id already in `answered` or `cleared`, or already holding a usable day-file value, is not missing — even if a stale `missing` array still lists it. Leave that stale `missing` array in place until this reply is parsed, so a numbered answer to the list already in the chat still maps by position. After the parse, recompute `missing` as `asked` minus `answered`/`cleared`. If any of those remain, send one follow-up containing only those lines. Do not add `requiredOrder` ids that were never in `asked` for that date. Do not switch the follow-up to another day in the same burst. Do not follow up for a morning item the day file already holds.
7. Intakes: only `profile.intakes`. `ask=daily` items are in the questionnaire. `if-mentioned` only when he named them.
8. Ordinary substances he names himself → `oneOffSubstances`. See **Прочие вещества** below. Do not add one to the profile unless he said «трекай это».
9. Ask diary energy morning and evening on the 1–10 scale from the script. Ask mood morning and evening on the 0–4 scale, in the same slots as energy. Ask the last meal time and the time he finished computer work on the morning wave. Both are «когда последний раз» for that night's sleep: keep the times and the sleep quality, and do not invent a correlation in the confirmation. Ask питание on the evening wave and on a first catch-up as one line: what he ate. Hunger, surplus, and deficit are invited inside the food line and are not numbered. Do not ask БЖУ, grams, or a calorie number, and do not follow up when hunger or the surplus/deficit is missing. Do not ask whether he ate in the 4 hours before sleep; compute that from `lastMealAt` and `sleep.bedtime`. `routine-log` separately asks how much ordinary work distracted him (1–3). It does not ask how much strength that work took. Never map the distraction score to `energy.morning` / `energy.evening`, `mood.morning` / `mood.evening`, or another diary field.
10. Profile intakes: follow that item's `accept` and `unit`. «нет» on a morning item with `closeOnMorningNo: false` leaves it for the evening; the same «нет» on an evening or catch-up clears it. `да` / «принимал» / «пил» without the quantity the `accept` text requires is incomplete. Never infer one intake or dose from another.
11. Profile custom slots: store the value the slot's `store` or `values` describe. A slot is separate from `training`. Morning «нет» follows `closeOnMorningNo`.
12. Медитация: integer minutes. «нет» clears it (evening / catch-up) or leaves it for the evening (morning). «да» / «медитировал» without minutes is incomplete. «полчаса» = 30, «час» = 60 only if he said that. Do not invent minutes.
13. Чтение установок: `да` / `читал` → `attitudesRead: true`; `нет` / `не читал` → `false` (evening / catch-up) or leave for the evening (morning «нет»). Do not guess from «потом» or silence.
14. Per-item comments are optional. After the value, leftover text in parentheses, after an em-dash/dash, or after a comma that is clearly commentary → `comments.<itemId>`. Do not write `comments.notes`. Do not put these into `notes`. Omit the key if he gave no comment. A comment without a usable value does not answer the item. Never follow up for a missing comment.
15. Sleep on a new questionnaire needs **both clock times and quality 1–10**. Write `sleep.bedtime` and `sleep.wake` as `ЧЧ:ММ` (24-hour, zero-padded). Then write `sleep.hours` from the formula below. Do not ask him for hours and do not subtract 10–15 minutes. One clock time stores that time and leaves `sleep` open: ask only the missing time and, if needed, quality. A bare duration («7,5») on the new line does not close sleep and is not bedtime; quote it and ask for the two clock times. If he also gave a 1–10 quality, keep it and do not ask quality again once the times arrive. «плохо» / «шумно» without a quality number is not quality — keep asking the number, and keep the words as `comments.sleep` when the times are already there. Do not write `quality=poor` on new days. Do not rewrite old `ok`/`poor` into a number. A follow-up of a list that asked for hours still accepts hours: one number alone is hours, two numbers are hours then quality. Do not demand clock times for that in-flight list, and do not drop hours already stored.
16. Clock times: `23:40`, `23.40`, `23-40`, `7:10`, and «11 вечера» / «7 утра» / «полночь» (`00:00`) when the hour is unambiguous. «лёг» / «отход» / «уснул» marks bedtime; «встал» / «подъём» / «проснулся» marks wake. Without those labels, the first time is bedtime and the second is wake. Four digits next to those words (`2340`, `0710`) are `ЧЧ:ММ` when they are a real time. Do not read `7,5` or a 1–10 quality as a clock time.
17. Voice STT on a 1–10 field (оценка дня, энергия, качество сна): `10` stays 10. A two-digit number outside 1–10 such as `24` may be `2.4` if X.Y lands in range — accept that. If it is still not a 1–10 value, keep the item missing and ask again. Do not invent a score from «плохо» or from a number that is already used as a clock time. Mood is not this scale: `0–4` or the words дно / норм / среднее / хорошее / прёт. A 1–10 energy number does not fill mood.
18. Питание: see **Питание** below. The day's food is the evening wave. The last meal's clock time is the morning wave.
19. Чтение и просмотр: see **Чтение и просмотр** below. Optional. Record minutes and what he names. Do not follow up for either.
20. Люди: see **Люди** below. On a new list, «нет» closes the item. «Было» without who and without an effect word does not. Do not read a name or an effect out of mood, the day note, or a free note.

After a successful parse: write the entry, update `survey.json`, send one all-missing follow-up **or** close the wave.

Morning close (day not yet final), human labels:

```text
Дневник утро 17.09: сон 23:40–07:10 (7,5 ч), качество 6, последний приём пищи 21:30 (за 2 ч 10 мин до сна), компьютер до 22:10, энергия утром 5, настроение утром норм, медитация 15 мин, установки да, затем каждый утренний пункт профиля его словами (значение или «нет»). Вечером спрошу только то, чего ещё нет.
```

Full-day close:

```text
Дневник 17.09 записан: сон 23:40–07:10 (7,5 ч) / качество 6, последний приём пищи 21:30 (за 2 ч 10 мин до сна), компьютер до 22:10, энергия утро 5 вечер 4, настроение утром норм, вечером хорошее, оценка дня 6, работа 2, тренировки не было, медитация 15 мин, установки да, людей не было, затем каждый пункт профиля его словами, еда: овсянка и курица, дефицит, голод был, чтение и просмотр: 40 мин, подкаст про сон, заметка нет.
```

On either close, when `within4hOfSleep` was computed or set by «не ел», put that into the last-meal clause («за 2 ч 10 мин до сна», «раньше чем за 4 часа», «не ел»). Do not add a separate question. If `oneOffSubstances` is non-empty, add one clause: «Ещё: витамин D, сигареты.» If the list is empty, do not mention the field and do not write «ещё нет». Mention чтение и просмотр only when `media` is present. If he skipped it, leave that clause out. When people were there, the social clause is «люди: тимлид, вдохновляли», «люди: Аня, нейтрально», «люди: сосед, раздражали», or, when the effects differ, «люди: Аня — нейтрально; тимлид — вдохновляли». Say the Russian word, not `inspired`.

If he only answered ritual and the survey is still awaiting: handle ritual, then do not duplicate the questionnaire — it is already in the chat. If state is idle but a wave is due for this slot, send it after the ritual confirm.

If the whole reply was diary but incomplete or unusable, send one follow-up with all still-missing lines.

## Scales (storage)

Remind these in the script messages (already there). Do not substitute a “typical” day.

| Field | Scale | Empty means |
| --- | --- | --- |
| `effectiveness` | 1–10, decimals ok. 5 = нейтральный, 10 = шедевр, 1 = один из худших | not recorded |
| `work` | 0–3. Criteria = `profile.workCriteria`, or the script words if null | **not** 0. 0 = явно не работал |
| `mood.morning` / `mood.evening` | 0 дно, 1 не очень, 2 среднее или норм, 3 хорошее, 4 прёт | not recorded. 0 = дно. Same scale as the 1.5.0 single mood, two readings like energy. Legacy integer `mood` stays one number |
| `training` | 0 нет, 1 лёгкая, 2 обычная, 3 вымотан | **not** 0. 0 = явно не было трени |
| profile custom slot | the slot's `values` | not recorded until he answers |
| `meditation.minutes` | integer minutes; «нет» omits the object | not recorded until he answers. «да» without minutes stays missing |
| `attitudesRead` | true = читал, false = не читал | not recorded. false only after he said «нет» |
| `social` | нет → `{happened: false}`. Если были: `who` + `effect` `irritated` / `neutral` / `inspired`, либо `people` когда влияние разное. Старая строка: `great` | не было (`happened: false`) — only after he said «нет». На новой строке `happened: true` без кто и без влияния не закрывает пункт |
| `sleep` | `bedtime` and `wake` as `ЧЧ:ММ`; `hours` computed, step 0.5; `quality` 1–10 (decimals ok). Legacy days may still have hours without clock times, and `ok` \| `poor` | not recorded. Night that **ended this morning**. Times or legacy hours without numeric quality = sleep still missing |
| `energy.morning` / `energy.evening` | 1–10, decimals ok. 5 = обычно, 10 = полный заряд, 1 = совсем нет сил | not recorded. Morning is start-of-day; evening is end-of-day |
| `nutrition.what` | free text, his words. «не ел» / «нет» / «ничего» is an answer | not recorded. «да» without the food stays missing |
| `media.what` / `media.minutes` | optional. `what` is his words; `minutes` is an integer he named («полчаса»=30, «час»=60). Either field is enough. «нет» stores `what` and omits `minutes` | omit the object. Silence is not «нет» and is not chased. A bare «да» writes nothing |
| `nutrition.balance` | `surplus` (профицит / профит / переел) or `deficit` (дефицит / не доел). Optional, inside the food answer | omit the key. Never follow up. Never its own line |
| `nutrition.hungry` | true = голод был, false = не было. Optional, inside the food answer | omit the key. Silence is not false. Never follow up. Never its own line |
| `nutrition.lastMealAt` | `ЧЧ:ММ` of the last meal before that sleep. «не ел» omits the key and sets `within4hOfSleep` false | not recorded until he answers. Morning line. One of the two «когда последний раз» marks |
| `sleep.lastComputerAt` | `ЧЧ:ММ` when he finished computer work before that sleep. Explicit `null` = «не работал». Absent key = not recorded | not recorded until he answers. Morning line. The other «когда последний раз» mark. Not the evening work score and not routine-log |
| `nutrition.within4hOfSleep` | computed: gap from `lastMealAt` to `sleep.bedtime` ≤ 4 h. «не ел» stores false. Legacy days may still hold a direct yes/no | omit when the gap cannot be computed. Not its own line on a new questionnaire |
| `comments` | optional string per survey item id, not `notes` | omit key |
| `notes` / `tag` / `period` | free text; tag rare; period `long_weekend` \| `trip` | omit |
| `intakes[]` | only ids in `profile.intakes` | omit object = did not take / not tracking |
| `oneOffSubstances` | array of strings he actually said: vitamins, cigarettes, nootropics, other ordinary substances | omit the key. Never ask. Silence is not «нет» |

С `specVersion` 1.7.0 новые дни и день, который этот прогон дописывает, пишутся этой версией. Настроение — два слота, `mood.morning` и `mood.evening`, шкала та же, что у одной оценки с 1.5.0. Сон хранит `bedtime`, `wake` и посчитанные `hours`. Люди, когда они были, хранят кто и влияние. См. **Люди**. В подтверждении называть слово ступени настроения (не очень, среднее, хорошее), слово влияния (раздражали, нейтрально, вдохновляли) и время сна, не одну цифру часов, которую он не называл, и не английский ключ `effect`.

Слова шкалы: настроение — дно / нулевое / ноль = 0, не очень = 1, среднее / норм = 2, хорошее = 3, прёт = 4. Тренировка — не было = 0, лёгкая = 1, обычная = 2, вымотан / сдох = 3. Голое число в ответе на уже отправленный опрос этой шкалы — это эти же ступени. Утро и вечер не подменяют друг друга: число в ответе на утреннюю строку пишется в `mood.morning`.

День со `specVersion` ниже 1.6.0 не дробить на два настроения и не добирать время отхода, подъёма, последнего приёма пищи и компьютера. Список, в котором `lastComputer` не был пронумерован, этим пунктом не дополнять. Ниже 1.5.0 не переписывать шкалу. Там настроение: 0 дно, 1 норм, 2 хорошее, 3 прёт. Тренировка: 0 не было, 1 обычная, 2 вымотан. 23.09 так и лежит: настроение 2 = хорошее, тренировка 1 = обычная, сон — часы без времени на часах.

Если он поправляет день ниже 1.5.0 словами новой шкалы («не очень», «среднее», «лёгкая») либо числом, которого на старой шкале нет (настроение 4, тренировка 3), поднять этот день до 1.5.0. Число, которое он только что назвал на новой шкале, записать как есть. Уже лежащие старые числа перевести: настроение 1→2, 2→3, 3→4; тренировка 1→2, 2→3. Нуль не сдвигать. Поле, которое он только что назвал словом, вторым проходом не сдвигать. Пока он отвечает одним числом настроения на старую шкалу того же дня, оставить целое `mood` и старый смысл. Отдельные «утром» и «вечером» поднимают день до 1.6.0 и пишут только названные слоты по шкале 1.6.0; старое целое в оба слота не копировать. Названные время отхода и подъёма тоже поднимают день до 1.6.0, часы пересчитать и в подтверждении сказать, если они отличаются от уже записанных. Ответ по новой строке людей поднимает день до 1.7.0. Уже закрытый день ниже 1.7.0 с записанным `social.happened` не открывать и не дописывать `who` или `effect` задним числом.

File `status` `complete` = `effectiveness` + `sleep.hours`. The **survey** is not done until every id in `asked` has an answer (including explicit 0 / «нет»). A full day is the expanded `requiredOrder`: core ids plus every id in `profile.waves`. `sleep.lastComputerAt` is one of them; an explicit `null` counts as the answer. Comments are never required. `nutrition.balance`, `nutrition.hungry`, computed `nutrition.within4hOfSleep`, and `media` are not items. Naming `media` or leaving it out does not open or close the survey. `oneOffSubstances` is not one of them either: naming it or leaving it out does not open or close the survey.

Sleep math, only after both times parse. Let bedtime and wake be minutes from midnight. `minutes = wake − bedtime`; if `minutes ≤ 0`, add `1440`. If `minutes` is 0 or greater than 960, do not write `hours` — ask the times again. Otherwise `hours = ((minutes + 15) // 30) / 2` (step 0.5; a remainder of exactly 15 minutes rounds up). Do not subtract 10–15 minutes. A partial `sleep` object may hold whichever of `bedtime`, `wake`, and `quality` is already known. Write `hours` in the same edit as the second time. Quality is a 1–10 rating, not `ok`/`poor`.

Examples: 23:40→07:10 = 7.5; 00:20→07:00 = 6.5; 23:00→06:10 = 7; 22:50→07:05 = 8.5.

`lastMealAt` and `lastComputerAt` are kept so a later reading can relate a late meal and late computer work to `sleep.quality` of that same night. Do not summarize a correlation from one day. Do not copy either time into `notes`.

Last-meal gap, only when both `nutrition.lastMealAt` and `sleep.bedtime` exist. `gap = bedtime − lastMeal` in minutes; if the meal clock is later than bedtime, treat the meal as the previous evening (`gap = bedtime + 1440 − lastMeal`). `gap ≤ 240` → `within4hOfSleep: true`. `240 < gap ≤ 1080` → `false`. `gap > 1080` → omit `within4hOfSleep` (the clock falls inside the sleep interval or is not “before bed”). «не ел» → `within4hOfSleep: false` and no `lastMealAt`. Recompute the flag when either time changes. Do not infer the meal time from `nutrition.what`.

A number intake stores the number in that item's `unit`. Free-form answer is fine if the number is clear. «Нет» on an evening or catch-up omits the intake object. Do not merge two profile intakes into one sourceTemplate code, and do not infer a dose from another intake.

An intake whose `unit` is `g_ethanol`: grams of ethanol, drinks > 3°. Кефир/квас skip. `л × % × 10` (0.5 л × 5% → 25).

## Люди (`social`)

One evening line, and the same line on a first catch-up. Not a morning item. Three facts: were there people, who, and how they affected him. He named the effects: раздражали, нейтрально, вдохновляли.

- «нет» / «не было» / «никого» / «людей не было» → `happened: false`. Omit `who`, `effect`, and `people`. That closes `social`.
- «да» / «было» / «были» without a person and without an effect word → `happened: true` only. The item stays open.
- Who is his words: «Аня», «тимлид», «созвон с тимлидом». Do not invent a name, and do not pull one out of `notes`, mood, or a free note. «Были люди» is not a who.
- One effect for the people he named → `who` plus `effect`: раздражали / бесили → `irritated`; нейтрально / никак не повлияли → `neutral`; вдохновляли / вдохновили / заряжали / зарядило / круто → `inspired`. Do not also write `great` on this line.
- Different effects → `people`: an array of `{who, effect}`. Omit the single `effect`. Do not collapse two effects into one. «с Никой и тимлидом, вдохновляли» is one `who` and one `effect`, not two people, because he gave them one effect.
- A phrase that describes the influence without one of those words («настроение поднялось») stays in `comments.social` and does not set `effect`. Ask the three words.
- Leftover color that is not the name and not the effect → `comments.social`. Do not copy `who` into the comment only to repeat it.
- A partial answer is kept. Follow up only the gap, quoting what is already stored:
  - who and effect both missing: «Люди: было «…». Кто это был и как повлияли: раздражали, нейтрально или вдохновляли.»
  - who present, effect missing: «Люди: было «Аня». Как повлияли: раздражали, нейтрально или вдохновляли.»
  - effect present, who missing: «Люди: повлияли «вдохновляли». Кто это был?»
- Do not use `items.social.line` for that gap. Do not attach the rest of the wave to it.
- A day below 1.7.0 that already has `social.happened` is closed. Do not ask who or effect for it, and do not move an old `comments.social` name into `who`.
- A follow-up of a list that already went out as «Люди: нет / было / было и круто.» keeps that old line. «было» closes with `happened: true`. «круто» also sets `great: true`. The tail stays `comments.social`. Do not require `who` or `effect`, and do not switch that list to the new line.
- Confirm in words: «людей не было», «люди: тимлид, вдохновляли», «люди: Аня — нейтрально; тимлид — вдохновляли».

## Прочие вещества (`oneOffSubstances`)

Open list for ordinary things that must not become their own columns or survey lines: any vitamins, cigarettes, nootropics, and similar minor substances he names. Anything already in `profile.intakes` stays there.

- Never ask. Not in `morningOrder`, `requiredOrder`, `asked`, or `missing`. A follow-up never adds this line. Silence does not mean «нет» and does not block the survey.
- When he names one, append a short string in his words. One substance per item: «витамин D и магний, покурил» → `["витамин D", "магний", "сигареты"]`. Keep a dose or count only when he gave it («витамин D 2000 МЕ», «сигареты, полпачки»). «Витаминки» without names stays `"витамины"`. Do not invent the list or a dose, and do not ask which or how much.
- «Покурил» is cigarettes. A named nootropic is that name, not a new profile intake.
- Same day, later mention: append. Do not wipe items already stored. An exact repeat is not a second item. A later dose on the same substance replaces that item. A correction («не сигареты, а никотиновая жвачка») drops the wrong item.
- An unprompted «нет» / «витаминов не было» does not create an item and does not clear the list.
- A legacy single string on an older file stays as-is. When this day is updated with a new mention, turn that string into the first array item, then append.
- Do not copy these into `notes` or `comments` unless he also gave a real day note or a comment on another item. Do not put a `profile.intakes` label here.
- Confirm with «Ещё: …» only when the array is non-empty. Do not add a profile column unless he said «трекай это».

## Питание (`nutrition`)

Two different facts. The last meal's clock time is a morning line (`lastMeal`), about the night that just ended. What he ate during the day is an evening line (`food`), and a first catch-up line. Hunger is not a line. The yes/no «за 4 часа до сна» is not a line on a new questionnaire.

- `lastMeal` → `nutrition.lastMealAt`, `ЧЧ:ММ`. «не ел» / «не было» closes it with `within4hOfSleep: false` and no `lastMealAt`. «да» / «ел» without a clock time stays missing. When bedtime is also known, set `within4hOfSleep` from the gap rule in **Scales**. Do not ask that boolean.
- `food` → `nutrition.what`, his words. «не ел» / «ничего» / a labeled «нет» stores that phrase and closes `food`. «да» / «ел» / «нормально» without the food stays missing. Do not ask or invent grams, kcal, or БЖУ. Do not split the day into breakfast / lunch / dinner unless he did. Do not pull a last-meal clock time out of this answer.
- The food line invites an optional note: hunger, and surplus or deficit. Record only what he actually said, on that same answer, not in `notes`.
- Estimate → `nutrition.balance`: профицит / профит / переел / объелся → `surplus`; дефицит / не доел / недоел → `deficit`. Calories and nutrition in general, not a macro split. No estimate → omit `balance`. Do not follow up. Do not infer it from the dishes. Both sides in one answer, or an unclear «много» / «мало» → omit `balance` and keep the clause in `comments.food`. «в ноль» / «ровно» is not a third value: omit `balance`.
- Hunger → `nutrition.hungry`, still inside the food answer. Голод был / испытывал голод → `true`; голода не было / не голодал → `false`. «немного» / «слегка» → `true` and the qualifier in `comments.food`. Not mentioned → omit the key. Silence is not `false`. Do not infer hunger from the dishes or from «не ел». Do not number `hunger`, do not add it to `asked` / `missing`, and do not follow up for it. A qualifier that is only the hunger fact already stored in `hungry` does not need a second copy in `comments`.
- A follow-up whose sent list still numbers `ateBeforeSleep` keeps that old line until it is answered. да / ел → `within4hOfSleep: true`; нет / не ел → `false`. If he names the food instead of да/нет, store `true` and that food in `comments.ateBeforeSleep`. Do not add `lastMeal` to that same follow-up. Do not infer the boolean from the day's meals. A day that already has this boolean and no `lastMealAt` stays closed for the pre-sleep question.
- Other leftover words on the food answer go to `comments.food`. The estimate itself is `balance`, not `notes`.
- Leftover unlabeled «нет» after the intakes still maps only onto the next still-missing profile intakes of that wave, in `waves` order. It does not close food, the last meal, or media, and it does not set `hungry`.
- Do not append `food`, `lastMeal`, or `ateBeforeSleep` to a follow-up of a list that was sent without them. A day whose `asked` never included them can stay `complete`. If an already-sent list numbered `hunger` and that id is still unanswered on a follow-up of that list, ask it once with the old line and then stop. Do not put `hunger` on any new questionnaire.

`Fb|GAB` / `Anx`-style mixed fields from the source template: number **and** `name`. Do not infer a profile intake from a template dose.

## Чтение и просмотр (`media`)

Optional. One unnumbered line on the first evening send and the first catch-up. Not on `morningOrder`, not in `requiredOrder`, not in `asked` or `missing`. Not the attitudes yes/no and not the study report.

- Ask two things in that one line: how many minutes, and what exactly he read, listened to, or watched (a book, podcast, audiobook, or video, useful or fiction).
- `media.minutes` is an integer. «полчаса» = 30, «час» = 60, «полтора часа» = 90 only when he said that. Do not invent minutes. Do not take them from focus, study, or routine.
- `media.what` is his words. Several titles stay one string. Do not invent a title.
- Either field is enough. If he names only minutes, or only the title, write that and do not ask for the other.
- «нет» / «ничего» / «не читал» / «не смотрел» / «не слушал» stores that phrase in `what` and omits `minutes`.
- Silence omits `media`. Do not write «нет» for him. Do not follow up, and do not repeat the line on the missing-items message.
- «да» / «читал» / «смотрел» / «слушал» without minutes and without a title writes nothing and is not chased.
- A later answer the same day merges: a new title replaces `what`, a new duration replaces `minutes`. Do not wipe the field he did not mention.
- Words that are not the material or the duration go to `comments.media`. Do not copy the answer into `notes`, `study/`, or `notes/entries/`.
- «Чтение установок» stays `attitudes`. Yes/no there does not fill `media`. A title on this line does not set `attitudesRead`.
- If the same reply also reports study, `study-log` writes that from the study words. Do not copy `media` into the study file. Do not copy the study report into `media` unless those words are also his answer to this line.
- Confirm the clause only when `media` is present: «40 мин, подкаст про сон», «подкаст про сон», «40 мин», or «нет». If the object is absent, do not mention the line.

## Fill

1. Date = Europe/Moscow. `weekday` ∈ пн вт ср чт пт сб вс, must match the date.
2. Merge into an existing file. Never wipe fields he already gave (except the evening day total over a morning value).
3. Quote him. Unknown → `null` / omit, never guess.
4. Month file only if he gave theses, body measures, or a baseline «часто» stack.

Entry shape: `journal/examples/day-shape.json`. Source spreadsheet samples stay in `source-*.json`. New writes use current `specVersion`. `source` = `telegram` | `chat` | `voice`. Do not rewrite old days to invent quality 1–10, clock times, split mood, energy, meditation, attitudes, nutrition, media, comments, who, or effect.

## Verify

Before saying the day is written, and on ad-hoc «проверь журнал»:

- [ ] JSON parses. Filename date = `date`. Weekday matches Moscow calendar.
- [ ] The day just written uses the current `spec` / `specVersion`. An older file may keep the version it was written with; do not rewrite it only to bump the version. No extra keys beyond the day schema (`note` on the entry is not allowed).
- [ ] Numbers in range for that file's `specVersion`. `work`/`training` empty kept `null`, not coerced to 0. From 1.6.0, `mood` is an object with `morning` / `evening` on 0–4, and `sleep.bedtime` / `sleep.wake` / `nutrition.lastMealAt` / `sleep.lastComputerAt` are `ЧЧ:ММ` when present. `sleep.lastComputerAt` may be `null` only after he said he did not work at the computer. `sleep.hours`, when both times are present, matches the formula. From 1.5.0 and below 1.6.0, `mood` is one integer 0–4 and `training` is 0–3. Below 1.5.0, `mood` is 0–3 (2 = хорошее) and `training` is 0–2 (1 = обычная). `energy.morning` / `energy.evening` and numeric `sleep.quality` are 1–10. `meditation.minutes` is a positive integer when present. `attitudesRead` is boolean or absent. `nutrition.what`, when present, is a non-empty string. `media`, when present, is an object with `what` and/or `minutes`; `minutes` is an integer 1–1440. An empty `media` object is not valid. `nutrition.balance` is only `surplus` or `deficit`. `nutrition.hungry` and `nutrition.within4hOfSleep` are boolean or absent. A partial `nutrition` or `sleep` object is valid. From 1.7.0, `social.effect` is only `irritated`, `neutral`, or `inspired`. `social.people`, when present, is a non-empty array and each item has `who` and `effect`. `happened: false` has no `who`, `effect`, or `people`. A partial `social` object (`happened: true` with only `who`, or only `effect`) is valid while the item is still open. Do not set both a single `effect` and `people`. `great` may remain on a day below 1.7.0.
- [ ] `comments` values are non-empty strings keyed by survey item id. No `comments.notes`. No `note` on the entry.
- [ ] `intakes[].id` ⊆ profile. No sourceTemplate doses invented.
- [ ] `oneOffSubstances`, when present, is a non-empty array of non-empty strings (a legacy single string is still valid and is not rewritten unless this day is otherwise being updated). It does not repeat a label already in `profile.intakes`.
- [ ] Mixed intakes have `name`. Sleep `multipleOf` 0.5.
- [ ] `status` matches the data (`complete` only if оценка дня + сон).

On ad-hoc verify: last 7 days from `askFrom`. Report empty / partial / complete. Fix only schema mistakes (weekday, status, extra keys). Do not invent scores to make a day complete.

## Profile (`journal/profile.json`)

Profile controls `workCriteria`, `customSlots`, and `intakes`. Edit **only** when he said to — «профиль дневника», «трекай …», «критерии work», «не трекай …».

1. Show the current profile in a few lines.
2. Change only what he named. Do not load Prl / ежовик / Fen / the rest from the spec.
3. `workCriteria`: need text for 0, 1, 2, 3. If he gave one level, ask the rest.
4. Each custom slot: stable `id`, `label`, `type`, `ask`, `line`, `accept`, `reject`, `closeOnMorningNo`; for enums, `values`. Put the id in the `waves` array for the part of the day he named.
5. Each intake: `id` (stable slug), `label`, `valueType` (`number` | `integer` | `enum` | `mixed`), `unit` if any, `ask` `daily` | `if-mentioned`, `line`, `accept`, `reject`, `closeOnMorningNo`, optional `codes` / `note`.
6. Remove an intake only if he said to stop tracking it. Existing day files stay as they are. Also drop its id from `waves`.
7. Confirm the new profile in words, then write the file.

The questionnaire follows `profile.customSlots` and `profile.intakes` with `ask=daily`, plus the core items. Which wave an id is on is `profile.waves`, not a list in this skill. Nutrition is the morning clock time `lastMeal` plus the evening line `food`, not intakes and not custom slots. `media` is the optional evening line for minutes and what he read, listened to, or watched. It is not a required item, not a custom slot, and not an intake. Do not add it to `requiredOrder`. `lastComputer` is the morning clock time on `sleep`, next to `lastMeal`: both exist to relate late food and late computer work to that night's sleep quality. Hunger, surplus, and deficit are optional parts of the food answer. A new daily item goes into the `waves` array for the part of the day he named. Do not edit `survey-script.json` to add it. Do not ask sourceTemplate substances. Do not add vitamins, cigarettes, nootropics, or `oneOffSubstances` to either order.

Do not mix a profile dump into every morning.

## Git (entries + profile + survey)

Operational data, like ritual. After a real write (entry, month, profile he confirmed, or survey state change):

1. `git add` only `journal/entries/` `journal/months/` `journal/profile.json` `journal/survey.json` — nothing else.
2. `git commit` (`Journal YYYY-MM-DD …` or `Journal profile: …` or `Journal YYYY-MM-DD survey sent`).
3. `git fetch origin master`.
4. Land that commit on `master` (checkout `master` + merge, or `git push origin HEAD:master` if the branch has only that commit).
5. `git push origin master`.
6. Do not wait for «ок». If push fails, say so. A PR is not a substitute.

Do not put skill / catalog / spec / `survey-script.json` edits in that commit. Those wait for «ок».

If the same run also wrote `ritual/`, make **two** commits: ritual first (its rule), journal second.

## Hard rules

- Do not invent scores, hours, doses, names, who, or how people affected him. Do not read that out of mood, the day note, or a free note. Do not reopen a day below 1.7.0 that already has `social.happened` to collect who or effect. On the new people line, «было» without who and without an effect word does not close `social`.
- Do not ask the author's substance list.
- Do not shame empty days.
- Do not put diary scores inside the morning/evening ritual SMS.
- Send every item of the current wave together in one numbered Telegram questionnaire.
- Do not send one Telegram message per diary item.
- Do not ask оценка дня / работа / тренировка / люди / `waves.evening` / еда / заметка / энергия вечером / настроение вечером in the morning wave. Do not ask the optional чтение и просмотр line in the morning either. Do ask bedtime, wake, sleep quality, the last meal time, the time he finished computer work, morning mood, meditation minutes, attitudes yes/no, and the morning profile waves when they are still on `morningOrder`.
- Do not skip today's sleep, last meal, computer time, morning energy, or morning mood in the morning because the evening exists. A 1.6.0 morning file that still lacks bedtime, wake, numeric sleep quality, the last meal, the computer time, morning energy, or morning mood is not closed. A legacy file with hours and numeric quality is closed for sleep without clock times. A day whose sent list never numbered `lastComputer` is not reopened for it.
- Do not ask in the evening an item the day file already holds. Sleep, the last meal, the computer time, morning energy, and morning mood go into the evening wave only when that value is still missing. Do not repeat медитация, установки, or a morning profile id once a usable morning value is stored.
- Do not use spreadsheet jargon in Telegram.
- Do not parse the routine-work distraction rating as `work`, `mood`, `energy`, or another diary field.
- Do not treat ritual `skipped` / «пропустил» as a diary skip unless he said so.
- Do not write Notion for this diary.
- Do ask the last meal time in the morning. Do ask питание on the evening wave and on a first catch-up as one line: free-text food. Do ask чтение и просмотр once, unnumbered, on the first evening send and the first catch-up: minutes and what exactly he read, listened to, or watched. Either answer is enough. «нет» stores that word in `media.what`. Silence writes nothing. Do not number it, do not add it to `asked` or `missing`, and do not follow up for the line, the minutes, or the title. Do not put it on a follow-up or on the morning wave. Do not treat it as чтение установок or as the study report. Do not copy it into `notes`, `study/`, or `notes/entries/`. Do not take its minutes from focus, study, or routine. Hunger, surplus, and deficit belong in the food answer when he says them. Do not number hunger. Do not ask БЖУ, grams, or kcal. Do not follow up for a missing surplus, deficit, or hunger. Do not ask «ел ли за 4 часа до сна» on a new list; compute `within4hOfSleep`. Do ask diary energy and mood morning and evening. Do not nag for a missing per-item comment. Do not add `moodMorning`, `moodEvening`, `lastMeal`, or `lastComputer` to a follow-up of a list that was sent without them. Do not treat «не работал» on the evening work line as `sleep.lastComputerAt`.
- Do not ask vitamins, cigarettes, nootropics, or any other ordinary substance as a survey item. If he names them, write `oneOffSubstances` and do not follow up for a dose or a missing list.
- Do not follow up with items that were not on a questionnaire already sent for that date. New `requiredOrder` fields do not sneak into an in-flight wave and do not block `complete` for a day whose `asked` never included them.
- Do not move `survey.date` / `slot` / `missing` from yesterday's catch-up onto today's morning. Today's list lives in `days[today].asked`.
- Do not retry a diary `/send` after a timeout, an empty response, or `duplicate: true`. That retry is how the morning questionnaire was delivered twice.
- The survey line «заметка» and any note whose subject is how the day went stay in the day-file field `notes`. The survey line «чтение, подкасты и видео» stays in `media`. An idea, an experience, or a view that is not about this day goes to `free-notes` (`notes/entries/`), not into either field.
