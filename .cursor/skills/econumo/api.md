# Econumo API notes

Base URL from `ECONUMO_BASE_URL`. OpenAPI is `GET /api/doc.json`. Health is `GET /health`.

Login `POST /api/v1/user/login-user` returns a raw `{token, user}`. Other calls use `Authorization: Bearer` and wrap success as `{success, data}`.

Dates on writes are `Y-m-d H:i:s`, not ISO-8601. `updatedAt` on an account update uses that same format and must be non-empty.

## Accounts

`POST /api/v1/account/create-account` requires `id` (uuid), `name` (3–64), `currencyId`, `folderId`, `balance` (string), `icon`. Blank `icon` is a 400. `account_balance_wallet` is accepted.

`POST /api/v1/account/update-account` requires `id`, `name`, `balance`, `currencyId`, `icon`, `updatedAt`. It reconciles the balance with a transaction described `Balance adjustment`.

`POST /api/v1/account/move-account` body `{id, folderId, afterId}`. `afterId` null places the account first in that folder.

`POST /api/v1/account/delete-account` is a soft delete. `POST /api/v1/budget/remove-account` (`{id: budgetId, accountId}`) first, or the budget still references it.

`GET /api/v1/account/get-account-list` and `get-folder-list` are the check after a change. A 200 from the write is not the check.

## Transactions

`POST /api/v1/transaction/create-transaction`: `id`, `type` (`expense` | `income` | `transfer`), `accountId`, `amount` (string), `date`. Expense and income need `categoryId`. A transfer needs `accountRecipientId` and `amountRecipient`. The list afterwards returns a server id, not the id from the request, so a repeat import has to match the operation itself.

`POST /api/v1/transaction/delete-transaction` body is `{id}`.

`GET /api/v1/transaction/get-transaction-list` needs `periodStart` and `periodEnd` as `Y-m-d H:i:s`. A date-only value returns 400.

`POST /api/v1/transaction/update-transaction` can move `date`. Send `id`, `accountId`, `amount`, `type`, `description`, `date`.

## Budget plan and pace

`GET /api/v1/budget/get-budget-plan?id=&from=Y-m-d&months=1` is the month sheet. `from` snaps to the first of the month. Each expense envelope has `cells[0].planned` (the budget) and `cells[0].actual` (spent). A child category has `actual` only. The pace check uses the envelope: `planned × day / days`, day = today's date in Europe/Moscow. An empty `planned` is not a budget. See `scripts/spending_pace.py`.

`GET /api/v1/budget/get-budget-list` finds **Основной**.

## Budget and categories

`/budget` stays empty until a budget exists and categories sit in its envelopes. Categories in the catalog are not enough.

`POST /api/v1/budget/create-budget`: `id`, `name`, `currencyId`, `accountIds` (at least one), `startDate`.

`POST /api/v1/budget/create-folder`: `id`, `budgetId`, `name`.

`POST /api/v1/budget/create-envelope`: `id`, `budgetId`, `folderId`, `currencyId`, `name`, `categories` (ids), `side` (`expense`), `icon` (`category` is accepted).

`POST /api/v1/category/create-category`: `id`, `name`, `type` (`expense` | `income`).

Profile currency: `POST /api/v1/user/update-currency` with `{"currency":"<catalog.json → econumo.currency>"}` (ISO code, not an id).

## Currencies

`POST /api/v1/currency/update-currency` returns 403 for currencies created by the CLI (`user_id` is null). Do not loop on that call.

`GET /api/v1/currency/get-currency-rate-list` is the latest row per currency. Rate is units of that currency per 1 USD. The base currency is USD.
