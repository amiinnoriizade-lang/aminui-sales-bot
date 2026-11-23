#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/aminui-sales-bot}"
SERVICE="aminui-sales-bot"
if [[ $EUID -ne 0 ]]; then echo 'Run with sudo/root'; exit 1; fi
apt-get update
apt-get install -y python3 python3-venv python3-pip ca-certificates
mkdir -p "$APP_DIR"
cp -a . "$APP_DIR/"
cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
if [[ ! -f .env ]]; then cp .env.example .env; fi
chmod 600 .env
if ! grep -q '^APP_ENCRYPTION_KEY=.' .env; then KEY=$( .venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'); sed -i "s|^APP_ENCRYPTION_KEY=.*|APP_ENCRYPTION_KEY=$KEY|" .env; fi
cat > "/etc/systemd/system/${SERVICE}.service" <<EOF
[Unit]
Description=AminUI Telegram Sales Bot
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
WorkingDirectory=$APP_DIR
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
echo "Installed. Edit $APP_DIR/.env, then: systemctl start $SERVICE"
