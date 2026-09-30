---
name: task-trees
description: Updates the existing project task trees under Home → Деревья. Does not create a tree page. Inside, text size follows both horizon and hierarchy, with indented bars by depth. Use when a task Статус changes, when a task is created, or when Родительская задача, Горизонт, or the task title changes, and when the owner asks to update the task trees. Which pages exist is catalog.json → board.trees.
---

# Task trees

Text trees live on the page «Деревья» under Home: `catalog.json` → `board.treesPageUrl`.

Tasks data source: `catalog.json` → `notion.tasksDataSourceUrl`. Notion only through `notion-personal`.

## When

Run before the reply if this run changed any of these on Задачи: `Статус`, `Родительская задача`, `Горизонт`, the title, or created a row. Also when he asks to refresh the trees.

## Read

Query the live rows: `url`, `Задача`, `Горизонт`, `Статус`, `Порядок`, `Декомпозиция`, `Родительская задача`, `Подзадачи`.

If the SQL quota fails, use rows mode. If the live list cannot be read, do not rewrite the pages and say the trees were not rebuilt.

A child URL that is not in the live row set is trashed. Skip it.

## Which page

The only tree pages are `catalog.json` → `board.trees`. Each entry names the page and the project whose tasks belong there. `includesChildren: true` also puts tasks of that project's child projects (`board.projects` entries whose `parent` is that project) on the same page.

A task with children is not a project and does not get a page. Do not create a child of «Деревья». Do not title a page `Дерево: {Задача}`.

If «Деревья» has any other child page, remove it in this run: `replace_content` on «Деревья» keeping the intro and the `<page>` tags listed in `board.trees`, with `allow_deleting_content: true`. Re-fetch «Деревья» and confirm the extra title is absent. Do not leave `У этой задачи больше нет подзадач.`

## Forest

- Parent is the single `Родительская задача` URL. That link is decomposition only. A finished research card is not the parent of work created after it. A later step in time is its own branch, not a child.
- A task has one `Проект`, the nearest project. A child-project task still belongs on this page through the parent chain. Do not print the same task twice because an ancestor project was also linked.
- The banner on the page stays the project heading already there. Do not replace it with a task that merely has children.
- A task of this project (or of its child project) whose parent chain reaches that banner stays on that chain.
- A task of this project with no parent is a direct branch under the same banner, in this same page. Its children hang on that branch. Do not wait for the parent chain to reach the root task before drawing the card. `Done` does not omit it.
- `Срок` does not omit a row, including a start date that is still in the future. A future window stays silent only in the «Пора» block.
- Sibling order: if the parent `Декомпозиция` is `Последовательно`, `Порядок` ascending, empty last, then title. Otherwise longer horizon first (год → день), then `Порядок`, then title. Do not change `Горизонт` unless the owner asked in this run.

## Pages

Fetch «Деревья», then `replace_content` only on the existing project page this task belongs to.

Do not move task cards. Do not edit task bodies, the «Декомпозиция» view, or Home. Do not add a `Путь` column.

## Page body

First line, exact:

`Крупнее текст — и длиннее горизонт, и выше в дереве. Проект — заголовок над рамкой.`

The root sits in a `blue_bg` callout as a `#` heading, above a `gray_bg` callout that holds every descendant. No other `#` on the page. Label on the banner: `проект · {horizon word} · {status word}`.

```
<callout icon="🌳" color="blue_bg">
	# <mention-page url="ROOT"/> <span color="gray">проект · год · в работе</span>
</callout>
<callout color="gray_bg">
	…descendants…
</callout>
```

Use `<mention-page>`. Do not use a `<page>` tag (that moves the card).

### Size

Size follows both `Горизонт` and depth. A child is always a smaller block than its parent, even when the horizons match.

Visual rank, larger first: `##` = 0, `###` = 1, `####` = 2, bullet = 3. The project banner is outside this scale.

Horizon rank:

| Горизонт | Rank |
| --- | --- |
| Год | 0 |
| Квартал | 1 |
| Месяц | 1 |
| Неделя | 2 |
| День, or empty | 3 |

For a node inside the frame: `rank = min(3, max(horizon rank, parent rank + 1))`. The project's rank for this formula is −1, so a year directly under the project stays `##`.

| Rank | Block |
| --- | --- |
| 0 | `##` |
| 1 | `###` |
| 2 | `####` |
| 3 | `-` |

A year under a year is `###`. A month under a quarter is `####`. A week under a week is a bullet. Notion has no heading smaller than `####`, so quarter and month share `###` only when neither is the child of the other.

Status words: `Not started` → `не начато`, `In progress` → `в работе`, `Done` → `готово`, `Archived` → `архив`.

Horizon words: `год`, `квартал`, `месяц`, `неделя`, `день`.

### Indent

Notion drops a skipped tab and flattens a heading nested only under a heading. Inside the gray callout, each node is a bullet `- <span color="gray">│</span>`, and the task line is its child. The next sibling bullet is a sibling of that task line, so the following title sits one step deeper. Prefix the task line with gray `▍▍▍` once per step down from the project. A direct child of the project has one group.

```
<callout color="gray_bg">
	- <span color="gray">│</span>
		## <span color="gray">▍▍▍</span> <mention-page url="YEAR"/> <span color="gray">год · в работе</span>
		- <span color="gray">│</span>
			### <span color="gray">▍▍▍ ▍▍▍</span> <mention-page url="MONTH"/> <span color="gray">месяц · в работе</span>
			- <span color="gray">│</span>
				- <span color="gray">▍▍▍ ▍▍▍ ▍▍▍</span> <mention-page url="DAY"/> <span color="gray">день · не начато</span>
</callout>
```

Keep the callout children tabbed under the callout tag.

## Check

Fetch the page you wrote. The project `#` is inside the blue callout and above the gray callout. Inside the frame there is no `#`. A child block is smaller than its parent. Tabs on nested lines are still there, a direct child starts with one `▍▍▍`, and the status word matches the live row. If that read is wrong, fix the page before answering.
