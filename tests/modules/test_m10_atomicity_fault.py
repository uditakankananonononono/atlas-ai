import unittest
from datetime import datetime, timezone, timedelta
from app.modules.m10_email_assistant.lane_store import EmailStore
from app.modules.m10_email_assistant.lane_service import EmailAssistant
from app.modules.m10_email_assistant.lane_models import MailboxRef, ProviderMessage, DraftStatus, SendResult
from app.modules.m10_email_assistant.lane_provider import ProviderPage

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
MB = MailboxRef("t1", "mb1", "me@example.com", "fake")

class Prov:
    def __init__(self, n=1): self.n, self.sent = n, []
    def sync(self, mailbox, cursor, limit):
        ms = tuple(ProviderMessage("p%d" % i, "th%d" % i, "bob@example.com", ("me@example.com",), "Hello", "please reply by Friday", T0 + timedelta(minutes=i), {}, None) for i in range(self.n))
        return ProviderPage(ms, "c1")
    def send(self, mailbox, **kw):
        self.sent.append(kw); return SendResult("prov-1", T0)

def make():
    s = EmailStore(); a = EmailAssistant(s, Prov(), clock=lambda: T0 + timedelta(days=1))
    a.sync(MB); mid = a.store.thread  # noqa
    row = s._db.execute("SELECT id FROM messages").fetchone()[0]
    d = a.create_reply_draft(MB, row, "Thanks, will do")
    return s, a, d

class Boom(Exception): pass

class Atomicity(unittest.TestCase):
    def test_request_approval_failure_leaves_no_pending_row(self):
        s, a, d = make()
        orig = s.update_draft
        def bad(*x, **k):
            if k.get("status") == DraftStatus.PENDING_APPROVAL: raise Boom()
            return orig(*x, **k)
        s.update_draft = bad
        with self.assertRaises(Boom): a.request_approval("t1", d.id, "u")
        s.update_draft = orig
        self.assertIsNone(s.pending_approval("t1", d.id))
        self.assertEqual(s.get_draft("t1", d.id).status, DraftStatus.DRAFT)
        a.request_approval("t1", d.id, "u")  # retry works
        self.assertEqual(s.get_draft("t1", d.id).status, DraftStatus.PENDING_APPROVAL)

    def test_decide_failure_after_status_write_leaves_approval_pending(self):
        s, a, d = make()
        ap = a.request_approval("t1", d.id, "u")
        orig = s.update_draft
        def bad(*x, **k):
            if k.get("status") == DraftStatus.APPROVED: raise Boom()
            return orig(*x, **k)
        s.update_draft = bad
        with self.assertRaises(Boom): a.decide("t1", ap.id, "boss", True)
        s.update_draft = orig
        self.assertIsNotNone(s.pending_approval("t1", d.id))
        self.assertEqual(s.get_draft("t1", d.id).status, DraftStatus.PENDING_APPROVAL)
        a.decide("t1", ap.id, "boss", True)
        self.assertEqual(s.get_draft("t1", d.id).status, DraftStatus.APPROVED)

    def test_stale_revision_decision_does_not_record_approval(self):
        s, a, d = make()
        ap = a.request_approval("t1", d.id, "u")
        s._db.execute("UPDATE drafts SET revision=revision+1 WHERE id=?", (d.id,)); s._db.commit()
        with self.assertRaises(RuntimeError): a.decide("t1", ap.id, "boss", True)
        row = s._db.execute("SELECT status FROM approvals WHERE id=?", (ap.id,)).fetchone()[0]
        self.assertEqual(row, "pending")

    def test_sync_triage_failure_does_not_advance_cursor_or_store_messages(self):
        s = EmailStore(); a = EmailAssistant(s, Prov(2))
        def bad(m): raise Boom()
        a.triage.classify = bad
        with self.assertRaises(Boom): a.sync(MB)
        self.assertIsNone(s.cursor("t1", "mb1"))
        self.assertEqual(s._db.execute("SELECT count(*) FROM messages").fetchone()[0], 0)

    def test_sync_store_failure_after_page_write_rolls_back_page_and_cursor(self):
        for target in ("save_triage", "complete_followups_for_thread"):
            s = EmailStore(); a = EmailAssistant(s, Prov(2))
            def bad(*x, **k): raise Boom()
            setattr(s, target, bad)
            with self.assertRaises(Boom): a.sync(MB)
            self.assertIsNone(s.cursor("t1", "mb1"), target)
            self.assertEqual(s._db.execute("SELECT count(*) FROM messages").fetchone()[0], 0, target)
            delattr(s, target)
            self.assertEqual(a.sync(MB).imported, 2)  # retry sees the page again

    def test_happy_paths_unchanged(self):
        s, a, d = make()
        ap = a.request_approval("t1", d.id, "u"); a.decide("t1", ap.id, "boss", True)
        out = a.send_approved(MB, d.id)
        self.assertEqual(out.status, DraftStatus.SENT)
        self.assertEqual(s.cursor("t1", "mb1"), "c1")
        r = a.sync(MB); self.assertEqual((r.imported, r.updated), (0, 1))
        with self.assertRaises(RuntimeError): a.decide("t1", ap.id, "boss", False)

    def test_wrong_mailbox_cannot_send_or_draft(self):
        s, a, d = make()
        ap = a.request_approval("t1", d.id, "u"); a.decide("t1", ap.id, "boss", True)
        with self.assertRaises(KeyError): a.send_approved(MailboxRef("t1", "other", "o@example.com", "fake"), d.id)
        with self.assertRaises(KeyError): a.send_approved(MailboxRef("t2", "mb1", "me@example.com", "fake"), d.id)
        self.assertEqual(a.provider.sent, [])

if __name__ == "__main__": unittest.main()
