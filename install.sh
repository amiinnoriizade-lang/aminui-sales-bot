#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR="${APP_DIR:-/opt/aminui-sales-bot}"
SERVICE="aminui-sales-bot"
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${EUID}" -ne 0 ]]; then echo "با root اجرا کنید: sudo bash install.sh" >&2; exit 1; fi
for f in run.py requirements.txt .env.example; do
  [[ -f "$SOURCE_DIR/$f" ]] || { echo "فایل ضروری پیدا نشد: $f" >&2; exit 1; }
done

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-pip ca-certificates
mkdir -p "$APP_DIR"
tar -C "$SOURCE_DIR" --exclude='./.git' --exclude='./.venv' --exclude='./data' -cf - . | tar -C "$APP_DIR" -xf -
mkdir -p "$APP_DIR/data"
cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

old_value() {
  [[ -f .env ]] || return 0
  .venv/bin/python - "$1" <<'PY'
import sys
from dotenv import dotenv_values
v = dotenv_values(".env").get(sys.argv[1], "")
print(v if v is not None else "")
PY
}
ask() {
  local label="$1" current="$2" required="$3" value
  while true; do
    if [[ -n "$current" ]]; then
      read -r -p "$label [Enter = مقدار قبلی]: " value
      value="${value:-$current}"
    else
      read -r -p "$label: " value
    fi
    if [[ "$required" != "yes" || -n "$value" ]]; then printf '%s' "$value"; return; fi
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

echo
echo "=== راه‌اندازی ربات فروش VPN ==="
echo "رمزها هنگام تایپ نمایش داده نمی‌شوند."
BOT_TOKEN="$(ask_secret 'توکن ربات تلگرام (BotFather)' "$(old_value BOT_TOKEN)")"
ADMIN_IDS="$(ask 'شناسه عددی مدیر تلگرام (چند مدیر با کاما)' "$(old_value ADMIN_IDS)" yes)"
VPNUI_BASE_URL="$(ask 'آدرس کامل پنل VPN-UI همراه پورت (مثال https://panel.example.com:2053)' "$(old_value VPNUI_BASE_URL)" yes)"
VPNUI_USERNAME="$(ask 'نام کاربری پنل VPN-UI' "$(old_value VPNUI_USERNAME)" yes)"
VPNUI_PASSWORD="$(ask_secret 'رمز عبور پنل VPN-UI' "$(old_value VPNUI_PASSWORD)")"

[[ "$VPNUI_BASE_URL" =~ ^https?:// ]] || { echo "آدرس پنل باید با http:// یا https:// شروع شود." >&2; exit 1; }
[[ "$ADMIN_IDS" =~ ^[0-9]+([[:space:]]*,[[:space:]]*[0-9]+)*$ ]] || { echo "شناسه مدیر باید عددی باشد و با کاما جدا شود." >&2; exit 1; }

VPNUI_VERIFY_TLS="$(ask 'اعتبارسنجی TLS؟ true/false' "$(old_value VPNUI_VERIFY_TLS || true)" no)"
VPNUI_VERIFY_TLS="${VPNUI_VERIFY_TLS:-true}"
VPN_PUBLIC_HOST="$(ask 'دامنه یا IP عمومی سرور VPN (اختیاری)' "$(old_value VPN_PUBLIC_HOST)" no)"
VPNUI_VLESS_INBOUND_ID="$(ask 'Inbound پیش‌فرض VLESS (اختیاری، 0 برای انتخاب از ربات)' "$(old_value VPNUI_VLESS_INBOUND_ID)" no)"
VPNUI_VLESS_INBOUND_ID="${VPNUI_VLESS_INBOUND_ID:-0}"
VPNUI_L2TP_INBOUND_ID="$(ask 'Inbound پیش‌فرض L2TP (اختیاری، 0 برای انتخاب از ربات)' "$(old_value VPNUI_L2TP_INBOUND_ID)" no)"
VPNUI_L2TP_INBOUND_ID="${VPNUI_L2TP_INBOUND_ID:-0}"
CARD_NUMBER="$(ask 'شماره کارت (اختیاری)' "$(old_value CARD_NUMBER)" no)"
CARDHOLDER_NAME="$(ask 'نام صاحب کارت (اختیاری)' "$(old_value CARDHOLDER_NAME)" no)"
PAYMENT_INSTRUCTIONS="$(ask 'متن راهنمای پرداخت' "$(old_value PAYMENT_INSTRUCTIONS)" no)"
PAYMENT_INSTRUCTIONS="${PAYMENT_INSTRUCTIONS:-رسید کارت‌به‌کارت را ارسال کنید.}"
DRY_RUN="$(ask 'حالت آزمایشی؟ true/false (فعلاً true توصیه می‌شود)' "$(old_value DRY_RUN)" no)"
DRY_RUN="${DRY_RUN:-true}"
[[ "$DRY_RUN" == "true" || "$DRY_RUN" == "false" ]] || { echo "DRY_RUN فقط true یا false است." >&2; exit 1; }

APP_ENCRYPTION_KEY="$(old_value APP_ENCRYPTION_KEY)"
if [[ -z "$APP_ENCRYPTION_KEY" ]]; then
  APP_ENCRYPTION_KEY="$(.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
fi
DATABASE_PATH="$(old_value DATABASE_PATH)"
DATABASE_PATH="${DATABASE_PATH:-./data/bot.sqlite3}"
DEFAULT_PLANS_JSON="$(old_value DEFAULT_PLANS_JSON)"
DEFAULT_PLANS_JSON="${DEFAULT_PLANS_JSON:-[]}"

export BOT_TOKEN ADMIN_IDS VPNUI_BASE_URL VPNUI_USERNAME VPNUI_PASSWORD VPNUI_VERIFY_TLS
export VPN_PUBLIC_HOST VPNUI_VLESS_INBOUND_ID VPNUI_L2TP_INBOUND_ID APP_ENCRYPTION_KEY
export CARD_NUMBER CARDHOLDER_NAME PAYMENT_INSTRUCTIONS DRY_RUN DATABASE_PATH DEFAULT_PLANS_JSON
.venv/bin/python - <<'PY'
import os
from dotenv import set_key
path = ".env"
keys = [
 "BOT_TOKEN","ADMIN_IDS","VPNUI_BASE_URL","VPNUI_USERNAME","VPNUI_PASSWORD",
 "VPNUI_VERIFY_TLS","VPN_PUBLIC_HOST","VPNUI_VLESS_INBOUND_ID","VPNUI_L2TP_INBOUND_ID",
 "APP_ENCRYPTION_KEY","CARD_NUMBER","CARDHOLDER_NAME","PAYMENT_INSTRUCTIONS",
 "DRY_RUN","DATABASE_PATH","DEFAULT_PLANS_JSON"
]
open(path, "a").close()
for key in keys:
    set_key(path, key, os.environ.get(key, ""), quote_mode="always")
PY
chmod 600 .env

cat > "/etc/systemd/system/${SERVICE}.service" <<EOF
[Unit]
Description=AminUI Telegram Sales Bot
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/run.py
Restart=on-failure
RestartSec=5
User=root
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=$APP_DIR
[Install]
WantedBy=multi-user.target
EOF
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
systemctl enable "$SERVICE"
echo
echo "تنظیمات با موفقیت در $APP_DIR/.env ذخیره شد."
echo "حالت آزمایشی: $DRY_RUN"
echo "برای شروع ربات: systemctl start $SERVICE"
echo "برای گزارش اجرا: journalctl -u $SERVICE -f"
