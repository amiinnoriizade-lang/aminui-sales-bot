from pathlib import Path
from contextlib import asynccontextmanager
import aiosqlite, json
SCHEMA='''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users(telegram_id INTEGER PRIMARY KEY, username TEXT, first_seen TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS plans(code TEXT PRIMARY KEY, protocol TEXT NOT NULL, inbound_id INTEGER NOT NULL DEFAULT 0, volume_gb INTEGER NOT NULL CHECK(volume_gb>=0), months INTEGER NOT NULL CHECK(months>=1), price INTEGER NOT NULL CHECK(price>=0), enabled INTEGER NOT NULL DEFAULT 1, transport TEXT NOT NULL DEFAULT 'udp');
CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL, plan_code TEXT NOT NULL, username TEXT NOT NULL, protocol TEXT NOT NULL, inbound_id INTEGER NOT NULL, volume_gb INTEGER NOT NULL, months INTEGER NOT NULL, amount INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'awaiting_receipt', receipt_file_id TEXT, panel_client_id TEXT, error TEXT, renewal_account_id INTEGER, transport TEXT NOT NULL DEFAULT 'udp', created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL, username TEXT NOT NULL COLLATE NOCASE UNIQUE, protocol TEXT NOT NULL, inbound_id INTEGER NOT NULL, panel_identity TEXT NOT NULL, credential_enc TEXT NOT NULL, email TEXT NOT NULL UNIQUE, volume_gb INTEGER NOT NULL, expiry_ms INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'active', order_id INTEGER, transport TEXT NOT NULL DEFAULT 'udp', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS test_claims(telegram_id INTEGER PRIMARY KEY, claimed_at TEXT DEFAULT CURRENT_TIMESTAMP, account_id INTEGER);
CREATE TABLE IF NOT EXISTS dynamic_services(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE, protocol TEXT NOT NULL, inbound_id INTEGER NOT NULL DEFAULT 0, months INTEGER NOT NULL CHECK(months BETWEEN 1 AND 36), rate INTEGER NOT NULL CHECK(rate BETWEEN 1 AND 100000000), min_gb INTEGER NOT NULL DEFAULT 1 CHECK(min_gb BETWEEN 1 AND 10000), max_gb INTEGER NOT NULL DEFAULT 1000 CHECK(max_gb BETWEEN min_gb AND 10000), enabled INTEGER NOT NULL DEFAULT 1, transport TEXT NOT NULL DEFAULT 'udp');
CREATE TABLE IF NOT EXISTS support_messages(id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL, message TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_accounts_user ON accounts(telegram_id);
'''
@asynccontextmanager
async def connect(path):
 db=await aiosqlite.connect(path)
 db.row_factory=aiosqlite.Row
 await db.execute('PRAGMA foreign_keys=ON')
 await db.execute('PRAGMA busy_timeout=5000')
 try:
  yield db
 finally:
  await db.close()

async def init_db(path,plans,inbounds=None):
 Path(path).parent.mkdir(parents=True,exist_ok=True)
 async with connect(path) as db:
  await db.executescript(SCHEMA)
  pcols={r['name'] for r in await (await db.execute('PRAGMA table_info(plans)')).fetchall()}
  if pcols and 'inbound_id' not in pcols:
   await db.execute('ALTER TABLE plans ADD COLUMN inbound_id INTEGER NOT NULL DEFAULT 0')
  if pcols and 'transport' not in pcols:
   await db.execute("ALTER TABLE plans ADD COLUMN transport TEXT NOT NULL DEFAULT 'udp'")
  ocols={r['name'] for r in await (await db.execute('PRAGMA table_info(orders)')).fetchall()}
  if ocols and 'transport' not in ocols:
   await db.execute("ALTER TABLE orders ADD COLUMN transport TEXT NOT NULL DEFAULT 'udp'")
  acols={r['name'] for r in await (await db.execute('PRAGMA table_info(accounts)')).fetchall()}
  if acols and 'transport' not in acols:
   await db.execute("ALTER TABLE accounts ADD COLUMN transport TEXT NOT NULL DEFAULT 'udp'")
  # Migrate legacy dynamic services to retain the selected Inbound per service.
  dcols={r['name'] for r in await (await db.execute('PRAGMA table_info(dynamic_services)')).fetchall()}
  if dcols and 'transport' not in dcols:
   await db.execute("ALTER TABLE dynamic_services ADD COLUMN transport TEXT NOT NULL DEFAULT 'udp'")
  if dcols and 'inbound_id' not in dcols:
   await db.execute('ALTER TABLE dynamic_services RENAME TO dynamic_services_legacy')
   await db.execute("CREATE TABLE dynamic_services(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE, protocol TEXT NOT NULL, inbound_id INTEGER NOT NULL DEFAULT 0, months INTEGER NOT NULL CHECK(months BETWEEN 1 AND 36), rate INTEGER NOT NULL CHECK(rate BETWEEN 1 AND 100000000), min_gb INTEGER NOT NULL DEFAULT 1 CHECK(min_gb BETWEEN 1 AND 10000), max_gb INTEGER NOT NULL DEFAULT 1000 CHECK(max_gb BETWEEN min_gb AND 10000), enabled INTEGER NOT NULL DEFAULT 1, transport TEXT NOT NULL DEFAULT 'udp')")
   await db.execute('INSERT INTO dynamic_services(id,code,protocol,inbound_id,months,rate,min_gb,max_gb,enabled) SELECT id,code,protocol,0,months,rate,min_gb,max_gb,enabled FROM dynamic_services_legacy')
   await db.execute('DROP TABLE dynamic_services_legacy')
  if inbounds:
   for proto,iid in inbounds.items():
    if proto in ('vless','l2tp') and int(iid)>0:
     await db.execute('UPDATE dynamic_services SET inbound_id=? WHERE protocol=? AND inbound_id=0',(int(iid),proto))
     await db.execute('UPDATE plans SET inbound_id=? WHERE protocol=? AND inbound_id=0',(int(iid),proto))
  cols={r['name'] for r in await (await db.execute('PRAGMA table_info(orders)')).fetchall()}
  if 'renewal_account_id' not in cols:
   await db.execute('ALTER TABLE orders ADD COLUMN renewal_account_id INTEGER')
  cur=await db.execute('SELECT COUNT(*) n FROM plans'); n=(await cur.fetchone())['n']
  if not n:
   for p in plans:
    if p.get('protocol') in ('vless','l2tp','openvpn') and int(p.get('months',0))>0 and int(p.get('volume_gb',-1))>=0:
     await db.execute('INSERT OR IGNORE INTO plans(code,protocol,inbound_id,volume_gb,months,price) VALUES(?,?,?,?,?,?)',(p['code'],p['protocol'],int((inbounds or {}).get(p['protocol'],0)),int(p['volume_gb']),int(p['months']),int(p['price'])))
  await db.commit()
async def save_user(path,user):
 async with connect(path) as db:
  await db.execute('INSERT INTO users(telegram_id,username) VALUES(?,?) ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username',(user.id,user.username)); await db.commit()
async def plans(path):
 async with connect(path) as db: return await (await db.execute('SELECT * FROM plans WHERE enabled=1 ORDER BY protocol,months,volume_gb')).fetchall()
async def add_order(path,uid,plan,username,inbound):
 async with connect(path) as db:
  await db.execute('BEGIN IMMEDIATE')
  cur=await db.execute('SELECT * FROM plans WHERE code=? AND enabled=1',(plan,)); p=await cur.fetchone()
  if not p: raise ValueError('پلن در دسترس نیست.')
  if p['inbound_id'] and int(p['inbound_id']) != int(inbound): raise ValueError('Inbound پلن تغییر کرده؛ دوباره خرید را شروع کنید')
  inbound=int(p['inbound_id'] or inbound)
  cur=await db.execute('SELECT 1 FROM accounts WHERE username=? COLLATE NOCASE',(username,))
  if await cur.fetchone(): raise ValueError('این نام کاربری قبلاً استفاده شده است.')
  cur=await db.execute("SELECT 1 FROM orders WHERE username=? COLLATE NOCASE AND status IN ('awaiting_receipt','review','processing')",(username,))
  if await cur.fetchone(): raise ValueError('این نام کاربری در یک سفارش دیگر رزرو شده است.')
  cur=await db.execute('INSERT INTO orders(telegram_id,plan_code,username,protocol,inbound_id,volume_gb,months,amount,transport) VALUES(?,?,?,?,?,?,?,?,?)',(uid,plan,username,p['protocol'],inbound,p['volume_gb'],p['months'],p['price'],p['transport']))
  await db.commit(); return cur.lastrowid,dict(p)
async def attach_receipt(path,oid,uid,fileid):
 async with connect(path) as db:
  cur=await db.execute("UPDATE orders SET receipt_file_id=?,status='review',updated_at=CURRENT_TIMESTAMP WHERE id=? AND telegram_id=? AND status='awaiting_receipt'",(fileid,oid,uid)); await db.commit(); return cur.rowcount==1
async def claim_order(path,oid):
 async with connect(path) as db:
  await db.execute('BEGIN IMMEDIATE'); cur=await db.execute("UPDATE orders SET status='processing',updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='review'",(oid,)); await db.commit(); return cur.rowcount==1
async def finish_order(path,oid,identity,account_values):
 async with connect(path) as db:
  await db.execute('BEGIN IMMEDIATE')
  cur=await db.execute('SELECT * FROM orders WHERE id=?',(oid,)); o=await cur.fetchone()
  if not o or o['status']!='processing': raise ValueError('وضعیت سفارش تغییر کرده است.')
  await db.execute('INSERT INTO accounts(telegram_id,username,protocol,inbound_id,panel_identity,credential_enc,email,volume_gb,expiry_ms,status,order_id,transport) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',account_values)
  await db.execute("UPDATE orders SET status='paid',panel_client_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(identity,oid)); await db.commit()
async def release_order_for_retry(path,oid,err):
 async with connect(path) as db:
  cur=await db.execute("UPDATE orders SET status='review',error=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='processing'",(err[:500],oid)); await db.commit(); return cur.rowcount==1
async def fail_order(path,oid,err):
 # Provisioning may have reached the remote panel; do not make it retryable.
 await mark_order_unknown(path,oid,err)
async def mark_order_unknown(path,oid,err):
 async with connect(path) as db:
  cur=await db.execute("UPDATE orders SET status='provisioning_unknown',error=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='processing'",(err[:500],oid))
  await db.commit()
  return cur.rowcount == 1
async def claim_test(path,uid):
 async with connect(path) as db:
  try: await db.execute('INSERT INTO test_claims(telegram_id) VALUES(?)',(uid,)); await db.commit(); return True
  except aiosqlite.IntegrityError: return False
async def set_test_account(path,uid,aid):
 async with connect(path) as db: await db.execute('UPDATE test_claims SET account_id=? WHERE telegram_id=?',(aid,uid)); await db.commit()
async def user_accounts(path,uid):
 async with connect(path) as db: return await (await db.execute('SELECT * FROM accounts WHERE telegram_id=? ORDER BY id DESC',(uid,))).fetchall()
async def all_accounts(path):
 async with connect(path) as db: return await (await db.execute('SELECT * FROM accounts ORDER BY id DESC LIMIT 100')).fetchall()
async def get_order(path,oid):
 async with connect(path) as db: return await (await db.execute('SELECT * FROM orders WHERE id=?',(oid,))).fetchone()
async def orders_review(path):
 async with connect(path) as db: return await (await db.execute("SELECT * FROM orders WHERE status IN ('review','provisioning_unknown') ORDER BY id")).fetchall()
async def stats(path):
 async with connect(path) as db:
  a=await (await db.execute('SELECT COUNT(*) n FROM users')).fetchone(); b=await (await db.execute("SELECT COUNT(*) n FROM accounts WHERE status='active'")).fetchone(); c=await (await db.execute("SELECT COALESCE(SUM(amount),0) n FROM orders WHERE status='paid'")).fetchone(); d=await (await db.execute('SELECT COUNT(*) n FROM orders')).fetchone(); return a['n'],b['n'],c['n'],d['n']
async def set_price(path,code,price):
 async with connect(path) as db: cur=await db.execute('UPDATE plans SET price=? WHERE code=?',(price,code)); await db.commit(); return cur.rowcount
async def add_plan(path,code,protocol,vol,months,price):
 async with connect(path) as db: await db.execute('INSERT INTO plans(code,protocol,volume_gb,months,price) VALUES(?,?,?,?,?)',(code,protocol,vol,months,price)); await db.commit()
async def save_support(path,uid,msg):
 async with connect(path) as db: await db.execute('INSERT INTO support_messages(telegram_id,message) VALUES(?,?)',(uid,msg)); await db.commit()
async def recent_orders(path,uid):
 async with connect(path) as db: return await (await db.execute('SELECT * FROM orders WHERE telegram_id=? ORDER BY id DESC LIMIT 20',(uid,))).fetchall()

async def all_plans(path):
 async with connect(path) as db:
  return await (await db.execute('SELECT * FROM plans ORDER BY protocol,months,volume_gb')).fetchall()
async def set_plan_enabled(path,code,enabled):
 async with connect(path) as db:
  cur=await db.execute('UPDATE plans SET enabled=? WHERE code=?',(1 if enabled else 0,code)); await db.commit(); return cur.rowcount
async def delete_plan(path,code):
 async with connect(path) as db:
  cur=await db.execute("DELETE FROM plans WHERE code=? AND NOT EXISTS(SELECT 1 FROM orders WHERE plan_code=?)",(code,code)); await db.commit(); return cur.rowcount
async def update_plan(path,code,protocol,vol,months,price):
 async with connect(path) as db:
  cur=await db.execute('UPDATE plans SET protocol=?,volume_gb=?,months=?,price=? WHERE code=?',(protocol,vol,months,price,code)); await db.commit(); return cur.rowcount
async def get_setting(path,key,default=''):
 async with connect(path) as db:
  await db.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
  row=await (await db.execute('SELECT value FROM settings WHERE key=?',(key,))).fetchone()
  return row['value'] if row else default
async def set_setting(path,key,value):
 async with connect(path) as db:
  await db.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
  await db.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value)); await db.commit()
async def recent_users(path,limit=30):
 async with connect(path) as db:
  return await (await db.execute('SELECT u.telegram_id,u.username,COUNT(a.id) account_count FROM users u LEFT JOIN accounts a ON a.telegram_id=u.telegram_id GROUP BY u.telegram_id ORDER BY u.first_seen DESC LIMIT ?',(limit,))).fetchall()

async def dynamic_services(path, enabled_only=True):
 async with connect(path) as db:
  q='SELECT * FROM dynamic_services'+(' WHERE enabled=1' if enabled_only else '')+' ORDER BY protocol,months'
  return await (await db.execute(q)).fetchall()
async def add_dynamic_service(path,code,protocol,months,rate,min_gb,max_gb,inbound_id=0,transport='udp'):
 async with connect(path) as db:
  await db.execute('INSERT INTO dynamic_services(code,protocol,inbound_id,months,rate,min_gb,max_gb,transport) VALUES(?,?,?,?,?,?,?,?)',(code,protocol,inbound_id,months,rate,min_gb,max_gb,transport)); await db.commit()
async def update_dynamic_service(path,code,field,value):
 if field not in ('protocol','inbound_id','months','rate','min_gb','max_gb','enabled','transport'): raise ValueError('invalid field')
 async with connect(path) as db:
  cur=await db.execute(f'UPDATE dynamic_services SET {field}=? WHERE code=?',(value,code)); await db.commit(); return cur.rowcount
async def delete_dynamic_service(path,code):
 # Keep the service row so historical orders and audit context are never lost.
 return await update_dynamic_service(path,code,'enabled',0)
async def add_custom_order(path,uid,service_code,volume,username,inbound):
 import re
 if type(uid) is not int or uid <= 0: raise ValueError('شناسه کاربر معتبر نیست')
 if type(inbound) is not int or inbound <= 0: raise ValueError('شناسه ورودی پنل معتبر نیست')
 if type(volume) is not int or not 1 <= volume <= 1000: raise ValueError('حجم باید بین ۱ تا ۱۰۰۰ گیگ باشد')
 if not isinstance(username,str) or not re.fullmatch(r'[A-Za-z0-9_]{3,32}',username): raise ValueError('نام کاربری معتبر نیست')
 if not isinstance(service_code,str) or not service_code: raise ValueError('سرویس معتبر نیست')
 async with connect(path) as db:
  await db.execute('BEGIN IMMEDIATE')
  row=await (await db.execute('SELECT * FROM dynamic_services WHERE code=? AND enabled=1',(service_code,))).fetchone()
  if not row: raise ValueError('سرویس در دسترس نیست')
  if row['inbound_id'] and int(row['inbound_id']) != inbound: raise ValueError('Inbound این سرویس تغییر کرده؛ دوباره خرید را شروع کنید')
  if row['protocol'] not in ('vless','l2tp','openvpn'): raise ValueError('ساخت خودکار حساب فقط برای VLESS، L2TP و OpenVPN پیاده‌سازی شده است')
  if type(row['months']) is not int or not 1 <= row['months'] <= 36: raise ValueError('مدت سرویس نامعتبر است')
  if type(row['rate']) is not int or not 1 <= row['rate'] <= 10000000: raise ValueError('قیمت سرویس نامعتبر است')
  if volume < row['min_gb'] or volume > row['max_gb']: raise ValueError('حجم خارج از محدوده مجاز است')
  price=volume*row['rate']*row['months']
  if not 0 < price <= 1000000000000: raise ValueError('مبلغ سفارش خارج از محدوده مجاز است')
  if await (await db.execute('SELECT 1 FROM accounts WHERE username=? COLLATE NOCASE',(username,))).fetchone(): raise ValueError('این نام کاربری قبلاً استفاده شده است')
  if await (await db.execute("SELECT 1 FROM orders WHERE username=? COLLATE NOCASE AND status IN ('awaiting_receipt','review','processing')",(username,))).fetchone(): raise ValueError('این نام کاربری در سفارش دیگری رزرو شده است')
  plan_code=f"dyn-{row['id']}-{volume}-{row['months']}"
  await db.execute('INSERT INTO plans(code,protocol,inbound_id,volume_gb,months,price,enabled,transport) VALUES(?,?,?,?,?,?,1,?) ON CONFLICT(code) DO UPDATE SET protocol=excluded.protocol,inbound_id=excluded.inbound_id,volume_gb=excluded.volume_gb,months=excluded.months,price=excluded.price,enabled=1,transport=excluded.transport',(plan_code,row['protocol'],inbound,volume,row['months'],price,row['transport']))
  cur=await db.execute('INSERT INTO orders(telegram_id,plan_code,username,protocol,inbound_id,volume_gb,months,amount,transport) VALUES(?,?,?,?,?,?,?,?,?)',(uid,plan_code,username,row['protocol'],inbound,volume,row['months'],price,row['transport']))
  await db.commit()
  return cur.lastrowid,{'protocol':row['protocol'],'volume_gb':volume,'months':row['months'],'price':price,'rate':row['rate'],'transport':row['transport']}


async def add_renewal_order(path,uid,account_id,plan_code):
 async with connect(path) as db:
  await db.execute('BEGIN IMMEDIATE')
  a=await (await db.execute("SELECT * FROM accounts WHERE id=? AND telegram_id=? AND status='active'",(account_id,uid))).fetchone()
  p=await (await db.execute('SELECT * FROM plans WHERE code=? AND enabled=1',(plan_code,))).fetchone()
  if not a or not p: raise ValueError('حساب یا پلن معتبر نیست.')
  if a['protocol'] != p['protocol']: raise ValueError('پروتکل پلن با حساب یکسان نیست.')
  if p['inbound_id'] and int(a['inbound_id']) != int(p['inbound_id']): raise ValueError('Inbound پلن با حساب یکسان نیست؛ پلن همان Inbound را انتخاب کنید.')
  cur=await db.execute('INSERT INTO orders(telegram_id,plan_code,username,protocol,inbound_id,volume_gb,months,amount,renewal_account_id,transport) VALUES(?,?,?,?,?,?,?,?,?,?)',(uid,plan_code,a['username'],a['protocol'],a['inbound_id'],p['volume_gb'],p['months'],p['price'],account_id,a['transport']))
  await db.commit()
  return cur.lastrowid,dict(p)

async def finish_renewal(path,oid,account_id,expiry_ms,volume_gb):
 async with connect(path) as db:
  await db.execute('BEGIN IMMEDIATE')
  o=await (await db.execute("SELECT status,renewal_account_id FROM orders WHERE id=?",(oid,))).fetchone()
  if not o or o['status']!='processing' or o['renewal_account_id']!=account_id:
   raise ValueError('وضعیت سفارش تمدید تغییر کرده است.')
  await db.execute("UPDATE accounts SET expiry_ms=?,volume_gb=?,status='active' WHERE id=?",(expiry_ms,volume_gb,account_id))
  await db.execute("UPDATE orders SET status='paid',panel_client_id='renewed',updated_at=CURRENT_TIMESTAMP WHERE id=?",(oid,))
  await db.commit()
