from concurrent.futures import ThreadPoolExecutor
from threading import Event
from app.modules.m10_email_assistant.lane_store import EmailStore

def test_second_transaction_waits_then_survives_rollback():
 s=EmailStore();s._db.execute('CREATE TABLE audit_marker(name TEXT)');s._db.commit()
 a_open,b_started,release=Event(),Event(),Event();b_entered=Event()
 def a():
  try:
   with s.transaction() as db:
    db.execute("INSERT INTO audit_marker VALUES ('A')");a_open.set();assert release.wait(5);raise RuntimeError('rollback')
  except RuntimeError:pass
 def b():
  assert a_open.wait(5);b_started.set()
  with s.transaction() as db:
   b_entered.set();db.execute("INSERT INTO audit_marker VALUES ('B')")
 with ThreadPoolExecutor(max_workers=2) as ex:
  fa=ex.submit(a);fb=ex.submit(b)
  try:
   assert b_started.wait(5)
   assert not b_entered.wait(.1),'B entered transaction before A ended'
  finally:release.set()
  fa.result(timeout=5);fb.result(timeout=5)
 assert [r[0] for r in s._db.execute('SELECT name FROM audit_marker').fetchall()]==['B']

def test_baseexception_rollback_preserves_prior_commit_and_depth():
 s=EmailStore();s._db.execute('CREATE TABLE audit_marker(name TEXT)');s._db.commit()
 try:
  with s.transaction() as db:
   db.execute("INSERT INTO audit_marker VALUES ('lost')")
   with s.transaction():raise KeyboardInterrupt('stop')
 except KeyboardInterrupt:pass
 with s.transaction() as db:db.execute("INSERT INTO audit_marker VALUES ('saved')")
 assert [r[0] for r in s._db.execute('SELECT name FROM audit_marker').fetchall()]==['saved']
 assert s._tx_depth==0
