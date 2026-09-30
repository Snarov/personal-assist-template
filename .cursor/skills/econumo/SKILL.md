---
name: econumo
description: Records and reads the owner's finances in his self-hosted Econumo (accounts, expenses, income, transfers, debts, budgets, categories). Use when he mentions Econumo, a payment, an expense, income, a transfer, a debt, an account balance, an account from catalog.json → econumo, потратил, перевёл, пришло, or asks to log money from Telegram or this repo.
---

# Econumo

The owner's books live in Econumo, not in Notion, `journal/`, `routine/`, or `notes/`. A money clause is not a task comment, not a diary line, and not a free note. The shelf is `catalog.json` → `econumo`, not a list in this skill.

Addresses and the secret names are in `catalog.json` → `econumo`. Request shapes that have already bitten us are in [api.md](api.md). Read that file before the first write in a run.

## Credentials

Use `ECONUMO_BASE_URL`, `ECONUMO_USERNAME`, and `ECONUMO_PASSWORD` when those environment variables are set (Cursor cloud secrets). Otherwise read the same three names from Infisical using `catalog.json` → `econumo.secrets` (project, environment, path). MCP `user-infisical` / `infisical`.

Never print the password, a session token, or a personal access token. Never commit them. Never SSH to the VPS for a normal money write.

Login: `POST /api/v1/user/login-user` with `{username, password}`. The body is `{token, user}`, not wrapped in `data`. Send `Authorization: Bearer <token>` after that.

## Books

Read `catalog.json` → `econumo` before the first write. Profile currency is `currency`. Own accounts are `accounts` in folder `folders.own`. Debts are `debtAccounts` in `folders.debts`. The budget is `budget`. Categories are flat; a child keeps the 1Money name `Parent (Child)`.

A debt name in `debtNameStoredAs` is stored under the mapped spelling because a name must be 3–64 characters. Leave it that way.

Do not recreate a name in `removedAccounts`. A string in `categoryNotAccount` is a category, not an account.

Fetch the live account list and category list before writing. The catalog is the intended shelf, not a cache of balances.

## What he says

Do not invent an amount, a category, a currency, a date, or a direction. Today's date is `catalog.json` → `timezone` when he does not name one. The amount is in the account's currency unless he names another. If he does not name an account, use `defaultAccount` (set on `defaultAccountSetOn`). An alias in `aliases` maps his word onto that account. A named account still wins.

| He means | Do |
| --- | --- |
| Spent, paid, купил | Expense on the account he named, category he named |
| Income, пришло, зарплата | Income on that account. A word in `aliases` lands on the mapped account |
| Transfer, перевёл с … на … | Transfer. Both accounts and, if the currencies differ, both amounts |
| Set a balance, «на карте сейчас N» | `update-account` to that balance. Not an expense |
| «обнули» / «в ноль» | Set that account, or every account if he means all of them, to `0.00` |
| Debt and a direction | «я должен Маме» is a negative balance on Мама. «Мама должна мне» is positive. A number with no direction → ask once |
| no account, or «карта» with no bank | `defaultAccount`. Do not ask which own account |
| New own account | Only when he names it and the currency. Do not pick the currency |
| Delete | Only the account he named |

Match a category by the live list. `кофе` → `Еда (Кофе)` when that is the only fit. Two categories could fit → ask. Create a category only when he says it is a new one and gives the name. Put a new expense category into the budget envelope group he names, or ask which group.

A pure balance correction writes a `Balance adjustment` dated now, and the open budget month then shows it as income or spending. After you re-read the account and the balance matches, move that adjustment's date to the last second before the budget `startDate` (`Y-m-d H:i:s`). Do not move a real expense, income, or transfer.

## After a write

Re-fetch the account (and the transaction, for a payment). The confirm states the account, amount, currency, and category or the other account, in his words. If the write did not stick, say so in the same message.

An expense is not finished until **Pace** has run. Income, a transfer, a debt, and a balance correction do not run it.

Telegram: one result inside the reply he already gets (`POST /send`, `kind=reply`, `purpose=confirm`). Do not send a second «принял». The pace alert, when the script sends one, is a separate message (`kind=pace`). Do not paste it into the confirm. Then `POST /inbox/ack` for the messages you handled. Money-only text does not close a ritual slot and does not become a diary answer.

In this repo, with no Telegram ask, do not message Telegram. The pace script is the exception: it sends its own alert when this expense pushed a budget line over the day's pace.

## Pace

After every `create-transaction` of type `expense`, and after an expense whose amount went up, run this before the confirm:

```bash
python3 .cursor/skills/econumo/scripts/spending_pace.py \
  --category "Еда (Кофе)" \
  --amount 4.50 \
  --currency BYN
```

`--category` is the category just written, name or id, as stored. `--amount` is that expense in the account currency. `--currency` is the account currency (`catalog.json` → `econumo.currency` when he did not name one). `--date` is the expense date `Y-m-d` when it is not today in `catalog.json` → `timezone`.

The limit sits on the envelope in the budget named by `catalog.json` → `econumo.budget.name`, not on a child category. «Еда (Кофе)» counts toward Еда. A child has no pace of its own.

Today's pace is `budget × day / days`. `day` is today's date in `catalog.json` → `timezone`, `days` is the length of that month. On 29 September a budget of 3000 has pace 2900. Spending equal to the pace is not over.

The script sends Telegram only when this expense moved the envelope from at or under the pace to over it. A later expense in an envelope that is already over does not send again. The message is one line, for example: `Еда выше темпа из-за «Еда (Кофе)»: 3100 BYN при темпе 2900 (бюджет 3000, день 29 из 30).`

It uses `kind=pace` and `purpose=alert`, so it does not take the confirm slot. Do not send that text yourself.

An envelope with no planned amount has no pace. The script does not notify. Do not invent a limit. Say the category is not in the budget when `matched` is false.

An expense dated outside the current month does not change today's pace. The script does not notify.

If the script prints `ok: false` or exits non-zero, say in the same reply that the pace check did not finish. Do not say the spending is within the pace.

There is no Cursor hook for this. The write is an API call, not a file event, and a hook on every turn would fire without a new expense. This command is the required step. Do not pass `--no-notify` after a real expense. That flag is a dry reading.

With no `--category`, the script prints every envelope that has a budget and does not send. Use that when he asks how the pace looks, not after a write.

## History already loaded

`catalog.json` → `econumo.historyImport` names the file already loaded when `loaded` is true, from `from` through `through`. Income with an empty category is `uncategorized`. Accounts that are not on the live shelf are in `deletedFolder`, named with `deletedSuffix`. They are not in the budget `budget.name`. Do not import that file again while `loaded` is true. The script matches an existing operation by date, accounts, amount, category, and note, because Econumo replaces the request id.

Balances are the sum of these operations. The export has no opening balances. He types the current cash himself. Do not copy the footer snapshot from that file, and do not zero the accounts after the import.

## Do not

- Finish an expense without `scripts/spending_pace.py`. Do not pass `--no-notify` on that run.
- Import `econumo.historyImport.file` again while `loaded` is true.
- Restore a balance from that file. He enters the current cash himself.
- Put money into Notion, `journal/`, `routine/`, or `notes/`.
- Guess a rate. The base currency is USD. A stored rate is how many units of that currency equal 1 USD. If a total looks like mixed currencies added together, say the rate is missing. Do not edit the server database to invent one.
