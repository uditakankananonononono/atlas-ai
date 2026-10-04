"""Booted app: a 422 never echoes the rejected request value, only loc/msg/type."""
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app, raise_server_exceptions=False)
URL = "/api/v1/grant-writer/success-analysis"
P = "protein folding transformer model drug discovery simulation proposal text"

def test_oversize_example_422_has_no_input_echo_and_is_small():
    r = c.post(URL, json={"proposal": P, "funded_examples": ["SECRETWORD " * 20_001]})
    assert r.status_code == 422 and "SECRETWORD" not in r.text and len(r.text) < 1000
    d = r.json()["detail"][0]
    assert set(d) == {"type", "loc", "msg"} and d["loc"][:2] == ["body", "funded_examples"] or d["loc"][0] == "body"

def test_type_error_422_keeps_location_but_not_value():
    r = c.post(URL, json={"proposal": "Bearer sk-live-SECRET " * 3, "funded_examples": "Bearer sk-live-SECRET"})
    assert r.status_code == 422 and "sk-live" not in r.text and r.json()["detail"][0]["loc"][-1] == "funded_examples"

def test_valid_request_unaffected():
    assert c.post(URL, json={"proposal": P, "funded_examples": []}).status_code == 200

def test_unknown_caller_keys_and_long_or_odd_loc_elements_become_a_placeholder():
    from fastapi import FastAPI
    from pydantic import BaseModel, ConfigDict, field_validator
    import app.main as m
    class M(BaseModel):
        model_config = ConfigDict(extra="forbid")
        a: int
        b: dict[int, int] = {}
        @field_validator("a")
        @classmethod
        def _echo(cls, v): raise ValueError(f"custom validator echoes {v} Bearer sk-live-SECRET")
    probe = FastAPI(); probe.add_exception_handler(m.RequestValidationError, m._validation_errors_without_input)
    @probe.post("/p")
    def p(x: M): return {}
    cc = TestClient(probe, raise_server_exceptions=False)
    key = "sk-live-" + "K" * 5000
    r = cc.post("/p", json={"a": 1, key: 1, "b": {"notint": 1}})
    assert r.status_code == 422 and "sk-live" not in r.text and "KKKK" not in r.text and "custom validator" not in r.text and len(r.text) < 1500
    d = r.json()["detail"]
    assert any(e["loc"][-1] == "<field>" for e in d) and all(set(e) == {"type", "loc", "msg"} for e in d)
    assert any(e["type"] == "value_error" and e["msg"] == "invalid value" for e in d)


def test_public_reason_is_echoed_but_detail_with_caller_input_is_not():
    from pydantic import BaseModel, model_validator
    from fastapi import FastAPI
    from app.core.public_validation import PublicValidationError
    import app.main as m
    class M(BaseModel):
        key_id: str
        @model_validator(mode="after")
        def v(self):
            raise PublicValidationError("untrusted provider public key", self.key_id)
    class Plain(BaseModel):
        key_id: str
        @model_validator(mode="after")
        def v(self):
            raise ValueError(f"untrusted provider public key: {self.key_id}")   # ordinary ValueError stays generic
    a = FastAPI(); a.add_exception_handler(m.RequestValidationError, m._validation_errors_without_input)
    a.post("/x")(lambda body: 1)
    @a.post("/pub")
    def pub(b: M): return 1
    @a.post("/plain")
    def plain(b: Plain): return 1
    t = TestClient(a)
    r = t.post("/pub", json={"key_id": "CALLERSECRET"})
    assert r.status_code == 422 and "untrusted provider public key" in r.text and "CALLERSECRET" not in r.text
    r = t.post("/plain", json={"key_id": "CALLERSECRET"})
    assert r.status_code == 422 and "CALLERSECRET" not in r.text and "untrusted" not in r.text

def test_public_validation_error_rejects_overlong_reason():
    import pytest
    from app.core.public_validation import PublicValidationError
    with pytest.raises(ValueError):
        PublicValidationError("x" * 121)
