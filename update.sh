#!/usr/bin/env bash
# updater-revision: legacy-install-path-compat-2026-11-24
set -Eeuo pipefail
APP_DIR="${APP_DIR:-/opt/aminui-sales-bot}"
if [[ ! -d "$APP_DIR" && -d /opt/vpnui-sales-bot ]]; then APP_DIR="/opt/vpnui-sales-bot"; fi
SERVICE="${SERVICE:-aminui-sales-bot}"
if [[ "$SERVICE" == "aminui-sales-bot" ]] && ! systemctl cat "$SERVICE" >/dev/null 2>&1 && systemctl cat vpnui-sales-bot.service >/dev/null 2>&1; then SERVICE="vpnui-sales-bot"; fi
REPO="https://github.com/amiinnoriizade-lang/aminui-sales-bot.git"
if [[ "${EUID}" -ne 0 ]]; then echo "با root اجرا کنید: sudo bash update.sh" >&2; exit 1; fi
cd "$APP_DIR"
if systemctl is-active --quiet "$SERVICE"; then WAS_ACTIVE=1; else WAS_ACTIVE=0; fi
if [[ -d .git ]]; then
  LOCAL_CHANGES="$(git status --porcelain --untracked-files=all | awk '
    /^\?\? \.env(\.backup.*)?$/ { next }
    /^\?\? \.venv\// { next }
    /^\?\? data\// { next }
    /^\?\? app\/__pycache__\// { next }
    { print }
  ')"
  if [[ -n "$LOCAL_CHANGES" ]]; then
    echo "تغییر محلی در فایل‌های پروژه وجود دارد؛ ابتدا آن‌ها را بررسی کنید:" >&2
    printf "%s\n" "$LOCAL_CHANGES" >&2
    exit 1
  fi
fi
STAMP="$(date +%Y%m%d-%H%M%S)"
SOURCE_BACKUP="/root/vpnui-sales-bot-source-$STAMP.tar.gz"
HAD_GIT=0
OLD_HEAD=''
if [[ -d .git ]]; then HAD_GIT=1; OLD_HEAD="$(git rev-parse HEAD)"; fi
tar -C "$APP_DIR" --exclude='./.git' --exclude='./.venv' --exclude='./data' --exclude='./.env' --exclude='./.env.backup*' -czf "$SOURCE_BACKUP" .
[[ ! -f .env ]] || cp -a .env ".env.backup.$STAMP"
DB_PATH="$(.venv/bin/python -c 'from dotenv import dotenv_values; print(dotenv_values(".env").get("DATABASE_PATH") or "./data/bot.sqlite3")' 2>/dev/null || echo './data/bot.sqlite3')"
if [[ "$DB_PATH" != /* ]]; then DB_PATH="$APP_DIR/$DB_PATH"; fi
if [[ -f "$DB_PATH" ]]; then cp -a "$DB_PATH" "$DB_PATH.backup.$STAMP"; fi

rollback() {
  echo "به‌روزرسانی ناموفق بود؛ سورس قبلی برگردانده می‌شود." >&2
  tar -C "$APP_DIR" -xzf "$SOURCE_BACKUP"
  if [[ "$HAD_GIT" -eq 1 ]]; then git reset --hard "$OLD_HEAD" >/dev/null 2>&1 || true; else rm -rf .git; fi
  if [[ "$WAS_ACTIVE" -eq 1 ]]; then systemctl restart "$SERVICE" || true; fi
}
trap rollback ERR

if [[ ! -d .git ]]; then
  apt-get update
  apt-get install -y git
  TMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$TMP_DIR"' EXIT
  git clone --depth 1 "$REPO" "$TMP_DIR/repo"
  tar -C "$TMP_DIR/repo" --exclude='./.git' --exclude='./.env' --exclude='./.env.*' --exclude='./.venv' --exclude='./data' -cf - . | tar -C "$APP_DIR" -xf -
  cp -a "$TMP_DIR/repo/.git" "$APP_DIR/.git"
else
  ORIGIN="$(git remote get-url origin)"
  [[ "$ORIGIN" == "$REPO" || "$ORIGIN" == "${REPO%.git}" ]] || { echo "مخزن origin با پروژه مورد انتظار یکی نیست: $ORIGIN" >&2; exit 1; }
  git pull --ff-only origin main
fi

.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m compileall -q app run.py
.venv/bin/python -m unittest discover -s tests -v

cat > "/etc/systemd/system/${SERVICE}.service" <<UNIT
[Unit]
Description=VPN-UI Telegram Sales Bot
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/run.py
Restart=on-failure
RestartSec=30
User=root
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=$APP_DIR
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
trap - ERR
if [[ "$WAS_ACTIVE" -eq 1 ]]; then systemctl restart "$SERVICE"; fi
systemctl --no-pager --full status "$SERVICE" || true
echo "سورس پشتیبان: $SOURCE_BACKUP"
