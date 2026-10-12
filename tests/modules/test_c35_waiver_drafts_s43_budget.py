"""S4.3 c35.waiver_drafts: container budget, key/item caps and depth cap run before any traversal.
Hermetic, stdlib unittest, no network."""
import importlib.util
import pathlib
import sys
import unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c35/waiver_drafts.py"
_spec = importlib.util.spec_from_file_location("c35_waiver_drafts_budget", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c35_waiver_drafts_budget"] = m
_spec.loader.exec_module(m)

TEMPLATE = "Dear {contact}, I am {name} from {school}. I request a fee waiver for {opportunity} (fee {fee}, deadline {deadline})."
OVER = "APPLY_REFUSED_OVERSIZE:request"
BAD = "APPLY_REFUSED_BAD_TYPE:request"


def op(i, fee="USD 25", **kw):
    d = {"id": i, "title": "Contest " + str(i), "fee": fee, "contact_email": "x@y.org", "deadline": "2026-12-01"}
    d.update(kw)
    return d


def req(**kw):
    r = {"as_of": "2026-10-11", "profile": {"name": "UserA", "school": "Test School"},
         "opportunities": [op("o1")], "template": TEMPLATE}
    r.update(kw)
    return r


def code(request):
    try:
        m.run(request)
    except ValueError as e:
        return str(e)
    return None


class SpyDict(dict):
    iterations = 0

    def __iter__(self):
        type(self).iterations += 1
        return dict.__iter__(self)

    def items(self):
        type(self).iterations += 1
        return dict.items(self)

    def keys(self):
        type(self).iterations += 1
        return dict.keys(self)

    def values(self):
        type(self).iterations += 1
        return dict.values(self)


class SpyList(list):
    iterations = 0

    def __iter__(self):
        type(self).iterations += 1
        return list.__iter__(self)


class SpyTuple(tuple):
    iterations = 0

    def __iter__(self):
        type(self).iterations += 1
        return tuple.__iter__(self)


def fresh(*classes):
    for c in classes:
        c.iterations = 0


def nest(depth, leaf):
    node = leaf
    for _ in range(depth):
        node = [node]
    return node


class KeyCap(unittest.TestCase):
    def test_dict_with_33_keys_refused_without_being_read(self):
        fresh(SpyDict)
        big = SpyDict({"k%d" % i: 1 for i in range(33)})
        self.assertEqual(code(req(opportunities=[big])), BAD)   # subclass: refused by type, never read
        self.assertEqual(SpyDict.iterations, 0)
        self.assertEqual(code(req(opportunities=[{"k%d" % i: 1 for i in range(33)}])), OVER)

    def test_32_keys_is_not_oversize(self):
        extra = {"k%d" % i: 1 for i in range(32)}
        self.assertEqual(code(req(opportunities=[extra])), "APPLY_REFUSED_UNKNOWN:opportunities")

    def test_top_level_33_keys_refused_before_unknown_key_check(self):
        r = req()
        for i in range(33 - len(r)):
            r["x%d" % i] = 1
        self.assertEqual(len(r), 33)
        self.assertEqual(code(r), OVER)

    def test_oversize_beats_forbidden_key_inside_the_big_dict(self):
        big = {"k%d" % i: 1 for i in range(32)}
        big["send"] = 1
        self.assertEqual(len(big), 33)
        self.assertEqual(code(req(opportunities=[big])), OVER)
        del big["k0"]
        self.assertEqual(code(req(opportunities=[big])), "APPLY_REFUSED_SEND:send")


class ItemCap(unittest.TestCase):
    def test_list_over_cap_refused_without_iteration(self):
        fresh(SpyList)
        items = SpyList([[] for _ in range(1002)])
        self.assertEqual(code(req(opportunities=[{"a": items}])), BAD)
        self.assertEqual(SpyList.iterations, 0)

    def test_tuple_over_cap_refused_without_iteration(self):
        fresh(SpyTuple)
        items = SpyTuple(() for _ in range(1002))
        self.assertEqual(code(req(opportunities=[{"a": items}])), BAD)
        self.assertEqual(SpyTuple.iterations, 0)

    def test_exactly_1001_items_not_oversize(self):
        # the scan cap is 1001 so the unit's own opportunities cap (1000) can still fire at 1001
        self.assertEqual(code(req(opportunities=[{"a": [1] * 1001}])), "APPLY_REFUSED_UNKNOWN:opportunities")
        self.assertEqual(code(req(opportunities=[{"a": (1,) * 1001}])), "APPLY_REFUSED_UNKNOWN:opportunities")
        self.assertEqual(code(req(opportunities=[{"a": [1] * 1002}])), OVER)
        self.assertEqual(code(req(opportunities=[{"a": (1,) * 1002}])), OVER)

    def test_opportunities_1000_ok_1001_own_code_1002_scan_code(self):
        self.assertIsNone(code(req(opportunities=[op("o%d" % i) for i in range(1000)])))
        self.assertEqual(code(req(opportunities=[op("o%d" % i) for i in range(1001)])),
                         "APPLY_REFUSED_OVERSIZE:opportunities")
        self.assertEqual(code(req(opportunities=[op("o%d" % i) for i in range(1002)])), OVER)

    def test_oversize_beats_forbidden_key_in_other_items(self):
        items = [{"login": 1}] + [[] for _ in range(1001)]
        self.assertEqual(len(items), 1002)
        self.assertEqual(code(req(opportunities=[{"a": items}])), OVER)


class DepthCap(unittest.TestCase):
    def test_depth_32_ok_33_refused(self):
        # depth counts containers from the request (depth 0) down; the forbidden key sits at the deepest dict
        deep_ok = nest(30, {"login": 1})       # request(0) > opportunities list(1) ... exactly at the cap
        self.assertEqual(code(req(opportunities=[deep_ok])), "APPLY_REFUSED_NOCREDS:login")
        self.assertEqual(code(req(opportunities=[nest(31, {"login": 1})])), OVER)

    def test_deep_chain_never_walked_past_the_cap(self):
        fresh(SpyDict)
        leaf = SpyDict({"login": 1})
        self.assertEqual(code(req(opportunities=[nest(200, leaf)])), OVER)   # depth refusal precedes reaching the subclass
        self.assertEqual(SpyDict.iterations, 0)

    def test_cyclic_structure_terminates(self):
        a = []
        a.append(a)
        self.assertEqual(code(req(opportunities=[a])), "APPLY_REFUSED_BAD_TYPE:opportunities")


class ContainerBudget(unittest.TestCase):
    @staticmethod
    def build(total, tail=None):
        """A request with exactly `total` distinct containers: request, profile, opportunities list, then
        chunk dicts each holding one list of empty lists (<= 1001 items per list)."""
        remaining = total - 3
        opps = []
        while remaining > 0:
            k = min(remaining - 2, 500)      # a chunk is a dict + a list + k empty lists = k + 2 containers
            assert k >= 0
            opps.append({"a": [[] for _ in range(k)]})
            remaining -= k + 2
        assert remaining == 0
        if tail is not None:
            opps.append(tail)
        return req(opportunities=opps)

    def test_exact_budget_boundary(self):
        self.assertEqual(code(self.build(10000)), "APPLY_REFUSED_UNKNOWN:opportunities")
        self.assertEqual(code(self.build(10001)), OVER)

    def test_budget_exceeded_refused_before_reaching_late_forbidden_key(self):
        late = {"login": 1}
        self.assertEqual(code(self.build(9999, late)), "APPLY_REFUSED_NOCREDS:login")   # 10000th container
        self.assertEqual(code(self.build(10000, late)), OVER)                            # 10001st: refused first

    def test_shared_container_counted_once(self):
        shared = []
        self.assertEqual(code(req(opportunities=[{"a": [shared] * 1000, "b": [shared] * 1000}])),
                         "APPLY_REFUSED_UNKNOWN:opportunities")


class LyingSubclass(unittest.TestCase):
    """A dict/list/tuple subclass can lie about __len__ and iterate far more than it reports.
    The scan accepts exact builtins only, so a subclass is refused by type before anything reads it."""

    def test_dict_subclass_with_lying_len_never_read(self):
        class Liar(dict):
            reads = 0

            def __len__(self):
                return 1

            def __iter__(self):
                type(self).reads += 1
                return dict.__iter__(self)

            def items(self):
                type(self).reads += 1
                return dict.items(self)
        big = Liar({"k%d" % i: 1 for i in range(100000)})
        self.assertEqual(code(req(opportunities=[big])), BAD)
        self.assertEqual(Liar.reads, 0)

    def test_list_and_tuple_subclass_with_lying_len_never_read(self):
        class LList(list):
            reads = 0

            def __len__(self):
                return 1

            def __iter__(self):
                type(self).reads += 1
                return list.__iter__(self)

        class LTuple(tuple):
            reads = 0

            def __len__(self):
                return 1

            def __iter__(self):
                type(self).reads += 1
                return tuple.__iter__(self)
        self.assertEqual(code(req(opportunities=[{"a": LList([[]] * 5000)}])), BAD)
        self.assertEqual(code(req(opportunities=[{"a": LTuple([()] * 5000)}])), BAD)
        self.assertEqual((LList.reads, LTuple.reads), (0, 0))

    def test_subclass_refused_at_any_depth_and_before_forbidden_keys(self):
        self.assertEqual(code(req(opportunities=[nest(10, SpyDict())])), BAD)
        self.assertEqual(code(req(opportunities=[{"login": 1, "a": SpyList()}])), BAD)

    def test_root_subclass_refused_unread(self):
        fresh(SpyDict)
        root = SpyDict(req())
        self.assertEqual(code(root), BAD)
        self.assertEqual(SpyDict.iterations, 0)

    def test_exact_builtins_unaffected(self):
        self.assertEqual(code(req(opportunities=[{"a": ({"pay": 1},)}])), "APPLY_REFUSED_SPEND:pay")


class TextCapBoundaries(unittest.TestCase):
    """Literal N accepted, N+1 refused (OVERSIZE:<field>), for the unit's own text caps."""

    def check(self, field, limit, build, accepted=None):
        self.assertNotEqual(code(build("a" * limit)), "APPLY_REFUSED_OVERSIZE:" + field, field)
        self.assertEqual(code(build("a" * (limit + 1))), "APPLY_REFUSED_OVERSIZE:" + field)
        if limit > 1:
            self.assertNotEqual(code(build("a" * (limit - 1))), "APPLY_REFUSED_OVERSIZE:" + field)

    def test_id_128(self):
        self.check("id", 128, lambda v: req(opportunities=[op(v)]))
        self.assertIsNone(code(req(opportunities=[op("a" * 128)])))

    def test_title_200(self):
        self.check("title", 200, lambda v: req(opportunities=[op("o1", title=v)]))
        self.assertIsNone(code(req(opportunities=[op("o1", title="a" * 200)])))

    def test_contact_name_200(self):
        self.check("contact_name", 200, lambda v: req(opportunities=[op("o1", contact_name=v)]))
        self.assertIsNone(code(req(opportunities=[op("o1", contact_name="a" * 200)])))

    def test_deadline_100(self):
        self.check("deadline", 100, lambda v: req(opportunities=[op("o1", deadline=v)]))
        self.assertIsNone(code(req(opportunities=[op("o1", deadline="a" * 100)])))

    def test_profile_value_200(self):
        for key in ("name", "school"):
            self.check("profile", 200, lambda v, k=key: req(profile={k: v}))
            full = {"name": "N", "school": "S"}
            full[key] = "a" * 200
            self.assertIsNone(code(req(profile=full)))

    def test_as_of_64_65_63(self):
        # as_of is also an ISO date: 64 'a' chars pass the cap and fail the date shape (BAD_TYPE:as_of); 65 fails the cap first
        self.assertEqual(code(req(as_of="a" * 63)), "APPLY_REFUSED_BAD_TYPE:as_of")
        self.assertEqual(code(req(as_of="a" * 64)), "APPLY_REFUSED_BAD_TYPE:as_of")
        self.assertEqual(code(req(as_of="a" * 65)), "APPLY_REFUSED_OVERSIZE:as_of")
        self.assertEqual(code(req(as_of="2026-10-11")), None)


class KeyAdmission(unittest.TestCase):
    """Dict keys: exact str only (subclass refused untouched), raw length cap 200 before normalization."""

    def test_str_subclass_key_refused_untouched(self):
        class K(str):
            touched = 0

            def casefold(self):
                type(self).touched += 1
                return str.casefold(self)

            def replace(self, *a):
                type(self).touched += 1
                return str.replace(self, *a)

            def __len__(self):
                type(self).touched += 1
                return str.__len__(self)

            def __eq__(self, o):
                type(self).touched += 1
                return str.__eq__(self, o)

            __hash__ = str.__hash__
        k = K("send")
        K.touched = 0   # hashing/insertion into the dict happens in the test, not in the unit
        for r in (req(extra={k: 1}), req(opportunities=[{k: 1}]), req(profile={k: 1})):
            self.assertEqual(code(r), BAD)
        self.assertEqual(K.touched, 0)

    def test_subclass_key_precedes_forbidden_key(self):
        class K(str):
            pass
        self.assertEqual(code(req(extra={"login": 1, K("a"): 1})), BAD)

    def test_raw_key_length_200_ok_201_oversize(self):
        self.assertEqual(code(req(**{"a" * 200: 1})), "APPLY_REFUSED_UNKNOWN:request")
        self.assertEqual(code(req(**{"a" * 201: 1})), OVER)
        self.assertEqual(code(req(opportunities=[{"a" * 201: 1}])), OVER)
        self.assertEqual(code(req(**{"a" * 199: 1})), "APPLY_REFUSED_UNKNOWN:request")

    def test_overlong_key_precedence(self):
        # overlong beats unknown-key, forbidden keys and non-str keys; a bounded forbidden key keeps its class
        self.assertEqual(code(req(**{"a" * 201: 1, "login": 1})), OVER)
        self.assertEqual(code(req(**{"a" * 201: 1, "send": 1})), OVER)
        self.assertEqual(code({**req(), 5: 1, "b" * 201: 1}), OVER)
        self.assertEqual(code(req(**{"a" * 200: 1, "send": 1})), "APPLY_REFUSED_SEND:send")
        self.assertEqual(code(req(**{"a" * 200: 1, "login": 1})), "APPLY_REFUSED_NOCREDS:login")

    def test_huge_key_refused_by_length_only(self):
        self.assertEqual(code(req(extra={"A" * 1000000: 1})), OVER)

    def test_overlong_key_never_normalized_allocation_pin(self):
        # casefold/replace of a 20M-char exact str would allocate >= 20 MB; refusal on raw length allocates ~nothing
        import tracemalloc
        key = "A" * 20000000
        r = req(extra={key: 1})
        tracemalloc.start()
        try:
            got = code(r)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(got, OVER)
        self.assertLess(peak, 2000000)

    def test_normalization_still_applies_to_bounded_keys(self):
        self.assertEqual(code(req(**{"API-KEY": 1})), "APPLY_REFUSED_NOCREDS:api_key")
        self.assertEqual(code(req(**{"Smtp-Host": 1})), "APPLY_REFUSED_SEND:smtp_host")

    def test_non_str_key_still_bad_type_key(self):
        self.assertEqual(code({**req(), 5: 1}), "APPLY_REFUSED_BAD_TYPE:key")


class ValidInputUnchanged(unittest.TestCase):
    def test_nested_forbidden_keys_still_found(self):
        o = op("o1", "5")
        o["extra"] = {"deep": [{"x": {"login": 1}}]}
        self.assertEqual(code(req(opportunities=[o])), "APPLY_REFUSED_NOCREDS:login")
        self.assertEqual(code(req(opportunities=[{"a": ({"pay": 1},)}])), "APPLY_REFUSED_SPEND:pay")
        self.assertEqual(code(req(opportunities=[[{"submit": 1}]])), "APPLY_REFUSED_SUBMIT:submit")

    def test_non_str_key_still_bad_type_key(self):
        self.assertEqual(code(req(opportunities=[{1: "x"}])), "APPLY_REFUSED_BAD_TYPE:key")

    def test_a_full_valid_request_still_drafts(self):
        out = m.run(req(opportunities=[op("o%d" % i) for i in range(1000)]))
        self.assertTrue(out)


if __name__ == "__main__":
    unittest.main()
