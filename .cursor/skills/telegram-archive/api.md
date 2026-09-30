# Viewer API and MCP

## MCP

Endpoint: `catalog.json` → `telegramArchive.mcp.endpoint`. Header `Authorization: Bearer` plus `TELEGRAM_ARCHIVE_MCP_TOKEN`. Header `Accept: application/json, text/event-stream`. Body is JSON-RPC 2.0.

1. `initialize` with `protocolVersion` `2025-03-26`, empty `capabilities`, and a `clientInfo`. The response header `Mcp-Session-Id` is required after this.
2. `notifications/initialized` with that session header. No `id`.
3. `tools/call` with `params.name` and `params.arguments`. `resources/read` uses `params.uri`.

A missing or wrong bearer is 401. Do not retry in a loop.

Tools: `list_chats`, `list_folders`, `search_messages`, `get_messages`, `get_pinned_messages`, `get_messages_by_date`, `get_chat_stats`, `get_topics`, `refresh_stats`.

Resources: `telegram-archive://stats`, `telegram-archive://chats`, `telegram-archive://folders`, `telegram-archive://health`.

`list_chats` takes `limit` (default 100). Other chat tools take `chat_id`, and that value is the `ref` from `list_chats`. `search_messages` also takes `query` and `limit` (default 20, max 200). `get_messages` takes `limit` (default 50, max 500), `offset`, or `before_date` plus `before_id`, or `after_id`. `get_messages_by_date` takes `date` `YYYY-MM-DD`, `timezone`, and `limit` (default 1000, max 5000). Dates in tool results are naive UTC.

`GET /api/chats/{ref}/messages/by-date` on the viewer is a different call: it jumps to one message. The MCP tool returns the day.

## Viewer API

Base URL: `catalog.json` → `telegramArchive.baseUrl`. Cookie after login: `viewer_auth`.

Search is word-prefix AND. `undo` does not match `mundo`. Punctuation-only queries fall back to a substring scan. Page with `offset` until `has_more` is false. Offset stops at 5000 on global search.

## Login

`POST /api/login` body `{"username","password"}`. Success is `{"success": true, "role": "master"|"viewer", "username"}` plus `Set-Cookie: viewer_auth=…`. 401 is a bad password. 429 is the login rate limit: stop and say so, do not retry in a loop.

## Find a chat

`GET /api/chats?search=&folder_id=&limit=&offset=`

`folder_id` is a Telegram folder id from `catalog.json` → `telegramArchive.folders`. The body is `{chats, total, limit, offset, has_more}`. Each chat has `ref` (put this in later URLs), `id` (numeric Telegram id, not a URL), `title`, `username`, `type`, `folder_id`.

`GET /api/chats/{ref}` is one chat. `GET /api/folders` lists every Telegram folder on the account. Only the ids in `catalog.json` → `telegramArchive.folders` are backed up.

## Messages in one chat

`GET /api/chats/{ref}/messages`

| Query | Meaning |
| --- | --- |
| `limit` | 1–500, default 50. Newest first |
| `offset` | Slow on deep pages |
| `search` | Word-prefix search inside this chat |
| `before_date` | Naive UTC ISO timestamp. Pair with `before_id` to page older |
| `before_id` | Message id. With `before_date`, the keyset cursor. Alone, ids smaller than this |
| `after_id` | Ids greater than this |
| `topic_id` | Forum topic |

The body is a list of messages, not wrapped. `date` is naive UTC.

A whole calendar day in Europe/Moscow: take local midnight and the next local midnight, convert both to naive UTC, then page with `before_date` set to the end instant and `before_id` from the last row, and keep rows whose `date` is still ≥ the start instant. Stop when a row is older than the start.

`GET /api/chats/{ref}/messages/by-date?date=YYYY-MM-DD&timezone=Europe/Moscow` returns one message: the first on or after that local date. 404 means nothing on or after it.

`GET /api/chats/{ref}/pinned`

`GET /api/chats/{ref}/topics`

`GET /api/chats/{ref}/stats`

## Across chats

`GET /api/search/messages?q=&limit=&offset=`

`limit` 1–100. Body: `{query, limit, offset, has_more, indexed, results}`. Each result has `id`, `date`, `text`, `sender_name`, `matched_in` (`transcript` when only a transcript matched), and `chat.ref` plus `chat.title`.

`GET /api/tags/{tag}?scope=all|mine|chat&chat_ref=&limit=&offset=`

`tag` is `#word` or `$TICKER` (1–8 latin letters). `#` plus only digits is rejected. `scope=chat` requires `chat_ref`.

## Edits, media, export

`GET /api/changes` — recent edits across the archive.

`GET /api/chats/{ref}/messages/{message_id}/versions` — one message's history.

`GET /api/chats/{ref}/media` and `GET /api/chats/{ref}/media/counts` — metadata. The backup does not store media files.

`GET /api/media/{media_id}/transcripts` and `GET /api/chats/{ref}/media/{media_key}/transcripts` — text of a voice or audio, when a transcript exists.

`GET /api/chats/{ref}/export?from=&to=` — JSON. `from` is inclusive. A bare `to` date includes that whole day.

## Status

`GET /api/health` — no auth required by the route list; still send the cookie.

`GET /api/stats` — archive totals. Timezone in the payload is the viewer's.

`GET /api/status` — listener and database. Read this when he asks whether the listener is up.

`GET /api/accounts` — which Telegram account the archive is signed in as.

`POST /api/stats/refresh` — only when he asks. Master session. Expensive.
