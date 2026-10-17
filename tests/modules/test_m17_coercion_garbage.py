"""m17 advice-essay coaching rows 710-809: external-field coercion repair.
RED on pristine: bare int() on externally supplied fields raises uncaught
TypeError (non-scalar input) or OverflowError (non-finite float, e.g. JSON
1e999) -> HTTP 500, because the documented host route maps only ValueError
to 422. Repair: _coerce_int codes all three to ValueError with
field-static messages. Previously valid coercions (numeric strings,
booleans, truncating floats, defaults) are preserved - pinned here and by
the byte-equivalence grid artifact accompanying the delivery."""
import unittest

from app.modules.m17_advice_essay.coaching_state_machines_710_809 import run_row

INF = float('inf')  # what a JSON parser yields for a literal like 1e999


class TestCoercionGarbage(unittest.TestCase):
    def test_726_rehearsals_non_scalar_refused(self):
        with self.assertRaises(ValueError):
            run_row('public_speaking', {'takeaway': 't', 'duration_minutes': 5,
                                        'rehearsals': ['a']})

    def test_726_rehearsals_non_finite_refused(self):
        with self.assertRaises(ValueError):
            run_row('public_speaking', {'takeaway': 't', 'duration_minutes': 5,
                                        'rehearsals': INF})

    def test_741_agenda_minutes_non_scalar_refused(self):
        with self.assertRaises(ValueError):
            run_row('facilitation', {'purpose': 'p', 'decision_rule': 'd', 'roles': ['r'],
                                     'agenda_items': [{'item': 'a', 'minutes': {'x': 1}}]})

    def test_742_idea_target_non_scalar_refused(self):
        with self.assertRaises(ValueError):
            run_row('brainstorming', {'prompt': 'p', 'idea_target': ['a']})

    def test_742_idea_target_non_finite_refused(self):
        with self.assertRaises(ValueError):
            run_row('brainstorming', {'prompt': 'p', 'idea_target': INF})

    def test_746_turns_value_non_scalar_refused(self):
        with self.assertRaises(ValueError):
            run_row('debate', {'claim': 'c', 'sides': ['a', 'b'],
                               'turns': {'a': {'n': 1}}})

    def test_refusal_messages_are_field_static(self):
        try:
            run_row('brainstorming', {'prompt': 'p', 'idea_target': ['sentinel-zz']})
        except ValueError as e:
            self.assertNotIn('sentinel-zz', str(e))
            self.assertIn('idea_target', str(e))
        else:
            self.fail('expected ValueError')


class TestPreviouslyValidPreserved(unittest.TestCase):
    def test_726_string_and_bool_preserved(self):
        run_row('public_speaking', {'takeaway': 't', 'duration_minutes': 5, 'rehearsals': '3'})
        run_row('public_speaking', {'takeaway': 't', 'duration_minutes': 5, 'rehearsals': True})

    def test_741_string_minutes_preserved(self):
        run_row('facilitation', {'purpose': 'p', 'decision_rule': 'd', 'roles': ['r'],
                                 'agenda_items': [{'item': 'a', 'minutes': '15'}]})

    def test_742_string_target_preserved(self):
        run_row('brainstorming', {'prompt': 'p', 'idea_target': '6'})

    def test_746_string_turns_preserved(self):
        run_row('debate', {'claim': 'c', 'sides': ['a', 'b'], 'turns': {'a': '2'}})


def _real_deps():
    try:
        import fastapi, pydantic
        return getattr(pydantic, 'VERSION', None) is not None
    except ImportError:
        return False


@unittest.skipUnless(_real_deps(), 'native HTTP candidate: real fastapi+pydantic required')
class TestNativeHttp(unittest.TestCase):
    def _client(self):
        import uuid
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.modules.m17_advice_essay.routes import build_router
        from app.modules.m17_advice_essay.service import AdviceEssayService
        from app.modules.m17_advice_essay.in_memory_repository import InMemoryModule17Repository
        self._owner = uuid.uuid4()
        svc = AdviceEssayService(InMemoryModule17Repository())
        app = FastAPI()
        app.include_router(build_router(lambda: svc, lambda: self._owner))
        return TestClient(app, raise_server_exceptions=False)

    def _post(self, client, method, data):
        return client.post('/v1/modules/17/coaching/state-machine',
                           json={'owner_id': str(self._owner), 'method': method, 'data': data})

    def test_garbage_is_422_not_500(self):
        c = self._client()
        r = self._post(c, 'public_speaking', {'takeaway': 't', 'duration_minutes': 5,
                                              'rehearsals': ['a']})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()['detail'], 'rehearsals must be an integer')
        self.assertEqual(self._post(c, 'brainstorming', {'prompt': 'p', 'idea_target': ['a']}).status_code, 422)
        self.assertEqual(self._post(c, 'debate', {'claim': 'c', 'sides': ['a', 'b'],
                                                  'turns': {'a': {'n': 1}}}).status_code, 422)
        self.assertEqual(self._post(c, 'facilitation', {'purpose': 'p', 'decision_rule': 'd', 'roles': ['r'],
                                                        'agenda_items': [{'item': 'a', 'minutes': {'x': 1}}]}).status_code, 422)

    def test_non_finite_json_literal_is_422_not_500(self):
        c = self._client()
        body = ('{"owner_id": "%s", "method": "brainstorming", '
                '"data": {"prompt": "p", "idea_target": 1e999}}' % self._owner)
        r = c.post('/v1/modules/17/coaching/state-machine', content=body,
                   headers={'content-type': 'application/json'})
        self.assertEqual(r.status_code, 422)

    def test_valid_coercion_200(self):
        c = self._client()
        r = self._post(c, 'public_speaking', {'takeaway': 't', 'duration_minutes': 5,
                                              'rehearsals': '3'})
        self.assertEqual(r.status_code, 200)


if __name__ == '__main__':
    unittest.main()
