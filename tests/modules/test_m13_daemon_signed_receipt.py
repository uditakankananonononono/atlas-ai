"""Real daemon policy output, Ed25519 signer, transport JSON and HTTP verifier.
No live PC connection or real-site navigation claimed."""
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from types import SimpleNamespace
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.modules.m13_browser_agent.pc_daemon.daemon import Daemon,DeviceIdentity
from app.modules.m13_browser_agent.pc_daemon.config import DaemonConfig
from app.modules.m13_browser_agent.session_bridge import protocol
from app.modules.m13_browser_agent.session_bridge.routes import router,get_registry
from app.auth.context import require_tenant
from test_m13_session_bridge_registry import registry

@pytest.mark.asyncio
async def test_real_daemon_output_to_verify_route(registry,tmp_path):
    identity=DeviceIdentity(Ed25519PrivateKey.generate())
    c=registry.create_challenge('tenant-a')
    paired=registry.confirm_pairing(c['server_nonce'],c['code'],name='PC',public_key=identity.public_key_pem(),capabilities=['navigate'])
    config=DaemonConfig(server_url='http://localhost',device_id=paired['device_id'],command_secret=paired['command_secret'],key_path=str(tmp_path/'unused-key'),capabilities=['navigate'])
    daemon=Daemon(config,identity)
    app=FastAPI();app.include_router(router)
    app.dependency_overrides[get_registry]=lambda:registry
    app.dependency_overrides[require_tenant]=lambda:SimpleNamespace(tenant_id='tenant-a')
    with TestClient(app) as client:
        for i in range(2):
            # Unpermitted screenshot creates genuine daemon policy-block output,
            # with no fake browser or mocked signing path.
            output=await daemon.execute(protocol.make_command(protocol.CommandKind.SCREENSHOT,{},command_id=f'cmd-{i}'))
            wire=json.loads(json.dumps(output))
            assert wire['receipt']['phase']=='blocked'
            assert 'signed_receipt' in wire
            body=wire['signed_receipt'];assert len(body['events'])==i+1
            response=client.post(f"/browser-agent/bridge/devices/{paired['device_id']}/verify-receipt",json=body)
            assert response.status_code==200,response.text
            assert response.json()['events_verified']==i+1
            assert response.json()['receipt_complete']
            foreign=Ed25519PrivateKey.generate().sign(body['events'][-1]['event_hash'].encode()).hex()
            assert client.post(f"/browser-agent/bridge/devices/{paired['device_id']}/verify-receipt",json={**body,'signature':foreign}).status_code==422
