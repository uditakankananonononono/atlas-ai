from app.collectors.registry import COLLECTORS
from app.core.webhooks import verify_webhook
import hashlib,hmac

def test_new_free_collectors_registered():
    assert {"reddit_public","github_topics","open_access"} <= COLLECTORS.keys()

def test_custom_webhook_signature():
    body=b'{"title":"Opportunity"}'; secret="s"; signature=hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    assert verify_webhook(secret,body,signature)["title"] == "Opportunity"
