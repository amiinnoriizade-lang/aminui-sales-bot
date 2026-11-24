❤️ حمایت مالی از پروژه (Donate)

اگر این پروژه برای شما مفید بوده، می‌توانید با کمک مالی از ادامه توسعه آن حمایت کنید.

کیف پول TRON (TRX)

TUqbpFe8XmL2qcEdQ77SybMU8YW5vf2qGn

کیف پول بیت‌کوین (BTC)

17F1gSMENRr5tAmTnPEoduvtSGGY3KMVz

کیف پول Polygon

0x88B8841E9f47B57f7fd1bBb6375FcA6CB786EE28

کیف پول تتر (USDT - TRC20)

TFUvPCaon7eBk1Xaoce3geZPjnks3kEaqW

کیف پول BNB

0x88B8841E9f47B57f7fd1bBb6375FcA6CB786EE28

کیف پول اتریوم (ETH)

0x88B8841E9f47B57f7fd1bBb6375FcA6CB786EE28

از حمایت و همراهی شما سپاسگزاریم ❤️

---
 ربات فروش و مدیریت سرویس VPN پنل VPN-UI*

ربات تلگرامی فروش VPN با قابلیت مدیریت کاربران، پلن‌های فروش، پرداخت کارت‌به‌کارت و اتصال به پنل مدیریت سرویس‌های VPN.

امکانات

منوی گرافیکی مشتری در تلگرام

پنل مدیریت گرافیکی برای مدیر

تعریف و ویرایش پلن‌های فروش

تنظیم مدت اعتبار و حجم سرویس

پشتیبانی از حجم نامحدود

انتخاب نام کاربری دلخواه توسط مشتری

جلوگیری از نام کاربری تکراری

پرداخت کارت‌به‌کارت با تأیید دستی مدیر

مدیریت حساب‌های VPN

اتصال به پنل VPN-UI

مدیریت تنظیمات از طریق متغیرهای محیطی

ذخیره اطلاعات در پایگاه داده SQLite

پیش‌نیازها

Ubuntu 22.04 یا 24.04

Python 3.10 یا بالاتر

دسترسی SSH

توکن ربات تلگرام

شناسه عددی مدیر تلگرام

نصب سریع

ابتدا مخزن را دریافت کنید:

git clone https://github.com/amiinnoriizade-lang/aminui-sales-bot.git cd aminui-sales-bot

سپس نصب را اجرا کنید:

chmod +x install.sh sudo ./install.sh

تنظیمات

فایل نمونه تنظیمات را کپی کنید:

cp .env.example .env

مقادیر موردنیاز را در فایل ".env" تنظیم کنید.

نکته امنیتی: فایل ".env" حاوی اطلاعات محرمانه است و نباید در GitHub منتشر شود.

اجرا

python3 run.py

اجرای سرویس در Ubuntu

در صورت نصب سرویس systemd:

sudo systemctl enable vpnui-sales-bot sudo systemctl start vpnui-sales-bot

مشاهده وضعیت:

sudo systemctl status vpnui-sales-bot

مشاهده گزارش:

sudo journalctl -u vpnui-sales-bot -f

به‌روزرسانی

chmod +x update.sh sudo ./update.sh

قبل از به‌روزرسانی، از پایگاه داده نسخه پشتیبان تهیه کنید.

اجرای تست‌ها

python3 -m pytest -v

ساختار پروژه

"app/": کدهای اصلی برنامه

"tests/": تست‌های نرم‌افزار

"data/": اطلاعات پایگاه داده

"requirements.txt": وابستگی‌های Python

".env.example": نمونه تنظیمات

"install.sh": اسکریپت نصب

"update.sh": اسکریپت به‌روزرسانی

امنیت

اطلاعات محرمانه را در مخزن عمومی قرار ندهید.

فایل ".env" را منتشر نکنید.

از پایگاه داده به‌صورت منظم پشتیبان بگیرید.

قبل از انتشار نسخه جدید، تست‌ها را اجرا کنید.

*پنل VPN-UI
ویژگی و امکانات پنل VPN-UI
PPTP

L2TP (RAW)

L2TP/IPsec

OpenVPN

OpenConnect (cisco)

SSTP

IKEv2

WireGuard (C)

AmneziaWG (نسخه‌ی مبهم‌سازی‌شده‌ی WireGuard)

GRE (تونل‌های site-to-site بین روترها، در صورت نیاز روی IPsec)

MTProto Proxy (Telegram)

SSH
پنل نماینده 
پنل مدیریت با دسترسی های مختلف

نصب‌پنل با آدرس مستقیم :

curl -Ls https://raw.githubusercontent.com/Sir-MmD/vpn-ui/refs/heads/main/deploy.sh | sudo bash

ادرس پروژه : 


https://github.com/Sir-MmD/vpn-ui/blob/main/README_FA.md
