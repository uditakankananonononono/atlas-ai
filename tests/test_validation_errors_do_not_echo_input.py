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
