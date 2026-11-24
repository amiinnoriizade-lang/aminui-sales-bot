# VPN-UI Telegram 销售机器人

这是一个用于销售和管理 VPN 账号的 Telegram 机器人，通过 HTTP API 连接到一个 VPN-UI 面板实例，并使用 SQLite 保存本地应用数据。

## 功能

- 波斯语客户菜单，以及 Telegram 图形化管理员菜单。
- 固定套餐和按流量计价的服务（流量 × 每 GB 每月价格 × 月数）。
- 客户可自选用户名，机器人和面板都会检查用户名是否重复。
- 银行卡转账付款：客户提交付款凭证，由管理员手动批准或拒绝。
- 创建 VLESS 和 L2TP 账号；L2TP/IPsec PSK 从所选 inbound 设置中读取。
- 当连接的面板版本提供相应接口时，获取并发送 OpenVPN TCP/UDP 配置文件。
- 每位客户一次的 VLESS 试用：1 GB、24 小时，由管理员选择试用 inbound。
- 账号列表、续费、流量查询、启用/禁用/删除账号、客服消息、群发通知和数据库备份。
- 使用 Fernet 加密保存的账号凭据。

机器人管理单个已连接 VPN-UI 实例中的兼容 inbound，并不是多面板管理系统。本版本尚未实现 WireGuard 和 OpenConnect 账号创建。

## 环境要求

- Ubuntu 22.04 或 24.04
- Python 3.10+
- Telegram Bot Token 和管理员的数字 Telegram ID
- 具有 inbound/客户端管理权限且可访问的 VPN-UI 面板账号
- 客户能够访问的公网 VPN IP 地址或域名

## 安装

```bash
git clone https://github.com/amiinnoriizade-lang/aminui-sales-bot.git
cd aminui-sales-bot
sudo bash install.sh
```

安装程序会询问 Telegram Token、管理员 ID 和 VPN-UI 面板连接信息。输入密钥时不会回显，并会以受限权限保存到 `.env` 文件。加密密钥只生成一次；请安全备份，保存账号凭据后不要更换该密钥。

默认安装目录为 `/opt/vpnui-sales-bot`，systemd 服务名称为 `vpnui-sales-bot.service`。可通过 `APP_DIR` 修改应用目录。

启动并查看服务：

```bash
sudo systemctl start vpnui-sales-bot
sudo systemctl status vpnui-sales-bot --no-pager
sudo journalctl -u vpnui-sales-bot -f
```

## Telegram 首次配置

1. 使用管理员账号向机器人发送 `/start`。
2. 打开 **مدیریت ربات**（机器人管理）。
3. 检查面板连接并查看可用 inbound。
4. 为免费试用账号选择一个启用状态的 VLESS inbound。
5. 创建固定套餐或按流量计价的套餐，并为每个套餐选择 inbound。
6. 设置银行卡号、持卡人姓名和付款说明。
7. 运行 `/paneltest`，检查面板 API 的读取权限。

创建账号会在已连接的面板中写入真实客户端。正式向客户提供服务前，请使用测试账号验证实际 VPN-UI 版本和所选 inbound。

## 安全

- 不要将 `.env`、环境文件备份、SQLite 数据库或面板凭据提交到 GitHub。
- 请在安全位置同时备份 `.env` 和 SQLite 数据库。
- 妥善保存 `APP_ENCRYPTION_KEY`；没有它就无法解密已加密的凭据。
- 必须验证 TLS 证书。
- 每个 Telegram Bot Token 只运行一个 polling 实例，以避免轮询冲突。
