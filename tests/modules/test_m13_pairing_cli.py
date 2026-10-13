"""Public pairing is fail-closed since dec4c06d. No bound client replacement is claimed.
Token precedence and 401/403 transport behavior are untested while this entry refuses.
"""
import json
import pytest
from app.modules.m13_browser_agent.pc_daemon import __main__ as cli
from app.modules.m13_browser_agent.pc_daemon.daemon import pair_with_server

@pytest.mark.parametrize('case,flag,env_token,direct', [
 ('refusal-flag-present','tok-abc',None,False),
 ('refusal-env-present',None,'tok-env',False),
 ('refusal-both-present','tok-flag','tok-env',False),
 ('refusal-no-token',None,None,False),
 ('refusal-direct-no-token',None,None,True),
 ('refusal-direct-no-token-repeat',None,None,True),
 ('refusal-existing-config',None,'tok-env',False),
 ('refusal-flag-present-repeat','tok-flag',None,False),
 ('refusal-blank-with-env','','tok-env',False),
 ('refusal-blank-without-env','',None,False),
])
def test_unbound_pairing_refusal_zero_http_and_no_key_writes(monkeypatch,tmp_path,case,flag,env_token,direct):
    calls=[]
    def post(*args,**kwargs):
        calls.append((args,kwargs))
        raise AssertionError('refused pairing reached HTTP')
    monkeypatch.setattr('httpx.post',post)
    monkeypatch.setattr(cli,'DEFAULT_STATE_DIR',tmp_path)
    if env_token is None:monkeypatch.delenv('ATLAS_PAIR_TOKEN',raising=False)
    else:monkeypatch.setenv('ATLAS_PAIR_TOKEN',env_token)
    config=tmp_path/'config.json';config.write_text(json.dumps({'device_id':'keep-me'}))
    before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(PermissionError,match='EFFECT_UNBOUND_REFUSED'):
        if direct:
            pair_with_server('https://atlas.test','n','123456',name='pc',capabilities=['navigate'],
                             pacing_seconds=None,key_path=tmp_path/'k.pem',config_path=config,token=flag)
        else:
            args=['pair','--server','https://atlas.test','--nonce','n','--code','123456']
            if flag is not None:args+=['--token',flag]
            cli.main(args)
    assert calls==[]
    assert {p.name:p.read_bytes() for p in tmp_path.iterdir()}==before
