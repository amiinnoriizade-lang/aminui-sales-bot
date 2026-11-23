#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/aminui-sales-bot}"
cd "$APP_DIR"
cp -a .env .env.backup.$(date +%Y%m%d-%H%M%S)
.venv/bin/pip install -r requirements.txt
systemctl restart aminui-sales-bot
systemctl --no-pager --full status aminui-sales-bot
