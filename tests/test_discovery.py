from app.collectors.discovery import candidate_from_result

def test_extracts_candidate_with_evidence():
    row=candidate_from_result("AI agents","https://x.com/example/status/123","Agent research thread")
    assert row.platform == "x" and row.account_key == "example"
    assert row.topic == "AI agents" and row.evidence_text == "Agent research thread"

def test_reserved_instagram_paths_are_not_accounts():
    assert candidate_from_result("art","https://www.instagram.com/explore/tags/art/","result") is None
