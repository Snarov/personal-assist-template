# Учёба

Отдельный дневной лог учёбы. В понедельник–пятницу к норме прибавляется 30 минут, недобор переходит на следующий будний день. Суббота и воскресенье 30 минут не начисляют и учёбу не спрашивают. Утро в будний день называет сегодняшнюю норму. Вечер спрашивает, удалось ли, сколько минут, что выучено и куда это уже внедрено или будет внедрено. Дни раньше `catalog.json` → `study.accrueFrom` в долг не входят. Пока дата пустая, долг не копится.

| Путь | Что это |
| --- | --- |
| `study.spec.json` | JSON Schema дневной записи и описание списка тем |
| `entries/YYYY-MM-DD.json` | Один день по часовому поясу Europe/Moscow |
| `topics.json` | Плоский список тем, в порядке записи |

Дневная запись живёт в git. В Notion одна база «Учёба» (`catalog.json` → `study`): плоский список карточек. Одна карточка — одна тема или одно упражнение. Свойство только «Тема». На карточке материалы и ссылки. Приоритета, родителя, горизонта, минут и даты нет. Отдельной базы «Темы учёбы» нет. Отчёт дня отдельной строкой не становится. Это не строка в «Задачах».

Пример списка:

```json
{
  "spec": "study-topics",
  "specVersion": "1.0.0",
  "topics": [
    {
      "title": "Пример темы",
      "body": "Коротко, что это за тема.",
      "notionPageUrl": "https://www.notion.so/...",
      "added": "2026-01-01"
    }
  ]
}
```

Пример закрытого дня:

```json
{
  "spec": "study",
  "specVersion": "1.1.0",
  "date": "2026-09-30",
  "weekday": "ср",
  "status": "complete",
  "accruedMinutes": 30,
  "carryIn": 30,
  "dueMinutes": 60,
  "targetMinutes": 60,
  "carryOut": 0,
  "metTarget": true,
  "totalMinutes": 60,
  "items": [
    {
      "what": "как устроена выбранная тема",
      "minutes": 60,
      "goal": "Цель",
      "goalPageUrl": "https://www.notion.so/...",
      "project": "Проект",
      "projectPageUrl": "https://www.notion.so/...",
      "tasks": [
        {
          "title": "Задача",
          "pageUrl": "https://www.notion.so/..."
        }
      ],
      "tasksDeclined": false,
      "application": "применю это в названной задаче",
      "applicationWhen": "willImplement",
      "purpose": "зачем это внедрять",
      "notionPageUrl": null
    }
  ],
  "source": "voice"
}
```

Правила чтения и записи — в `.cursor/skills/study-log/SKILL.md`.
