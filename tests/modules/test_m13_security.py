import pytest
from app.modules.m13_browser_agent.security import NavigationBlocked,validate_public_url
def test_localhost_blocked():
 with pytest.raises(NavigationBlocked):validate_public_url("http://localhost/x")
def test_embedded_credentials_blocked():
 with pytest.raises(NavigationBlocked):validate_public_url("https://u:p@example.com")
