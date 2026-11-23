from cryptography.fernet import Fernet
import secrets,string,re
class SecretBox:
 def __init__(self,key): self.f=Fernet(key.encode())
 def enc(self,s): return self.f.encrypt(s.encode()).decode()
 def dec(self,s): return self.f.decrypt(s.encode()).decode()
def password(n=18): return ''.join(secrets.choice(string.ascii_letters+string.digits+'-_') for _ in range(n))
def valid_username(s): return bool(re.fullmatch(r'[A-Za-z0-9_.-]{3,32}',s or ''))
