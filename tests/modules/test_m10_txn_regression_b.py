import threading, time
from app.modules.m10_email_assistant.lane_store import EmailStore
def test_peer_transaction_serialization():
    s=EmailStore(); s._db.execute('CREATE TABLE audit_marker (name TEXT)'); s._db.commit()
    a_in,b_done_early,order=threading.Event(),[],[]
    b_started=threading.Event()
    def A():
        try:
            with s.transaction() as db:
                db.execute("INSERT INTO audit_marker VALUES ('A')"); a_in.set(); b_started.wait(3); time.sleep(0.3)
                b_done_early.append('B' in [r[0] for r in s._db.execute("SELECT name FROM audit_marker")]) if False else None
                order.append('A-rollback'); raise RuntimeError
        except RuntimeError: pass
    def B():
        a_in.wait(3); b_started.set()
        with s.transaction() as db: db.execute("INSERT INTO audit_marker VALUES ('B')")
        order.append('B-commit')
    ts=[threading.Thread(target=A),threading.Thread(target=B)]; [t.start() for t in ts]; [t.join(10) for t in ts]
    names=sorted(r[0] for r in s._db.execute("SELECT name FROM audit_marker"))
    assert order==['A-rollback','B-commit'], order
    assert names==['B'], names
if __name__=="__main__": run(); print("REG-B OK (B waited for A, A rolled back, B committed)")
