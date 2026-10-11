"""Independent-review follow-up: precise boundaries and output contracts."""
import hashlib
import json
import sys
import unittest
from test_layers import m, packet


class ReviewPins(unittest.TestCase):
    def refusal(self, value, code, message):
        with self.assertRaises(m.Refusal) as caught:
            m.run(value)
        self.assertEqual(caught.exception.code, code)
        self.assertIn(message, str(caught.exception))

    def test_literal_cap_values(self):
        self.assertEqual(m.MAX_TEXT, 20000)
        self.assertEqual(m.MAX_ROWS, 128)
        self.assertEqual(m.MAX_REQUIREMENTS, 32)

    def test_text_n_accepted_n_plus_one_refused(self):
        p = packet(); p['goal'] = 'x' * 20000
        self.assertEqual(m.run(p)['goal'], p['goal'])
        p['goal'] += 'x'
        self.refusal(p, 'FLEET_REFUSED_LIMIT', 'goal exceeds text cap')

    def test_rows_n_accepted_n_plus_one_refused(self):
        p = packet(); p['facts'] = [{'id': 'f' + str(i), 'text': 'fact', 'source_id': 'supplied'} for i in range(128)]
        p['evidence_map'] = {}
        self.assertEqual(len(m.run(p)['critique']['unused_facts']), 128)
        p['facts'].append({'id': 'f128', 'text': 'fact', 'source_id': 'supplied'})
        self.refusal(p, 'FLEET_REFUSED_LIMIT', 'facts exceeds row cap')

    def test_references_n_accepted_n_plus_one_refused(self):
        p = packet(); p['facts'] = [{'id': 'f' + str(i), 'text': 'fact', 'source_id': 'supplied'} for i in range(128)]
        p['evidence_map'] = {'r1': [f['id'] for f in p['facts']]}
        self.assertEqual(len(m.run(p)['outline'][0]['fact_ids']), 128)
        p['evidence_map']['r1'].append('f0')
        self.refusal(p, 'FLEET_REFUSED_LIMIT', 'r1 facts exceeds reference cap')

    def test_capabilities_n_accepted_n_plus_one_refused(self):
        p = packet(); p['tools'][0]['capabilities'] = ['biology'] * 128
        self.assertEqual(m.run(p)['tool_selection']['selected_ids'], ['outline-tool'])
        p['tools'][0]['capabilities'].append('biology')
        self.refusal(p, 'FLEET_REFUSED_SCHEMA', 'tool capabilities must be a bounded list')

    def test_requirements_n_accepted_n_plus_one_refused(self):
        p = packet(); p['requirements_text'] = '\n'.join('item ' + str(i) for i in range(32))
        p['evidence_map'] = {}
        self.assertEqual(m.run(p)['coverage']['requirements'], 32)
        p['requirements_text'] += '\nitem 32'
        self.refusal(p, 'FLEET_REFUSED_LIMIT', 'requirements exceed cap')

    def test_packet_limit_minus_one_at_limit_plus_one(self):
        # Metadata unused by the finite parser still counts toward serialized cap.
        p = packet(); p['facts'][0]['padding'] = ''
        base = len(json.dumps(p, sort_keys=True, ensure_ascii=False, allow_nan=False))
        for length in [999999, 1000000]:
            p['facts'][0]['padding'] = 'x' * (length - base)
            self.assertEqual(len(json.dumps(p, sort_keys=True, ensure_ascii=False, allow_nan=False)), length)
            self.assertEqual(m.run(p)['status'], 'draft_for_review')
        p['facts'][0]['padding'] += 'x'
        self.refusal(p, 'FLEET_REFUSED_LIMIT', 'packet exceeds one million characters')

    def test_url_guard_each_component(self):
        for url in ['http://example.org', 'https://user@example.org', 'https://:password@example.org', 'https://']:
            p = packet(); p['advice_sources'][0]['url'] = url
            with self.subTest(url=url):
                self.refusal(p, 'FLEET_REFUSED_SOURCE', 'credential-free HTTPS')

    def test_honesty_flags_exact(self):
        # Per-fact truth_verified is internal metadata, not a public output claim.
        snapshots = []
        def capture(frame, event, arg):
            if event == 'return' and frame.f_code is m.run.__code__:
                snapshots.append(frame.f_locals['facts'])
            return capture
        prior = sys.gettrace()
        try:
            sys.settrace(capture); r = m.run(packet())
        finally:
            sys.settrace(prior)
        self.assertIs(r['tool_selection']['executed'], False)
        self.assertIs(r['tool_selection']['costs_independently_verified'], False)
        self.assertIs(r['authenticity']['user_review_required'], True)
        self.assertEqual(set(snapshots[0]), {'f1', 'f2'})
        for fact in snapshots[0].values():
            self.assertIs(fact['truth_verified'], False)

    def test_advice_rank_limit_exclusion_tie_order(self):
        p = packet(); p['requirements_text'] = 'biology'; p['evidence_map'] = {}
        p['advice_sources'] = [dict(p['advice_sources'][0], id=i, text='biology') for i in ['d', 'c', 'b', 'a']]
        p['advice_sources'].append(dict(p['advice_sources'][0], id='zero', text='unrelated music'))
        r = m.run(p)
        self.assertEqual(r['advice'][0]['source_ids'], ['a', 'b', 'c'])
        self.assertEqual([x['source_id'] for x in r['advice'][0]['excerpts']], ['a', 'b', 'c'])

    def test_zero_overlap_advice_excluded_with_spare_capacity(self):
        p = packet(); p['advice_sources'] = [dict(p['advice_sources'][0], text='unrelated music')]
        self.assertEqual(m.run(p)['advice'][0]['source_ids'], [])

    def test_free_tool_needs_capability_match(self):
        p = packet(); p['tools'][0]['capabilities'] = ['irrelevant orchestration']
        r = m.run(p)
        self.assertEqual(r['tool_selection']['selected_ids'], [])
        self.assertEqual(r['tool_selection']['matches'], {})
        self.assertEqual(r['tool_selection']['rejected'], [])

    def test_nonstring_text_schema_refusal(self):
        for value in [17, False, [], {}, None]:
            for key in ['goal', 'requirements_text']:
                p = packet(); p[key] = value
                with self.subTest(key=key, value=value):
                    self.refusal(p, 'FLEET_REFUSED_SCHEMA', key + ' must be nonempty text')
            p = packet(); p['facts'][0]['text'] = value
            self.refusal(p, 'FLEET_REFUSED_SCHEMA', 'fact text must be nonempty text')

    def test_missing_requirements_schema_refusal(self):
        p = packet(); del p['requirements_text']
        self.refusal(p, 'FLEET_REFUSED_SCHEMA', 'requirements_text must be nonempty text')

    def test_string_id_list_guard(self):
        for value in ['f1', [1], [False], [None], [{}]]:
            p = packet(); p['evidence_map']['r1'] = value
            with self.subTest(value=value):
                self.refusal(p, 'FLEET_REFUSED_SCHEMA', 'r1 facts must be string IDs')

    def test_evidence_map_nondict(self):
        for value in [[], None, 'r1', 0]:
            p = packet(); p['evidence_map'] = value
            self.refusal(p, 'FLEET_REFUSED_REFERENCE', 'evidence_map must reference extracted requirement IDs')

    def test_exact_fields_set_accepted(self):
        p = packet(); p.update(draft_claims=[], action='draft', as_of='2026-10-11')
        self.assertEqual(set(p), m.FIELDS)
        self.assertEqual(len(p), 9)
        self.assertEqual(m.run(p)['status'], 'needs_facts')

    def test_dash_only_requirement(self):
        p = packet(); p['requirements_text'] = '-'
        self.refusal(p, 'FLEET_REFUSED_REQUIREMENTS', 'at least one explicit requirement is needed')

    def test_codes_policy_scrape_and_unknown_action(self):
        p = packet(); p['action'] = 'scrape'
        self.refusal(p, 'POLICY_REFUSED_SCRAPE', 'C3 cannot execute external actions')
        p = packet(); p['advice_sources'][0]['access'] = 'private'
        self.refusal(p, 'POLICY_REFUSED_SCRAPE', 'only public or explicitly supplied advice is accepted')
        p = packet(); p['action'] = 'other'
        self.refusal(p, 'FLEET_REFUSED_ACTION', 'only draft preparation is supported')
        p = packet(); p['action'] = None
        self.refusal(p, 'FLEET_REFUSED_SCHEMA', 'action must be text')

    def test_empty_claim_fact_ids_exact_refusal(self):
        p = packet(); p['draft_claims'] = [{'text': p['facts'][0]['text'], 'fact_ids': []}]
        self.refusal(p, 'FLEET_REFUSED_FABRICATE', 'claim must equal an attributed supplied fact')

    def test_digest_sorted_keys_and_nonascii(self):
        p = packet(); p['goal'] = 'Biology café विचार'
        expected = hashlib.sha256(json.dumps(p, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        r = m.run(p)
        self.assertEqual(r['input_sha256'], expected)
        self.assertEqual(m.run(dict(reversed(list(p.items()))))['input_sha256'], expected)
        escaped = hashlib.sha256(json.dumps(p, sort_keys=True, ensure_ascii=True, allow_nan=False).encode()).hexdigest()
        self.assertNotEqual(r['input_sha256'], escaped)

if __name__ == '__main__': unittest.main()
