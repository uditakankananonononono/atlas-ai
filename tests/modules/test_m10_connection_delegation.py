"""SQLite helper delegation preserves instrumentation and lock ownership."""
import threading
from app.modules.m10_email_assistant.lane_store import EmailStore


def test_trace_callback_and_connection_metadata_are_delegated():
    store = EmailStore()
    seen = []
    store._db.set_trace_callback(seen.append)
    store._db.execute("SELECT 42").fetchone()
    assert any("SELECT 42" in sql for sql in seen)
    assert isinstance(store._db.total_changes, int)
    store._db.set_trace_callback(None)


def test_delegated_method_waits_for_transaction_lock():
    store = EmailStore()
    entered, done = threading.Event(), threading.Event()
    def worker():
        entered.set()
        store._db.set_trace_callback(None)
        done.set()
    with store.transaction():
        thread = threading.Thread(target=worker)
        thread.start()
        assert entered.wait(1)
        assert not done.wait(0.05)
    thread.join(2)
    assert not thread.is_alive() and done.is_set()


def test_delegated_call_runs_under_the_transaction_lock():
    # The existing lock-wait pin resolves the delegated attribute inside the
    # transaction, so it only proves the lookup is locked. A callable resolved
    # before the transaction must still serialize its call under the lock;
    # an unwrapped callable would run straight through.
    store = EmailStore()
    delegated = store._db.set_trace_callback
    entered, done = threading.Event(), threading.Event()
    def worker():
        entered.set()
        delegated(None)
        done.set()
    with store.transaction():
        thread = threading.Thread(target=worker)
        thread.start()
        assert entered.wait(1)
        assert not done.wait(0.05)
    thread.join(2)
    assert not thread.is_alive() and done.is_set()
