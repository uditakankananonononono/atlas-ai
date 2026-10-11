"""Draft only until parent/core confirmed. Local fixtures, no network."""
import importlib.util
from pathlib import Path
import tempfile,hashlib,unittest
from unittest import mock
from types import SimpleNamespace
import os
CORE=Path(__file__).resolve().parents[2]/'backend/app/core/project_deliverable_contract.py'
s=importlib.util.spec_from_file_location('F12',CORE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def packet(artifacts=None):
 return {'project_id':'atlas','domain':'software','source_lines':['P76|L64'],'repository':'https://example.test/repo','requested_targets':{'datasets':0,'project_tools':0,'program_tools':0},'artifacts':artifacts or [],'benchmark':None}
def artifact(path='file',data=b'a',id='a'):
 return {'id':id,'kind':'code','path':path,'sha256':hashlib.sha256(data).hexdigest()}
class BoundaryPins(unittest.TestCase):
 def test_group1_default_10mb_exact_and_over(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'file';data=b'a'*10000000;p.write_bytes(data)
   self.assertEqual(m.check_deliverables(td,packet([artifact(data=data)]))['artifacts'][0]['status'],'FILE_HASH_MATCH')
   p.write_bytes(data+b'a')
   self.assertEqual(m.check_deliverables(td,packet([artifact(data=data+b'a')]))['artifacts'][0]['status'],'TOO_LARGE')
 def test_group2_file_byte_limits(self):
  with tempfile.TemporaryDirectory() as td:
   for n in [1,1000000000]:self.assertEqual(m.check_deliverables(td,packet(),max_file_bytes=n)['measured_artifact_count'],0)
   for n in [0,1000000001]:
    with self.assertRaises(m.ContractError):m.check_deliverables(td,packet(),max_file_bytes=n)
 def test_group3_artifact_cardinality(self):
  d=packet([artifact(path='f'+str(i),id='a'+str(i)) for i in range(10000)])
  self.assertEqual(len(m.validate_spec(d)['artifacts']),10000)
  d['artifacts'].append(artifact(path='overflow',id='overflow'))
  with self.assertRaises(m.ContractError):m.validate_spec(d)
 def test_group4_target_exact_bounds(self):
  for key in ['datasets','project_tools','program_tools']:
   for n in [0,1000000]:
    d=packet();d['requested_targets'][key]=n;self.assertEqual(m.validate_spec(d)['requested_targets'][key],n)
   for n in [-1,1000001]:
    d=packet();d['requested_targets'][key]=n
    with self.assertRaises(m.ContractError):m.validate_spec(d)
 def test_group7_repository_text_errors(self):
  for text in ['x'*2001,'https://example.test/'+chr(31),'https://example.test/'+chr(127),5,None,[]]:
   d=packet();d['repository']=text
   with self.assertRaises(m.ContractError) as cm:m.validate_spec(d)
   self.assertEqual(str(cm.exception),'Invalid text')
 def test_group10_artifact_identity_path_and_benchmark_ref(self):
  for a in [artifact(id='bad'+chr(31)),artifact(id=5),artifact(path='x'*2001)]:
   with self.assertRaises(m.ContractError):m.validate_spec(packet([a]))
  with self.assertRaises(m.ContractError):m.validate_spec(packet([artifact(path='one'),artifact(path='two')]))
  d=packet([artifact()]);d['benchmark']={'comparator':'x','metric':'y','dataset_artifact_id':'unknown','result_artifact_id':'a','protocol':'z'}
  with self.assertRaises(m.ContractError):m.validate_spec(d)
 def test_group11_container_types(self):
  for d in [5,[]]:
   with self.assertRaises(m.ContractError):m.validate_spec(d)
  for key in ['project_id','requested_targets','benchmark']:
   d=packet();d[key]=5 if key=='project_id' else ['datasets','project_tools','program_tools'] if key=='requested_targets' else ['comparator','metric','dataset_artifact_id','result_artifact_id','protocol']
   with self.assertRaises(m.ContractError):m.validate_spec(d)
  d=packet();d['source_lines']='P76|L64'
  with self.assertRaises(m.ContractError) as cm:m.validate_spec(d)
  self.assertEqual(str(cm.exception),'Source references required')
 def test_group12_empty_exact_and_changed_mtime(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'file';p.write_bytes(b'')
   self.assertEqual(m.check_deliverables(td,packet([artifact(data=b'')]))['artifacts'][0]['status'],'EMPTY_FILE')
   p.write_bytes(b'a')
   wrong=artifact();wrong['sha256']='0'*64
   self.assertEqual(m.check_deliverables(td,packet([wrong]))['artifacts'][0]['status'],'HASH_MISMATCH')
   real_fstat=os.fstat;calls=[]
   def changed(fd):
    st=real_fstat(fd);calls.append(fd)
    return SimpleNamespace(st_mode=st.st_mode,st_size=st.st_size,st_mtime_ns=st.st_mtime_ns+(1 if len(calls)==2 else 0),st_ctime_ns=st.st_ctime_ns,st_dev=st.st_dev,st_ino=st.st_ino)
   with mock.patch.object(m.os,'fstat',side_effect=changed):
    self.assertEqual(m.check_deliverables(td,packet([artifact()]))['artifacts'][0]['status'],'CHANGED_DURING_READ')

 def test_group5_port_bounds(self):
  for port in [1,65535]:
   d=packet();d['repository']='https://example.test:'+str(port)+'/a';m.validate_spec(d)
  d=packet();d['repository']='https://example.test:0/a'
  with self.assertRaises(m.ContractError):m.validate_spec(d)
 def test_group6_hostname253_and254(self):
  host='.'.join(['a'*63]*3+['b'*61])
  self.assertEqual(len(host),253)
  d=packet();d['repository']='https://'+host+'/a';m.validate_spec(d)
  d['repository']='https://'+host+'b/a'
  with self.assertRaises(m.ContractError):m.validate_spec(d)
 def test_group8_url_backslash(self):
  d=packet();d['repository']='https://example.test/a\\b'
  with self.assertRaises(m.ContractError):m.validate_spec(d)
 def test_group9_password_only_userinfo(self):
  d=packet();d['repository']='https://:pw@example.test/a'
  with self.assertRaises(m.ContractError):m.validate_spec(d)
if __name__=='__main__':unittest.main()
