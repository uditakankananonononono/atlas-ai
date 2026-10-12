import base64,json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.modules.m17_narrative_architect.publication_key_registry import RegisterPublicationKey
KEY=Ed25519PrivateKey.generate()
def register(registry):
    raw=KEY.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    registry.register(RegisterPublicationKey(provider='publisher',key_id='k',public_key_base64=base64.b64encode(raw).decode()))
    return registry
class SignedAdapter:
    def prepare(self,a,r):return self.receipt(a,r)
    def publish(self,a,r):return self.receipt(a,r)
    def receipt(self,a,r):
        value={'provider':'publisher','provider_id':'p','essay_id':'e','revision_sha256':r,'audience_boundary':a,'published_at':'2026-10-12T00:00:00Z','key_id':'k'}
        value['signature_base64']=base64.b64encode(KEY.sign(json.dumps(value,sort_keys=True,separators=(',',':')).encode())).decode()
        return value
