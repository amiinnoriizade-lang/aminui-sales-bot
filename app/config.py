import os, json
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: set[int]
    panel_base_url: str
    panel_username: str
    panel_password: str
    verify_tls: bool
    database_path: str
    public_host: str
    vless_inbound: int
    l2tp_inbound: int
    encryption_key: str
    card_number: str
    cardholder_name: str
    payment_instructions: str
    dry_run: bool
    default_plans: list

def load_config():
    token = os.getenv('BOT_TOKEN', '').strip()
    base = os.getenv('VPNUI_BASE_URL', '').strip().rstrip('/')
    user = os.getenv('VPNUI_USERNAME', '').strip()
    pw = os.getenv('VPNUI_PASSWORD', '')
    admins = {int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()}

    if not token:
        raise RuntimeError('BOT_TOKEN تنظیم نشده است.')
    if not admins:
        raise RuntimeError('حداقل یک ADMIN_IDS لازم است.')
    if not all((base, user, pw)):
        raise RuntimeError('VPNUI_BASE_URL / USERNAME / PASSWORD لازم است.')

    public_host = os.getenv('VPN_PUBLIC_HOST', '').strip()
    if not public_host:
        raise RuntimeError('VPN_PUBLIC_HOST تنظیم نشده است؛ IP یا دامنه عمومی قابل اتصال کاربران را وارد کنید.')

    key = os.getenv('APP_ENCRYPTION_KEY', '').strip()
    if not key:
        raise RuntimeError('APP_ENCRYPTION_KEY تنظیم نشده است؛ کلید Fernet بسازید.')
    try:
        from cryptography.fernet import Fernet
        Fernet(key.encode())
    except Exception as e:
        raise RuntimeError('APP_ENCRYPTION_KEY معتبر نیست.') from e

    try:
        plans = json.loads(os.getenv('DEFAULT_PLANS_JSON', '[]'))
    except Exception as e:
        raise RuntimeError('DEFAULT_PLANS_JSON نامعتبر است.') from e
    if not isinstance(plans, list):
        raise RuntimeError('DEFAULT_PLANS_JSON باید آرایه JSON باشد.')

    # Real provisioning is enabled in this release. TLS verification stays mandatory.
    return Config(
        token, admins, base, user, pw, True,
        os.getenv('DATABASE_PATH', './data/bot.sqlite3'),
        public_host,
        int(os.getenv('VPNUI_VLESS_INBOUND_ID', '0')),
        int(os.getenv('VPNUI_L2TP_INBOUND_ID', '0')),
        key,
        os.getenv('CARD_NUMBER', '').strip(),
        os.getenv('CARDHOLDER_NAME', '').strip(),
        os.getenv('PAYMENT_INSTRUCTIONS', 'رسید کارت‌به‌کارت را ارسال کنید.'),
        False,
        plans
    )
