#!/usr/bin/env bash
# Install the Telegram relay described by a catalog.
#   ./telegram-relay/deploy.sh
#       uses ../catalog.json (the primary instance)
#   ./telegram-relay/deploy.sh telegram-relay/instances/second.json
#       uses that file and refuses to touch the primary unit, directory, or port
# Touches only the selected deploy.unit. Never overwrites an existing relay.env.
# If deploy.hermesEnv is empty, TELEGRAM_BOT_TOKEN must already be in
# relay.env or in the environment. Without a token the unit is installed
# and left disabled. This script does not start any other unit.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PRIMARY="$ROOT/../catalog.json"
if [[ $# -gt 1 ]]; then
  echo "usage: ./telegram-relay/deploy.sh [instance.json]" >&2
  exit 1
fi
if [[ $# -eq 1 ]]; then
  if [[ "$1" = /* ]]; then
    CATALOG="$1"
  elif [[ -f "$1" ]]; then
    CATALOG="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
  elif [[ -f "$ROOT/../$1" ]]; then
    CATALOG="$ROOT/../$1"
  else
    echo "instance file not found: $1" >&2
    exit 1
  fi
else
  CATALOG="$PRIMARY"
fi

cfg="$(python3 - "$CATALOG" "$PRIMARY" <<'PY'
import json, os, shlex, sys
catalog_path, primary_path = sys.argv[1:]
data = json.load(open(catalog_path, encoding="utf-8"))
deploy = data["deploy"]
telegram = data["telegram"]
if os.path.realpath(catalog_path) != os.path.realpath(primary_path):
    primary = json.load(open(primary_path, encoding="utf-8"))["deploy"]
    same = []
    if deploy.get("unit") == primary.get("unit"):
        same.append("unit")
    if deploy.get("installDir") == primary.get("installDir"):
        same.append("installDir")
    if int(deploy.get("port") or 0) == int(primary.get("port") or 0):
        same.append("port")
    if same:
        raise SystemExit("instance file targets the primary relay (" + ", ".join(same) + "); refusing")
    if deploy.get("hermesEnv"):
        raise SystemExit("a second instance must not set deploy.hermesEnv")
cursor_env = deploy.get("cursorEnvName")
if cursor_env is None:
    cursor_env = data.get("cursorEnvironment") or ""
fields = {
    "REMOTE": deploy["host"],
    "DEST": deploy["installDir"],
    "STATE_DIR": deploy["stateDir"],
    "UNIT": deploy["unit"],
    "BIND": deploy.get("bind") or "127.0.0.1",
    "PORT": deploy["port"],
    "CHAT_ID": telegram.get("allowedChatId") or "",
    "NGINX_SITE": deploy["nginxSite"],
    "NGINX_LOCATION": deploy["nginxLocation"],
    "NGINX_INSERT": deploy.get("nginxInsertBefore") or "\tlocation = / {",
    "PYTHON": deploy["python"],
    "HERMES_ENV": deploy.get("hermesEnv") or "",
    "CURSOR_ENV": cursor_env or "",
}
for key, value in fields.items():
    print(f"{key}={shlex.quote(str(value))}")
PY
)" || exit 1
eval "$cfg"

REMOTE="${DEPLOY_REMOTE:-$REMOTE}"
DEST="${DEPLOY_INSTALL_DIR:-$DEST}"
echo "Deploying $UNIT from $CATALOG to $REMOTE:$DEST port $PORT"

UNIT_LOCAL="$(mktemp)"
trap 'rm -f "$UNIT_LOCAL"' EXIT
python3 - "$UNIT_LOCAL" "$UNIT" "$DEST" "$HERMES_ENV" "$PYTHON" <<'PY'
import sys
from pathlib import Path
path, unit, dest, hermes, python = sys.argv[1:]
lines = [
    "[Unit]",
    f"Description=Telegram relay ({unit})",
    "After=network-online.target",
    "Wants=network-online.target",
    "",
    "[Service]",
    "Type=simple",
    "User=root",
    f"WorkingDirectory={dest}",
]
if hermes:
    lines.append(f"EnvironmentFile=-{hermes}")
lines.extend([
    f"EnvironmentFile={dest}/relay.env",
    f"ExecStart={python} {dest}/relay.py",
    "Restart=always",
    "RestartSec=3",
    "NoNewPrivileges=yes",
    "",
    "[Install]",
    "WantedBy=multi-user.target",
    "",
])
Path(path).write_text("\n".join(lines))
PY

ssh "$REMOTE" "mkdir -p $(printf '%q' "$DEST") $(printf '%q' "$STATE_DIR")"
scp -q "$ROOT/relay.py" "$ROOT/relay.env.example" "$REMOTE:$DEST/"
scp -q "$UNIT_LOCAL" "$REMOTE:$DEST/${UNIT}.service"

q() { printf '%q' "$1"; }
ssh "$REMOTE" bash -s -- \
  "$(q "$DEST")" "$(q "$UNIT")" "$(q "$BIND")" "$(q "$PORT")" "$(q "$CHAT_ID")" "$(q "$STATE_DIR")" \
  "$(q "$NGINX_SITE")" "$(q "$NGINX_LOCATION")" "$(q "$NGINX_INSERT")" "$(q "$HERMES_ENV")" "$(q "$CURSOR_ENV")" \
  "$(q "${TELEGRAM_BOT_TOKEN:-}")" <<'REMOTE'
set -euo pipefail
DEST="$1"
UNIT="$2"
BIND="$3"
PORT="$4"
CHAT_ID="$5"
STATE_DIR="$6"
NGINX_SITE="$7"
NGINX_LOCATION="$8"
NGINX_INSERT="$9"
HERMES_ENV="${10}"
CURSOR_ENV="${11}"
TOKEN="${12:-}"

chmod 755 "$DEST/relay.py"
install -m 644 "$DEST/${UNIT}.service" "/etc/systemd/system/${UNIT}.service"

if [[ ! -f "$DEST/relay.env" ]]; then
  secret="$(openssl rand -hex 32)"
  umask 077
  {
    printf 'TELEGRAM_ALLOWED_CHAT_IDS=%s\n' "$CHAT_ID"
    printf 'RELAY_SECRET=%s\n' "$secret"
    printf 'RELAY_BIND=%s\n' "$BIND"
    printf 'RELAY_PORT=%s\n' "$PORT"
    printf 'RELAY_STATE_PATH=%s/state.json\n' "$STATE_DIR"
    printf 'CURSOR_WEBHOOK_URL=\n'
    printf 'CURSOR_WEBHOOK_KEY=\n'
    printf 'CURSOR_API_KEY=\n'
    printf 'CURSOR_ENV_NAME=%s\n' "$CURSOR_ENV"
    if [[ -z "$HERMES_ENV" && -n "$TOKEN" ]]; then
      printf 'TELEGRAM_BOT_TOKEN=%s\n' "$TOKEN"
    fi
  } > "$DEST/relay.env"
  echo "created $DEST/relay.env"
fi

if [[ -f "$DEST/relay.env" ]]; then
  # relay.py has no default chat: without this line every message is dropped.
  # An empty catalog chat id must not overwrite a chat id already in relay.env.
  if [[ -n "$CHAT_ID" ]] && ! grep -qE '^TELEGRAM_ALLOWED_CHAT_IDS=.+' "$DEST/relay.env"; then
    sed -i '/^TELEGRAM_ALLOWED_CHAT_IDS=$/d' "$DEST/relay.env"
    printf 'TELEGRAM_ALLOWED_CHAT_IDS=%s\n' "$CHAT_ID" >> "$DEST/relay.env"
  fi
  grep -q '^CURSOR_API_KEY=' "$DEST/relay.env" || echo 'CURSOR_API_KEY=' >> "$DEST/relay.env"
  grep -q '^CURSOR_ENV_NAME=' "$DEST/relay.env" || printf 'CURSOR_ENV_NAME=%s\n' "$CURSOR_ENV" >> "$DEST/relay.env"
  grep -q '^RELAY_LAUNCH_COOLDOWN_SEC=' "$DEST/relay.env" || echo 'RELAY_LAUNCH_COOLDOWN_SEC=360' >> "$DEST/relay.env"
  if [[ -z "$HERMES_ENV" && -n "$TOKEN" ]] && ! grep -qE '^TELEGRAM_BOT_TOKEN=.+' "$DEST/relay.env"; then
    sed -i '/^TELEGRAM_BOT_TOKEN=$/d' "$DEST/relay.env"
    printf 'TELEGRAM_BOT_TOKEN=%s\n' "$TOKEN" >> "$DEST/relay.env"
  fi
fi

if ! grep -qE '^CURSOR_WEBHOOK_URL=.+' "$DEST/relay.env" && ! grep -qE '^CURSOR_API_KEY=.+' "$DEST/relay.env"; then
  echo "WARNING: set CURSOR_WEBHOOK_URL or CURSOR_API_KEY in $DEST/relay.env so Telegram replies start a cloud agent" >&2
fi
if ! grep -qE '^CURSOR_API_KEY=.+' "$DEST/relay.env"; then
  echo "WARNING: set CURSOR_API_KEY in $DEST/relay.env to auto-archive finished ritual chats" >&2
fi

if ! grep -qF "location ${NGINX_LOCATION}" "$NGINX_SITE"; then
  python3 - "$NGINX_SITE" "$NGINX_LOCATION" "$NGINX_INSERT" "$BIND" "$PORT" <<'PY'
import sys
from pathlib import Path
path, location, needle, bind, port = sys.argv[1:]
if not location.endswith("/"):
    location += "/"
file = Path(path)
text = file.read_text()
block = (
    f"\tlocation {location} {{\n"
    f"\t\tproxy_pass http://{bind}:{port}/;\n"
    "\t\tproxy_set_header Host $host;\n"
    "\t\tproxy_set_header X-Real-IP $remote_addr;\n"
    "\t\tproxy_read_timeout 60s;\n"
    "\t}\n\n"
)
if needle not in text:
    raise SystemExit("nginx insert point not found")
file.write_text(text.replace(needle, block + needle, 1))
PY
  nginx -t
  systemctl reload nginx
fi

token_ok=0
if [[ -n "$HERMES_ENV" && -f "$HERMES_ENV" ]] && grep -qE '^TELEGRAM_BOT_TOKEN=.+' "$HERMES_ENV"; then
  token_ok=1
fi
if grep -qE '^TELEGRAM_BOT_TOKEN=.+' "$DEST/relay.env"; then
  token_ok=1
fi
secret_ok=0
if grep -qE '^RELAY_SECRET=.+' "$DEST/relay.env" && grep -qE '^TELEGRAM_ALLOWED_CHAT_IDS=.+' "$DEST/relay.env"; then
  secret_ok=1
fi

systemctl daemon-reload
if [[ "$token_ok" -ne 1 || "$secret_ok" -ne 1 ]]; then
  echo "Installed $UNIT but did not enable it: TELEGRAM_BOT_TOKEN, RELAY_SECRET, or TELEGRAM_ALLOWED_CHAT_IDS is missing." >&2
  echo "Put the token in $DEST/relay.env or in deploy.hermesEnv, then rerun. The unit was not restarted." >&2
  exit 0
fi

systemctl enable --now "$UNIT"
systemctl restart "$UNIT"
echo "waiting for /health"
ok=0
for _ in $(seq 1 20); do
  if out="$(curl -fsS --max-time 2 "http://${BIND}:${PORT}/health" 2>/dev/null)"; then
    printf '%s\n' "$out"
    ok=1
    break
  fi
  sleep 1
done
if [[ "$ok" -ne 1 ]]; then
  echo "health check failed after restart" >&2
  systemctl --no-pager -l status "$UNIT" || true
  exit 1
fi
systemctl is-active "$UNIT"
REMOTE
