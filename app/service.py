import calendar,time,uuid,json
from datetime import datetime,timezone
from urllib.parse import quote,urlsplit
from .security import password
from .vpnui import VPNUIError

def add_months_ms(months,from_ms=None):
 dt=datetime.fromtimestamp((from_ms or int(time.time()*1000))/1000,timezone.utc)
 m=dt.month-1+months; y=dt.year+m//12; m=m%12+1; d=min(dt.day,calendar.monthrange(y,m)[1])
 return int(dt.replace(year=y,month=m,day=d).timestamp()*1000)
def gb_bytes(gb): return int(gb)*1024**3
def validate_openvpn_transport(inbound_obj,transport):
 if transport not in ('tcp','udp'): raise VPNUIError('نوع اتصال OpenVPN نامعتبر است.')
 settings=inbound_obj.get('settings',{})
 if isinstance(settings,str): settings=json.loads(settings)
 if not isinstance(settings,dict) or not settings.get(f'{transport}Enable',False):
  raise VPNUIError(f'اتصال OpenVPN {transport.upper()} در تنظیمات این Inbound فعال نیست.')
async def create_panel_account(panel,cfg,protocol,inbound,username,uid,volume_gb,months,trial=False,transport='udp',inbound_obj=None):
 if protocol not in ('vless','l2tp','openvpn'):
  raise VPNUIError(f'پروتکل پشتیبانی نمی‌شود: {protocol}')
 if not isinstance(username,str) or not username or len(username)>64:
  raise VPNUIError('نام کاربری نامعتبر است.')
 if type(uid) is not int or uid <= 0:
  raise VPNUIError('شناسه تلگرام نامعتبر است.')
 if type(volume_gb) is not int or volume_gb < 0:
  raise VPNUIError('حجم نامعتبر است.')
 if type(months) is not int or months < 0:
  raise VPNUIError('مدت اعتبار نامعتبر است.')
 inbound_obj=inbound_obj or await panel.get_inbound(inbound); p=inbound_obj.get('protocol','').lower()
 if not inbound_obj.get('enable') or p!=protocol: raise VPNUIError(f'Inbound {inbound} فعال یا از نوع {protocol} نیست.')
 if protocol=='openvpn': validate_openvpn_transport(inbound_obj,transport)
 email=username; subid=uuid.uuid4().hex[:16]; expiry=(int(time.time()*1000)+86400000) if trial else (add_months_ms(months) if months else 0)
 common={'email':email,'enable':True,'limitIp':1,'totalGB':gb_bytes(volume_gb),'expiryTime':expiry,'tgId':int(uid),'subId':subid,'comment':f'Telegram {uid}','reset':0}
 if protocol=='vless':
  client_uuid=str(uuid.uuid4()); client={'id':client_uuid,'uuid':client_uuid,'flow':'','encryption':'none',**common}
  identity=client_uuid; credential=client_uuid
 elif protocol=='l2tp':
  pw=password(); client={'id':username,'password':pw,'slot':0,**common}; identity=pw; credential=pw
 else:
  pw=password(); client={'id':username,'password':pw,'slot':0,**common}; identity=pw; credential=pw
 result=await panel.add_client(inbound,client)
 if not isinstance(result,dict) or result.get('success') is False: raise VPNUIError('پنل ساخت حساب را تأیید نکرد.')
 if result.get('dry_run'): raise VPNUIError('DRY_RUN فعال است؛ ساخت واقعی انجام نشد و سفارش نباید تحویل شود.')
 return {'identity':identity,'credential':credential,'email':email,'expiry_ms':expiry,'client':client}
def render_connection(cfg,protocol,inbound_obj,username,credential):
 host=(cfg.public_host or str(inbound_obj.get('listen') or '').strip() or urlsplit(cfg.panel_base_url).hostname or '').strip()
 if host in ('0.0.0.0','::','127.0.0.1','localhost'): host=urlsplit(cfg.panel_base_url).hostname or ''
 if not host: raise VPNUIError('آدرس عمومی سرور VPN مشخص نیست؛ VPN_PUBLIC_HOST را تنظیم کنید.')
 port=int(inbound_obj.get('port') or 0)
 if protocol=='openvpn':
  raise VPNUIError('برای OpenVPN باید فایل پروفایل را مستقیماً از API پنل دریافت و ارسال کنید.')
 if protocol=='l2tp':
  s=inbound_obj.get('settings',{}); s=json.loads(s) if isinstance(s,str) else s
  psk=s.get('ipsecPsk','')
  if s.get('ipsecEnable') and not psk: raise VPNUIError('Inbound L2TP فاقد IPsec PSK است؛ تحویل متوقف شد.')
  return f'پروتکل: L2TP/IPsec\nسرور: {host}\nنام کاربری: {username}\nرمز عبور: {credential}\nIPsec PSK: {psk or "غیرفعال"}\n'
 s=inbound_obj.get('streamSettings',{}); s=json.loads(s) if isinstance(s,str) else s
 net=s.get('network','tcp'); sec=s.get('security','none'); params={'type':net,'security':sec,'encryption':'none'}
 if sec=='tls':
  tls=s.get('tlsSettings',{}); params['sni']=tls.get('serverName') or host
  if tls.get('alpn'): params['alpn']=','.join(tls['alpn'])
 elif sec=='reality':
  r=s.get('realitySettings',{}); params['sni']=r.get('serverName') or host; params['fp']=r.get('fingerprint','chrome'); params['pbk']=r.get('publicKey',''); params['sid']=(r.get('shortIds') or [''])[0]
 if net=='ws':
  w=s.get('wsSettings',{}); params['path']=w.get('path','/')
  if w.get('headers',{}).get('Host'): params['host']=w['headers']['Host']
 link=f"vless://{credential}@{host}:{port}?"+'&'.join(f'{k}={quote(str(v),safe=",/:+")}' for k,v in params.items() if v is not None)+f'#{quote(username)}'
 return 'لینک اتصال VLESS:\n'+link


async def renew_panel_account(panel, account, months, volume_gb):
 """Extend the existing remote client without creating a second client."""
 import json
 inbound=await panel.get_inbound(account['inbound_id'])
 settings=inbound.get('settings',{})
 if isinstance(settings,str): settings=json.loads(settings)
 clients=settings.get('clients',[]) if isinstance(settings,dict) else []
 match=None
 for client in clients:
  identity=client.get('id') if account['protocol']=='vless' else client.get('password')
  if str(identity)==str(account['panel_identity']):
   match=client
   break
 if match is None:
  raise VPNUIError('حساب در Inbound پنل پیدا نشد؛ تمدید متوقف شد.')
 now=int(time.time()*1000)
 current=int(match.get('expiryTime') or account['expiry_ms'] or 0)
 base=max(now,current)
 expiry=add_months_ms(months,base)
 match['expiryTime']=expiry
 match['totalGB']=gb_bytes(volume_gb)
 match['enable']=True
 match['reset']=0
 result=await panel.update_client(account['inbound_id'],account['panel_identity'],match)
 if not isinstance(result,dict) or result.get('success') is False or result.get('dry_run'):
  raise VPNUIError('پنل تمدید حساب را تأیید نکرد.')
 return expiry
