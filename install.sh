#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR="${APP_DIR:-/opt/vpnui-sales-bot}"
SERVICE="vpnui-sales-bot"
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${EUID}" -ne 0 ]]; then
  echo "با root اجرا کنید: sudo bash install.sh" >&2
  exit 1
fi
for f in run.py requirements.txt .env.example app/main.py; do
  [[ -f "$SOURCE_DIR/$f" ]] || { echo "فایل ضروری پیدا نشد: $f" >&2; exit 1; }
done

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-pip ca-certificates
mkdir -p "$APP_DIR"
if [[ "$SOURCE_DIR" != "$APP_DIR" ]]; then
  tar -C "$SOURCE_DIR" \
    --exclude='./.git' --exclude='./.venv' --exclude='./data' \
    --exclude='./.env' --exclude='./.env.*' --exclude='!./.env.example' \
    --exclude='./__pycache__' -cf - . | tar -C "$APP_DIR" -xf -
  cp "$SOURCE_DIR/.env.example" "$APP_DIR/.env.example"
fi
mkdir -p "$APP_DIR/data"
cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
[[ -f .env ]] || cp .env.example .env

old_value() {
  .venv/bin/python - "$1" <<'PY'
import sys
from dotenv import dotenv_values
v = dotenv_values('.env').get(sys.argv[1], '')
print(v if v is not None else '')
PY
}
ask_value() {
  local label="$1" current="$2" required="$3" value
  while true; do
    if [[ -n "$current" ]]; then
      read -r -p "$label [Enter = حفظ مقدار قبلی]: " value
      value="${value:-$current}"
    else
      read -r -p "$label: " value
    fi
    if [[ "$required" != yes || -n "$value" ]]; then printf '%s' "$value"; return; fi
    echo "این مقدار اجباری است." >&2
  done
}
ask_secret() {
  local label="$1" current="$2" value
  if [[ -n "$current" ]]; then
    read -r -s -p "$label [Enter = حفظ رمز قبلی]: " value; echo >&2
    printf '%s' "${value:-$current}"
  else
    while true; do
      read -r -s -p "$label: " value; echo >&2
      [[ -n "$value" ]] && { printf '%s' "$value"; return; }
      echo "این مقدار اجباری است." >&2
    done
  fi
}

echo "=== راه‌اندازی ربات فروش VPN ==="
BOT_TOKEN="$(ask_secret 'توکن ربات تلگرام' "$(old_value BOT_TOKEN)" yes)"
ADMIN_IDS="$(ask_value 'شناسه عددی مدیر (چند مدیر با کاما)' "$(old_value ADMIN_IDS)" yes)"
VPNUI_BASE_URL="$(ask_value 'آدرس پنل VPN-UI همراه پورت و Base Path' "$(old_value VPNUI_BASE_URL)" yes)"
VPNUI_USERNAME="$(ask_value 'نام کاربری پنل' "$(old_value VPNUI_USERNAME)" yes)"
VPNUI_PASSWORD="$(ask_secret 'رمز عبور پنل' "$(old_value VPNUI_PASSWORD)")"
VPN_PUBLIC_HOST="$(ask_value 'IP یا دامنه عمومی اتصال VPN (اختیاری)' "$(old_value VPN_PUBLIC_HOST)" no)"

[[ "$VPNUI_BASE_URL" =~ ^https?:// ]] || { echo "آدرس پنل باید با http:// یا https:// شروع شود." >&2; exit 1; }
[[ "$ADMIN_IDS" =~ ^[0-9]+([[:space:]]*,[[:space:]]*[0-9]+)*$ ]] || { echo "شناسه مدیر باید عددی و با کاما جدا شود." >&2; exit 1; }
VPNUI_VERIFY_TLS=true
APP_ENCRYPTION_KEY="$(old_value APP_ENCRYPTION_KEY)"
if [[ -z "$APP_ENCRYPTION_KEY" ]]; then
  APP_ENCRYPTION_KEY="$(.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
fi
DATABASE_PATH="$(old_value DATABASE_PATH)"
DATABASE_PATH="${DATABASE_PATH:-./data/bot.sqlite3}"
DEFAULT_PLANS_JSON="$(old_value DEFAULT_PLANS_JSON)"
DEFAULT_PLANS_JSON="${DEFAULT_PLANS_JSON:-[]}"
export BOT_TOKEN ADMIN_IDS VPNUI_BASE_URL VPNUI_USERNAME VPNUI_PASSWORD VPNUI_VERIFY_TLS VPN_PUBLIC_HOST APP_ENCRYPTION_KEY DATABASE_PATH DEFAULT_PLANS_JSON
.venv/bin/python - <<'PY'
import os
from dotenv import set_key
keys = ['BOT_TOKEN','ADMIN_IDS','VPNUI_BASE_URL','VPNUI_USERNAME','VPNUI_PASSWORD','VPNUI_VERIFY_TLS','VPN_PUBLIC_HOST','APP_ENCRYPTION_KEY','DATABASE_PATH','DEFAULT_PLANS_JSON']
for key in keys:
    set_key('.env', key, os.environ.get(key, ''), quote_mode='always')
PY
chmod 600 .env

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
systemctl enable "$SERVICE"
echo
echo "نصب و تنظیمات تمام شد."
echo "مسیر: $APP_DIR"
echo "سرویس: $SERVICE"
echo "ساخت حساب واقعی فعال است؛ Inbound و روش پرداخت را از منوی مدیریت ربات تنظیم کنید."
echo "برای اجرا: systemctl start $SERVICE"
echo "برای گزارش: journalctl -u $SERVICE -f"
