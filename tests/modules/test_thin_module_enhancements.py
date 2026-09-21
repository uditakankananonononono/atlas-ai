from datetime import datetime,timezone,timedelta
import pytest
from app.modules.m21_claire.local_client_protocol import PairingService
from app.modules.m15_document_generator.service import Service
from app.modules.m15_document_generator.schemas import *
class A:
 def put(self,x):return x
def test_m15_preflight_finds_duplicate_citations_and_overflow():
 s=Service(A());v=s.create_version('t','d',CreateVersionRequest(title='Deck',format='pptx',template_id='base',content={'slides':[{'title':'One','body':'x'*1300}]},citations=[Citation(key='a',title='A'),Citation(key='a',title='B')]))
 out=s.preflight(v);assert not out['ready'] and any('unique' in x for x in out['issues']) and out['warnings']
def test_m21_pairing_expires_and_requires_capabilities():
 p=PairingService();c=p.challenge();
 with pytest.raises(ValueError):p.confirm(c.server_nonce,c.code,'pc','fp',set())
 p=PairingService();c=p.challenge();d=p.confirm(c.server_nonce,c.code,'pc','fp',{'read_file'});assert not d.revoked;p.revoke(d.id);assert d.revoked
