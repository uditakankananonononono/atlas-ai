from cryptography.fernet import Fernet
from app.platform.encryption import SecretCipher
def test_api_key_envelope_encryption_roundtrip_and_tamper_failure():
 c=SecretCipher(Fernet.generate_key().decode());token=c.encrypt('secret');assert token!='secret' and c.decrypt(token)=='secret'
 try:c.decrypt(token[:-2]+'xx')
 except ValueError:pass
 else:raise AssertionError('tamper accepted')
