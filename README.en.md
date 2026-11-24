# VPN-UI Telegram Sales Bot

A Telegram sales and account-management bot for a single VPN-UI panel instance. It connects to the panel HTTP API and stores local application data in SQLite.

## Features

- Persian customer menu and graphical Telegram admin menu.
- Fixed plans and volume-priced services (volume × price per GB per month × months).
- Customer-selected usernames with duplicate checks in the bot and panel.
- Card-to-card payments with receipt submission and manual administrator approval or rejection.
- VLESS and L2TP account provisioning. The L2TP/IPsec PSK is read from the selected inbound settings.
- OpenVPN TCP/UDP profile delivery when the connected panel build provides the supported endpoint.
- One-time 1 GB / 24-hour VLESS trial, configured by an administrator.
- Account listing, renewal, traffic lookup, account enable/disable/delete, support messages, broadcasts, and database backup.
- Fernet encryption for stored account credentials.

The bot manages compatible inbounds on one connected VPN-UI instance; it is not a multi-panel manager. WireGuard and OpenConnect provisioning are not implemented in this release.

## Requirements

- Ubuntu 22.04 or 24.04
- Python 3.10+
- Telegram bot token and numeric Telegram administrator ID(s)
- Reachable VPN-UI panel account with permission to manage inbounds and clients
- Public VPN hostname or IP reachable by customers

## Installation

```bash
git clone https://github.com/amiinnoriizade-lang/aminui-sales-bot.git
cd aminui-sales-bot
sudo bash install.sh
```

The installer asks for the Telegram token, administrator IDs, and VPN-UI connection details. Secrets are entered without being displayed and stored in `.env` with restricted permissions. The encryption key is generated once. Keep a secure backup; never replace it after credentials have been stored.

The installer defaults to `/opt/aminui-sales-bot` and creates the `aminui-sales-bot.service` systemd unit. The application directory can be changed with `APP_DIR`.

Start and inspect the service:

```bash
sudo systemctl start aminui-sales-bot
sudo systemctl status aminui-sales-bot --no-pager
sudo journalctl -u aminui-sales-bot -f
```

## First setup in Telegram

1. Send `/start` from an administrator account.
2. Open **مدیریت ربات** (Bot Management).
3. Check the panel connection and review available inbounds.
4. Select an active VLESS inbound for the free trial.
5. Create fixed plans or volume-priced services and select the inbound for each.
6. Configure the card number, cardholder name, and payment instructions.
7. Run `/paneltest` to check panel API read access.

Provisioning creates real clients on the connected panel. Validate your exact VPN-UI build and selected inbound with a controlled test account before offering the service to customers.

## Updating

Run the repository's `update.sh` from the installed application directory as root. The updater is designed to back up application data and settings before updating; review the script and keep an independent backup before production updates.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Security

- Never commit `.env`, environment backups, SQLite databases, or panel credentials.
- Back up `.env` and the SQLite database together, securely and separately from GitHub.
- Keep `APP_ENCRYPTION_KEY`; without it, encrypted credentials cannot be decrypted.
- TLS certificate verification is mandatory.
- Run only one polling instance per Telegram bot token to avoid polling conflicts.


## Project support wallets

**TRON (TRX / TRC20)**
`TUqbpFe8XmL2qcEdQ77SybMU8YW5vf2qGn`

**Bitcoin (BTC)**
`17F1gSMENRr5tAmTnPEoduvtSGGY3KMVzB`

**Polygon**
`0x88B8841E9f47B57f7fd1bBb6375FcA6CB786EE28`

**USDT (TRC20)**
`TFUvPCaon7eBk1Xaoce3geZPjnks3kEaqW`

**BNB**
`0x88B8841E9f47B57f7fd1bBb6375FcA6CB786EE28`

**Ethereum (ETH)**
`0x88B8841E9f47B57f7fd1bBb6375FcA6CB786EE28`

Always select the exact currency and network. Transfers on the wrong network may result in permanent loss.

## Full installation and setup

Run on the server:

```bash
git clone https://github.com/amiinnoriizade-lang/aminui-sales-bot.git
cd aminui-sales-bot
sudo bash install.sh
```

The installer asks for the Telegram bot token, numeric administrator ID(s), VPN-UI panel URL (including port and base path), panel username and password, and optionally the public VPN host/IP. Secrets are not echoed and are stored in `.env` with restricted permissions. The encryption key is generated once; back it up securely and never replace it after account credentials have been stored.

Default installation path: `/opt/aminui-sales-bot`. systemd service: `aminui-sales-bot.service`. Set `APP_DIR` to use a different application directory.

Start and inspect:

```bash
sudo systemctl start aminui-sales-bot
sudo systemctl status aminui-sales-bot --no-pager
sudo journalctl -u aminui-sales-bot -f
```

## First Telegram setup

1. Send `/start` from an administrator account.
2. Open **مدیریت ربات** (Bot Management).
3. Review panel inbounds and confirm the connection.
4. Select an active VLESS inbound for the free trial.
5. Create fixed or volume-priced plans and assign an inbound to each.
6. Configure the card number, cardholder name, and payment instructions.
7. Run `/paneltest` to check panel API read access.

Account creation writes real clients to the connected panel. Test the exact panel build and inbound with a controlled account before selling access.

## Updating

As root, from the installed application directory:

```bash
cd /opt/aminui-sales-bot
sudo bash update.sh
```

The updater backs up source, `.env`, and the default SQLite database; installs dependencies; compiles the code; and runs unit tests. It restarts the service only if it was active before the update. If your installation uses another path, enter that directory before running the script.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Additional security notes

Back up `.env` and SQLite together. Keep `APP_ENCRYPTION_KEY`. TLS verification is mandatory. Never publish secrets or databases to GitHub. Run only one polling instance per Telegram bot token.
