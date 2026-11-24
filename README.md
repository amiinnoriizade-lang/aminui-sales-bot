# VPN-UI Telegram Sales Bot

Telegram sales and account-management bot for one VPN-UI panel instance. It uses the panel HTTP API and a local SQLite database.

## Features in this source

- Persian customer menu and graphical Telegram admin menu.
- Fixed plans and volume-priced services (volume × price per GB per month × months).
- Customer-selected usernames with local and panel-side duplicate checks.
- Card-to-card payment: receipt photo, manual admin approval/rejection, then provisioning.
- VLESS and L2TP account provisioning; L2TP/IPsec PSK is read from the selected inbound settings.
- OpenVPN TCP/UDP profile retrieval and delivery when the selected panel build exposes the supported profile endpoint.
- One-time 1 GB / 24-hour VLESS trial, with its inbound selected by an administrator.
- Account listing, renewal, traffic lookup, admin enable/disable/delete, support messages, broadcasts, and database backup.
- Fernet encryption for stored account credentials.

The bot can select among compatible inbounds in the connected VPN-UI instance. It is not a multi-panel orchestrator. WireGuard and OpenConnect provisioning are not implemented in this release.

## Requirements

- Ubuntu 22.04 or 24.04
- Python 3.10+
- A Telegram bot token and numeric Telegram admin ID(s)
- A reachable VPN-UI panel account with permission to manage inbounds/clients
- A public VPN hostname or IP clients can reach

## Install

```bash
git clone https://github.com/amiinnoriizade-lang/aminui-sales-bot.git
cd aminui-sales-bot
sudo bash install.sh
```

The installer prompts for the Telegram token, admin IDs, and VPN-UI connection details. Secrets are entered without being echoed and saved in `/opt/vpnui-sales-bot/.env` with mode `600`. The encryption key is generated once; keep a secure backup of it. Never replace it after credentials have been stored.

The canonical service and paths are:

- Application: `/opt/vpnui-sales-bot`
- systemd unit: `vpnui-sales-bot.service`
- Database: `/opt/vpnui-sales-bot/data/bot.sqlite3` by default

Start and inspect the bot:

```bash
sudo systemctl start vpnui-sales-bot
sudo systemctl status vpnui-sales-bot --no-pager
sudo journalctl -u vpnui-sales-bot -f
```

## First setup in Telegram

1. Send `/start` to the bot using an administrator Telegram account.
2. Open **مدیریت ربات**.
3. Open **مشاهده Inboundهای پنل** and confirm the panel connection.
4. For the free test account, open **Inbound اکانت تست** and select an active VLESS inbound.
5. Create fixed plans or volume-priced services and select the intended inbound for each.
6. Configure the card number, cardholder name, and payment instructions in **تنظیمات پرداخت**.
7. Run `/paneltest` to re-check panel API read access.

Provisioning writes real clients to the panel. First validate the exact VPN-UI build and the selected inbound with a controlled test account. The bot performs preflight checks before writing, including the connection host and L2TP PSK when IPsec is enabled. A write with an ambiguous result is locked for manual reconciliation to avoid duplicate accounts.

## Update

Run as root:

```bash
cd /opt/vpnui-sales-bot
sudo bash update.sh
```

The updater backs up source, `.env`, and the default SQLite database before updating. It compiles the code and runs the unit tests before restarting an already-running service. It does not start a service that was previously stopped.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

GitHub Actions runs the same test suite on pushes and pull requests.

## Security and backups

- Never commit `.env`, `.env.*` backups, SQLite files, or panel credentials.
- Back up `.env` and the SQLite database together, securely and separately from GitHub.
- Keep `APP_ENCRYPTION_KEY`; without it, encrypted credentials in the database cannot be decrypted.
- TLS certificate verification is mandatory; do not disable it.
- Run only one polling instance for a given Telegram bot token. A second instance causes Telegram polling conflicts.

## Panel API compatibility

The client uses VPN-UI endpoints for listing/getting inbounds, adding/updating/deleting clients, and fetching OpenVPN profiles. VPN-UI forks can differ. Passing local unit tests does not prove that a particular panel fork accepts every write endpoint; verify the exact panel build before selling accounts.
