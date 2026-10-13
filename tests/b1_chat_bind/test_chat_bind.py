import copy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"backend/app/modules/m20_general_cognitive_worker/c30_b1"))
import unittest
from app.modules.m20_general_cognitive_worker.c30_b1.chat_bind import ChatBinder, Refused, make_snapshot, split_spans


def msg(i='m1', body='Build Atlas. Test it!', **kw):
    return dict(message_id=i, body=body, ts='2026-10-01T10:00:00+00:00', author='user', service='WhatsApp', conversation_id='owner', **kw)


def snap(rows):
    return make_snapshot(rows, as_of='2026-10-11T10:00:00+00:00', observed_total=len(rows), history_complete=False)


class Tests(unittest.TestCase):
    def test_lossless_spans(self):
        text=' Build m20.3\nNext?  Done! '
        spans=split_spans(text)
        self.assertEqual(''.join(s['text'] for s in spans), text)
        self.assertTrue(any('m20.3' in s['text'] for s in spans))

    def test_only_owner_channels(self):
        for field,value in [('author','agent'),('service','agent_peer'),('service','mobile_chat'),('service','agent_chat')]:
            row=msg(); row[field]=value
            with self.assertRaises(Refused): snap([row])

    def test_duplicate_and_count(self):
        with self.assertRaises(Refused): snap([msg(),msg()])
        with self.assertRaises(Refused): make_snapshot([msg()],as_of='2026-10-11T10:00:00+00:00',observed_total=2,history_complete=False)

    def test_time_and_future(self):
        row=msg();row['ts']='not a date'
        with self.assertRaises(Refused):snap([row])
        row['ts']='2026-12-01T10:00:00+00:00'
        with self.assertRaises(Refused):snap([row])

    def test_unmapped_fails(self):
        b=ChatBinder(snap([msg()]))
        self.assertEqual(b.report()['refusal'],'PLAN_REFUSED_UNMAPPED')
        self.assertEqual(b.report()['counts']['UNMAPPED'],2)
        self.assertFalse(b.report()['passed'])

    def test_implemented_requires_evidence(self):
        b=ChatBinder(snap([msg(body='Build Atlas')]))
        sid=b.spans[0]['span_id']
        with self.assertRaises(Refused):b.bind(sid,'IMPLEMENTED', {'unit':'B1'})
        b.bind(sid,'IMPLEMENTED',dict(unit='B1',tests='test_b1',mutation='battery-1',commit='a'*40))
        self.assertTrue(b.report()['passed'])
        self.assertEqual(b.report()['scope']['data_source'],'supplied owner-only DB snapshot')

    def test_stops_pin_later_exact_span(self):
        a=msg(body='Build student portfolio')
        z=msg('m2',body='Stop student portfolio');z['ts']='2026-10-02T10:00:00+00:00'
        b=ChatBinder(snap([a,z]));first=b.spans[0]['span_id'];last=b.spans[1]['span_id']
        with self.assertRaises(Refused):b.bind(first,'STOPPED_BY_USER',dict(pin='fake',topic='student-portfolio'))
        b.bind(first,'STOPPED_BY_USER',dict(pin=last,topic='student-portfolio'))
        self.assertEqual(b.report()['counts']['STOPPED_BY_USER'],1)
        self.assertEqual(b.execution_gate(first),'PLAN_REFUSED_STOPPED')

    def test_earlier_pin_rejected(self):
        a=msg(body='Stop doc200');z=msg('m2',body='Build doc200');z['ts']='2026-10-02T10:00:00+00:00'
        b=ChatBinder(snap([a,z]))
        with self.assertRaises(Refused):b.bind(b.spans[1]['span_id'],'STOPPED_BY_USER',dict(pin=b.spans[0]['span_id'],topic='doc200'))

    def test_resume_is_explicit(self):
        rows=[msg(body='Build doc200'),msg('m2',body='Stop doc200'),msg('m3',body='Resume doc200')]
        rows[1]['ts']='2026-10-02T10:00:00+00:00';rows[2]['ts']='2026-10-03T10:00:00+00:00'
        b=ChatBinder(snap(rows));ids=[s['span_id'] for s in b.spans]
        b.bind(ids[0],'STOPPED_BY_USER',dict(pin=ids[1],topic='doc200'))
        b.revise(ids[0],'UNMAPPED',dict(pin=ids[2],reason='explicit resume'))
        self.assertEqual(b.execution_gate(ids[0]),'PLAN_REFUSED_UNMAPPED')
        self.assertEqual(len(b.audit),2)

    def test_bad_substitute(self):
        b=ChatBinder(snap([msg(body='Build anything')]))
        with self.assertRaises(Refused):b.bind(b.spans[0]['span_id'],'REFUSED_WITH_SUBSTITUTE',dict(substitute='X99',unit='C5'))
        b.bind(b.spans[0]['span_id'],'REFUSED_WITH_SUBSTITUTE',dict(substitute='X8',unit='C5',reason='bounded substitute'))

    def test_exclusion_review_is_not_automatic(self):
        b=ChatBinder(snap([msg(body='Hi')]))
        with self.assertRaises(Refused):b.exclude(b.spans[0]['span_id'],'')
        b.exclude(b.spans[0]['span_id'],'reviewed greeting, no request')
        self.assertTrue(b.report()['passed'])
        self.assertEqual(b.report()['reviewed_nonrequests'],1)

    def test_unknown_span_and_state(self):
        b=ChatBinder(snap([msg()]))
        with self.assertRaises(Refused):b.bind('missing','UNMAPPED',{})
        with self.assertRaises(Refused):b.bind(b.spans[0]['span_id'],'DONE',{})

    def test_private_payload_not_public_report(self):
        b=ChatBinder(snap([msg(body='PRIVATE_SENTINEL')]))
        self.assertNotIn('PRIVATE_SENTINEL',str(b.report()))
        self.assertIn('PRIVATE_SENTINEL',str(b.private_ledger()))

    def test_database_reconciliation(self):
        b=ChatBinder(snap([msg()]))
        self.assertTrue(b.reconcile([msg()]))
        changed=msg();changed['body']='changed'
        with self.assertRaises(Refused):b.reconcile([changed])
        with self.assertRaises(Refused):b.reconcile([])

    def test_no_snapshot_tamper(self):
        s=snap([msg()]);s['rows'][0]['body']='tamper'
        with self.assertRaises(Refused):ChatBinder(s)

    def test_policy_rejects_side_effects(self):
        with self.assertRaises(Refused):ChatBinder(snap([msg()]),action='outreach')

    def test_empty_history_is_not_complete(self):
        b=ChatBinder(snap([]))
        self.assertFalse(b.report()['passed'])

    def test_existing_bind_needs_revision(self):
        b=ChatBinder(snap([msg(body='Build Atlas')]))
        sid=b.spans[0]['span_id'];b.bind(sid,'UNMAPPED',{})
        with self.assertRaises(Refused):b.bind(sid,'UNMAPPED',{})

if __name__=='__main__':unittest.main()

class DatabaseTests(unittest.TestCase):
    def test_recomputed_from_db(self):
        import sqlite3
        from app.modules.m20_general_cognitive_worker.c30_b1.db_chat_bind import ingest, reconcile
        db=sqlite3.connect(':memory:')
        db.execute('CREATE TABLE phone_messages (message_id TEXT, body TEXT, ts TEXT, author TEXT, service TEXT, conversation_id TEXT)')
        for row in (msg(),dict(msg('agent'),author='agent'),dict(msg('internal'),service='agent_chat')):
            db.execute('INSERT INTO phone_messages VALUES (?,?,?,?,?,?)',tuple(row[k] for k in ('message_id','body','ts','author','service','conversation_id')))
        b=ChatBinder(ingest(db,as_of='2026-10-11T10:00:00+00:00'))
        self.assertEqual(b.report()['source_messages'],1)
        self.assertTrue(reconcile(db,b))
        db.execute("UPDATE phone_messages SET body='changed' WHERE message_id='m1'")
        with self.assertRaises(Refused):reconcile(db,b)

class GuardTests(unittest.TestCase):
    def test_schema_guards(self):
        for row in ([],dict(msg(),extra='bad'),dict(msg(),body=None),dict(msg(),message_id='')):
            with self.assertRaises(Refused):snap([row])
    def test_naive_time(self):
        with self.assertRaises(Refused):snap([dict(msg(),ts='2026-10-01T10:00:00')])
    def test_no_pin_or_topic(self):
        b=ChatBinder(snap([msg(body='Build doc230'),dict(msg('m2',body='Stop doc230'),ts='2026-10-02T10:00:00+00:00')]))
        for e in ({},{'pin':b.spans[1]['span_id']}):
            with self.assertRaises(Refused):b.bind(b.spans[0]['span_id'],'STOPPED_BY_USER',e)
    def test_same_pin_and_revision_missing(self):
        b=ChatBinder(snap([msg(body='Build doc230')]))
        sid=b.spans[0]['span_id']
        with self.assertRaises(Refused):b.bind(sid,'STOPPED_BY_USER',dict(pin=sid,topic='doc230'))
        with self.assertRaises(Refused):b.revise(sid,'UNMAPPED',dict(pin=sid,reason='bad'))
    def test_revision_requires_newer_pin_and_reason(self):
        rows=[msg(body='Build doc200'),dict(msg('m2',body='Stop doc200'),ts='2026-10-02T10:00:00+00:00'),dict(msg('m3',body='Resume doc200'),ts='2026-10-03T10:00:00+00:00')]
        b=ChatBinder(snap(rows));ids=[s['span_id'] for s in b.spans]
        b.bind(ids[0],'STOPPED_BY_USER',dict(pin=ids[1],topic='doc200'))
        for e in ({'pin':ids[1],'reason':'stale'},{'pin':ids[2]}):
            with self.assertRaises(Refused):b.revise(ids[0],'UNMAPPED',e)

class AdditionalTests(unittest.TestCase):
    def test_pin_must_be_stop_worded(self):
        rows=[msg(body='Build Atlas'),dict(msg('m2',body='Hello'),ts='2026-10-02T10:00:00+00:00')]
        b=ChatBinder(snap(rows))
        with self.assertRaises(Refused):b.bind(b.spans[0]['span_id'],'STOPPED_BY_USER',dict(pin=b.spans[1]['span_id'],topic='Atlas'))
    def test_db_offsets(self):
        import sqlite3
        from app.modules.m20_general_cognitive_worker.c30_b1.db_chat_bind import ingest
        db=sqlite3.connect(':memory:')
        db.execute('CREATE TABLE phone_messages (message_id TEXT, body TEXT, ts TEXT, author TEXT, service TEXT, conversation_id TEXT)')
        db.execute('INSERT INTO phone_messages VALUES (?,?,?,?,?,?)',('m1','Build','2026-10-01T15:30:00+05:30','user','WhatsApp','owner'))
        self.assertEqual(ingest(db,as_of='2026-10-01T10:01:00+00:00')['observed_total'],1)

class RouteTests(unittest.TestCase):
    def test_tenants_and_paths(self):
        from app.modules.m20_general_cognitive_worker.c30_b1.route_adapter import Routes
        r=Routes({})
        with self.assertRaises(Refused):r.dispatch('POST','/api/v1/c30/chat-bind/run','',snap([msg()]))
        with self.assertRaises(Refused):r.dispatch('GET','/api/v1/c30/chat-bind/report','b')
        self.assertEqual(r.dispatch('POST','/api/v1/c30/chat-bind/run','a',snap([msg()]))['source_messages'],1)
        self.assertEqual(r.dispatch('GET','/api/v1/c30/chat-bind/report','a')['counts']['UNMAPPED'],2)
        with self.assertRaises(Refused):r.dispatch('GET','/api/v1/c30/chat-bind/report','b')
        with self.assertRaises(Refused):r.dispatch('GET','/private','a')

class MissingRevisionTest(unittest.TestCase):
    def test_no_previous_binding(self):
        rows=[msg(body='Build Atlas'),dict(msg('m2',body='Resume Atlas'),ts='2026-10-02T10:00:00+00:00')]
        b=ChatBinder(snap(rows))
        with self.assertRaises(Refused):b.revise(b.spans[0]['span_id'],'UNMAPPED',dict(pin=b.spans[1]['span_id'],reason='resume'))

class AuditRepairTests(unittest.TestCase):
    def binder(self):
        return ChatBinder(snap([msg(body='Build Atlas'),dict(msg('m2',body='Pause Atlas'),ts='2026-10-02T10:00:00+00:00')]))

    def test_execution_state_returns(self):
        for state, expected in [('PARKED_BY_USER','PLAN_REFUSED_STOPPED'),('SUPERSEDED','PLAN_REFUSED_STOPPED'),('UNMAPPED','PLAN_REFUSED_UNMAPPED'),('IMPLEMENTED','B1_CLASSIFIED_NOT_EXECUTION_AUTHORITY')]:
            b=self.binder();sid=b.spans[0]['span_id']
            e=dict(pin=b.spans[1]['span_id'],topic='Atlas') if state in {'PARKED_BY_USER','SUPERSEDED'} else {}
            if state=='IMPLEMENTED':e=dict(unit='B1',tests='test',mutation='battery',commit='a'*40)
            b.bind(sid,state,e)
            self.assertEqual(b.execution_gate(sid),expected)

    def test_revise_validates_state_and_evidence(self):
        for state,evidence in [('DONE',{}),('IMPLEMENTED',{}),('REFUSED_WITH_SUBSTITUTE',dict(substitute='X31'))]:
            b=self.binder();sid=b.spans[0]['span_id'];b.bind(sid,'UNMAPPED',{})
            evidence.update(pin=b.spans[1]['span_id'],reason='review')
            with self.assertRaises(Refused):b.revise(sid,state,evidence)

    def test_exclude_twice_bound_and_audit(self):
        b=self.binder();sid=b.spans[0]['span_id'];b.exclude(sid,'reviewed no request')
        self.assertEqual(b.audit[-1],dict(span_id=sid,reviewed_nonrequest=True,reason='reviewed no request'))
        with self.assertRaises(Refused):b.exclude(sid,'again')
        b=self.binder();sid=b.spans[0]['span_id'];b.bind(sid,'UNMAPPED',{})
        with self.assertRaises(Refused):b.exclude(sid,'bound')

    def test_history_complete_never_true(self):
        s=make_snapshot([msg()],as_of='2026-10-11T10:00:00+00:00',observed_total=1,history_complete=True)
        self.assertIs(s['history_complete'],False)
        self.assertIs(ChatBinder(s).report()['scope']['history_complete'],False)

    def test_substitute_boundaries(self):
        for sub in ('X1','X30','X0','X31'):
            b=self.binder();sid=b.spans[0]['span_id'];e=dict(substitute=sub,unit='C5',reason='bounded')
            if sub in ('X1','X30'):
                b.bind(sid,'REFUSED_WITH_SUBSTITUTE',e)
                self.assertEqual(b.bindings[sid]['evidence']['substitute'],sub)
            else:
                with self.assertRaises(Refused):b.bind(sid,'REFUSED_WITH_SUBSTITUTE',e)

    def test_time_equal_boundaries(self):
        row=msg();s=make_snapshot([row],as_of=row['ts'],observed_total=1)
        self.assertEqual(len(s['rows']),1)
        b=ChatBinder(snap([msg(body='Build Atlas'),msg('m2',body='Pause Atlas')]))
        b.bind(b.spans[0]['span_id'],'PARKED_BY_USER',dict(pin=b.spans[1]['span_id'],topic='Atlas'))
        self.assertEqual(b.report()['counts']['PARKED_BY_USER'],1)

    def test_empty_body(self):
        self.assertEqual(split_spans(''),[dict(start=0,end=0,text='')])
        self.assertEqual(ChatBinder(snap([msg(body='')])).report()['candidate_spans'],1)

    def test_positive_channels(self):
        for channel in ('iMessage','SMS','RCS'):
            self.assertEqual(snap([dict(msg(),service=channel)])['rows'][0]['service'],channel)

    def test_parked_word_guard_and_revision(self):
        b=ChatBinder(snap([msg(body='Build Atlas'),dict(msg('m2',body='Hello'),ts='2026-10-02T10:00:00+00:00')]))
        with self.assertRaises(Refused):b.bind(b.spans[0]['span_id'],'PARKED_BY_USER',dict(pin=b.spans[1]['span_id'],topic='Atlas'))
        b.bind(b.spans[0]['span_id'],'UNMAPPED',{})
        with self.assertRaises(Refused):b.revise(b.spans[0]['span_id'],'PARKED_BY_USER',dict(pin=b.spans[1]['span_id'],topic='Atlas',reason='park'))

    def test_package_import_path(self):
        import subprocess
        code=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker'
        if not code.exists():code=Path(__file__).parent
        p=subprocess.run([sys.executable,'-c','from c30_b1.db_chat_bind import ingest; from c30_b1.route_adapter import Routes'],cwd=code,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)

    def test_invalid_db_timestamps_are_not_dropped(self):
        import sqlite3
        from app.modules.m20_general_cognitive_worker.c30_b1.db_chat_bind import ingest
        for timestamp in (None,'garbage','2026-12-01T10:00:00+00:00'):
            db=sqlite3.connect(':memory:')
            db.execute('CREATE TABLE phone_messages (message_id TEXT, body TEXT, ts TEXT, author TEXT, service TEXT, conversation_id TEXT)')
            db.execute('INSERT INTO phone_messages VALUES (?,?,?,?,?,?)',('bad','Build',timestamp,'user','WhatsApp','owner'))
            with self.assertRaisesRegex(Refused,'PLAN_REFUSED_DB_COUNT'):ingest(db,as_of='2026-10-11T10:00:00+00:00')

class FinalAuditPins(unittest.TestCase):
    def test_never_bound_execution_is_unmapped(self):
        b=ChatBinder(snap([msg(body='Build Atlas')]))
        self.assertNotIn(b.spans[0]['span_id'],b.bindings)
        self.assertEqual(b.execution_gate(b.spans[0]['span_id']),'PLAN_REFUSED_UNMAPPED')

    def test_unknown_exclusion_refused(self):
        b=ChatBinder(snap([msg()]))
        with self.assertRaises(Refused):b.exclude('never-existed','reviewed')

    def test_superseded_needs_pin_and_topic(self):
        b=ChatBinder(snap([msg(body='Build Atlas'),dict(msg('m2',body='Use new plan'),ts='2026-10-02T10:00:00+00:00')]))
        for evidence in ({},{'pin':'not-a-span','topic':'Atlas'},{'pin':b.spans[1]['span_id']}):
            with self.assertRaises(Refused):b.bind(b.spans[0]['span_id'],'SUPERSEDED',evidence)

    def test_no_need_stop_word_alternative(self):
        b=ChatBinder(snap([msg(body='Build Atlas'),dict(msg('m2',body='no need for Atlas yet'),ts='2026-10-02T10:00:00+00:00')]))
        b.bind(b.spans[0]['span_id'],'PARKED_BY_USER',dict(pin=b.spans[1]['span_id'],topic='Atlas'))
        self.assertEqual(b.execution_gate(b.spans[0]['span_id']),'PLAN_REFUSED_STOPPED')
