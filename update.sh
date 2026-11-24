#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="$(printenv APP_DIR 2>/dev/null || true)"
[[ -n "$APP_DIR" ]] || APP_DIR="/opt/vpnui-sales-bot"
SERVICE="$(printenv SERVICE 2>/dev/null || true)"
[[ -n "$SERVICE" ]] || SERVICE="vpnui-sales-bot"
REPO="https://github.com/amiinnoriizade-lang/aminui-sales-bot.git"

if [[ "$EUID" -ne 0 ]]; then
  echo "با root اجرا کنید: sudo bash update.sh" >&2
  exit 1
fi
[[ -d "$APP_DIR" ]] || { echo "مسیر نصب پیدا نشد: $APP_DIR" >&2; exit 1; }
[[ -x "$APP_DIR/.venv/bin/python" ]] || { echo "محیط Python نصب نیست؛ ابتدا install.sh را اجرا کنید." >&2; exit 1; }
[[ -f "$APP_DIR/.env" ]] || { echo "فایل .env پیدا نشد؛ به‌روزرسانی متوقف شد." >&2; exit 1; }

cd "$APP_DIR"
if systemctl is-active --quiet "$SERVICE"; then WAS_ACTIVE=1; else WAS_ACTIVE=0; fi
STAMP="$(date +%Y%m%d-%H%M%S)"
SOURCE_BACKUP="/root/vpnui-sales-bot-source-$STAMP.tar.gz"
ENV_BACKUP="/root/vpnui-sales-bot-env-$STAMP"
DB_PATH="$("$APP_DIR/.venv/bin/python" - <<'PY'
from dotenv import dotenv_values
print(dotenv_values('.env').get('DATABASE_PATH') or './data/bot.sqlite3')
PY
)"
if [[ "$DB_PATH" != /* ]]; then DB_PATH="$APP_DIR/$DB_PATH"; fi

tar -C "$APP_DIR" \
  --exclude='./.git' --exclude='./.venv' --exclude='./data' \
  --exclude='./.env' --exclude='./.env.*' \
  --exclude='./__pycache__' --exclude='*.pyc' \
  --exclude='*.sqlite*' --exclude='*.tar.gz' \
  -czf "$SOURCE_BACKUP" .
cp -a "$APP_DIR/.env" "$ENV_BACKUP"
chmod 600 "$ENV_BACKUP"
if [[ -f "$DB_PATH" ]]; then
  cp -a "$DB_PATH" "$DB_PATH.backup.$STAMP"
fi

rollback() {
  local rc="$?"
  trap - ERR
  set +e
  echo "به‌روزرسانی ناموفق بود؛ سورس قبلی برگردانده می‌شود." >&2
  find "$APP_DIR" -mindepth 1 -maxdepth 1 \
    ! -name '.env' ! -name '.env.*' ! -name '.venv' \
    ! -name 'data' ! -name '.git' -exec rm -rf {} +
  tar -C "$APP_DIR" -xzf "$SOURCE_BACKUP"
  if [[ "$WAS_ACTIVE" -eq 1 ]]; then
    systemctl restart "$SERVICE"
  fi
  echo "بکاپ سورس: $SOURCE_BACKUP" >&2
  exit "$rc"
}
trap rollback ERR

if ! command -v git >/dev/null 2>&1; then
  apt-get update
  apt-get install -y git
fi
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
git clone --depth 1 --branch main "$REPO" "$TMP_DIR/repo"

for f in run.py requirements.txt .env.example app/main.py; do
  [[ -f "$TMP_DIR/repo/$f" ]] || { echo "فایل ضروری در مخزن پیدا نشد: $f" >&2; false; }
done

tar -C "$TMP_DIR/repo" \
  --exclude='./.git' --exclude='./.env' --exclude='./.env.*' \
  --exclude='./.venv' --exclude='./data' \
  --exclude='./__pycache__' --exclude='*.pyc' \
  --exclude='*.sqlite*' --exclude='*.tar.gz' \
  -cf - . | tar -C "$APP_DIR" -xf -
cp "$TMP_DIR/repo/.env.example" "$APP_DIR/.env.example"

cd "$APP_DIR"
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m compileall -q app run.py
.venv/bin/python -m unittest discover -s tests -v

if [[ "$WAS_ACTIVE" -eq 1 ]]; then
  systemctl restart "$SERVICE"
  systemctl is-active --quiet "$SERVICE"
  systemctl --no-pager --full status "$SERVICE"
else
  echo "سورس به‌روزرسانی شد؛ سرویس قبلاً متوقف بود و روشن نشد."
fi

trap - ERR
echo "به‌روزرسانی با موفقیت انجام شد."
echo "بکاپ سورس: $SOURCE_BACKUP"
echo "بکاپ تنظیمات: $ENV_BACKUP"
