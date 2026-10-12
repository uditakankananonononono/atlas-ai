"""Isolated actual entry functions: scoped zero-effect refusal, not full integration.

Isolated guard-removal checks remove the exact refusal from the source AST and
rerun the refusal check. Accepted mutant failures include ProviderTouched
(RuntimeError), NameError, AttributeError, TypeError and pytest.fail.Exception;
these are exception/failure-discriminating checks, not assertion-only kills or
an external pytest FAILED receipt classifier. SKIP classification is not applicable
to this in-process helper. No mutated provider traffic is possible.
"""
import ast,asyncio,copy,pathlib,types
import pytest

ROOT=pathlib.Path(__file__).resolve().parents[3]
APP=ROOT/'backend/app'

# module, actual function/class, minimal source line (disambiguates protocols)
ENTRY_CASES=[
 ('modules/m04_research_scientist/tools/adapters.py','run_workflow',30),
 ('modules/m10_email_assistant/gmail.py','watch',180),
 ('modules/m10_email_assistant/routes.py','connect_account',0),
 ('modules/m10_email_assistant/routes.py','renew_watches',0),
 ('modules/m10_email_assistant/service.py','connect_account',0),
 ('modules/m10_email_assistant/service.py','renew_watches',0),
 ('modules/m11_calendar_intelligence/google_calendar.py','watch',70),
 ('modules/m11_calendar_intelligence/google_calendar.py','stop_channel',70),
 ('modules/m11_calendar_intelligence/routes.py','ensure_watch',0),
 ('modules/m24_billing/stripe_client.py','create_checkout',0),
 ('modules/m24_billing/stripe_client.py','cancel_subscription',0),
 ('modules/m24_billing/stripe_client.py','create_invoice',0),
 ('modules/m13_browser_agent/pc_daemon/daemon.py','pair_with_server',0),
 ('modules/m13_browser_agent/playwright_adapter.py','fill',0),
 ('modules/m13_browser_agent/playwright_adapter.py','click',0),
]

class ProviderTouched(RuntimeError):pass
class Spy:
    calls=0
    def __getattr__(self,name):
        type(self).calls+=1
        raise ProviderTouched(name)

def refusal(effect):raise PermissionError('EFFECT_UNBOUND_REFUSED: '+effect)

def isolated_entry(rel,name,min_line,mutated=False):
    tree=ast.parse((APP/rel).read_text())
    fn=next(copy.deepcopy(n) for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name and n.lineno>min_line)
    if isinstance(fn.body[0],ast.Expr) and isinstance(fn.body[0].value,ast.Constant) and isinstance(fn.body[0].value.value,str):fn.body=fn.body[1:]
    fn.decorator_list=[];fn.returns=None
    for arg in (*fn.args.posonlyargs,*fn.args.args,*fn.args.kwonlyargs):arg.annotation=None
    fn.args.defaults=[];fn.args.kw_defaults=[None]*len(fn.args.kwonlyargs)
    if mutated:
        assert isinstance(fn.body[0],ast.Expr) and isinstance(fn.body[0].value,ast.Call) and isinstance(fn.body[0].value.func,ast.Name) and fn.body[0].value.func.id=='refuse_unbound_effect'
        fn.body=fn.body[1:] or [ast.Pass()]
    module=ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[]))
    env={'refuse_unbound_effect':refusal,'httpx':Spy(),'os':Spy(),'protocol':Spy()}
    exec(compile(module,str(APP/rel),'exec'),env)
    func=env[name]
    args=[Spy() for _ in fn.args.args];kwargs={a.arg:Spy() for a in fn.args.kwonlyargs}
    return func,args,kwargs

def assert_entry_refuses(rel,name,line,mutated=False):
    Spy.calls=0;fn,args,kwargs=isolated_entry(rel,name,line,mutated)
    with pytest.raises(PermissionError,match='EFFECT_UNBOUND_REFUSED'):
        out=fn(*args,**kwargs)
        if asyncio.iscoroutine(out):asyncio.run(out)
    assert Spy.calls==0

@pytest.mark.parametrize('rel,name,line',ENTRY_CASES)
def test_actual_entry_refuses_before_provider_or_account_access(rel,name,line):
    assert_entry_refuses(rel,name,line)

@pytest.mark.parametrize('rel,name,line',ENTRY_CASES)
def test_removing_each_actual_entry_refusal_is_killed(rel,name,line):
    try:assert_entry_refuses(rel,name,line,mutated=True)
    except (ProviderTouched,NameError,AttributeError,TypeError,pytest.fail.Exception):pass
    else:pytest.fail('gate-removal mutant survived')


def test_browser_manager_returns_only_read_wrapper_and_wrap_removal_is_killed():
    source=(APP/'modules/m13_browser_agent/playwright_adapter.py').read_text()
    tree=ast.parse(source)
    fn=next(n for n in ast.walk(tree) if isinstance(n,ast.AsyncFunctionDef) and n.name=='page')
    def check(fn):
        returns=[n.value for n in ast.walk(fn) if isinstance(n,ast.Return)]
        assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='_ReadOnlyPage' for n in returns)
    check(fn)
    mutant=copy.deepcopy(fn)
    for n in ast.walk(mutant):
        if isinstance(n,ast.Return) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='_ReadOnlyPage':n.value=n.value.args[0]
    with pytest.raises(AssertionError):check(mutant)


def test_daemon_generic_click_fill_refusal_and_condition_removal_is_killed():
    from enum import Enum
    class Kind(Enum):FILL='fill';CLICK_NAV='click_nav';CLICK_SUBMIT='click_submit'
    tree=ast.parse((APP/'modules/m13_browser_agent/pc_daemon/daemon.py').read_text())
    fn=next(n for n in ast.walk(tree) if isinstance(n,ast.AsyncFunctionDef) and n.name=='_run')
    guard=next(n for n in fn.body if isinstance(n,ast.If) and any(isinstance(x,ast.Call) and isinstance(x.func,ast.Name) and x.func.id=='refuse_unbound_effect' for x in ast.walk(n)))
    def check(stmt):
        code=compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(stmt)],type_ignores=[])),'daemon-guard','exec')
        for kind in (Kind.FILL,Kind.CLICK_NAV):
            with pytest.raises(PermissionError,match='EFFECT_UNBOUND_REFUSED'):
                exec(code,{'kind':kind,'CommandKind':Kind,'refuse_unbound_effect':refusal})
    check(guard)
    mutant=copy.deepcopy(guard);mutant.test=ast.Constant(False)
    with pytest.raises(pytest.fail.Exception):check(mutant)


def test_imported_http_adapters_zero_transport_calls():
    import httpx
    from app.modules.m04_research_scientist.tools.adapters import GalaxyAdapter
    from app.modules.m10_email_assistant.gmail import HttpxGmailClient
    from app.modules.m11_calendar_intelligence.google_calendar import HttpxGoogleCalendarClient
    from app.modules.m24_billing.stripe_client import StripeClient
    calls=[]
    def handler(request):
        calls.append(request)
        raise AssertionError('provider transport reached')
    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            gmail=HttpxGmailClient(http);cal=HttpxGoogleCalendarClient(http)
            stripe=StripeClient('sk_test_offline',transport=httpx.MockTransport(handler))
            for call in (
                lambda:GalaxyAdapter('https://galaxy.invalid','offline').run_workflow('workflow','history',{}),
                lambda:gmail.watch('offline','topic'),
                lambda:cal.watch('offline','calendar',channel_id='channel',address='https://offline.invalid',token='offline'),
                lambda:cal.stop_channel('offline',channel_id='channel',resource_id='resource'),
                lambda:stripe.create_checkout(None,'https://offline.invalid','https://offline.invalid','tenant','arbitrary-id'),
                lambda:stripe.cancel_subscription('subscription','arbitrary-id'),
                lambda:stripe.create_invoice('customer','description',100,'usd','arbitrary-id'),
            ):
                with pytest.raises(PermissionError,match='EFFECT_UNBOUND_REFUSED'):await call()
    asyncio.run(check());assert calls==[]


def test_imported_browser_wrapper_zero_driver_writes_and_reads_preserved():
    from app.modules.m13_browser_agent.playwright_adapter import _ReadOnlyPage
    class Locator:
        async def fill(self,value):raise AssertionError('driver fill reached')
        async def click(self):raise AssertionError('driver click reached')
        async def input_value(self):return 'read value'
    class Page:
        url='https://offline.invalid'
        def locator(self,selector):return Locator()
        async def content(self):return '<p>read</p>'
    async def check():
        page=_ReadOnlyPage(Page())
        assert await page.content()=='<p>read</p>'
        assert await page.locator('input').input_value()=='read value'
        for call in (lambda:page.locator('input').fill('x'),lambda:page.locator('button').click()):
            with pytest.raises(PermissionError,match='EFFECT_UNBOUND_REFUSED'):await call()
        for name in ('raw','evaluate','mouse','keyboard','context'):
            with pytest.raises(AttributeError):getattr(page,name)
    asyncio.run(check())


def test_shared_refusal_boundary_and_removal_mutant_is_killed():
    from app.runtime.guardrails.scoped_refusal import refuse_unbound_effect
    def check(fn):
        with pytest.raises(PermissionError,match='EFFECT_UNBOUND_REFUSED'):
            fn('offline effect')
    check(refuse_unbound_effect)
    with pytest.raises(pytest.fail.Exception):check(lambda effect:None)
