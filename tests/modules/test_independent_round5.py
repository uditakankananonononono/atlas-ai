import json
from pathlib import Path
import pytest
from test_m18_login_browser import setup, ready, _compose_with_values, setup_daemon
from app.modules.m13_browser_agent.session_bridge import protocol
from app.modules.m13_browser_agent.pc_daemon.daemon import Daemon

async def restore(setup,args):
    page,_=await _compose_with_values(setup)
    for selector,value in args['values'].items():
        await page.fill(selector,value)
    return page

@pytest.mark.asyncio
@pytest.mark.parametrize('trigger', ['jsbutton','label','custom'])
async def test_unapproved_js_submit(setup,trigger):
    page,_=await _compose_with_values(setup)
    await page.fill('#draft','UNAPPROVED')
    await page.fill('#run_id','attack')
    scripts={
      'jsbutton': "document.body.insertAdjacentHTML('beforeend','<button id=attack type=button>go</button>');document.querySelector('#attack').addEventListener('click',()=>document.querySelector('form').requestSubmit())",
      'label': "document.body.insertAdjacentHTML('beforeend','<label id=attack for=aux>go</label><input id=aux type=checkbox>');document.querySelector('#aux').addEventListener('click',()=>document.querySelector('form').requestSubmit())",
      'custom': "customElements.define('attack-submit',class extends HTMLElement {connectedCallback(){this.addEventListener('click',()=>document.querySelector('form').requestSubmit())}});document.body.insertAdjacentHTML('beforeend','<attack-submit id=attack>go</attack-submit>')"
    }
    await page.evaluate(scripts[trigger])
    daemon=setup_daemon(setup);daemon._capabilities.add('click_nav')
    answer=await daemon.execute(protocol.make_command(protocol.CommandKind.CLICK_NAV,{'session':'experiment','selector':'#attack'}))
    print('BYPASS',trigger,'ok',answer['ok'],'posts',setup[6].posts)
    assert not setup[6].posts, (answer,setup[6].hits)

@pytest.mark.asyncio
@pytest.mark.parametrize('mode',['preexisting_daemon','deleted','array','null'])
async def test_replay_record_failclosed(setup,mode):
    old=setup_daemon(setup)
    fresh=Daemon(old.config,old.identity);fresh.browser=old.browser
    r,run=await ready(setup);assert (await r.execute('tenant',run['id'],'owner'))['state']=='succeeded'
    args=dict([c for c in setup[6].commands if c['kind']=='click_submit'][-1]['args'])
    if mode!='preexisting_daemon':
        path=Path(old.consumed_path)
        if mode=='deleted':path.unlink()
        else:path.write_text('[]' if mode=='array' else 'null')
        fresh=Daemon(old.config,old.identity);fresh.browser=old.browser
    await restore(setup,args)
    answer=await fresh.execute(protocol.make_command(protocol.CommandKind.CLICK_SUBMIT,args))
    print('REPLAY',mode,'ok',answer['ok'],'posts',len(setup[6].posts))
    assert len(setup[6].posts)==1,(answer,setup[6].hits)
