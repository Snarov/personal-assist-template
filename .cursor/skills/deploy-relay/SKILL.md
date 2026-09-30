---
name: deploy-relay
description: Deploys telegram-relay to the host in catalog.json and checks /health. Use when the user says deploy to prod, deploy the relay, ship telegram-relay, or выкати реле.
---

# Deploy relay

The host, unit, paths, port, and nginx site are `catalog.json` → `deploy`. The only deploy path is `./telegram-relay/deploy.sh` from the repo root. It copies `relay.py` over SSH, writes the systemd unit from those fields, restarts only `deploy.unit`, and waits for `/health` on `deploy.bind`:`deploy.port`.

Another relay on the same host is a separate instance file, starting from `telegram-relay/instances/example.json`. Deploy it with `./telegram-relay/deploy.sh telegram-relay/instances/example.json` after that file has its own unit, directory, and port. `hermesEnv` stays empty unless this instance really has one. The script refuses to run if the instance file points at the same unit, directory, or port as `catalog.json`. Without `TELEGRAM_BOT_TOKEN` and `allowedChatId` it installs the unit and does not enable it.

Do not restart any other unit. Do not SSH to the host except through this script, and do not run the script unless the owner asked to deploy.

Ships `relay.py` on disk, not a git ref. If that file differs from `HEAD`, say so before deploying. `telegram-relay/personal-assist-telegram.service` is a snapshot of this instance. The script generates the live unit and does not copy that file.

## Deploy

1. From `telegram-relay/`: `python3 test_relay.py`. Stop if it fails.
2. Read `host`, `unit`, and `installDir` from `catalog.json` → `deploy`. Compare checksums. Do not print `relay.env`.

```bash
sha256sum telegram-relay/relay.py
ssh -o BatchMode=yes "$HOST" "sha256sum $INSTALL/relay.py"
```

3. If the hashes already match, say this host is on this build and stop. Do not restart.
4. From the repo root: `./telegram-relay/deploy.sh` for the catalog instance. For another instance: `./telegram-relay/deploy.sh telegram-relay/instances/example.json`.
5. Confirm the remote `relay.py` hash equals local for that install directory. The primary unit must stay `active`. A second unit with no bot token stays disabled; do not treat that as a failed primary deploy. When the selected unit is enabled, `/health` on its port has `"ok": true`.

`relay.env` on the host is not overwritten. A new file gets the chat id, bind, port, state path, and Cursor environment name from the catalog. The script appends `CURSOR_API_KEY`, `CURSOR_ENV_NAME`, and `RELAY_LAUNCH_COOLDOWN_SEC` only when those lines are missing. A new setting that already has a default in `relay.py` (for example `RELAY_SEND_DEDUPE_SEC`) needs no host edit.

When `deploy.hermesEnv` is set, the bot token may live only in that file. When it is empty, `TELEGRAM_BOT_TOKEN` must be in `relay.env` or in the environment that runs `deploy.sh`. Without a token the script installs the unit and does not enable it, so `Restart=always` cannot crash-loop on an empty token.

## If it fails

`deploy.sh` exits non-zero and prints `systemctl status` for `deploy.unit` when `/health` does not answer. Then:

```bash
ssh -o BatchMode=yes "$HOST" "journalctl -u $UNIT -n 80 --no-pager"
```

Report that output. Do not loop restarts. If `ssh` to `deploy.host` fails in batch mode, stop and say the host is unreachable.

## Report

- Whether `relay.py` changed on the host
- `/health` JSON (`ok`, `inbox`, `last_launch`, `last_archive`)
- Service state of `deploy.unit` only

Do not commit this deploy. A skill or script edit still waits for «ок» / «заливай».
