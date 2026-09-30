# Ritual journal

One file per ritual day: `YYYY-MM-DD.md` (Mon–Sat, Europe/Moscow). Open misses also live in `.cursor/rules/ritual-memory.mdc` → `## Сейчас пропущено`.

Journal starts at `catalog.json` → `ritual.journalStart`. Do not backfill earlier days.

```markdown
# YYYY-MM-DD

## Утро
- Статус: sent | answered | skipped | missed
- Отправлено: …
- Ответ: —
- Фокус: —

## Вечер
- Статус: sent | answered | skipped | missed
- Отправлено: —
- Ответ: —
- Итог: —
- Мешало: —
```

`sent` = asked, waiting. `answered` = владелец ответил. `skipped` = он написал «пропустил», или вечер дня без фокуса закрыт как выходной. `missed` = слот протух без ответа (ставит следующий ритуал).

Вечер без ответа — открытый пропуск только если в тот день был фокус. «сегодня ничего» / «отдыхаем» и `Фокус: —` — фокуса не было: такой вечер становится `skipped` и в `## Сейчас пропущено` не попадает. Голос с дневником, свободная заметка или «день нормальный» без минут и без явного итога по фокус-задачам вечер не закрывает.

Each slot write is committed and pushed to `master` in the same Cloud run. The next morning/evening reads `master`, not a leftover PR.
