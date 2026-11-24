#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR="${APP_DIR:-/opt/aminui-sales-bot}"
SERVICE="aminui-sales-bot"

if [[ "${EUID}" -ne 0 ]]; then
  echo "با root اجرا کنید: sudo bash update.sh" >&2
  exit 1
fi
cd "$APP_DIR"
if systemctl is-active --quiet "$SERVICE"; then WAS_ACTIVE=1; else WAS_ACTIVE=0; fi
STAMP="$(date +%Y%m%d-%H%M%S)"
[[ ! -f .env ]] || cp -a .env ".env.backup.$STAMP"
[[ ! -f data/bot.sqlite3 ]] || cp -a data/bot.sqlite3 "data/bot.sqlite3.backup.$STAMP"

if [[ ! -d .git ]]; then
  echo "این نصب Git clone نیست؛ در حال تبدیل امن به نصب قابل به‌روزرسانی..."
  apt-get update
  apt-get install -y git
  TMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$TMP_DIR"' EXIT
  git clone --depth 1 https://github.com/amiinnoriizade-lang/aminui-sales-bot.git "$TMP_DIR/repo"
  tar -C "$TMP_DIR/repo" --exclude='./.git' -cf - . | tar -C "$APP_DIR" -xf -
  cp -a "$TMP_DIR/repo/.git" "$APP_DIR/.git"
  echo "سورس دریافت شد و مسیر به Git متصل شد."
else
  git pull --ff-only
fi
.venv/bin/python -m pip install -r requirements.txt
mkdir -p "/etc/systemd/system/${SERVICE}.service.d"
cat > "/etc/systemd/system/${SERVICE}.service.d/restart-policy.conf" <<'EOF'
[Unit]
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Restart=on-failure
RestartSec=30
EOF
systemctl daemon-reload
if [[ "$WAS_ACTIVE" -eq 1 ]]; then
  systemctl restart "$SERVICE"
fi
systemctl --no-pager --full status "$SERVICE" || true
