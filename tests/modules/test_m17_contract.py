from pathlib import Path


def test_external_adapter_has_no_credentials_or_evasion_surface():
    text = Path("backend/app/modules/m17_advice_essay/adapters.py").read_text()
    forbidden_signatures = ("password:", "cookie:", "proxy:", "login(", "create_account(", "like(", "follow(")
    assert not any(value in text.lower() for value in forbidden_signatures)


def test_no_external_network_library_imported_at_module_import_time():
    module_dir = Path("backend/app/modules/m17_advice_essay")
    text = "\n".join(path.read_text() for path in module_dir.glob("*.py"))
    assert "import requests" not in text
    assert "import httpx" not in text
    assert "from selenium" not in text
    assert "from playwright" not in text
