"""M10 trusted timestamps: RFC 3161 verification against the pinned FreeTSA CA and
retired-key verification gated on a timestamp from before the key's cutoff."""
import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from asn1crypto import tsp
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import Header
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.main import app
from app.modules.m10_email_assistant import attestation_timestamps as ts
from app.modules.m10_email_assistant import reviewer_key_registry as rk
from app.modules.m10_email_assistant.routes import get_attestation_timestamps, get_reviewer_key_registry

FIX = Path(__file__).resolve().parents[1] / "fixtures"
# Real FreeTSA response over b"hello atlas", genTime 2026-09-24T06:18:32Z.
RESP = tsp.TimeStampResp.load((FIX / "freetsa_sample.tsr").read_bytes())
TOKEN = RESP["time_stamp_token"].dump()
DATA = (FIX / "freetsa_sample.data").read_bytes()
DIGEST = hashlib.sha256(DATA).digest()
GEN = datetime(2026, 9, 24, 6, 18, 32, tzinfo=timezone.utc)
C = TestClient(app)
V = "/api/v1/email-assistant/promise-state-reconciliation/evidence/verify"
K = "/api/v1/email-assistant/promise-state-reconciliation/reviewer-keys"
H = {"X-Atlas-Tenant": "t", "X-Atlas-Actor": "owner"}


def test_pinned_freetsa_files_match_published_hashes():
    assert hashlib.sha256((ts.TSA_DIR / "freetsa_cacert.pem").read_bytes()).hexdigest() == "2151b61137ffa86bf664691ba67e7da0b19f98c758e3d228d5d8ebf27e044438"
    assert hashlib.sha256((ts.TSA_DIR / "freetsa_tsa.crt").read_bytes()).hexdigest() == "8bfb0305bb64e2571ca507552ef3245cb1c2fee8728e0ff8689225081ea13467"


def test_real_freetsa_token_verifies_offline():
    assert ts.verify_rfc3161(TOKEN, DIGEST, ts.TsaTrust.configured()) == GEN


def test_token_for_other_data_is_rejected():
    with pytest.raises(ts.TimestampError, match="does not cover"):
        ts.verify_rfc3161(TOKEN, hashlib.sha256(b"hello atlaS").digest(), ts.TsaTrust.configured())


def test_flipped_token_byte_is_rejected():
    bad = bytearray(TOKEN)
    bad[-20] ^= 0x01  # inside the TSA signature
    with pytest.raises(ts.TimestampError):
        ts.verify_rfc3161(bytes(bad), DIGEST, ts.TsaTrust.configured())


def test_edited_gen_time_breaks_signature():
    ci = tsp.ContentInfo.load(TOKEN)
    sd = ci["content"]
    tst = tsp.TSTInfo.load(sd["encap_content_info"]["content"].parsed.dump())
    tst["gen_time"] = datetime(2020, 1, 1, tzinfo=timezone.utc)
    sd["encap_content_info"]["content"] = tst
    with pytest.raises(ts.TimestampError):
        ts.verify_rfc3161(tsp.ContentInfo({"content_type": "signed_data", "content": sd}).dump(force=True), DIGEST, ts.TsaTrust.configured())


def test_untrusted_ca_is_rejected():
    k = ec.generate_private_key(ec.SECP256R1())
    n = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "evil")])
    c = (x509.CertificateBuilder().subject_name(n).issuer_name(n).public_key(k.public_key()).serial_number(1)
         .not_valid_before(datetime(2020, 1, 1)).not_valid_after(datetime(2040, 1, 1)).sign(k, hashes.SHA256()))
    with pytest.raises(ts.TimestampError, match="does not chain"):
        ts.verify_rfc3161(TOKEN, DIGEST, ts.TsaTrust(c.public_bytes(serialization.Encoding.PEM), "evil"))


def test_client_sends_rfc3161_request_and_rejects_replayed_response():
    seen = {}

    def handler(request):
        seen["ct"] = request.headers["content-type"]
        req = tsp.TimeStampReq.load(request.content)
        seen["digest"] = req["message_imprint"]["hashed_message"].native
        seen["cert_req"] = req["cert_req"].native
        return httpx.Response(200, content=RESP.dump(), headers={"content-type": "application/timestamp-reply"})

    client = ts.Rfc3161Client("https://tsa.test/tsr", httpx.Client(transport=httpx.MockTransport(handler)))
    # The stored FreeTSA reply carries an old nonce, so replaying it must fail.
    with pytest.raises(ts.TimestampError, match="nonce"):
        client.stamp(DIGEST)
    assert seen == {"ct": "application/timestamp-query", "digest": DIGEST, "cert_req": True}


def test_local_scheme_verifies_but_is_not_trusted_by_default():
    local = ts.LocalTimestamper(base64.b64encode(b"s" * 32).decode(), clock=lambda: GEN)
    token = local.stamp(DIGEST)
    assert ts.verify_local(token, DIGEST, local.public_key()) == GEN
    with pytest.raises(ts.TimestampError):
        ts.verify_local(token, hashlib.sha256(b"x").digest(), local.public_key())


# --------------------------------------------------------------------- end to end
SESSIONS = {}


def fixture_attestation():
    """Attestation whose canonical digest we can stamp with the mocked TSA."""
    private = Ed25519PrivateKey.generate()
    raw = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    a = {"reviewer_id": "owner", "decision_sha256": "a" * 64, "key_id": "v1"}
    a["signature_base64"] = base64.b64encode(private.sign(json.dumps(a, sort_keys=True, separators=(",", ":")).encode())).decode()
    return private, raw, a


class FakeTsa:
    """Mocked TSA: returns a token over whatever digest is requested, signed by a
    test CA that the service is configured to trust, at a chosen genTime."""

    def __init__(self, gen_time):
        self.gen_time, self.calls, self.fail = gen_time, 0, False
        self.ca_key = ec.generate_private_key(ec.SECP384R1())
        name = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "Test TSA CA")])
        self.ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(self.ca_key.public_key())
                   .serial_number(1).not_valid_before(datetime(2020, 1, 1)).not_valid_after(datetime(2040, 1, 1))
                   .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True).sign(self.ca_key, hashes.SHA384()))
        self.key = ec.generate_private_key(ec.SECP384R1())
        tname = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "Test TSA")])
        self.cert = (x509.CertificateBuilder().subject_name(tname).issuer_name(name).public_key(self.key.public_key())
                     .serial_number(2).not_valid_before(datetime(2020, 1, 1)).not_valid_after(datetime(2040, 1, 1))
                     .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.TIME_STAMPING]), critical=True)
                     .sign(self.ca_key, hashes.SHA384()))

    def trust(self):
        return ts.TsaTrust(self.ca.public_bytes(serialization.Encoding.PEM), "test-tsa")

    def token(self, digest, nonce):
        from asn1crypto import algos, cms, core, x509 as ax509
        tst = tsp.TSTInfo({"version": "v1", "policy": "1.2.3.4", "message_imprint": {"hash_algorithm": {"algorithm": "sha256"},
                           "hashed_message": digest}, "serial_number": self.calls, "gen_time": self.gen_time, "nonce": nonce})
        content = tst.dump()
        acert = ax509.Certificate.load(self.cert.public_bytes(serialization.Encoding.DER))
        attrs = cms.CMSAttributes([
            cms.CMSAttribute({"type": "content_type", "values": ["tst_info"]}),
            cms.CMSAttribute({"type": "message_digest", "values": [hashlib.sha384(content).digest()]}),
            cms.CMSAttribute({"type": "signing_certificate_v2", "values": [{"certs": [{"cert_hash": hashlib.sha256(acert.dump()).digest()}]}]}),
        ])
        sig = self.key.sign(attrs.dump(), ec.ECDSA(hashes.SHA384()))
        signer = cms.SignerInfo({"version": "v1", "sid": cms.SignerIdentifier({"issuer_and_serial_number": {
            "issuer": acert.issuer, "serial_number": acert.serial_number}}), "digest_algorithm": {"algorithm": "sha384"},
            "signed_attrs": attrs, "signature_algorithm": {"algorithm": "sha384_ecdsa"}, "signature": sig})
        sd = cms.SignedData({"version": "v3", "digest_algorithms": [{"algorithm": "sha384"}],
                             "encap_content_info": {"content_type": "tst_info", "content": core.ParsableOctetString(content)},
                             "certificates": [acert], "signer_infos": [signer]})
        return tsp.ContentInfo({"content_type": "signed_data", "content": sd})

    def handler(self, request):
        self.calls += 1
        if self.fail:
            return httpx.Response(503)
        req = tsp.TimeStampReq.load(request.content)
        tok = self.token(req["message_imprint"]["hashed_message"].native, req["nonce"].native)
        return httpx.Response(200, content=tsp.TimeStampResp({"status": {"status": "granted"}, "time_stamp_token": tok}).dump())


@pytest.fixture
def env():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    sessions = sessionmaker(bind=e, expire_on_commit=False)
    clock = {"now": datetime(2026, 9, 24, 7, 0, tzinfo=timezone.utc)}
    tsa = FakeTsa(datetime(2026, 9, 24, 7, 0, tzinfo=timezone.utc))
    stamper = ts.AttestationTimestamps("t", sessions, scheme="rfc3161", trust=tsa.trust(),
                                       rfc3161=ts.Rfc3161Client("https://tsa.test/tsr", httpx.Client(transport=httpx.MockTransport(tsa.handler))))

    def registry(x_atlas_actor: str = Header(default="owner")):
        return rk.ReviewerKeyRegistry("t", sessions, actor_id=x_atlas_actor, clock=lambda: clock["now"])

    app.dependency_overrides[get_reviewer_key_registry] = registry
    app.dependency_overrides[get_attestation_timestamps] = lambda: stamper
    yield {"sessions": sessions, "clock": clock, "tsa": tsa, "stamper": stamper}
    app.dependency_overrides.clear()


def enroll(private, raw):
    fp = hashlib.sha256(raw).hexdigest()
    proof = private.sign(rk.enrollment_statement("t", "owner", "v1", fp))
    r = C.post(K, headers=H, json={"reviewer_id": "owner", "key_id": "v1", "public_key_base64": base64.b64encode(raw).decode(),
                                   "proof_signature_base64": base64.b64encode(proof).decode()})
    assert r.status_code == 200, r.text


def body(a):
    msg = b"I sent it"
    return {"messages": [{"message_id": "m", "content_base64": base64.b64encode(msg).decode(), "content_sha256": hashlib.sha256(msg).hexdigest()}],
            "attestations": [a]}


def test_verified_attestation_is_timestamped_and_survives_retirement(env):
    private, raw, a = fixture_attestation()
    enroll(private, raw)
    r = C.post(V, headers=H, json=body(a))
    assert r.status_code == 200, r.text
    stamp = r.json()["timestamps"][0]
    assert stamp["timestamped"] is True and stamp["authority"] == "rfc3161:test-tsa"
    assert r.json()["reviewers"][0]["verified_via"] == "active-key"
    env["clock"]["now"] = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)
    assert C.post(f"{K}/owner/v1/retire", headers=H, json={"reason": "left team"}).status_code == 200
    r = C.post(V, headers=H, json=body(a))
    assert r.status_code == 200, r.text
    rev = r.json()["reviewers"][0]
    assert rev["verified_via"] == "timestamp-before-retirement"
    assert rev["timestamp"].startswith("2026-09-24T07:00") and rev["key_valid_before"].startswith("2026-09-24T09:00")
    assert r.json()["timestamps"][0]["reused"] is True
    assert env["tsa"].calls == 1


def test_retired_key_without_timestamp_is_rejected(env):
    private, raw, a = fixture_attestation()
    enroll(private, raw)
    env["stamper"].scheme = "off"
    assert C.post(V, headers=H, json=body(a)).status_code == 200
    assert C.post(f"{K}/owner/v1/retire", headers=H, json={"reason": "left"}).status_code == 200
    env["stamper"].scheme = "rfc3161"
    r = C.post(V, headers=H, json=body(a))
    assert r.status_code == 422 and "no trusted timestamp" in r.text
    assert env["tsa"].calls == 0  # never stamps a signature from a retired key


def test_timestamp_after_cutoff_is_rejected(env):
    private, raw, a = fixture_attestation()
    enroll(private, raw)
    env["tsa"].gen_time = datetime(2026, 9, 24, 10, 0, tzinfo=timezone.utc)  # stamped after the key is retired
    assert C.post(V, headers=H, json=body(a)).status_code == 200
    env["clock"]["now"] = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)
    assert C.post(f"{K}/owner/v1/retire", headers=H, json={"reason": "left"}).status_code == 200
    r = C.post(V, headers=H, json=body(a))
    assert r.status_code == 422 and "not before the key cutoff" in r.text


def test_compromise_moves_cutoff_back_and_rejects_earlier_stamp(env):
    private, raw, a = fixture_attestation()
    enroll(private, raw)  # created_at 07:00
    env["tsa"].gen_time = datetime(2026, 9, 24, 8, 0, tzinfo=timezone.utc)
    env["clock"]["now"] = datetime(2026, 9, 24, 8, 0, tzinfo=timezone.utc)
    assert C.post(V, headers=H, json=body(a)).status_code == 200
    env["clock"]["now"] = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)
    r = C.post(f"{K}/owner/v1/retire", headers=H, json={"reason": "laptop stolen", "compromised": True,
                                                        "compromised_since": "2026-09-24T07:30:00Z"})
    assert r.status_code == 200 and r.json()["signatures_valid_before"].startswith("2026-09-24T07:30")
    r = C.post(V, headers=H, json=body(a))
    assert r.status_code == 422 and "not before the key cutoff" in r.text


def test_compromise_without_known_time_trusts_nothing(env):
    private, raw, a = fixture_attestation()
    enroll(private, raw)
    assert C.post(V, headers=H, json=body(a)).status_code == 200  # stamped at 07:00 == created_at
    env["clock"]["now"] = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)
    C.post(f"{K}/owner/v1/retire", headers=H, json={"reason": "leaked", "compromised": True})
    assert C.post(V, headers=H, json=body(a)).status_code == 422


def test_tsa_outage_does_not_fail_verification(env):
    private, raw, a = fixture_attestation()
    enroll(private, raw)
    env["tsa"].fail = True
    r = C.post(V, headers=H, json=body(a))
    assert r.status_code == 200 and r.json()["valid"] is True
    assert r.json()["timestamps"][0]["timestamped"] is False


def test_tampered_stored_token_proves_nothing(env):
    private, raw, a = fixture_attestation()
    enroll(private, raw)
    C.post(V, headers=H, json=body(a))
    with env["sessions"].begin() as db:
        row = db.query(ts.AttestationTimestampRow).one()
        t = bytearray(row.token); t[-10] ^= 1; row.token = bytes(t)
    env["clock"]["now"] = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)
    C.post(f"{K}/owner/v1/retire", headers=H, json={"reason": "left"})
    assert C.post(V, headers=H, json=body(a)).status_code == 422


def test_local_timestamps_ignored_unless_explicitly_trusted(env):
    private, raw, a = fixture_attestation()
    enroll(private, raw)
    local = ts.LocalTimestamper(base64.b64encode(b"s" * 32).decode(), clock=lambda: datetime(2026, 9, 24, 7, 5, tzinfo=timezone.utc))
    stamper = env["stamper"]
    stamper.scheme, stamper.local = "atlas-local", local
    assert C.post(V, headers=H, json=body(a)).json()["timestamps"][0]["authority"] == "atlas-local"
    env["clock"]["now"] = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)
    C.post(f"{K}/owner/v1/retire", headers=H, json={"reason": "left"})
    assert C.post(V, headers=H, json=body(a)).status_code == 422
    stamper.trust_local = True
    assert C.post(V, headers=H, json=body(a)).status_code == 200
