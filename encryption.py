"""Envelope encryption for API-key material before durable storage."""
from cryptography.fernet import Fernet,InvalidToken
class SecretCipher:
 def __init__(self,key:str):
  try:self.cipher=Fernet(key.encode())
  except Exception as exc:raise ValueError('ATLAS_API_KEY_ENCRYPTION_KEY must be a Fernet key') from exc
 def encrypt(self,value:str)->str:
  if not value:raise ValueError('secret is empty')
  return self.cipher.encrypt(value.encode()).decode()
 def decrypt(self,value:str)->str:
  try:return self.cipher.decrypt(value.encode()).decode()
  except InvalidToken as exc:raise ValueError('encrypted secret authentication failed') from exc
