from __future__ import annotations
import json,httpx
class VPNUIError(RuntimeError): pass
class VPNUIClient:
 def __init__(self,base_url,username,password,verify_tls=True,dry_run=True):
  self.base_url=base_url.rstrip('/'); self.username=username; self.password=password; self.dry_run=dry_run; self._logged_in=False
  self.http=httpx.AsyncClient(timeout=httpx.Timeout(25),verify=verify_tls,follow_redirects=False,headers={'X-Requested-With':'XMLHttpRequest','Accept':'application/json'})
 async def close(self): await self.http.aclose()
 async def _json(self,r):
  if r.status_code==404: raise VPNUIError('پاسخ 404 پنل؛ Base Path یا مسیر API را بررسی کنید.')
  if r.status_code in (301,302,307,308): raise VPNUIError('پنل درخواست را به صفحه ورود هدایت کرد.')
  r.raise_for_status(); ct=r.headers.get('content-type','')
  if 'json' not in ct: raise VPNUIError(f'پاسخ پنل JSON نیست: {ct}')
  d=r.json()
  if isinstance(d,dict) and d.get('success') is False: raise VPNUIError(str(d.get('msg') or 'درخواست پنل رد شد.'))
  return d
 async def login(self):
  d=await self._json(await self.http.post(self.base_url+'/login',data={'username':self.username,'password':self.password}))
  if isinstance(d,dict) and isinstance(d.get('obj'),dict) and d['obj'].get('twoFactorRequired'): raise VPNUIError('2FA پنل در این نسخه پشتیبانی نشده است.')
  self._logged_in=True; return d
 async def request(self,method,path,**kwargs):
  if not self._logged_in: await self.login()
  r=await self.http.request(method,self.base_url+path,**kwargs)
  if r.status_code==404:
   self._logged_in=False; await self.login(); r=await self.http.request(method,self.base_url+path,**kwargs)
  return await self._json(r)
 async def list_inbounds(self):
  d=await self.request('GET','/panel/api/inbounds/list'); o=d.get('obj') if isinstance(d,dict) else None
  if not isinstance(o,list): raise VPNUIError('ساختار لیست Inbound نامعتبر است.')
  return o
 async def get_inbound(self,iid):
  d=await self.request('GET',f'/panel/api/inbounds/get/{int(iid)}'); o=d.get('obj') if isinstance(d,dict) else None
  if not isinstance(o,dict): raise VPNUIError('ساختار Inbound نامعتبر است.')
  return o
 async def existing_usernames(self,inbound_ids):
  names=set()
  # vpn-ui enforces account email uniqueness panel-wide, not just per Inbound.
  all_ids=set(int(i) for i in (inbound_ids or []))
  rows=await self.list_inbounds() or []
  for row in rows:
   if not isinstance(row,dict): continue
   try: all_ids.add(int(row.get('id')))
   except (TypeError,ValueError): continue
  for iid in all_ids:
   o=await self.get_inbound(iid)
   s=o.get('settings') if isinstance(o,dict) else None
   if isinstance(s,str):
    try: s=json.loads(s)
    except (TypeError,ValueError): s={}
   if not isinstance(s,dict): s={}
   clients=s.get('clients') or []
   if not isinstance(clients,(list,tuple)): clients=[]
   for c in clients:
    if not isinstance(c,dict): continue
    for k in ('id','vpnUsername','email','comment'):
     v=c.get(k)
     if isinstance(v,str) and v: names.add(v.casefold())
  return names
 async def add_client(self,inbound_id,client):
  if self.dry_run: return {'success':True,'dry_run':True,'msg':'No API write sent (DRY_RUN).'}
  return await self.request('POST','/panel/api/inbounds/addClient',data={'id':str(int(inbound_id)),'settings':json.dumps({'clients':[client]},separators=(',',':'))})
 async def update_client(self,inbound_id,identity,client):
  if self.dry_run: return {'success':True,'dry_run':True}
  from urllib.parse import quote
  return await self.request('POST',f'/panel/api/inbounds/updateClient/{quote(str(identity),safe="")}',data={'id':str(int(inbound_id)),'settings':json.dumps({'clients':[client]},separators=(',',':'))})
 async def delete_client(self,inbound_id,identity):
  if self.dry_run: return {'success':True,'dry_run':True}
  from urllib.parse import quote
  return await self.request('POST',f'/panel/api/inbounds/{int(inbound_id)}/delClient/{quote(str(identity),safe="")}')


 async def download_openvpn_profile(self,inbound_id,transport):
  transport=str(transport).lower()
  if transport not in ('tcp','udp'): raise VPNUIError('نوع اتصال OpenVPN نامعتبر است.')
  if not self._logged_in: await self.login()
  path=f'/panel/api/inbounds/{int(inbound_id)}/ovpn/{transport}'
  r=await self.http.get(self.base_url+path,headers={'Accept':'*/*'})
  if r.status_code==404:
   self._logged_in=False; await self.login(); r=await self.http.get(self.base_url+path,headers={'Accept':'*/*'})
  if r.status_code in (301,302,307,308): raise VPNUIError('پنل درخواست دریافت پروفایل را به صفحه ورود هدایت کرد.')
  r.raise_for_status()
  content_type=r.headers.get('content-type','').lower()
  body=r.content
  if not body or b'<client' in body[:200].lower() or b'<!doctype html' in body[:500].lower() or b'<html' in body[:500].lower():
   raise VPNUIError('پنل به‌جای فایل OpenVPN، پاسخ نامعتبر برگرداند.')
  if b'client' not in body[:2048].lower() or b'auth-user-pass' not in body.lower():
   raise VPNUIError('فایل دریافتی از پنل، پروفایل OpenVPN معتبر یا دارای auth-user-pass نیست.')
  if 'json' in content_type: raise VPNUIError('پنل به‌جای فایل .ovpn پاسخ JSON برگرداند.')
  return body
 async def get_client_traffic(self,identity):
  from urllib.parse import quote
  d=await self.request('GET',f'/panel/api/inbounds/getClientTrafficsById/{quote(str(identity),safe="")}')
  obj=d.get('obj') if isinstance(d,dict) else None
  if not isinstance(obj,dict): raise VPNUIError('ساختار اطلاعات مصرف حساب نامعتبر است.')
  return obj
