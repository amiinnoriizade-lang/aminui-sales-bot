import asyncio,tempfile,unittest,os
from app.db import init_db,add_order,claim_test,add_dynamic_service,delete_dynamic_service,dynamic_services
class TestDB(unittest.TestCase):
 def test_unique_trial_and_order_username(self):
  async def go():
   f=tempfile.mktemp(); await init_db(f,[{'code':'x','protocol':'vless','volume_gb':1,'months':1,'price':10}])
   self.assertTrue(await claim_test(f,1)); self.assertFalse(await claim_test(f,1))
   oid,_=await add_order(f,1,'x','sample',2)
   with self.assertRaises(ValueError): await add_order(f,2,'x','SAMPLE',2)
   os.unlink(f)
  asyncio.run(go())
 def test_delete_dynamic_service_preserves_record_as_disabled(self):
  async def go():
   f=tempfile.mktemp()
   await init_db(f,[])
   await add_dynamic_service(f,'keep-me','vless',1,100,1,20)
   self.assertEqual(await delete_dynamic_service(f,'keep-me'),1)
   self.assertEqual(len(await dynamic_services(f)),0)
   rows=await dynamic_services(f,False)
   self.assertEqual(len(rows),1)
   self.assertEqual(rows[0]['enabled'],0)
   os.unlink(f)
  asyncio.run(go())
 def test_provisioning_failure_is_not_automatically_retryable(self):
  async def go():
   f=tempfile.mktemp()
   await init_db(f,[{'code':'x','protocol':'vless','volume_gb':1,'months':1,'price':10}])
   oid,_=await add_order(f,1,'x','safeuser',2)
   from app.db import attach_receipt, claim_order, fail_order, get_order
   self.assertTrue(await attach_receipt(f,oid,1,'receipt'))
   self.assertTrue(await claim_order(f,oid))
   await fail_order(f,oid,'timeout after panel request')
   order=await get_order(f,oid)
   self.assertEqual(order['status'],'provisioning_unknown')
   self.assertFalse(await claim_order(f,oid))
   os.unlink(f)
  asyncio.run(go())

 def test_renewal_order_keeps_account_and_marks_paid(self):
  async def go():
   f=tempfile.mktemp()
   await init_db(f,[{'code':'x','protocol':'vless','volume_gb':5,'months':2,'price':100}])
   from app.db import add_order,add_renewal_order,finish_renewal,get_order,attach_receipt,claim_order
   oid,_=await add_order(f,7,'x','renewme',2)
   # Seed the original account as if the first sale had completed.
   async with __import__('app.db',fromlist=['connect']).connect(f) as db:
    await db.execute("INSERT INTO accounts(telegram_id,username,protocol,inbound_id,panel_identity,credential_enc,email,volume_gb,expiry_ms,status,order_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(7,'renewme','vless',2,'uuid','enc','renewme',1,1000,'active',oid))
    await db.commit()
    aid=(await (await db.execute("SELECT id FROM accounts WHERE username='renewme'")).fetchone())['id']
   roid,_=await add_renewal_order(f,7,aid,'x')
   await attach_receipt(f,roid,7,'receipt2'); self.assertTrue(await claim_order(f,roid))
   await finish_renewal(f,roid,aid,999999,5)
   order=await get_order(f,roid)
   self.assertEqual(order['status'],'paid')
   async with __import__('app.db',fromlist=['connect']).connect(f) as db:
    row=await (await db.execute('SELECT volume_gb,expiry_ms FROM accounts WHERE id=?',(aid,))).fetchone()
    self.assertEqual((row['volume_gb'],row['expiry_ms']),(5,999999))
   os.unlink(f)
  asyncio.run(go())


 def test_dynamic_service_is_bound_to_selected_inbound(self):
  async def go():
   f=tempfile.mktemp(); await init_db(f,[])
   await add_dynamic_service(f,'inbound-nine','openvpn',1,100,1,20,9,'tcp')
   oid,plan=await __import__('app.db',fromlist=['add_custom_order']).add_custom_order(f,11,'inbound-nine',2,'newuser',9)
   order=await __import__('app.db',fromlist=['get_order']).get_order(f,oid)
   self.assertEqual(order['inbound_id'],9)
   self.assertEqual(order['protocol'],'openvpn')
   self.assertEqual(order['transport'],'tcp')
   self.assertEqual(plan['price'],200)
   with self.assertRaises(ValueError):
    await __import__('app.db',fromlist=['add_custom_order']).add_custom_order(f,12,'inbound-nine',2,'otheruser',2)
   os.unlink(f)
  asyncio.run(go())

 def test_legacy_dynamic_services_migrate_without_losing_rows(self):
  async def go():
   f=tempfile.mktemp()
   import sqlite3
   c=sqlite3.connect(f)
   c.execute("CREATE TABLE dynamic_services(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE, protocol TEXT NOT NULL CHECK(protocol IN ('vless','l2tp')), months INTEGER NOT NULL, rate INTEGER NOT NULL, min_gb INTEGER NOT NULL DEFAULT 1, max_gb INTEGER NOT NULL DEFAULT 1000, enabled INTEGER NOT NULL DEFAULT 1)")
   c.execute("INSERT INTO dynamic_services(code,protocol,months,rate,min_gb,max_gb) VALUES('legacy','l2tp',1,100,1,50)")
   c.commit(); c.close()
   await init_db(f,[],{'l2tp':32})
   rows=await dynamic_services(f,False)
   self.assertEqual(len(rows),1)
   self.assertEqual(rows[0]['code'],'legacy')
   self.assertEqual(rows[0]['inbound_id'],32)
   os.unlink(f)
  asyncio.run(go())


 def test_seeded_plans_are_bound_to_default_inbounds(self):
  async def go():
   f=tempfile.mktemp()
   await init_db(f,[{'code':'l2tp-default','protocol':'l2tp','volume_gb':0,'months':1,'price':500}],{'l2tp':32})
   rows=await __import__('app.db',fromlist=['all_plans']).all_plans(f)
   self.assertEqual(rows[0]['inbound_id'],32)
   oid,_=await add_order(f,9,'l2tp-default','customer',32)
   order=await __import__('app.db',fromlist=['get_order']).get_order(f,oid)
   self.assertEqual(order['inbound_id'],32)
   os.unlink(f)
  asyncio.run(go())

if __name__=='__main__': unittest.main()
