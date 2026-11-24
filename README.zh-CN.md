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

默认安装目录为 `/opt/aminui-sales-bot`，systemd 服务名称为 `aminui-sales-bot.service`。可通过 `APP_DIR` 修改应用目录。

启动并查看服务：

```bash
sudo systemctl start aminui-sales-bot
sudo systemctl status aminui-sales-bot --no-pager
sudo journalctl -u aminui-sales-bot -f
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


## 项目支持钱包

**TRON（TRX / TRC20 网络）**
`TUqbpFe8XmL2qcEdQ77SybMU8YW5vf2qGn`

**Bitcoin（BTC）**
`17F1gSMENRr5tAmTnPEoduvtSGGY3KMVzB`

**Polygon**
`0x88B8841E9f47B57f7fd1bBb6375FcA6CB786EE28`

**USDT（TRC20）**
`TFUvPCaon7eBk1Xaoce3geZPjnks3kEaqW`

**BNB**
`0x88B8841E9f47B57f7fd1bBb6375FcA6CB786EE28`

**Ethereum（ETH）**
`0x88B8841E9f47B57f7fd1bBb6375FcA6CB786EE28`

请务必选择正确的币种和网络。使用错误网络转账可能导致资产永久丢失。

## 完整安装

在服务器上执行：

```bash
git clone https://github.com/amiinnoriizade-lang/aminui-sales-bot.git
cd aminui-sales-bot
sudo bash install.sh
```

安装程序会询问 Telegram Bot Token、管理员数字 ID、VPN-UI 面板地址（包含端口和基础路径）、面板用户名和密码，以及可选的公网 VPN IP 或域名。输入密钥时不会显示内容，并以受限权限保存到 `.env`。加密密钥只生成一次；请安全备份，保存账号凭据后不要更换。

默认安装目录：`/opt/aminui-sales-bot`。systemd 服务：`aminui-sales-bot.service`。可通过 `APP_DIR` 指定其他目录。

启动并查看服务：

```bash
sudo systemctl start aminui-sales-bot
sudo systemctl status aminui-sales-bot --no-pager
sudo journalctl -u aminui-sales-bot -f
```

## Telegram 首次配置

1. 使用管理员账号发送 `/start`。
2. 打开 **مدیریت ربات**（机器人管理）。
3. 检查面板连接并查看 inbound 列表。
4. 为免费试用选择一个启用状态的 VLESS inbound。
5. 创建固定套餐或流量套餐，并为每个套餐指定 inbound。
6. 设置银行卡号、持卡人姓名和付款说明。
7. 运行 `/paneltest` 检查面板 API 读取权限。

创建账号会在连接的面板中写入真实客户端。正式销售前，请用测试账号验证实际面板版本和所选 inbound。

## 更新

以 root 身份进入已安装的应用目录后执行：

```bash
cd /opt/aminui-sales-bot
sudo bash update.sh
```

更新程序会备份源代码、`.env` 和默认 SQLite 数据库，然后安装依赖、编译代码并运行单元测试。只有更新前服务处于运行状态时，才会在更新成功后重启服务。如果安装在其他目录，请先进入实际安装目录。

## 测试

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## 安全

请在安全位置同时备份 `.env` 和 SQLite 数据库，并妥善保存 `APP_ENCRYPTION_KEY`。必须验证 TLS 证书。不要将密钥或数据库上传到 GitHub。每个 Telegram Bot Token 只运行一个 polling 实例。
