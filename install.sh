#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/aminui-sales-bot}"
SERVICE="aminui-sales-bot"
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${EUID}" -ne 0 ]]; then
  echo "این نصب‌کننده باید با root اجرا شود: sudo bash install.sh" >&2
  exit 1
fi

if [[ ! -f "$SOURCE_DIR/run.py" || ! -f "$SOURCE_DIR/requirements.txt" || ! -f "$SOURCE_DIR/.env.example" ]]; then
  echo "ساختار مخزن ناقص است؛ run.py، requirements.txt یا .env.example پیدا نشد." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-pip ca-certificates

mkdir -p "$APP_DIR"
# Preserve an existing .env and database; copy project files without copying the Git metadata.
tar -C "$SOURCE_DIR" --exclude='./.git' --exclude='./.venv' --exclude='./data' -cf - . | tar -C "$APP_DIR" -xf -
mkdir -p "$APP_DIR/data"
cd "$APP_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
fi
chmod 600 .env

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

if ! grep -q '^APP_ENCRYPTION_KEY=.' .env; then
  KEY="$(.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
  if grep -q '^APP_ENCRYPTION_KEY=' .env; then
    sed -i "s|^APP_ENCRYPTION_KEY=.*|APP_ENCRYPTION_KEY=$KEY|" .env
  else
    printf '\nAPP_ENCRYPTION_KEY=%s\n' "$KEY" >> .env
  fi
fi

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

systemctl daemon-reload
systemctl enable "$SERVICE"
echo
echo "نصب وابستگی‌ها و ساخت سرویس تمام شد."
echo "فایل تنظیمات: $APP_DIR/.env"
echo "پس از تکمیل BOT_TOKEN، ADMIN_IDS و اطلاعات VPN-UI اجرا کنید:"
echo "  systemctl start $SERVICE"
echo "  journalctl -u $SERVICE -f"
