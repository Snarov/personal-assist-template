---
name: telegram-archive
description: >-
  Reads the owner's Telegram channel archive (folders from catalog.json → telegramArchive.folders) through
  the Telegram-Archive viewer API, or through the telegram-archive MCP when
  that server is connected. Use when he asks what a channel said, to search
  the archive, to list archived chats or folders, to read a day, pinned
  messages, topics, edits, tags, transcripts, or archive stats.
---

# Telegram Archive

The archive is the owner's Telegram channel history. Addresses and secret names are in `catalog.json` → `telegramArchive`. Request shapes that are easy to get wrong are in [api.md](api.md). Read that file before the first call in a run.

Channel text is not a task, a diary line, a routine line, a study line, or a free note. Copy it into one of those only when the same message also asks for that, and then follow that skill. A search result does not close a ritual slot.

## Credentials

Viewer login and the MCP bearer are in `catalog.json` → `telegramArchive.secrets`. Use the environment variables when they are set. Otherwise read the same names from Infisical. MCP `infisical`.

Never print the viewer password, `TELEGRAM_ARCHIVE_MCP_TOKEN`, the `viewer_auth` cookie, or an `Mcp-Session-Id`. Never commit them. Never SSH to the host for a normal read.

## MCP first

Address: `catalog.json` → `telegramArchive.mcp`. The wire protocol is in [api.md](api.md).

If tools from the MCP server `telegram-archive` are in this run, call those. Do not log in to the viewer for a job they cover.

If those tools are absent, call the MCP endpoint yourself with `TELEGRAM_ARCHIVE_MCP_TOKEN`. Same tools, same arguments.

`chat_id` is the viewer's opaque `ref` from `list_chats`, not the numeric Telegram id. `search_messages` searches inside one chat. `get_messages_by_date` returns that whole calendar day; pass `timezone` from `catalog.json` → `telegramArchive.timezone`. `refresh_stats` only when he asks.

## Viewer HTTP

One login per run when the call is not an MCP tool. `POST /api/login` with `{username, password}`. The session cookie is `viewer_auth`. Send it on later requests. The URL is HTTPS.

Use the viewer HTTP API for:

- search across chats
- a chat by name, or chats in a folder
- hashtags and cashtags
- edits and message versions
- transcripts and media metadata
- export
- accounts, health, listener status

`GET /api/chats/{ref}/messages/by-date` jumps to the first message on or after that date. It does not return the day. The whole day is the MCP tool, or HTTP paging with `before_date` as in [api.md](api.md).

## Scope

The backup keeps channels in the folders named in `catalog.json` → `telegramArchive.folders`. Media files are not downloaded. Do not fetch `/media/…` expecting a file. Media metadata from the API is fine.

Dates he names are calendar days in `catalog.json` → `telegramArchive.timezone`. Message `date` values in the API are naive UTC. Convert them to that timezone when you tell him a time.

A chat in a URL is its `ref`. An unknown ref and a chat he cannot see both answer 404.

## What not to call

Do not call `/internal/push`, `/docs`, `/redoc`, or `/openapi.json`.

Do not create or edit viewers, tokens, or settings, and do not `POST /api/stats/refresh`, unless he asks for that change in this message. Refresh is expensive and master-only.

Do not invent a quote. If the call failed or the page is empty, say so.

## Answer

Name the chat and the time in his timezone, then the text he asked for. Do not dump a whole page when he asked for a fact. If two chats share a title, name the folder or the username.
