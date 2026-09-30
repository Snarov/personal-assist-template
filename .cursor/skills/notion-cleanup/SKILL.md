---
name: notion-cleanup
description: Deletes, merges, reclassifies, and re-filters pages in the owner's personal Notion (Goals → Projects → Tasks). Use when he says a project is not a project, asks to remove or merge cards, or a view shows the wrong tasks.
---

# Notion cleanup

Structural changes in `notion-personal` only. Read `.cursor/rules/notion-workspace-hygiene.mdc` first. IDs in `catalog.json` → `notion`.

## Tools

- `notion-fetch` on a `collection://` or `view://` URL to see rows and view filters.
- `notion-move-pages` to change parent (row → page, page → database, task → other project is a **relation**, not a move).
- `notion-update-page` for properties, content, and view filters (`view://` pages accept `advancedFilter` and sorts).
- `notion-query-data-sources` can hit the plan limit mid-session (`plan_required`). Fall back to `notion-fetch` of the view / data source and `notion-search`.

## Delete a database row (the only way that works)

1. Confirm with the list first: fetch the Проекты data source (`projectsDataSourceUrl`) or the view the owner is looking at. Copy the exact page ids.
2. If the row has children or relations you want to keep, relink them to the survivor first (tasks → `Проект`, goal → `Проекты`).
3. `notion-move-pages` the row(s) into the scratch page «Не проекты» (`scratchBinPageUrl`). Reuse that page; do not create another bin.
4. `notion-update-page` on the scratch page: `command: replace_content`, `new_str` = one line («Пусто»), `allow_deleting_content: true`. Removing the child-page references deletes the moved pages.
5. Verify: re-fetch the data source / view **and** each parent goal page. The title must be absent from Проекты and from Goals → Проекты. Only then report.
6. Do not call `in_trash: true`. It returns success and does nothing.

Fallback if `move-pages` refuses (locked, archived ancestor): stop and tell the owner which page to trash by hand. Do not mark it Cancelled and call that done.

## Merge duplicate projects

1. Pick the survivor (the one with more tasks / the older card). Rename it if the merged name is broader.
2. Relink every task of the loser: set `Проект` to the survivor.
3. On the goal page, remove the loser from `Проекты`, make sure the survivor is present.
4. Delete the loser with the procedure above.
5. Update the survivor's body if it listed scope.

## Reclassify a project into a task

1. Check Задачи for an existing task with that title. If present, the "project" is a duplicate — just delete it.
2. Otherwise create the task through `create-task`, with `Проект` = the real project and `Статус` as the owner said. Do not delete the project card until that task's re-fetch shows project, horizon, priority, and parent or an explicit «без родителя».
3. The parent, horizon, and priority come from `create-task`. Do not leave `Горизонт=Месяц` unless he put this task on this month.

## Same task in two project groups

The tasks timeline «Дорожная карта» repeated every card of a child project: once in that project's band, again under its parent project. Cause: `Проект` held both the child project and its ancestor, and the view grouped by `Проект`. Sub-items then drew the same branch under both groups.

1. Fetch the view the owner is looking at. A `groupBy` on `Проект` plus a task whose `Проект` contains a project and that project's `Родительский проект` is this bug.
2. Set `Проект` to the nearest project only. Work on a child project stays on that child. Do not also link the parent project.
3. Leave `Родительская задача` as the one parent chain. Do not add a second parent and do not mint a task that only repeats a project name.
4. «Дорожная карта» does not group by `Проект`. If grouping is back, `CLEAR GROUP BY` on that view. Nesting is `Родительская задача`.
5. Re-fetch the task and the view. `Проект` is one URL. The view has no `groupBy`.

## Fix the «Месяц» view

- Filter: `Горизонт = Месяц` AND `Статус ∈ {In progress, Not started}`.
- Walk the rows: anything the owner did not name for this month → `Горизонт = Год`. Do not touch `Статус` while doing that.
- Re-fetch the view and list the survivors back to him.

## Verification checklist (before saying «готово»)

- [ ] Fetched the database view / data source after the write.
- [ ] Fetched each affected goal page; Проекты relation is correct.
- [ ] Tasks that pointed at a deleted project now point at the survivor.
- [ ] No new pages created that he did not ask for (except the scratch bin).
- [ ] Message names what was actually deleted, merged, relinked, and anything that failed.

## Postmortem 2026-09-13

What went wrong, in order:

1. **«Месяц» view.** Answered about the pile of tasks without opening the view's filter. It filtered only by `Статус`, so every `In progress` task showed up. Fix: added `Горизонт = Месяц`, moved stale tasks to `Год`, kept only the projects that belonged on that month.
2. **Phantom projects.** Several single deliverables and one duplicate lived in Проекты. A child task had also been promoted to a standalone monthly item. Fix: reclassified/relinked, deleted wrappers.
3. **Three false «deleted» reports.** First set `Статус=Cancelled`, then unlinked from Цели, then called `in_trash: true`. Each time reported success; each time the rows were still in Проекты and in Goals → Проекты. Root cause: trusted the write response instead of re-reading the list; the MCP ignores `in_trash`.
4. **What finally worked.** `notion-move-pages` out of the database into a scratch page «Не проекты», then `replace_content` on that page with `allow_deleting_content: true`. Verified against the data source and goal pages. Added `Статус ≠ Cancelled` filters to all six Проекты views as a safety net.
5. **Duplicate theme.** Two project cards described one effort. Merged into the survivor, relinked tasks and the goal.

Residue: the scratch page «Не проекты» still exists, empty. Reuse it as the bin; The owner can trash it by hand.

## Postmortem 2026-09-28

The roadmap showed a child project's tasks, then the same titles again under the parent project. Each of those tasks was linked to the child project and to the parent project, and the timeline grouped by `Проект`. Fix: one `Проект` (the child), parent chain left as the hierarchy, grouping removed from «Дорожная карта».

## Postmortem 2026-09-24

A sketch appeared as a Проекты row. The chat said «создай мне проект» and «сам поймёшь, под какую цель». The agent picked a goal, invented status, horizon, and dates, rewrote the goal page, and left the card with no tasks. He meant an idea. Fix: unlink the goal, delete the row through the scratch bin, put his sentence in Идеи with `Статус=Новая` and an empty review date. A sketch without a goal he named is not a project.

## Live layout 2026-09-14

Old hub «Дом», old «Планирование», «Метрики», and «Служебное» are in trash. MCP cannot restore them (`source_in_trash`). Do not write ritual rows there, and do not put those URLs back into `catalog.json`.

Live hub is catalog `hubPageUrl` (Дом). Live day board is titled «Фокус» (`planningPageUrl` / `planningDataSourceUrl`). Day cards live in the «Дни» view. The Tasks view «Сегодня» filters `Фокус сегодня`, not due date. «Месяц» stays `Горизонт = Месяц` AND `Статус ∈ {In progress, Not started}`.
