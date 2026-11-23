import unittest
from app.service import add_months_ms,gb_bytes
from datetime import datetime,timezone
class TestService(unittest.TestCase):
 def test_bytes(self): self.assertEqual(gb_bytes(1),1073741824); self.assertEqual(gb_bytes(0),0)
 def test_month_rollover(self):
  start=int(datetime(2024,1,31,tzinfo=timezone.utc).timestamp()*1000)
  out=datetime.fromtimestamp(add_months_ms(1,start)/1000,timezone.utc)
  self.assertEqual((out.year,out.month,out.day),(2024,2,29))
 def test_renew_existing_panel_client_preserves_identity_and_updates_expiry_quota(self):
  import asyncio
  from app.service import renew_panel_account
  class FakePanel:
   def __init__(self): self.client={'id':'uuid-1','email':'user1','enable':True,'expiryTime':0,'totalGB':1}; self.updated=None
   async def get_inbound(self,iid): return {'settings':{'clients':[self.client]}}
   async def update_client(self,iid,identity,client): self.updated=(iid,identity,dict(client)); return {'success':True}
  async def go():
   panel=FakePanel()
   account={'inbound_id':2,'protocol':'vless','panel_identity':'uuid-1','expiry_ms':0}
   expiry=await renew_panel_account(panel,account,1,10)
   self.assertGreater(expiry,0)
   self.assertEqual(panel.updated[1],'uuid-1')
   self.assertEqual(panel.updated[2]['totalGB'],10*1024**3)
   self.assertTrue(panel.updated[2]['enable'])
  asyncio.run(go())

if __name__=='__main__': unittest.main()
