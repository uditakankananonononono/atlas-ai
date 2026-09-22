from app.modules.m06_social_media_manager.service import Service,MemorySocialRepository
class A:
 def __init__(s):s.items=[]
 def put(s,x):s.items.append(x);return x
async def gen(*args):return 'm','x'
def test_central_approval_boundary_adds_tenant():
 a=A();svc=Service(approval_store=a,generate=gen,repository=MemorySocialRepository(),tenant_id='t1');request=svc._file_approval(action_type='publish',payload={'plan_id':'p'});assert request.payload=={'tenant_id':'t1','plan_id':'p'}
def test_empty_tenant_fails_closed():
 try:Service(approval_store=A(),generate=gen,repository=MemorySocialRepository(),tenant_id=' ')
 except ValueError as e:assert 'tenant_id' in str(e)
 else:raise AssertionError
