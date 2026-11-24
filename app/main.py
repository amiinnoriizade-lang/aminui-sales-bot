import asyncio,logging,os,shutil
from aiogram import Bot,Dispatcher,F
from aiogram.filters import CommandStart,Command
from aiogram.types import Message,CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton,BufferedInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State,StatesGroup
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from html import escape
from .config import load_config
from .db import *
from .vpnui import VPNUIClient,VPNUIError
from .security import SecretBox,valid_username
from .service import create_panel_account,render_connection,add_months_ms,gb_bytes,renew_panel_account,validate_openvpn_transport
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
class Flow(StatesGroup): username=State(); receipt=State(); support=State(); support_reply=State(); price=State(); broadcast=State(); card_number=State(); cardholder=State(); payment_text=State(); plan_price=State(); static_plan_volume=State(); static_plan_months=State(); static_plan_price=State(); static_plan_transport=State(); volume=State(); svc_months=State(); svc_rate=State(); svc_min=State(); svc_max=State(); welcome_text=State(); svc_edit_months=State(); svc_edit_rate=State(); svc_edit_min=State(); svc_edit_max=State(); svc_transport=State()
def kb(rows): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t,callback_data=d) for t,d in r] for r in rows])
async def main():
 cfg=load_config(); await init_db(cfg.database_path,cfg.default_plans,{'vless':cfg.vless_inbound,'l2tp':cfg.l2tp_inbound}); box=SecretBox(cfg.encryption_key)
 bot=Bot(cfg.bot_token,default=DefaultBotProperties(parse_mode=ParseMode.HTML)); dp=Dispatcher(storage=MemoryStorage())
 panel=VPNUIClient(cfg.panel_base_url,cfg.panel_username,cfg.panel_password,cfg.verify_tls,cfg.dry_run)
 def admin(uid): return uid in cfg.admin_ids
 def inbound(protocol):
  if protocol == 'vless': return cfg.vless_inbound
  if protocol == 'l2tp': return cfg.l2tp_inbound
  if protocol == 'openvpn': return 0
  raise ValueError('پروتکل پشتیبانی نمی‌شود.')
 @dp.message(CommandStart())
 async def start(m:Message):
  await save_user(cfg.database_path,m.from_user)
  rows=[[('🛍 خرید سرویس','catalog')],[('🧪 اکانت تست یک‌روزه','trial')],[('👤 سرویس‌های من','account')],[('🧾 سفارش‌های من','myorders')],[('☎️ پشتیبانی','support')]]
  if admin(m.from_user.id): rows.append([('⚙️ مدیریت ربات','admin:home')])
  welcome=await get_setting(cfg.database_path,'welcome_message','سلام به فروشگاه ما خوش آمدید 🌹\n\nلطفاً پلن و حجم مورد نظر خود را انتخاب کنید.\n\nحداکثر ۱۰ دقیقه بعد از ارسال رسید، اکانت شما تحویل داده می‌شود. ✅')
  await m.answer(escape(welcome),reply_markup=kb(rows))
 @dp.message(Command('paneltest'))
 async def paneltest(m:Message):
  if not admin(m.from_user.id): return
  try:
   rows=await panel.list_inbounds(); lines=[f"#{x.get('id')} {escape(str(x.get('protocol')))} {'فعال' if x.get('enable') else 'غیرفعال'}" for x in rows[:50]]
   await m.answer('اتصال موفق.\n'+'\n'.join(lines)+f'\nDRY_RUN={cfg.dry_run}')
  except Exception as e: await m.answer('خطا: '+escape(str(e)[:500]))
 @dp.callback_query(F.data=='catalog')
 async def catalog(c:CallbackQuery):
  await c.answer()
  services=await dynamic_services(cfg.database_path)
  ps=await plans(cfg.database_path)
  rows=[]
  if services:
   rows.append([('── سرویس‌های انتخاب حجم ──','noop')])
   for x in services:
    rows.append([(f"{x['protocol'].upper()}{(' '+x['transport'].upper()) if x['protocol']=='openvpn' else ''} | {x['months']} ماه | هر گیگ/ماه {x['rate']:,} تومان",f"service:{x['code']}")])
  if ps:
   rows.append([('── پلن‌های آماده ──','noop')])
   for p in ps:
    vol='نامحدود' if p['volume_gb']==0 else f"{p['volume_gb']} گیگ"
    rows.append([(f"{p['protocol'].upper()}{(' '+p['transport'].upper()) if p['protocol']=='openvpn' else ''} | {vol} | {p['months']} ماه | {p['price']:,} تومان",f"buy:{p['code']}")])
  if not rows: return await c.message.answer('فعلاً سرویسی تعریف نشده است.')
  await c.message.answer('سرویس موردنظر را انتخاب کنید:',reply_markup=kb(rows))
 @dp.callback_query(F.data.startswith('service:'))
 async def choose_service(c:CallbackQuery,state):
  await c.answer(); code=c.data.split(':',1)[1]
  services=await dynamic_services(cfg.database_path)
  svc=next((x for x in services if x['code']==code),None)
  if not svc: return await c.message.answer('این سرویس در دسترس نیست.')
  await state.update_data(service_code=code)
  await state.set_state(Flow.volume)
  await c.message.answer(f"چند گیگابایت می‌خواهید؟\nحداقل: {svc['min_gb']} و حداکثر: {svc['max_gb']} گیگابایت\nقیمت هر گیگ در ماه: {svc['rate']:,} تومان\nمدت: {svc['months']} ماه")
 @dp.message(Flow.volume)
 async def choose_volume(m:Message,state):
  raw=(m.text or '').strip()
  if not raw.isdigit(): return await m.answer('لطفاً حجم را فقط به‌صورت عدد وارد کنید.')
  volume=int(raw); data=await state.get_data(); svcs=await dynamic_services(cfg.database_path)
  svc=next((x for x in svcs if x['code']==data.get('service_code')),None)
  if not svc: await state.clear(); return await m.answer('سرویس دیگر فعال نیست؛ دوباره خرید را شروع کنید.')
  if volume<svc['min_gb'] or volume>svc['max_gb']: return await m.answer(f"حجم باید بین {svc['min_gb']} تا {svc['max_gb']} گیگ باشد.")
  amount=volume*svc['rate']*svc['months']
  await state.update_data(volume_gb=volume,estimated_amount=amount)
  await state.set_state(Flow.username)
  await m.answer(f"حجم انتخابی: {volume} گیگ\nمدت: {svc['months']} ماه\nمبلغ: {amount:,} تومان\n\nحالا نام کاربری دلخواه را وارد کنید:")
 @dp.callback_query(F.data.startswith('buy:'))
 async def buy(c:CallbackQuery,state):
  await c.answer(); code=c.data[4:]; ps=await plans(cfg.database_path); p=next((x for x in ps if x['code']==code),None)
  if not p: return await c.message.answer('پلن معتبر نیست.')
  await state.update_data(plan=code); await state.set_state(Flow.username)
  await c.message.answer('نام کاربری دلخواه را وارد کنید (۳ تا ۳۲ کاراکتر؛ حروف انگلیسی، عدد، نقطه، خط تیره یا زیرخط):')
 @dp.message(Flow.username)
 async def username(m:Message,state):
  name=m.text.strip() if m.text else ''
  if not valid_username(name): return await m.answer('نام کاربری معتبر نیست. دوباره وارد کنید.')
  data=await state.get_data()
  try:
   if data.get('service_code'):
    svc=next((x for x in await dynamic_services(cfg.database_path) if x['code']==data['service_code']),None)
    if not svc: raise ValueError('سرویس پیدا نشد')
    iid=int(svc['inbound_id'] or inbound(svc['protocol'])); remote=await panel.existing_usernames([iid])
    if name.casefold() in remote: return await m.answer('این نام در پنل استفاده شده؛ نام دیگری انتخاب کنید.')
    oid,plan=await add_custom_order(cfg.database_path,m.from_user.id,data['service_code'],int(data['volume_gb']),name,iid)
   else:
    ps=await plans(cfg.database_path); p=next((x for x in ps if x['code']==data.get('plan')),None)
    if not p: await state.clear(); return await m.answer('پلن منقضی شده؛ دوباره از فروشگاه انتخاب کنید.')
    iid=int(p['inbound_id'] or inbound(p['protocol'])); remote=await panel.existing_usernames([iid])
    if name.casefold() in remote: return await m.answer('این نام در پنل استفاده شده؛ نام دیگری انتخاب کنید.')
    oid,plan=await add_order(cfg.database_path,m.from_user.id,p['code'],name,iid)
  except Exception as e: return await m.answer('امکان ثبت سفارش نیست: '+escape(str(e)[:300]))
  await state.update_data(order_id=oid); await state.set_state(Flow.receipt)
  card_number=await get_setting(cfg.database_path,'card_number',cfg.card_number); cardholder=await get_setting(cfg.database_path,'cardholder_name',cfg.cardholder_name); paytext=await get_setting(cfg.database_path,'payment_instructions',cfg.payment_instructions)
  card=(f'\nشماره کارت: <code>{escape(card_number)}</code>\nبه نام: {escape(cardholder)}' if card_number else '\nاطلاعات کارت هنوز توسط مدیر تنظیم نشده است.')
  await m.answer(f'سفارش #{oid} ثبت شد.\nحجم: {plan["volume_gb"]} گیگ | مدت: {plan["months"]} ماه\nمبلغ: <b>{plan["price"]:,} تومان</b>{card}\n{escape(paytext)}\nپس از واریز تصویر رسید را همین‌جا ارسال کنید.')
 @dp.message(Flow.receipt,F.photo)
 async def receipt(m:Message,state):
  d=await state.get_data(); oid=d.get('order_id')
  if not oid: await state.clear(); return
  ok=await attach_receipt(cfg.database_path,oid,m.from_user.id,m.photo[-1].file_id)
  await state.clear()
  if not ok: return await m.answer('سفارش در وضعیت مناسب نیست.')
  o=await get_order(cfg.database_path,oid)
  for aid in cfg.admin_ids:
   try: await bot.send_photo(aid,m.photo[-1].file_id,caption=f"رسید سفارش #{oid}\nکاربر: {m.from_user.id}\nنام: {o['username']}\nپروتکل: {o['protocol']}{(' '+o['transport'].upper()) if o['protocol']=='openvpn' else ''}\nمبلغ: {o['amount']:,} تومان",reply_markup=kb([[('✅ تأیید و ساخت حساب',f'approve:{oid}'),('❌ رد رسید',f'reject:{oid}')]]))
   except Exception: logging.exception('admin receipt delivery failed')
  await m.answer('رسید دریافت شد. پس از بررسی مدیر، حساب به‌صورت خودکار تحویل داده می‌شود.')
 @dp.message(Flow.receipt)
 async def receipt_other(m:Message): await m.answer('لطفاً تصویر رسید را به‌صورت عکس ارسال کنید.')
 @dp.callback_query(F.data.startswith('approve:'))
 async def approve(c:CallbackQuery):
  if not admin(c.from_user.id): return await c.answer('دسترسی ندارید.',show_alert=True)
  await c.answer()
  try: oid=int(c.data.split(':',1)[1])
  except (ValueError,IndexError): return await c.message.answer('شناسه سفارش نامعتبر است.')
  if oid <= 0: return await c.message.answer('شناسه سفارش نامعتبر است.')
  if cfg.dry_run: return await c.message.answer('ساخت واقعی مسدود است: DRY_RUN=true. ابتدا API نوشتن پنل را با نسخه دقیق بررسی و سپس DRY_RUN را خاموش کنید.')
  if not await claim_order(cfg.database_path,oid): return await c.message.answer('این سفارش قبلاً بررسی شده یا در وضعیت تأیید نیست.')
  o=await get_order(cfg.database_path,oid)
  try:
   ovpn_profile=None
   write_started=False
   if o['renewal_account_id']:
    async with connect(cfg.database_path) as db:
     existing=await (await db.execute('SELECT * FROM accounts WHERE id=? AND telegram_id=?',(o['renewal_account_id'],o['telegram_id']))).fetchone()
    if not existing: raise ValueError('حساب مقصد تمدید پیدا نشد.')
    inbound_obj=await panel.get_inbound(existing['inbound_id'])
    if existing['protocol']!='openvpn': render_connection(cfg,existing['protocol'],inbound_obj,existing['username'],'PREFLIGHT')
    if existing['protocol']=='openvpn':
     validate_openvpn_transport(inbound_obj,existing['transport'])
     ovpn_profile=await panel.download_openvpn_profile(existing['inbound_id'],existing['transport'])
    write_started=True
    new_expiry=await renew_panel_account(panel,existing,o['months'],o['volume_gb'])
    if existing['protocol']=='openvpn':
     conn=f"OpenVPN {existing['transport'].upper()}\nنام کاربری: {existing['username']}\nرمز عبور: {box.dec(existing['credential_enc'])}"
    else:
     conn=render_connection(cfg,existing['protocol'],inbound_obj,existing['username'],box.dec(existing['credential_enc']))
    await finish_renewal(cfg.database_path,oid,existing['id'],new_expiry,o['volume_gb'])
   else:
    inbound_obj=await panel.get_inbound(o['inbound_id'])
    if o['protocol']!='openvpn': render_connection(cfg,o['protocol'],inbound_obj,o['username'],'PREFLIGHT')
    if o['protocol']=='openvpn':
     validate_openvpn_transport(inbound_obj,o['transport'])
     ovpn_profile=await panel.download_openvpn_profile(o['inbound_id'],o['transport'])
    write_started=True
    made=await create_panel_account(panel,cfg,o['protocol'],o['inbound_id'],o['username'],o['telegram_id'],o['volume_gb'],o['months'],transport=o['transport'],inbound_obj=inbound_obj)
    if o['protocol']=='openvpn':
     conn=f"OpenVPN {o['transport'].upper()}\nنام کاربری: {o['username']}\nرمز عبور: {made['credential']}"
    else:
     conn=render_connection(cfg,o['protocol'],inbound_obj,o['username'],made['credential'])
    account_values=(o['telegram_id'],o['username'],o['protocol'],o['inbound_id'],made['identity'],box.enc(made['credential']),made['email'],o['volume_gb'],made['expiry_ms'],'active',oid,o['transport'])
    await finish_order(cfg.database_path,oid,made['identity'],account_values)
  except Exception as e:
   if write_started:
    # Once a write may have reached the remote panel, never retry automatically.
    await mark_order_unknown(cfg.database_path,oid,str(e))
    logging.exception('order provisioning outcome unknown; manual panel reconciliation required')
    await c.message.answer('وضعیت ساخت حساب نامشخص است. برای جلوگیری از ساخت حساب تکراری، سفارش قفل شد. پنل را بررسی کنید و قبل از هر تلاش مجدد، وجود حساب را با نام کاربری سفارش تطبیق دهید.')
   else:
    await release_order_for_retry(cfg.database_path,oid,str(e))
    logging.exception('preflight failed before panel write; order returned to review')
    await c.message.answer('بررسی اولیه پنل ناموفق بود و هنوز ساخت حسابی انجام نشده است. سفارش برای تلاش مجدد به فهرست بررسی مدیر برگشت. خطا: '+escape(str(e)[:250]))
   return
  try:
   if ovpn_profile is not None:
    await bot.send_document(o['telegram_id'],BufferedInputFile(ovpn_profile,filename=f"{o['username']}-{o['transport']}.ovpn"),caption=f'پرداخت سفارش #{oid} تأیید شد.\nپروتکل: OpenVPN {o["transport"].upper()}\nنام کاربری: <code>{escape(o["username"])}</code>\nرمز عبور: <code>{escape(box.dec(existing["credential_enc"]) if o["renewal_account_id"] else made["credential"])}</code>')
   else:
    await bot.send_message(o['telegram_id'],f'پرداخت سفارش #{oid} تأیید شد.\n{escape(conn)}',disable_web_page_preview=True)
   await c.message.answer('حساب ساخته و برای مشتری ارسال شد.')
  except Exception:
   logging.exception('account created but Telegram delivery failed for order %s',oid)
   await c.message.answer('حساب در پنل ساخته و سفارش ثبت شد، اما ارسال پیام به مشتری ناموفق بود. از منوی «سرویس‌های من» اطلاعات حساب را مشاهده کنید.')
 @dp.callback_query(F.data.startswith('reject:'))
 async def reject(c:CallbackQuery):
  if not admin(c.from_user.id): return await c.answer('دسترسی ندارید.',show_alert=True)
  try: oid=int(c.data.split(':',1)[1])
  except (ValueError,IndexError): return await c.answer('شناسه سفارش نامعتبر است.',show_alert=True)
  if oid <= 0: return await c.answer('شناسه سفارش نامعتبر است.',show_alert=True)
  async with connect(cfg.database_path) as db:
   cur=await db.execute("UPDATE orders SET status='rejected',updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='review'",(oid,)); await db.commit()
  await c.answer('رد شد' if cur.rowcount else 'قبلاً بررسی شده')
  if cur.rowcount:
   o=await get_order(cfg.database_path,oid); await bot.send_message(o['telegram_id'],f'رسید سفارش #{oid} رد شد. برای پیگیری با پشتیبانی تماس بگیرید.')
 @dp.callback_query(F.data=='trial')
 async def trial(c:CallbackQuery):
  await c.answer()
  iid=int(await get_setting(cfg.database_path,'trial_vless_inbound',str(cfg.vless_inbound)) or 0)
  try:
   if iid <= 0:
    candidates=[x for x in await panel.list_inbounds() if str(x.get('protocol') or '').lower()=='vless' and x.get('enable')]
    if len(candidates)==1: iid=int(candidates[0]['id'])
    else: raise VPNUIError('مدیر باید Inbound اکانت تست را از منوی مدیریت ربات انتخاب کند.')
   inbound_obj=await panel.get_inbound(iid)
   if not inbound_obj.get('enable') or str(inbound_obj.get('protocol','')).lower()!='vless':
    raise VPNUIError('Inbound تست فعال یا از نوع VLESS نیست.')
   name=f'test{c.from_user.id}'
   render_connection(cfg,'vless',inbound_obj,name,'PREFLIGHT')
   remote=await panel.existing_usernames([iid])
   if name.casefold() in remote: raise ValueError('شناسه تست از قبل در پنل وجود دارد.')
  except Exception as e:
   return await c.message.answer('آماده‌سازی اکانت تست ناموفق بود: '+escape(str(e)[:300]))
  if not await claim_test(cfg.database_path,c.from_user.id):
   return await c.message.answer('شما قبلاً یک بار حساب تست دریافت کرده‌اید؛ تست مجدد امکان‌پذیر نیست.')
  try:
   made=await create_panel_account(panel,cfg,'vless',iid,name,c.from_user.id,1,0,True,inbound_obj=inbound_obj)
   conn=render_connection(cfg,'vless',inbound_obj,name,made['credential'])
   vals=(c.from_user.id,name,'vless',iid,made['identity'],box.enc(made['credential']),made['email'],1,made['expiry_ms'],'active',None)
   async with connect(cfg.database_path) as db:
    cur=await db.execute('INSERT INTO accounts(telegram_id,username,protocol,inbound_id,panel_identity,credential_enc,email,volume_gb,expiry_ms,status,order_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)',vals)
    await db.commit(); aid=cur.lastrowid
   await set_test_account(cfg.database_path,c.from_user.id,aid)
   await c.message.answer('اکانت تست ۱ گیگابایت / ۲۴ ساعت:\n'+escape(conn))
  except Exception as e:
   logging.exception('trial provisioning failed for telegram user %s',c.from_user.id)
   await c.message.answer('سهمیه تست رزرو شد اما ساخت یا ثبت حساب کامل نشد. مدیر باید پنل و وضعیت حساب را بررسی کند: '+escape(str(e)[:250]))
 @dp.callback_query(F.data=='account')
 async def account(c:CallbackQuery):
  await c.answer(); rows=await user_accounts(cfg.database_path,c.from_user.id)
  if not rows: return await c.message.answer('هنوز حسابی ندارید.')
  for a in rows:
   cred=box.dec(a['credential_enc']); exp='بدون انقضا' if not a['expiry_ms'] else __import__('datetime').datetime.fromtimestamp(a['expiry_ms']/1000).strftime('%Y-%m-%d %H:%M')
   usage='\\nمصرف: نامشخص'
   try:
    tr=await panel.get_client_traffic(a['panel_identity'])
    up=int(tr.get('up') or 0); down=int(tr.get('down') or 0)
    usage=f"\\nمصرف: {(up+down)/1024**3:.2f} GB"
    if a['volume_gb']: usage+=f" از {a['volume_gb']} GB"
   except Exception as e: logging.warning('traffic lookup failed for account %s: %s',a['id'],e)
   buttons=[]
   if a['status']=='active': buttons.append([('🔄 تمدید سرویس',f'renew:{a["id"]}')])
   if a['protocol']=='openvpn': buttons.append([('📥 دریافت مجدد فایل OpenVPN',f'getovpn:{a["id"]}')])
   await c.message.answer(f"{a['protocol'].upper()} | {a['username']}\\nحجم: {'نامحدود' if a['volume_gb']==0 else str(a['volume_gb'])+' GB'}{usage}\\nانقضا: {exp}\\nوضعیت: {a['status']}\\nرمز/شناسه: <code>{escape(cred)}</code>",
     reply_markup=kb(buttons) if buttons else None)
 @dp.callback_query(F.data.startswith('getovpn:'))
 async def get_openvpn_profile(c:CallbackQuery):
  await c.answer()
  try: aid=int(c.data.split(':',1)[1])
  except Exception: return await c.message.answer('شناسه حساب نامعتبر است.')
  async with connect(cfg.database_path) as db:
   a=await (await db.execute("SELECT * FROM accounts WHERE id=? AND telegram_id=? AND protocol='openvpn' AND status='active'",(aid,c.from_user.id))).fetchone()
  if not a: return await c.message.answer('حساب OpenVPN فعال پیدا نشد.')
  try:
   profile=await panel.download_openvpn_profile(a['inbound_id'],a['transport'])
   await bot.send_document(c.from_user.id,BufferedInputFile(profile,filename=f"{a['username']}-{a['transport']}.ovpn"),caption=f"OpenVPN {a['transport'].upper()}\nنام کاربری: <code>{escape(a['username'])}</code>\nرمز عبور: <code>{escape(box.dec(a['credential_enc']))}</code>")
  except Exception as e:
   logging.exception('OpenVPN profile resend failed for account %s',aid)
   await c.message.answer('دریافت فایل از پنل ناموفق بود: '+escape(str(e)[:250]))

 @dp.callback_query(F.data.startswith('renew:'))
 async def renew_start(c:CallbackQuery):
  await c.answer()
  try: aid=int(c.data.split(':',1)[1])
  except Exception: return await c.message.answer('شناسه حساب نامعتبر است.')
  async with connect(cfg.database_path) as db:
   a=await (await db.execute("SELECT * FROM accounts WHERE id=? AND telegram_id=? AND status='active'",(aid,c.from_user.id))).fetchone()
  if not a: return await c.message.answer('حساب فعال پیدا نشد.')
  ps=[p for p in await plans(cfg.database_path) if p['protocol']==a['protocol'] and (not p['inbound_id'] or int(p['inbound_id'])==int(a['inbound_id']))]
  if not ps: return await c.message.answer('پلن تمدید برای این پروتکل تعریف نشده است.')
  buttons=[]
  for p in ps:
   vol='نامحدود' if p['volume_gb']==0 else f"{p['volume_gb']} GB"
   buttons.append([(f"{vol} | {p['months']} ماه | {p['price']:,} تومان",f"renewplan:{aid}:{p['code']}")])
  await c.message.answer('پلن تمدید را انتخاب کنید:',reply_markup=kb(buttons))

 @dp.callback_query(F.data.startswith('renewplan:'))
 async def renew_plan(c:CallbackQuery,state):
  await c.answer()
  try:
   _,aid,code=c.data.split(':',2); oid,plan=await add_renewal_order(cfg.database_path,c.from_user.id,int(aid),code)
  except Exception as e: return await c.message.answer('ثبت سفارش تمدید ناموفق بود: '+escape(str(e)[:250]))
  await state.update_data(order_id=oid); await state.set_state(Flow.receipt)
  card_number=await get_setting(cfg.database_path,'card_number',cfg.card_number); cardholder=await get_setting(cfg.database_path,'cardholder_name',cfg.cardholder_name); paytext=await get_setting(cfg.database_path,'payment_instructions',cfg.payment_instructions)
  card=(f'\\nشماره کارت: <code>{escape(card_number)}</code>\\nبه نام: {escape(cardholder)}' if card_number else '\\nاطلاعات کارت هنوز توسط مدیر تنظیم نشده است.')
  await c.message.answer(f'سفارش تمدید #{oid} ثبت شد.\\nحجم پلن: {plan["volume_gb"]} GB | مدت: {plan["months"]} ماه\\nمبلغ: <b>{plan["price"]:,} تومان</b>{card}\\n{escape(paytext)}\\nپس از واریز تصویر رسید را ارسال کنید.')

 @dp.callback_query(F.data=='myorders')
 async def myorders(c:CallbackQuery):
  await c.answer(); rows=await recent_orders(cfg.database_path,c.from_user.id)
  await c.message.answer('\n'.join(f"#{x['id']} | {x['amount']:,} تومان | {x['status']}" for x in rows) or 'سفارشی ثبت نشده است.')
 @dp.callback_query(F.data=='support')
 async def support(c:CallbackQuery,state): await c.answer(); await state.set_state(Flow.support); await c.message.answer('پیام خود را ارسال کنید؛ برای خروج /cancel')
 @dp.message(Flow.support)
 async def support_msg(m:Message,state):
  if m.text=='/cancel': await state.clear(); return await m.answer('لغو شد.')
  await save_support(cfg.database_path,m.from_user.id,m.text or '[non-text message]'); await state.clear()
  for aid in cfg.admin_ids:
   try: await bot.send_message(aid,f'پشتیبانی از {m.from_user.id}:\n{escape(m.text or "پیام غیرمتنی")}',reply_markup=kb([[('پاسخ به کاربر',f'supportreply:{m.from_user.id}')]]))
   except Exception: pass
  await m.answer('پیام شما برای پشتیبانی ارسال شد.')
 @dp.callback_query(F.data.startswith('supportreply:'))
 async def support_reply_start(c:CallbackQuery,state):
  if not admin(c.from_user.id): return await c.answer('دسترسی ندارید.',show_alert=True)
  try: target=int(c.data.split(':',1)[1])
  except Exception: return await c.answer('شناسه کاربر نامعتبر است.',show_alert=True)
  await state.update_data(support_target=target)
  await state.set_state(Flow.support_reply)
  await c.answer()
  await c.message.answer(f'پاسخ برای کاربر {target} را ارسال کنید. /cancel برای لغو')

 @dp.message(Flow.support_reply)
 async def support_reply_send(m:Message,state):
  if not admin(m.from_user.id): await state.clear(); return
  if (m.text or '').strip()=='/cancel': await state.clear(); return await m.answer('پاسخ لغو شد.')
  data=await state.get_data(); target=data.get('support_target')
  if not target: await state.clear(); return await m.answer('کاربر مقصد مشخص نیست.')
  try:
   await bot.send_message(int(target),'پاسخ پشتیبانی:\\n'+escape(m.text or '[پیام غیرمتنی]'))
   await m.answer('پاسخ برای کاربر ارسال شد.')
  except Exception as e: await m.answer('ارسال پاسخ ناموفق بود: '+escape(str(e)[:200]))
  await state.clear()

 # Graphical admin panel
 def admin_home_kb():
  return kb([[('🧩 مدیریت سرویس‌ها','admin:services'),('📦 مدیریت پلن‌های ثابت','admin:plans')],
  [('🌐 مشاهده Inboundهای پنل','admin:inbounds'),('🧪 Inbound اکانت تست','admin:trialinbound')],[('💬 متن خوش‌آمدگویی','admin:welcome')],[('💳 تنظیمات پرداخت','admin:payment')],[('📋 سفارش‌های در انتظار','admin:orders'),('👥 کاربران','admin:users')],[('🧾 مدیریت حساب‌های VPN','admin:accounts')],[('📊 گزارش فروش','admin:stats'),('💾 پشتیبان دیتابیس','admin:backup')],[('📢 پیام همگانی','admin:broadcast')]])
 @dp.callback_query(F.data.startswith('admin:'))
 async def admin_menu(c:CallbackQuery,state):
  if not admin(c.from_user.id): return await c.answer('دسترسی ندارید.',show_alert=True)
  await c.answer(); action=c.data.split(':',1)[1]
  if action=='accounts':
   rows=await all_accounts(cfg.database_path); buttons=[]
   for a in rows:
    buttons.append([(f"{a['username']} | {a['protocol'].upper()} | {a['status']}",f"admin:acc:{a['id']}")])
   buttons.append([('⬅️ بازگشت','admin:home')])
   return await c.message.answer('مدیریت حساب‌های VPN:',reply_markup=kb(buttons))
  if action.startswith('acc:'):
   try: aid=int(action.split(':',1)[1])
   except Exception: return await c.message.answer('شناسه حساب نامعتبر است.')
   async with connect(cfg.database_path) as db:
    a=await (await db.execute('SELECT * FROM accounts WHERE id=?',(aid,))).fetchone()
   if not a: return await c.message.answer('حساب پیدا نشد.')
   buttons=[]
   if a['status']!='deleted':
    buttons.append([('⛔ غیرفعال‌سازی' if a['status']=='active' else '🟢 فعال‌سازی',f"admin:acctoggle:{aid}")])
    buttons.append([('🗑 حذف از پنل VPN',f"admin:accdelete:{aid}")])
   return await c.message.answer(f"حساب {a['username']} | {a['protocol'].upper()}\\nکاربر: {a['telegram_id']}\\nوضعیت: {a['status']}\\nInbound: {a['inbound_id']}",reply_markup=kb(buttons+[[('⬅️ بازگشت','admin:accounts')]]))
  if action.startswith('accdelete:'):
   try: aid=int(action.split(':',1)[1])
   except Exception: return await c.message.answer('شناسه حساب نامعتبر است.')
   return await c.message.answer('حذف حساب از پنل VPN قطعی است. ادامه می‌دهید؟',reply_markup=kb([[('بله، حذف شود',f'admin:accdeleteconfirm:{aid}'),('انصراف',f'admin:acc:{aid}')]]))
  if action.startswith('acctoggle:') or action.startswith('accdeleteconfirm:'):
   try: aid=int(action.split(':',1)[1])
   except Exception: return await c.message.answer('شناسه حساب نامعتبر است.')
   async with connect(cfg.database_path) as db:
    a=await (await db.execute('SELECT * FROM accounts WHERE id=?',(aid,))).fetchone()
   if not a: return await c.message.answer('حساب پیدا نشد.')
   try:
    if cfg.dry_run: raise VPNUIError('DRY_RUN فعال است؛ تغییر واقعی حساب انجام نشد.')
    if action.startswith('acctoggle:'):
     inbound_obj=await panel.get_inbound(a['inbound_id'])
     settings=inbound_obj.get('settings',{})
     if isinstance(settings,str): settings=__import__('json').loads(settings)
     clients=settings.get('clients',[])
     match=next((x for x in clients if str(x.get('id') if a['protocol']=='vless' else x.get('password'))==str(a['panel_identity'])),None)
     if match is None: raise VPNUIError('حساب در پنل پیدا نشد.')
     enabled=a['status']!='active'; match['enable']=enabled
     await panel.update_client(a['inbound_id'],a['panel_identity'],match)
     new_status='active' if enabled else 'disabled'
    else:
     await panel.delete_client(a['inbound_id'],a['panel_identity'])
     new_status='deleted'
    async with connect(cfg.database_path) as db:
     await db.execute('UPDATE accounts SET status=? WHERE id=?',(new_status,aid)); await db.commit()
    return await c.message.answer('وضعیت حساب در پنل و دیتابیس به‌روزرسانی شد.',reply_markup=kb([[('بازگشت به حساب','admin:acc:'+str(aid))],[('مدیریت حساب‌ها','admin:accounts')]]))
   except Exception as e:
    logging.exception('account management operation failed')
    return await c.message.answer('عملیات حساب ناموفق بود: '+escape(str(e)[:300]))
  if action=='home': return await c.message.answer('⚙️ پنل مدیریت ربات',reply_markup=admin_home_kb())
  if action=='inbounds':
   try:
    entries=await panel.list_inbounds()
    if not entries: return await c.message.answer('در پنل هیچ Inboundای پیدا نشد.')
    lines=[]
    for x in entries:
     proto=str(x.get('protocol') or 'نامشخص').lower(); iid=x.get('id'); port=x.get('port','-'); name=x.get('remark') or x.get('tag') or 'بدون نام'; enabled='فعال' if x.get('enable') else 'غیرفعال'
     support='قابل فروش خودکار' if proto in ('vless','l2tp','openvpn') else 'فقط نمایش؛ ساخت حساب هنوز پیاده‌سازی نشده'
     lines.append(f"#{iid} | {escape(str(name))} | {proto.upper()} | پورت {port} | {enabled}\n{support}")
    chunks=[]; current='Inboundهای موجود در پنل:\n\n'
    for line in lines:
     addition=line+'\n\n'
     if len(current)+len(addition)>3500 and current.strip():
      chunks.append(current); current=''
     current+=addition
    if current.strip(): chunks.append(current)
    if not chunks: chunks=['در پنل هیچ Inboundای پیدا نشد.']
    for chunk in chunks[:-1]: await c.message.answer(chunk)
    return await c.message.answer(chunks[-1],reply_markup=kb([[('➕ ساخت سرویس برای Inbound','admin:svcadd')],[('⬅️ بازگشت','admin:home')]]))
   except Exception as e: return await c.message.answer('دریافت Inboundها ناموفق بود: '+escape(str(e)[:300]))
  if action=='trialinbound':
   try: entries=await panel.list_inbounds()
   except Exception as e: return await c.message.answer('دریافت Inboundها ناموفق بود: '+escape(str(e)[:250]))
   buttons=[]
   for entry in entries:
    if str(entry.get('protocol') or '').lower()=='vless' and entry.get('enable'):
     buttons.append([(f"#{entry.get('id')} VLESS:{entry.get('port','-')}",f"admin:trialinboundset:{entry.get('id')}")])
   buttons.append([('⬅️ بازگشت','admin:home')])
   if len(buttons)==1: return await c.message.answer('Inbound فعال VLESS پیدا نشد.',reply_markup=kb(buttons))
   return await c.message.answer('Inbound مخصوص اکانت تست را انتخاب کنید:',reply_markup=kb(buttons))
  if action.startswith('trialinboundset:'):
   try:
    iid=int(action.split(':',1)[1]); obj=await panel.get_inbound(iid)
    if not obj.get('enable') or str(obj.get('protocol','')).lower()!='vless': raise ValueError('Inbound انتخابی فعال یا VLESS نیست.')
    await set_setting(cfg.database_path,'trial_vless_inbound',str(iid))
    return await c.message.answer(f'Inbound تست روی #{iid} ذخیره شد.',reply_markup=kb([[('⚙️ منوی مدیریت','admin:home')]]))
   except Exception as e: return await c.message.answer('ذخیره Inbound تست ناموفق بود: '+escape(str(e)[:250]))
  if action=='welcome':
   current=await get_setting(cfg.database_path,'welcome_message','سلام به فروشگاه ما خوش آمدید 🌹\n\nلطفاً پلن و حجم مورد نظر خود را انتخاب کنید.\n\nحداکثر ۱۰ دقیقه بعد از ارسال رسید، اکانت شما تحویل داده می‌شود. ✅')
   await state.set_state(Flow.welcome_text); return await c.message.answer('متن جدید خوش‌آمدگویی را ارسال کنید. برای لغو /cancel را بفرستید.\n\nمتن فعلی:\n'+escape(current))
  if action=='services':
   rows=await dynamic_services(cfg.database_path,False); buttons=[]
   for x in rows: buttons.append([(f"{'🟢' if x['enabled'] else '🔴'} {x['protocol'].upper()}{(' '+x['transport'].upper()) if x['protocol']=='openvpn' else ''} / Inbound #{x['inbound_id']} | {x['months']} ماه | {x['rate']:,} تومان/گیگ",f"admin:svc:{x['code']}")])
   buttons.append([('➕ افزودن سرویس','admin:svcadd'),('⬅️ بازگشت','admin:home')])
   return await c.message.answer('مدیریت سرویس‌های قیمت‌گذاری حجمی:',reply_markup=kb(buttons))
  if action=='svcadd':
   try: entries=await panel.list_inbounds()
   except Exception as e: return await c.message.answer('دریافت Inboundها ناموفق بود: '+escape(str(e)[:250]))
   buttons=[]
   for x in entries:
    proto=str(x.get('protocol') or '').lower()
    if proto in ('vless','l2tp','openvpn') and x.get('enable'):
     label=f"#{x.get('id')} {str(x.get('remark') or proto).strip()[:18]} | {proto.upper()}:{x.get('port','-')}"
     buttons.append([(label,f"admin:svcproto:{x.get('id')}:{proto}")])
   buttons.append([('لغو','admin:services')])
   return await c.message.answer('Inbound فعال موردنظر را انتخاب کنید. برای OpenVPN مدیر نوع TCP یا UDP را در مرحله بعد تعیین می‌کند.',reply_markup=kb(buttons))
  if action.startswith('svcproto:'):
   parts=action.split(':');
   if len(parts)!=3: return await c.message.answer('Inbound انتخابی نامعتبر است.')
   iid=int(parts[1]); proto=parts[2]
   try:
    obj=await panel.get_inbound(iid)
    if str(obj.get('protocol','')).lower()!=proto or not obj.get('enable'): raise ValueError('Inbound غیرفعال است یا پروتکل آن تغییر کرده است.')
   except Exception as e: return await c.message.answer('Inbound معتبر نیست: '+escape(str(e)[:250]))
   newsvc={'protocol':proto,'inbound_id':iid,'transport':'udp'}
   if proto=='openvpn':
    await state.update_data(newsvc=newsvc)
    return await c.message.answer('نوع اتصال این پلن را مدیر انتخاب می‌کند:',reply_markup=kb([[('OpenVPN UDP','admin:svctransport:udp'),('OpenVPN TCP','admin:svctransport:tcp')],[('لغو','admin:services')]]))
   await state.update_data(newsvc=newsvc); await state.set_state(Flow.svc_months); return await c.message.answer(f'Inbound #{iid} ({proto.upper()}) انتخاب شد. مدت اعتبار چند ماه باشد؟')
  if action.startswith('svctransport:'):
   transport=action.split(':',1)[1]
   if transport not in ('tcp','udp'): return await c.message.answer('نوع اتصال نامعتبر است.')
   data=await state.get_data(); x=data.get('newsvc')
   if not x or x.get('protocol')!='openvpn': return await c.message.answer('فرایند ساخت سرویس منقضی شده است.')
   x['transport']=transport; await state.update_data(newsvc=x); await state.set_state(Flow.svc_months)
   return await c.message.answer(f'OpenVPN {transport.upper()} انتخاب شد. مدت اعتبار چند ماه باشد؟')
  if action.startswith('svc:'):
   code=action.split(':',1)[1]; rows=await dynamic_services(cfg.database_path,False); x=next((z for z in rows if z['code']==code),None)
   if not x: return await c.message.answer('سرویس پیدا نشد.')
   return await c.message.answer(f"{x['protocol'].upper()} {x['transport'].upper() if x['protocol']=='openvpn' else ''} | Inbound #{x['inbound_id']} | {x['months']} ماه\nقیمت هر گیگ در ماه: {x['rate']:,}\nمحدوده حجم: {x['min_gb']} تا {x['max_gb']} گیگ\nوضعیت: {'فعال' if x['enabled'] else 'غیرفعال'}",reply_markup=kb([[('🌐 تغییر Inbound','admin:svcedit:inbound:'+code),('📅 تغییر مدت','admin:svcedit:months:'+code)],[('🔀 تغییر TCP/UDP','admin:svcedit:transport:'+code)],[('💵 تغییر قیمت هر گیگ','admin:svcedit:rate:'+code)],[('⬇️ حداقل حجم','admin:svcedit:min_gb:'+code),('⬆️ حداکثر حجم','admin:svcedit:max_gb:'+code)],[(('🔴 غیرفعال' if x['enabled'] else '🟢 فعال'),'admin:svctoggle:'+code)],[('🗑 حذف سرویس','admin:svcdel:'+code)],[('⬅️ بازگشت','admin:services')]]))
  if action.startswith('svcrate:'):
   code=action.split(':',1)[1]; await state.update_data(edit_service=code); await state.set_state(Flow.svc_rate); return await c.message.answer('قیمت جدید هر گیگابایت برای هر ماه را به تومان وارد کنید:')
  if action.startswith('svcedit:'):
   parts=action.split(':',2)
   if len(parts)!=3: return await c.message.answer('درخواست ویرایش نامعتبر است.')
   field,code=parts[1],parts[2]
   rows=await dynamic_services(cfg.database_path,False)
   x=next((z for z in rows if z['code']==code),None)
   if not x: return await c.message.answer('سرویس پیدا نشد.')
   if field=='inbound':
    try: entries=await panel.list_inbounds()
    except Exception as e: return await c.message.answer('دریافت Inboundها ناموفق بود: '+escape(str(e)[:250]))
    buttons=[]
    for entry in entries:
     proto=str(entry.get('protocol') or '').lower()
     if proto in ('vless','l2tp','openvpn') and entry.get('enable'):
      buttons.append([(f"#{entry.get('id')} {proto.upper()}:{entry.get('port','-')}",f"admin:svcsetinbound:{code}:{entry.get('id')}:{proto}")])
    buttons.append([('لغو','admin:svc:'+code)])
    return await c.message.answer('Inbound جدید را انتخاب کنید:',reply_markup=kb(buttons))
   if field=='transport':
    if x['protocol']!='openvpn': return await c.message.answer('این گزینه فقط برای سرویس OpenVPN است.')
    return await c.message.answer('نوع اتصال جدید را انتخاب کنید:',reply_markup=kb([[('UDP','admin:svcsettransport:'+code+':udp'),('TCP','admin:svcsettransport:'+code+':tcp')],[('لغو','admin:svc:'+code)]]))
   states={'months':Flow.svc_edit_months,'rate':Flow.svc_edit_rate,'min_gb':Flow.svc_edit_min,'max_gb':Flow.svc_edit_max}
   if field not in states: return await c.message.answer('فیلد ویرایش نامعتبر است.')
   await state.clear()
   await state.update_data(edit_service=code,edit_field=field)
   await state.set_state(states[field])
   prompts={'months':'مدت جدید را بین ۱ تا ۳۶ ماه وارد کنید:','rate':'قیمت جدید هر گیگ در هر ماه را به تومان وارد کنید:','min_gb':'حداقل حجم جدید را بین ۱ تا ۱۰۰۰ گیگ وارد کنید:','max_gb':'حداکثر حجم جدید را بین ۱ تا ۱۰۰۰ گیگ وارد کنید:'}
   return await c.message.answer(prompts[field])
  if action.startswith('svcsetinbound:'):
   parts=action.split(':')
   if len(parts)!=4: return await c.message.answer('درخواست تغییر Inbound نامعتبر است.')
   code,iid_raw,proto=parts[1],parts[2],parts[3]
   try:
    iid=int(iid_raw); obj=await panel.get_inbound(iid)
    if not obj.get('enable') or str(obj.get('protocol','')).lower()!=proto: raise ValueError('Inbound انتخابی فعال نیست یا نوع آن تغییر کرده است.')
    await update_dynamic_service(cfg.database_path,code,'protocol',proto)
    await update_dynamic_service(cfg.database_path,code,'inbound_id',iid)
    return await c.message.answer(f'Inbound سرویس به #{iid} تغییر کرد.',reply_markup=kb([[('بازگشت به سرویس','admin:svc:'+code)],[('مدیریت سرویس‌ها','admin:services')]]))
   except Exception as e: return await c.message.answer('تغییر Inbound انجام نشد: '+escape(str(e)[:250]))
  if action.startswith('svcsettransport:'):
   parts=action.split(':')
   if len(parts)!=3 or parts[2] not in ('tcp','udp'): return await c.message.answer('درخواست نوع اتصال نامعتبر است.')
   code,transport=parts[1],parts[2]
   n=await update_dynamic_service(cfg.database_path,code,'transport',transport)
   return await c.message.answer('نوع اتصال سرویس ذخیره شد.' if n else 'سرویس پیدا نشد.',reply_markup=kb([[('بازگشت به سرویس','admin:svc:'+code)],[('مدیریت سرویس‌ها','admin:services')]]))
  if action.startswith('svctoggle:'):
   code=action.split(':',1)[1]; rows=await dynamic_services(cfg.database_path,False); x=next((z for z in rows if z['code']==code),None)
   if not x: return await c.message.answer('سرویس پیدا نشد.',reply_markup=kb([[('مدیریت سرویس‌ها','admin:services')]]))
   n=await update_dynamic_service(cfg.database_path,code,'enabled',0 if x['enabled'] else 1)
   return await c.message.answer('وضعیت سرویس تغییر کرد.' if n else 'تغییر وضعیت انجام نشد.',reply_markup=kb([[('مدیریت سرویس‌ها','admin:services')]]))
  if action.startswith('svcdel:'):
   code=action.split(':',1)[1]
   return await c.message.answer('حذف این سرویس تأیید شود؟',reply_markup=kb([[('تأیید حذف','admin:svcdelconfirm:'+code),('انصراف','admin:svcdelcancel:'+code)]]))
  if action.startswith('svcdelcancel:'):
   code=action.split(':',1)[1]
   return await c.message.answer('حذف لغو شد.',reply_markup=kb([[('بازگشت به سرویس','admin:svc:'+code)],[('مدیریت سرویس‌ها','admin:services')]]))
  if action.startswith('svcdelconfirm:'):
   code=action.split(':',1)[1]; n=await delete_dynamic_service(cfg.database_path,code)
   return await c.message.answer('سرویس غیرفعال شد؛ سوابق آن حفظ شدند.' if n else 'سرویس پیدا نشد.',reply_markup=kb([[('مدیریت سرویس‌ها','admin:services')]]))
  if action=='plans':
   rows=await all_plans(cfg.database_path); buttons=[]
   for p in rows:
    status='🟢' if p['enabled'] else '🔴'; buttons.append([(f"{status} {p['code']} | {p['price']:,} تومان",f"admin:plan:{p['code']}")])
   buttons.append([('➕ افزودن پلن ثابت','admin:staticadd')]); buttons.append([('⬅️ بازگشت','admin:home')])
   return await c.message.answer('مدیریت پلن‌ها (برای ویرایش هر پلن انتخاب کنید):',reply_markup=kb(buttons))
  if action=='staticadd':
   await state.clear()
   try: entries=await panel.list_inbounds()
   except Exception as e: return await c.message.answer('دریافت Inboundها ناموفق بود: '+escape(str(e)[:250]))
   buttons=[]
   for entry in entries:
    proto=str(entry.get('protocol') or '').lower()
    if proto in ('vless','l2tp','openvpn') and entry.get('enable'):
     buttons.append([(f"#{entry.get('id')} {proto.upper()}:{entry.get('port','-')}",f"admin:staticproto:{entry.get('id')}:{proto}")])
   buttons.append([('لغو','admin:plans')])
   return await c.message.answer('Inbound پلن ثابت را انتخاب کنید:',reply_markup=kb(buttons))
  if action.startswith('staticproto:'):
   parts=action.split(':')
   if len(parts)!=3: return await c.message.answer('Inbound پلن نامعتبر است.')
   iid=int(parts[1]); proto=parts[2]
   try:
    obj=await panel.get_inbound(iid)
    if not obj.get('enable') or str(obj.get('protocol','')).lower()!=proto: raise ValueError('Inbound غیرفعال یا نامعتبر است.')
   except Exception as e: return await c.message.answer('Inbound پلن معتبر نیست: '+escape(str(e)[:250]))
   await state.clear()
   static_plan={'protocol':proto,'inbound_id':iid,'transport':'udp'}
   await state.update_data(static_plan=static_plan)
   if proto=='openvpn':
    return await c.message.answer('نوع اتصال این پلن را مدیر انتخاب می‌کند:',reply_markup=kb([[('OpenVPN UDP','admin:statictransport:udp'),('OpenVPN TCP','admin:statictransport:tcp')],[('لغو','admin:plans')]]))
   await state.set_state(Flow.static_plan_volume)
   return await c.message.answer(f'Inbound #{iid} انتخاب شد. حجم پلن را به گیگابایت وارد کنید؛ برای نامحدود عدد ۰ را بفرستید (حداکثر ۱۰۰۰):')
  if action.startswith('statictransport:'):
   transport=action.split(':',1)[1]
   if transport not in ('tcp','udp'): return await c.message.answer('نوع اتصال نامعتبر است.')
   data=await state.get_data(); x=data.get('static_plan')
   if not x or x.get('protocol')!='openvpn': return await c.message.answer('فرایند ساخت پلن منقضی شده است.')
   x['transport']=transport; await state.update_data(static_plan=x); await state.set_state(Flow.static_plan_volume)
   return await c.message.answer(f'OpenVPN {transport.upper()} انتخاب شد. حجم پلن را به گیگابایت وارد کنید؛ برای نامحدود عدد ۰ را بفرستید:')
  if action.startswith('planinbound:'):
   code=action.split(':',1)[1]
   try: entries=await panel.list_inbounds()
   except Exception as e: return await c.message.answer('دریافت Inboundها ناموفق بود: '+escape(str(e)[:250]))
   buttons=[]
   for entry in entries:
    proto=str(entry.get('protocol') or '').lower()
    if proto in ('vless','l2tp','openvpn') and entry.get('enable'):
     buttons.append([(f"#{entry.get('id')} {proto.upper()}:{entry.get('port','-')}",f"admin:plansetinbound:{code}:{entry.get('id')}:{proto}")])
   buttons.append([('لغو','admin:plan:'+code)])
   return await c.message.answer('Inbound جدید پلن را انتخاب کنید:',reply_markup=kb(buttons))
  if action.startswith('plansetinbound:'):
   parts=action.split(':')
   if len(parts)!=4: return await c.message.answer('درخواست تغییر Inbound نامعتبر است.')
   code,iid_raw,proto=parts[1],parts[2],parts[3]
   try:
    iid=int(iid_raw); obj=await panel.get_inbound(iid)
    if not obj.get('enable') or str(obj.get('protocol','')).lower()!=proto: raise ValueError('Inbound انتخابی فعال یا معتبر نیست.')
    async with connect(cfg.database_path) as db:
     cur=await db.execute('UPDATE plans SET protocol=?,inbound_id=? WHERE code=?',(proto,iid,code)); await db.commit()
    if not cur.rowcount: raise ValueError('پلن پیدا نشد.')
    return await c.message.answer(f'Inbound پلن به #{iid} تغییر کرد.',reply_markup=kb([[('بازگشت به پلن','admin:plan:'+code)],[('مدیریت پلن‌ها','admin:plans')]]))
   except Exception as e: return await c.message.answer('تغییر Inbound انجام نشد: '+escape(str(e)[:250]))
  if action.startswith('plantransport:'):
   code=action.split(':',1)[1]; rows=await all_plans(cfg.database_path); p=next((z for z in rows if z['code']==code),None)
   if not p: return await c.message.answer('پلن پیدا نشد.')
   if p['protocol']!='openvpn': return await c.message.answer('این گزینه فقط برای پلن OpenVPN است.')
   return await c.message.answer('نوع اتصال پلن را انتخاب کنید:',reply_markup=kb([[('UDP',f'admin:plansettransport:{code}:udp'),('TCP',f'admin:plansettransport:{code}:tcp')],[('لغو','admin:plan:'+code)]]))
  if action.startswith('plansettransport:'):
   parts=action.split(':')
   if len(parts)!=3 or parts[2] not in ('tcp','udp'): return await c.message.answer('درخواست نامعتبر است.')
   code,transport=parts[1],parts[2]
   async with connect(cfg.database_path) as db:
    cur=await db.execute('UPDATE plans SET transport=? WHERE code=?',(transport,code)); await db.commit()
   return await c.message.answer('نوع اتصال پلن ذخیره شد.' if cur.rowcount else 'پلن پیدا نشد.',reply_markup=kb([[('بازگشت به پلن','admin:plan:'+code)],[('مدیریت پلن‌ها','admin:plans')]]))
  if action=='payment':
   n=await get_setting(cfg.database_path,'card_number',cfg.card_number); h=await get_setting(cfg.database_path,'cardholder_name',cfg.cardholder_name); t=await get_setting(cfg.database_path,'payment_instructions',cfg.payment_instructions)
   return await c.message.answer(f"شماره کارت: <code>{escape(n)}</code>\nصاحب کارت: {escape(h)}\nمتن پرداخت: {escape(t)}",reply_markup=kb([[('✏️ تغییر شماره کارت','admin:setcardnum')],[('✏️ تغییر صاحب کارت','admin:setcardholder')],[('✏️ تغییر متن پرداخت','admin:setpaytext')],[('⬅️ بازگشت','admin:home')]]))
  if action=='setcardnum': await state.set_state(Flow.card_number); return await c.message.answer('شماره کارت جدید را ارسال کنید:')
  if action=='setcardholder': await state.set_state(Flow.cardholder); return await c.message.answer('نام صاحب کارت را ارسال کنید:')
  if action=='setpaytext': await state.set_state(Flow.payment_text); return await c.message.answer('متن راهنمای پرداخت را ارسال کنید:')
  if action=='orders':
   rows=await orders_review(cfg.database_path)
   if not rows: return await c.message.answer('سفارش در انتظار بررسی وجود ندارد.')
   for o in rows:
    text=f"سفارش #{o['id']}\nکاربر: {o['telegram_id']}\nنام: {o['username']}\nمبلغ: {o['amount']:,} تومان"
    if o['status']=='provisioning_unknown':
     text += "\n⚠️ وضعیت ساخت در پنل نامشخص است؛ برای جلوگیری از حساب تکراری، تأیید مجدد غیرفعال است. ابتدا پنل را بررسی کنید."
     markup=None
    else:
     markup=kb([[('✅ تأیید','approve:'+str(o['id'])),('❌ رد','reject:'+str(o['id']))]])
    await c.message.answer(text,reply_markup=markup)
    if o['receipt_file_id']:
     try: await bot.send_photo(c.from_user.id,o['receipt_file_id'])
     except Exception: pass
   return
  if action=='users':
   rows=await recent_users(cfg.database_path); return await c.message.answer('\n'.join(f"{r['telegram_id']} @{r['username'] or '-'} | حساب‌ها: {r['account_count']}" for r in rows) or 'کاربری نیست')
  if action=='stats':
   u,a,s,o=await stats(cfg.database_path); return await c.message.answer(f'کاربران: {u}\nحساب فعال: {a}\nفروش تأییدشده: {s:,} تومان\nکل سفارش‌ها: {o}')
  if action=='backup':
   from datetime import datetime
   dest=cfg.database_path+'.backup-'+datetime.now().strftime('%Y%m%d-%H%M%S'); shutil.copy2(cfg.database_path,dest)
   return await c.message.answer_document(__import__('aiogram').types.FSInputFile(dest),caption='نسخه پشتیبان دیتابیس')
  if action=='broadcast': await state.set_state(Flow.broadcast); return await c.message.answer('متن پیام همگانی را بفرستید:')
  if action.startswith('plan:'):
   code=action[5:]; rows=await all_plans(cfg.database_path); p=next((x for x in rows if x['code']==code),None)
   if not p: return await c.message.answer('پلن پیدا نشد.')
   return await c.message.answer(f"پلن {code}\nInbound: #{p['inbound_id']}\nنوع اتصال: {p['transport'].upper() if p['protocol']=='openvpn' else '-'}\nقیمت: {p['price']:,}\nحجم: {p['volume_gb']}GB\nمدت: {p['months']} ماه\nوضعیت: {'فعال' if p['enabled'] else 'غیرفعال'}",reply_markup=kb([[('🌐 تغییر Inbound',f'admin:planinbound:{code}')],[('🔀 تغییر TCP/UDP',f'admin:plantransport:{code}')],[('💵 تغییر قیمت',f'admin:price:{code}'),(('🔴 غیرفعال‌کردن' if p['enabled'] else '🟢 فعال‌کردن'),f'admin:toggle:{code}')],[('🗑 حذف پلن',f'admin:delete:{code}')],[('⬅️ بازگشت','admin:plans')]]))
  if action.startswith('price:'):
   code=action[6:]; await state.update_data(plan_code=code); await state.set_state(Flow.plan_price); return await c.message.answer('قیمت جدید را فقط به تومان و به‌صورت عدد ارسال کنید:')
  if action.startswith('toggle:'):
   code=action[7:]; rows=await all_plans(cfg.database_path); p=next((x for x in rows if x['code']==code),None)
   if not p: return await c.message.answer('پلن پیدا نشد.',reply_markup=kb([[('مدیریت پلن‌ها','admin:plans')]]))
   n=await set_plan_enabled(cfg.database_path,code,not bool(p['enabled']))
   return await c.message.answer('وضعیت پلن تغییر کرد.' if n else 'تغییر انجام نشد.',reply_markup=kb([[('مدیریت پلن‌ها','admin:plans')]]))
  if action.startswith('delete:'):
   code=action[7:]
   return await c.message.answer('حذف این پلن تأیید شود؟',reply_markup=kb([[('تأیید حذف','admin:deleteconfirm:'+code),('انصراف','admin:deletecancel:'+code)]]))
  if action.startswith('deletecancel:'):
   code=action[len('deletecancel:'):]
   return await c.message.answer('حذف لغو شد.',reply_markup=kb([[('بازگشت به پلن','admin:plan:'+code)],[('مدیریت پلن‌ها','admin:plans')]]))
  if action.startswith('deleteconfirm:'):
   code=action[len('deleteconfirm:'):]; n=await delete_plan(cfg.database_path,code)
   msg='پلن حذف شد.' if n else 'پلن سابقه سفارش دارد و حذف نشد.'
   return await c.message.answer(msg,reply_markup=kb([[('مدیریت پلن‌ها','admin:plans')]]))
 @dp.message(Flow.static_plan_volume)
 async def static_plan_volume(m:Message,state):
  if not admin(m.from_user.id):
   await state.clear(); return await m.answer('دسترسی ندارید.')
  t=(m.text or '').strip()
  if not t.isdigit() or not 0 <= int(t) <= 1000:
   return await m.answer('حجم باید عددی بین ۰ تا ۱۰۰۰ باشد؛ صفر یعنی نامحدود.')
  d=await state.get_data(); x=d.get('static_plan',{})
  x['volume_gb']=int(t); await state.update_data(static_plan=x)
  await state.set_state(Flow.static_plan_months)
  await m.answer('مدت اعتبار را به ماه وارد کنید (۱ تا ۳۶):')

 @dp.message(Flow.static_plan_months)
 async def static_plan_months(m:Message,state):
  if not admin(m.from_user.id):
   await state.clear(); return await m.answer('دسترسی ندارید.')
  t=(m.text or '').strip()
  if not t.isdigit() or not 1 <= int(t) <= 36:
   return await m.answer('مدت باید بین ۱ تا ۳۶ ماه باشد.')
  d=await state.get_data(); x=d.get('static_plan',{})
  x['months']=int(t); await state.update_data(static_plan=x)
  await state.set_state(Flow.static_plan_price)
  await m.answer('قیمت نهایی پلن را به تومان وارد کنید:')

 @dp.message(Flow.static_plan_price)
 async def static_plan_price(m:Message,state):
  if not admin(m.from_user.id):
   await state.clear(); return await m.answer('دسترسی ندارید.')
  t=(m.text or '').strip()
  if not t.isdigit() or not 0 <= int(t) <= 1000000000000:
   return await m.answer('قیمت باید عددی بین صفر تا یک تریلیون تومان باشد.')
  d=await state.get_data(); x=d.get('static_plan',{})
  import secrets
  code='plan'+secrets.token_hex(4)
  async with connect(cfg.database_path) as db:
   await db.execute('INSERT INTO plans(code,protocol,inbound_id,volume_gb,months,price,enabled,transport) VALUES(?,?,?,?,?,?,1,?)',(code,x['protocol'],x['inbound_id'],x['volume_gb'],x['months'],int(t),x.get('transport','udp')))
   await db.commit()
  await state.clear()
  volume='نامحدود' if x['volume_gb']==0 else f"{x['volume_gb']} گیگ"
  await m.answer(f"پلن ثابت ساخته شد.\nکد: {code}\nInbound: #{x['inbound_id']}\nپروتکل: {x['protocol'].upper()}{(' '+x.get('transport','udp').upper()) if x['protocol']=='openvpn' else ''}\nحجم: {volume}\nمدت: {x['months']} ماه\nقیمت: {int(t):,} تومان",reply_markup=kb([[('📦 مدیریت پلن‌های ثابت','admin:plans')],[('⚙️ منوی مدیریت','admin:home')]]))

 @dp.message(Flow.svc_months)
 async def svc_months(m:Message,state):
  if not admin(m.from_user.id):
   await state.clear(); return await m.answer('دسترسی ندارید.')
  t=(m.text or '').strip()
  if not t.isdigit() or int(t)<1 or int(t)>36: return await m.answer('مدت را بین ۱ تا ۳۶ ماه وارد کنید.')
  d=await state.get_data(); x=d.get('newsvc',{}); x['months']=int(t); await state.update_data(newsvc=x); await state.set_state(Flow.svc_rate); await m.answer('قیمت هر گیگابایت برای هر ماه را به تومان وارد کنید؛ مثال ۷۰۰۰:')
 @dp.message(Flow.svc_rate)
 async def svc_rate(m:Message,state):
  if not admin(m.from_user.id):
   await state.clear(); return await m.answer('دسترسی ندارید.')
  t=(m.text or '').strip()
  if not t.isdigit() or not 1 <= int(t) <= 10000000: return await m.answer('قیمت باید بین ۱ تا ۱۰ میلیون تومان باشد.')
  d=await state.get_data()
  if d.get('newsvc'):
   x=d['newsvc']; x['rate']=int(t); await state.update_data(newsvc=x); await state.set_state(Flow.svc_min); await m.answer('حداقل حجم مجاز به گیگابایت را وارد کنید؛ مثال ۱:')
  else:
   code=d.get('edit_service'); n=await update_dynamic_service(cfg.database_path,code,'rate',int(t)); await state.clear(); await m.answer('قیمت هر گیگ ذخیره شد.' if n else 'سرویس پیدا نشد.',reply_markup=kb([[('↩️ بازگشت به سرویس','admin:svc:'+code)],[('مدیریت سرویس‌ها','admin:services')]]))
 @dp.message(Flow.svc_min)
 async def svc_min(m:Message,state):
  if not admin(m.from_user.id):
   await state.clear(); return await m.answer('دسترسی ندارید.')
  t=(m.text or '').strip()
  if not t.isdigit() or not 1 <= int(t) <= 1000: return await m.answer('حداقل حجم باید بین ۱ تا ۱۰۰۰ گیگ باشد.')
  d=await state.get_data(); x=d['newsvc']; x['min_gb']=int(t); await state.update_data(newsvc=x); await state.set_state(Flow.svc_max); await m.answer('حداکثر حجم مجاز به گیگابایت را وارد کنید؛ مثال ۱۰۰۰:')
 @dp.message(Flow.svc_max)
 async def svc_max(m:Message,state):
  if not admin(m.from_user.id):
   await state.clear(); return await m.answer('دسترسی ندارید.')
  t=(m.text or '').strip()
  if not t.isdigit() or not 1 <= int(t) <= 1000: return await m.answer('حداکثر حجم باید بین ۱ تا ۱۰۰۰ گیگ باشد.')
  d=await state.get_data(); x=d['newsvc']; x['max_gb']=int(t)
  if x['max_gb']<x['min_gb']: return await m.answer('حداکثر حجم نباید کمتر از حداقل باشد.')
  import secrets
  code='svc'+secrets.token_hex(4)
  await add_dynamic_service(cfg.database_path,code,x['protocol'],x['months'],x['rate'],x['min_gb'],x['max_gb'],x.get('inbound_id',0),x.get('transport','udp')); await state.clear()
  await m.answer(f"سرویس ساخته شد.\nInbound: #{x.get('inbound_id',0)}\nپروتکل: {x['protocol'].upper()}{(' '+x.get('transport','udp').upper()) if x['protocol']=='openvpn' else ''}\nمدت: {x['months']} ماه\nهر گیگ در ماه: {x['rate']:,} تومان\nمحدوده حجم: {x['min_gb']} تا {x['max_gb']} گیگ",reply_markup=kb([[('📦 مدیریت سرویس‌ها','admin:services')],[('⚙️ منوی مدیریت','admin:home')]]))

 async def save_service_edit(m:Message,state,field):
  if not admin(m.from_user.id):
   await state.clear()
   return await m.answer('دسترسی ندارید.')
  raw=(m.text or '').strip()
  if not raw.isdigit():
   return await m.answer('لطفاً فقط عدد ارسال کنید.')
  value=int(raw)
  limits={'months':(1,36),'rate':(1,10000000),'min_gb':(1,1000),'max_gb':(1,1000)}
  low,high=limits[field]
  if not low <= value <= high:
   return await m.answer(f'مقدار باید بین {low} و {high} باشد.')
  data=await state.get_data()
  code=data.get('edit_service')
  rows=await dynamic_services(cfg.database_path,False)
  x=next((z for z in rows if z['code']==code),None)
  if not x:
   await state.clear()
   return await m.answer('سرویس پیدا نشد.')
  if field=='min_gb' and value>x['max_gb']:
   return await m.answer('حداقل حجم نمی‌تواند از حداکثر حجم بیشتر باشد.')
  if field=='max_gb' and value<x['min_gb']:
   return await m.answer('حداکثر حجم نمی‌تواند از حداقل حجم کمتر باشد.')
  n=await update_dynamic_service(cfg.database_path,code,field,value)
  await state.clear()
  if not n:
   return await m.answer('تغییر ذخیره نشد؛ سرویس پیدا نشد.')
  return await m.answer('تغییر با موفقیت ذخیره شد.',reply_markup=kb([[('↩️ بازگشت به سرویس','admin:svc:'+code)],[('مدیریت سرویس‌ها','admin:services')]]))

 @dp.message(Flow.svc_edit_months)
 async def save_edit_months(m:Message,state):
  await save_service_edit(m,state,'months')

 @dp.message(Flow.svc_edit_rate)
 async def save_edit_rate(m:Message,state):
  await save_service_edit(m,state,'rate')

 @dp.message(Flow.svc_edit_min)
 async def save_edit_min(m:Message,state):
  await save_service_edit(m,state,'min_gb')

 @dp.message(Flow.svc_edit_max)
 async def save_edit_max(m:Message,state):
  await save_service_edit(m,state,'max_gb')

 @dp.message(Flow.welcome_text)
 async def save_welcome_text(m:Message,state):
  if not admin(m.from_user.id):
   await state.clear(); return await m.answer('دسترسی ندارید.')
  value=(m.text or '').strip()
  if value=='/cancel':
   await state.clear(); return await m.answer('ویرایش متن خوش‌آمدگویی لغو شد.')
  if not value or len(value)>3500: return await m.answer('متن باید بین ۱ تا ۳۵۰۰ کاراکتر باشد.')
  await set_setting(cfg.database_path,'welcome_message',value)
  await state.clear()
  return await m.answer('متن خوش‌آمدگویی ذخیره شد. از این پس در /start نمایش داده می‌شود.',reply_markup=kb([[('⚙️ منوی مدیریت','admin:home')]]))

 @dp.message(Flow.card_number)
 async def save_card_number(m:Message,state):
  if not admin(m.from_user.id): return
  value=(m.text or '').replace(' ','').replace('-','')
  if not value.isdigit() or len(value)!=16: return await m.answer('شماره کارت باید ۱۶ رقم باشد. دوباره ارسال کنید.')
  await set_setting(cfg.database_path,'card_number',value); await state.clear(); await m.answer('شماره کارت ذخیره شد.')
 @dp.message(Flow.cardholder)
 async def save_cardholder(m:Message,state):
  if not admin(m.from_user.id): return
  await set_setting(cfg.database_path,'cardholder_name',(m.text or '')[:100]); await state.clear(); await m.answer('نام صاحب کارت ذخیره شد.')
 @dp.message(Flow.payment_text)
 async def save_payment_text(m:Message,state):
  if not admin(m.from_user.id): return
  await set_setting(cfg.database_path,'payment_instructions',(m.text or '')[:1000]); await state.clear(); await m.answer('متن پرداخت ذخیره شد.')
 @dp.message(Flow.plan_price)
 async def save_plan_price(m:Message,state):
  if not admin(m.from_user.id): return
  value=(m.text or '').strip(); data=await state.get_data()
  if not value.isdigit() or int(value)<0: return await m.answer('قیمت باید عدد صفر یا بیشتر باشد.')
  n=await set_price(cfg.database_path,data['plan_code'],int(value)); await state.clear(); await m.answer('قیمت پلن ذخیره شد.' if n else 'پلن پیدا نشد.')
 # Admin tools
 @dp.message(Command('orders'))
 async def admin_orders(m:Message):
  if not admin(m.from_user.id): return
  rows=await orders_review(cfg.database_path)
  await m.answer('\n'.join(f"#{x['id']} {x['username']} {x['amount']} تومان" for x in rows) or 'سفارش در انتظار بررسی وجود ندارد.')
 @dp.message(Command('stats'))
 async def admin_stats(m:Message):
  if not admin(m.from_user.id): return
  u,a,s,o=await stats(cfg.database_path); await m.answer(f'کاربران: {u}\nحساب فعال: {a}\nفروش تأییدشده: {s:,} تومان\nکل سفارش‌ها: {o}')
 @dp.message(Command('plans'))
 async def admin_plans(m:Message):
  if not admin(m.from_user.id): return
  ps=await plans(cfg.database_path); await m.answer('\n'.join(f"{p['code']} | {p['protocol']} | {p['volume_gb']}GB | {p['months']} ماه | {p['price']} تومان" for p in ps) or 'بدون پلن')
 @dp.message(Command('setprice'))
 async def admin_price(m:Message):
  if not admin(m.from_user.id): return
  x=(m.text or '').split()
  if len(x)!=3 or not x[2].isdigit(): return await m.answer('فرمت: /setprice CODE AMOUNT')
  n=await set_price(cfg.database_path,x[1],int(x[2])); await m.answer('قیمت به‌روزرسانی شد.' if n else 'کد پلن پیدا نشد.')
 @dp.message(Command('addplan'))
 async def admin_addplan_removed(m:Message):
  if admin(m.from_user.id): await m.answer('افزودن سرویس فقط از منوی ⚙️ مدیریت ربات انجام می‌شود.')
 @dp.message(Command('setcard'))
 async def admin_card(m:Message):
  if not admin(m.from_user.id): return
  await m.answer('شماره کارت و نام دارنده از طریق فایل .env تنظیم می‌شود؛ CARD_NUMBER و CARDHOLDER_NAME را ویرایش و سرویس را restart کنید.')
 @dp.message(Command('users'))
 async def admin_users(m:Message):
  if not admin(m.from_user.id): return
  async with connect(cfg.database_path) as db: rows=await (await db.execute('SELECT telegram_id,username,first_seen FROM users ORDER BY first_seen DESC LIMIT 50')).fetchall()
  await m.answer('\n'.join(f"{r['telegram_id']} @{r['username'] or '-'}" for r in rows) or 'کاربری ثبت نشده')
 @dp.message(Command('backup'))
 async def admin_backup(m:Message):
  if not admin(m.from_user.id): return
  from datetime import datetime
  dest=cfg.database_path+'.backup-'+datetime.now().strftime('%Y%m%d-%H%M%S')
  shutil.copy2(cfg.database_path,dest); await m.answer_document(__import__('aiogram').types.FSInputFile(dest),caption='نسخه پشتیبان دیتابیس')
 @dp.message(Command('broadcast'))
 async def admin_broadcast(m:Message,state):
  if not admin(m.from_user.id): return
  await state.set_state(Flow.broadcast); await m.answer('متن پیام همگانی را بفرستید.')
 @dp.message(Flow.broadcast)
 async def broadcast(m:Message,state):
  if not admin(m.from_user.id): return
  await state.clear()
  async with connect(cfg.database_path) as db: rows=await (await db.execute('SELECT telegram_id FROM users')).fetchall()
  sent=0
  for r in rows:
   try: await bot.send_message(r['telegram_id'],m.text or ''); sent+=1
   except Exception: pass
  await m.answer(f'ارسال شد: {sent}')
 @dp.message(Command('cancel'))
 async def cancel(m:Message,state): await state.clear(); await m.answer('لغو شد.')
 try:
  # Match the polling startup used by the previously working 22-Nov release.
  await dp.start_polling(bot)
 finally:
  await panel.close()
  await bot.session.close()
if __name__=='__main__': asyncio.run(main())
