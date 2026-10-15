import threading, time, inspect
from datetime import datetime, timezone
from app.modules.m10_email_assistant.lane_store import EmailStore
from app.modules.m10_email_assistant.lane_models import FollowUp, FollowUpStatus
T=datetime(2026,1,1,tzinfo=timezone.utc)

def barrier_case():
    """Real public write save_followup is paused after its execute, before its _commit.
    A transaction on another thread that rolls back must neither join it nor erase it."""
    store=EmailStore(); store._db.execute('CREATE TABLE audit_marker (name TEXT)'); store._db.commit()
    paused,release=threading.Event(),threading.Event(); real=store._commit; order=[]
    def hooked():
        if threading.current_thread().name=="writer":
            paused.set(); release.wait(3); order.append('writer-commit')
        real()
    store._commit=hooked
    f=FollowUp("f1","t1","mb1","th1",T,FollowUpStatus.OPEN,"r",T)
    def writer(): store.save_followup(f)
    def txn():
        assert paused.wait(3)
        try:
            with store.transaction() as db:
                order.append('txn-entered'); db.execute("INSERT INTO audit_marker VALUES ('tx')"); raise RuntimeError('rb')
        except RuntimeError: pass
    th=[threading.Thread(target=writer,name="writer"),threading.Thread(target=txn)]
    for t in th: t.start()
    time.sleep(0.3); release.set()
    for t in th: t.join(5)
    n=store._db.execute("SELECT count(*) FROM followups").fetchone()[0]
    return n, order

def test_peer_wholecall_barrier():
    n,order=barrier_case()
    assert n==1, ("standalone write lost", n, order)
    assert order==['writer-commit','txn-entered'], order
    missing=[k for k,v in inspect.getmembers(EmailStore,inspect.isfunction) if not k.startswith('_') and k!='transaction' and not hasattr(v,'__wrapped__')]
    assert not missing, missing
if __name__=="__main__":
    try: run(); print("BARRIER OK")
    except Exception as e: print("BARRIER FAIL", type(e).__name__, e)
