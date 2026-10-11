"""S5.6 / c36.world tests: seeded toy sim of supplied synthetic characters. Hermetic, stdlib unittest."""
import ast
import json
import pathlib
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
from app.modules.c36 import world as w  # noqa: E402

P = "VENT_REFUSED_"
# splitmix64(seed=7) first 12 outputs, hand-computed with the reference recurrence:
#   state += 0x9E3779B97F4A7C15; z = (state ^ state>>30) * 0xBF58476D1CE4E5B9;
#   z = (z ^ z>>27) * 0x94D049BB133111EB; out = z ^ z>>31   (all mod 2**64)
SM7 = [7191089600892374487, 309689372594955804, 16616101746815609346, 10753165928301472203,
       8346079845500723674, 4601199455465548305, 8632209307422871798, 6051947643683389182,
       2476628477891077985, 7621113624420504425, 1910343844960271083, 17706551433532105516]
SM0_FIRST = 16294208416658607535   # the well-known splitmix64 first output for seed 0


def agent(i="a1", name="Mira", traits=("curious",), actions=("browse", "chat")):
    return {"id": i, "name": name, "traits": list(traits), "actions": list(actions)}


def req(**kw):
    r = {"as_of": "2026-10-11", "seed": 7,
         "world": {"name": "Harbor", "places": ["pier", "cafe"], "steps": 3},
         "agents": [agent("a1", "Mira", actions=("browse", "chat")), agent("a2", "Joss", actions=("walk", "rest"))],
         "scenario": {"kind": "commercial_storyboard", "product": "Sample lamp"}}
    r.update(kw)
    return r


def code(r):
    try:
        w.run(r)
    except ValueError as e:
        return str(e)
    return None


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from strings(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from strings(v)


class Golden(unittest.TestCase):
    def test_splitmix_known_vector(self):
        d = w._splitmix64(0)
        self.assertEqual(d(), SM0_FIRST)
        d = w._splitmix64(7)
        self.assertEqual([d() for _ in range(12)], SM7)

    def test_two_agent_three_step_log(self):
        # draw order per step, per agent in input order: place index, then action index (value % list length)
        out = w.run(req())
        places, acts = ["pier", "cafe"], {"a1": ["browse", "chat"], "a2": ["walk", "rest"]}
        want, k = [], 0
        for step in (1, 2, 3):
            for aid in ("a1", "a2"):
                want.append((step, aid, places[SM7[k] % 2], acts[aid][SM7[k + 1] % 2]))
                k += 2
        self.assertEqual([(e["step"], e["agent_id"], e["place"], e["action"]) for e in out["events"]], want)
        self.assertEqual(want[0], (1, "a1", "cafe", "browse"))
        self.assertEqual(want[-1], (3, "a2", "cafe", "walk"))
        self.assertEqual(out["frames"][0],
                         "Frame 1 [SYNTHETIC-AI] Mira at cafe: browse. Product: Sample lamp. TO_WRITE: voiceover")
        self.assertEqual(out["coverage"], {"agents": 2, "steps": 3, "events": 6, "frames": 6})

    def test_modulo_uses_list_length(self):
        r = req(world={"name": "W", "places": ["p1", "p2", "p3"], "steps": 1},
                agents=[agent("a1", actions=("x", "y", "z", "q", "r"))])
        e = w.run(r)["events"][0]
        self.assertEqual((e["place"], e["action"]), (["p1", "p2", "p3"][SM7[0] % 3], ["x", "y", "z", "q", "r"][SM7[1] % 5]))

    def test_daily_life_has_no_product(self):
        out = w.run(req(scenario={"kind": "daily_life"}))
        self.assertEqual(out["frames"][0], "Frame 1 [SYNTHETIC-AI] Mira at cafe: browse. TO_WRITE: voiceover")
        out2 = w.run(req(scenario={"kind": "daily_life", "product": "Ignored"}))
        self.assertNotIn("Ignored", json.dumps(out2))

    def test_shape(self):
        out = w.run(req())
        self.assertEqual(sorted(out), ["agents", "coverage", "events", "frames", "scope", "world"])
        self.assertEqual(out["agents"][0], {"id": "a1", "name": "Mira", "traits": ["curious"],
                                            "actions": ["browse", "chat"], "label": "SYNTHETIC-AI", "ai_generated": True})
        self.assertEqual(set(out["events"][0]), {"step", "agent_id", "place", "action", "label", "ai_generated"})


class Worlds(unittest.TestCase):
    def big(self, n, seed):
        return req(seed=seed, world={"name": "W", "places": ["p%d" % i for i in range(6)], "steps": 5},
                   agents=[agent("a%d" % i, "N%d" % i, ("t",), ("x", "y", "z")) for i in range(n)])

    def test_3_and_20_agents_deterministic_and_seed_sensitive(self):
        for n in (3, 20):
            a = json.dumps(w.run(self.big(n, 11)), sort_keys=True)
            b = json.dumps(w.run(self.big(n, 11)), sort_keys=True)
            c = json.dumps(w.run(self.big(n, 12)), sort_keys=True)
            self.assertEqual(a, b)
            self.assertNotEqual(a, c)
            self.assertEqual(w.run(self.big(n, 11))["coverage"]["events"], 5 * n)

    def test_no_wall_clock_or_random_module(self):
        tree = ast.parse((_ROOT / "backend/app/modules/c36/world.py").read_text())
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        mods |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertFalse({"random", "time", "datetime", "secrets", "os", "socket", "subprocess"} & (mods | names))


class Label(unittest.TestCase):
    def test_every_agent_event_frame_labeled(self):
        out = w.run(req())
        for a in out["agents"]:
            self.assertEqual((a["label"], a["ai_generated"]), ("SYNTHETIC-AI", True))
        for e in out["events"]:
            self.assertEqual((e["label"], e["ai_generated"]), ("SYNTHETIC-AI", True))
        for f in out["frames"]:
            self.assertIn("[SYNTHETIC-AI]", f)
        self.assertTrue(out["frames"] and all(f.endswith("TO_WRITE: voiceover") for f in out["frames"]))

    def test_input_cannot_disable_label(self):
        for k in ("label", "ai_generated", "synthetic"):
            r = req()
            r["agents"][0][k] = False
            self.assertEqual(code(r), P + "UNKNOWN:agents")
        r = req()
        r["label"] = ""
        self.assertEqual(code(r), P + "UNKNOWN:request")

    def test_trait_and_action_text_cannot_remove_label(self):
        out = w.run(req(agents=[agent("a1", "SYNTHETIC-AI", ("x",), ("y",))]))
        self.assertTrue(all("[SYNTHETIC-AI]" in f for f in out["frames"]))


class ClassRefusals(unittest.TestCase):
    def test_one_per_class(self):
        for key, want in (("likeness", "DECEPTIVE:likeness"), ("publish", "EFFECT:publish"), ("token", "SEND:token"),
                          ("pay", "SPEND:pay"), ("password", "NOCREDS:password")):
            self.assertEqual(code(req(**{key: 1})), P + want, key)

    def test_all_table_keys(self):
        tables = {
            "SEND": "send approve approved approval approval_token smtp token email_send sender smtp_host smtp_port smtp_user",
            "SPEND": "pay purchase spend buy checkout card_number",
            "DECEPTIVE": "real_person likeness impersonate deepfake voice_clone endorsement testimonial celebrity",
            "EFFECT": "publish post upload deploy broadcast advertise",
            "NOCREDS": "login password username credentials otp api_key access_token refresh_token bearer pass passwd"}
        for cls, keys in tables.items():
            for k in keys.split():
                self.assertEqual(code(req(**{k: 1})), "%s%s:%s" % (P, cls, k))
                self.assertEqual(code(req(**{k.upper().replace("_", "-"): 1})), "%s%s:%s" % (P, cls, k))

    def test_precedence_send_spend_deceptive_effect_nocreds(self):
        order = [("token", "SEND:token"), ("pay", "SPEND:pay"), ("likeness", "DECEPTIVE:likeness"),
                 ("publish", "EFFECT:publish"), ("login", "NOCREDS:login")]
        for i in range(len(order)):
            r = req()
            for key, _ in reversed(order[i:]):
                r[key] = 1
            self.assertEqual(code(r), P + order[i][1])

    def test_alphabetically_first_key_in_class(self):
        self.assertEqual(code(req(token=1, approve=1)), P + "SEND:approve")
        self.assertEqual(code(req(upload=1, deploy=1, post=1)), P + "EFFECT:deploy")
        self.assertEqual(code(req(voice_clone=1, celebrity=1)), P + "DECEPTIVE:celebrity")

    def test_nested_in_dicts_lists_and_tuples(self):
        r = req()
        r["agents"][1]["traits"] = [{"deep": [{"likeness": 1}]}]
        self.assertEqual(code(r), P + "DECEPTIVE:likeness")
        self.assertEqual(code(req(scenario={"kind": "daily_life", "x": ({"publish": 1},)})), P + "EFFECT:publish")

    def test_forbidden_key_beats_unknown_and_type_errors(self):
        self.assertEqual(code(dict(req(seed="x"), likeness=1, junk=1)), P + "DECEPTIVE:likeness")

    def test_values_are_not_scanned(self):
        self.assertIsNone(code(req(scenario={"kind": "commercial_storyboard", "product": "publish likeness token"})))

    def test_refusal_never_echoes_content(self):
        secret = "ZZ-SECRET-9"
        for r in (req(**{secret: 1}), req(scenario={"kind": secret}), req(agents=[agent(secret * 40)]),
                  req(as_of=secret)):
            self.assertNotIn(secret, code(r) or "")
        self.assertNotIn(secret, code(req(**{secret: 1, "publish": secret})))


class Structure(unittest.TestCase):
    def test_request_not_dict(self):
        for r in (None, [], (), "x", 1):
            self.assertEqual(code(r), P + "BAD_TYPE:request")

    def test_non_str_key(self):
        self.assertEqual(code({**req(), 1: 2}), P + "BAD_TYPE:key")
        r = req()
        r["agents"][0][2] = 1
        self.assertEqual(code(r), P + "BAD_TYPE:key")

    def test_unknown_keys_each_level(self):
        self.assertEqual(code(req(extra=1)), P + "UNKNOWN:request")
        r = req(); r["world"]["x"] = 1
        self.assertEqual(code(r), P + "UNKNOWN:world")
        r = req(); r["agents"][1]["x"] = 1
        self.assertEqual(code(r), P + "UNKNOWN:agents")
        r = req(); r["scenario"]["x"] = 1
        self.assertEqual(code(r), P + "UNKNOWN:scenario")

    def test_unknown_kind_and_steps_seed(self):
        self.assertEqual(code(req(scenario={"kind": "news"})), P + "UNKNOWN:kind")
        for steps in (0, -1):
            r = req(); r["world"]["steps"] = steps
            self.assertEqual(code(r), P + "BAD_TYPE:steps")
        r = req(); r["world"]["steps"] = 101
        self.assertEqual(code(r), P + "OVERSIZE:steps")
        for bad in (True, False, 1.0, "7", None):
            r = req(); r["world"]["steps"] = bad
            self.assertEqual(code(r), P + "BAD_TYPE:steps", repr(bad))
            self.assertEqual(code(req(seed=bad if bad is not None else None)), P + "BAD_TYPE:seed", repr(bad))
        self.assertEqual(code(req(seed=-1)), P + "BAD_TYPE:seed")
        self.assertEqual(code(req(seed=4294967296)), P + "OVERSIZE:seed")

    def test_seed_and_steps_bounds_accepted(self):
        self.assertIsNone(code(req(seed=0)))
        self.assertIsNone(code(req(seed=4294967295)))
        r = req(); r["world"]["steps"] = 100
        self.assertEqual(w.run(r)["coverage"]["steps"], 100)
        r["world"]["steps"] = 1
        self.assertEqual(w.run(r)["coverage"]["events"], 2)

    def test_top_level_types(self):
        for k, v, f in (("as_of", 5, "as_of"), ("as_of", "2026-02-30", "as_of"), ("as_of", "0000-01-01", "as_of"),
                        ("as_of", "2026-1-1", "as_of"), ("world", [], "world"), ("agents", (), "agents"),
                        ("scenario", "x", "scenario")):
            self.assertEqual(code(req(**{k: v})), P + "BAD_TYPE:" + f, (k, v))
        self.assertIsNone(code(req(as_of="2028-02-29")))
        for bad in ("2027-02-29", "2026-02-29", "1900-02-29", "2100-02-29", "2026-10-00", "2026-00-10", "2026-13-01", "2026-04-31"):
            self.assertEqual(code(req(as_of=bad)), P + "BAD_TYPE:as_of", bad)
        for good in ("2000-02-29", "2024-02-29", "0001-01-01", "2026-12-31"):
            self.assertIsNone(code(req(as_of=good)), good)

    def test_missing_fields(self):
        for k in ("as_of", "seed", "world", "agents", "scenario"):
            r = req(); del r[k]
            self.assertEqual(code(r), P + "BAD_TYPE:" + k)
        r = req(); r["world"] = {"name": "W", "places": ["p"]}
        self.assertEqual(code(r), P + "BAD_TYPE:steps")
        r = req(); r["scenario"] = {"kind": "commercial_storyboard"}
        self.assertEqual(code(r), P + "BAD_TYPE:product")

    def test_type_before_empty_compound_pins(self):
        r = req(); r["world"]["name"] = None; r["world"]["places"] = []
        self.assertEqual(code(r), P + "BAD_TYPE:world_name")
        r = req(); r["world"]["places"] = None
        self.assertEqual(code(r), P + "BAD_TYPE:places")
        for bad in ("pier", ("pier",), {"a": 1}, 5, True):
            r = req(); r["world"]["places"] = bad
            self.assertEqual(code(r), P + "BAD_TYPE:places", repr(bad))
        r = req(scenario={"kind": "daily_life", "product": 1}, agents=[])
        self.assertEqual(code(r), P + "BAD_TYPE:product")
        r = req(scenario={"kind": "commercial_storyboard", "product": 1}, agents=[])
        self.assertEqual(code(r), P + "BAD_TYPE:product")
        r = req(agents="x")
        self.assertEqual(code(r), P + "BAD_TYPE:agents")

    def test_empty_lists(self):
        self.assertEqual(code(req(agents=[])), P + "EMPTY")
        r = req(); r["world"]["places"] = []
        self.assertEqual(code(r), P + "EMPTY")
        self.assertEqual(code(req(agents=[agent(traits=())])), P + "EMPTY")
        self.assertEqual(code(req(agents=[agent(actions=())])), P + "EMPTY")
        self.assertEqual(code(req(agents=[agent(name="   ")])), P + "EMPTY:name")

    def test_duplicates(self):
        self.assertEqual(code(req(agents=[agent("a1"), agent("a1", "Other")])), P + "BAD_TYPE:agents")
        for pair in (["Pier", "pier"], ["pier", "Pier"], ["STRASSE", "stra\u00dfe"]):
            r = req(); r["world"]["places"] = pair
            self.assertEqual(code(r), P + "BAD_TYPE:places", pair)
        self.assertIsNone(code(req(agents=[agent("a1"), agent("A1", "Other")])))

    def test_agent_item_types(self):
        self.assertEqual(code(req(agents=["x"])), P + "BAD_TYPE:agents")
        for bad in (1, None, ["x"]):
            self.assertEqual(code(req(agents=[agent(i=bad)])), P + "BAD_TYPE:id")
        a = agent(); a["traits"] = "curious"
        self.assertEqual(code(req(agents=[a])), P + "BAD_TYPE:traits")
        a = agent(); a["actions"] = [1]
        self.assertEqual(code(req(agents=[a])), P + "BAD_TYPE:actions")
        a = agent(); del a["name"]
        self.assertEqual(code(req(agents=[a])), P + "BAD_TYPE:name")

    def test_str_subclass_rejected(self):
        class S(str):
            pass
        self.assertEqual(code(req(agents=[agent(name=S("Mira"))])), P + "BAD_TYPE:name")


class Caps(unittest.TestCase):
    def edit(self, f):
        r = req()
        f(r)
        return r

    def boundary(self, field, limit, build):
        self.assertIsNone(code(build("a" * limit)), field)
        self.assertEqual(code(build("a" * (limit + 1))), P + "OVERSIZE:" + field)
        self.assertIsNone(code(build("a" * (limit - 1))), field)

    def test_text_caps_n_and_n_plus_1(self):
        self.boundary("id", 64, lambda v: req(agents=[agent(i=v)]))
        self.boundary("name", 100, lambda v: req(agents=[agent(name=v)]))
        self.boundary("traits", 64, lambda v: req(agents=[agent(traits=(v,))]))
        self.boundary("actions", 64, lambda v: req(agents=[agent(actions=(v,))]))
        self.boundary("places", 100, lambda v: self.edit(lambda r: r["world"].update(places=[v])))
        self.boundary("world_name", 100, lambda v: self.edit(lambda r: r["world"].update(name=v)))
        self.boundary("product", 200, lambda v: req(scenario={"kind": "commercial_storyboard", "product": v}))

    def test_as_of_raw_cap_10_before_date_grammar(self):
        self.assertEqual(code(req(as_of="a" * 10)), P + "BAD_TYPE:as_of")
        self.assertEqual(code(req(as_of="a" * 9)), P + "BAD_TYPE:as_of")
        self.assertEqual(code(req(as_of="a" * 11)), P + "OVERSIZE:as_of")
        self.assertEqual(code(req(as_of="a" * 1000000)), P + "OVERSIZE:as_of")
        self.assertEqual(code(req(as_of="2026-10-11 ")), P + "OVERSIZE:as_of")      # 11 chars, grammar never reached
        self.assertEqual(code(req(as_of="2026-10-111")), P + "OVERSIZE:as_of")
        self.assertEqual(code(req(as_of="2026-10-1")), P + "BAD_TYPE:as_of")        # 9 chars, grammar
        self.assertIsNone(code(req(as_of="2026-10-11")))

    def test_count_caps(self):
        many = lambda n: [agent("a%d" % i, "N") for i in range(n)]
        self.assertIsNone(code(req(agents=many(50))))
        self.assertEqual(code(req(agents=many(51))), P + "OVERSIZE:agents")
        self.assertIsNone(code(req(agents=[agent(traits=["t"] * 10)])))
        self.assertEqual(code(req(agents=[agent(traits=["t"] * 11)])), P + "OVERSIZE:traits")
        self.assertIsNone(code(req(agents=[agent(actions=["t"] * 10)])))
        self.assertEqual(code(req(agents=[agent(actions=["t"] * 11)])), P + "OVERSIZE:actions")
        self.assertIsNone(code(self.edit(lambda r: r["world"].update(places=["p%d" % i for i in range(30)]))))
        self.assertEqual(code(self.edit(lambda r: r["world"].update(places=["p%d" % i for i in range(31)]))),
                         P + "OVERSIZE:places")

    def test_text_too_long_never_surfaces(self):
        cases = [req(agents=[agent(name="a" * 101)]), req(agents=[agent(traits=("a" * 65,))]),
                 req(agents=[agent(actions=("a" * 65,))]), req(agents=[agent(i="a" * 65)]),
                 self.edit(lambda r: r["world"].update(places=["a" * 101])),
                 req(scenario={"kind": "commercial_storyboard", "product": "a" * 201})]
        for r in cases:
            self.assertNotIn("TEXT_TOO_LONG", code(r))
            self.assertIn("OVERSIZE", code(r))

    def test_oversize_beats_content_errors(self):
        # an over-cap later field wins over a content error earlier in list order
        bad = agent("a1", "Mira\x00")
        long_ = agent("a2", "a" * 101)
        self.assertEqual(code(req(agents=[bad, long_])), P + "OVERSIZE:name")
        self.assertEqual(code(req(agents=[agent(name="x\u200b"), agent("a2", traits=("t",) * 11)])), P + "OVERSIZE:traits")
        self.assertEqual(code(req(agents=[{"id": "a1"}, agent("a2", "a" * 101)])), P + "OVERSIZE:name")

    def test_cap_checked_before_duplicate_and_blank(self):
        self.assertEqual(code(req(agents=[agent("a1", "   "), agent("a1", "a" * 101)])), P + "OVERSIZE:name")


class Chars(unittest.TestCase):
    def test_control_format_and_separator_characters_refused(self):
        for ch in ("\x00", "\x1f", "\x7f", "\x85", "\u200b", "\u202e", "\ufeff", "\u2028", "\u2029", "\n", "\r", "\t"):
            for build in (lambda v: req(agents=[agent(name=v)]), lambda v: req(agents=[agent(traits=(v,))]),
                          lambda v: req(agents=[agent(actions=(v,))]), lambda v: req(agents=[agent(i=v)]),
                          lambda v: req(scenario={"kind": "commercial_storyboard", "product": v})):
                c = code(build("a" + ch + "b"))
                self.assertTrue(c and c.startswith(P), (repr(ch), c))
        r = req(); r["world"]["places"] = ["a\u200bb"]
        self.assertTrue(code(r).startswith(P))

    def test_unicode_text_is_carried_not_matched(self):
        out = w.run(req(agents=[agent(name="Zo\u00eb")]))
        self.assertIn("Zo\u00eb", out["frames"][0])


class Budget(unittest.TestCase):
    OVER = P + "OVERSIZE:request"

    def test_dict_keys_32_ok_33_oversize(self):
        r = req()
        for i in range(32 - len(r)):
            r["k%d" % i] = 1
        self.assertEqual(len(r), 32)
        self.assertEqual(code(r), P + "UNKNOWN:request")
        r["z"] = 1
        self.assertEqual(code(r), self.OVER)

    def test_list_items_64_ok_65_oversize(self):
        r = req(); r["agents"][0]["traits"] = ["t"] * 10
        self.assertIsNone(code(r))
        x = {"a": [1] * 64}
        self.assertEqual(code(req(extra=x)), P + "UNKNOWN:request")
        self.assertEqual(code(req(extra={"a": [1] * 65})), self.OVER)
        self.assertEqual(code(req(extra={"a": (1,) * 65})), self.OVER)
        # schema cap still fires first for agents at 51..64 and the scan takes over at 65
        many = lambda n: [agent("a%d" % i) for i in range(n)]
        self.assertEqual(code(req(agents=many(64))), P + "OVERSIZE:agents")
        self.assertEqual(code(req(agents=many(65))), self.OVER)

    def test_depth_32_ok_33_oversize(self):
        def nest(d, leaf):
            for _ in range(d):
                leaf = [leaf]
            return leaf
        self.assertEqual(code(req(extra=nest(30, {"login": 1}))), P + "NOCREDS:login")  # request=0, extra list=1 ... dict at 31
        self.assertEqual(code(req(extra=nest(31, {"login": 1}))), P + "NOCREDS:login")  # dict at depth 32
        self.assertEqual(code(req(extra=nest(32, {"login": 1}))), self.OVER)            # dict would be depth 33

    def test_container_budget_10000_ok_10001_oversize(self):
        def distinct(o):
            seen, stack = set(), [o]
            while stack:
                n = stack.pop()
                if type(n) in (dict, list, tuple) and id(n) not in seen:
                    seen.add(id(n))
                    stack.extend(n.values() if type(n) is dict else n)
            return len(seen)
        def with_total(total):
            r = req(extra=[])
            need = total - distinct(r)
            groups = []
            while need > 0:
                group = []
                need -= 1                      # the group list itself
                while need > 0 and len(group) < 60:
                    k = min(need - 1, 60)      # one chunk list + k empty lists
                    if k < 0:
                        break
                    group.append([[] for _ in range(k)])
                    need -= k + 1
                groups.append(group)
            self.assertEqual(need, 0)
            r["extra"] = groups
            self.assertEqual(distinct(r), total)
            self.assertLessEqual(max(len(g) for g in groups), 64)
            return r
        self.assertEqual(code(with_total(10000)), P + "UNKNOWN:request")
        self.assertEqual(code(with_total(10001)), self.OVER)

    def test_shared_container_counted_once(self):
        shared = []
        self.assertEqual(code(req(extra=[shared] * 60 + [[shared] * 60])), P + "UNKNOWN:request")

    def test_cycle_terminates(self):
        a = []
        a.append(a)
        self.assertEqual(code(req(extra=a)), P + "UNKNOWN:request")

    def test_oversize_beats_forbidden_and_non_str_keys(self):
        big = {"k%d" % i: 1 for i in range(33)}
        big["publish"] = 1
        self.assertEqual(code(req(extra=big)), self.OVER)
        self.assertEqual(code(req(extra=[{1: 2}] + [[]] * 64)), self.OVER)


class _Counting:
    reads = 0


class Hostile(unittest.TestCase):
    def test_dict_subclass_never_read_even_with_lying_len(self):
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

            def keys(self):
                type(self).reads += 1
                return dict.keys(self)

            def values(self):
                type(self).reads += 1
                return dict.values(self)

            def get(self, *a):
                type(self).reads += 1
                return dict.get(self, *a)

            def __getitem__(self, k):
                type(self).reads += 1
                return dict.__getitem__(self, k)
        big = Liar({"k%d" % i: 1 for i in range(100000)})
        for r in (req(extra=big), req(world=big), req(scenario=big), req(agents=[big]), Liar(req())):
            self.assertEqual(code(r), P + "BAD_TYPE:request")
        self.assertEqual(Liar.reads, 0)

    def test_list_and_tuple_subclasses_never_read(self):
        class LL(list):
            reads = 0

            def __len__(self):
                return 1

            def __iter__(self):
                type(self).reads += 1
                return list.__iter__(self)

            def __getitem__(self, i):
                type(self).reads += 1
                return list.__getitem__(self, i)

        class LT(tuple):
            reads = 0

            def __len__(self):
                return 1

            def __iter__(self):
                type(self).reads += 1
                return tuple.__iter__(self)

            def __getitem__(self, i):
                type(self).reads += 1
                return tuple.__getitem__(self, i)
        r = req()
        r["agents"] = LL([agent("a%d" % i) for i in range(5000)])
        self.assertEqual(code(r), P + "BAD_TYPE:request")
        self.assertEqual(code(req(extra=LT([()] * 5000))), P + "BAD_TYPE:request")
        r = req(); r["world"]["places"] = LL(["p"])
        self.assertEqual(code(r), P + "BAD_TYPE:request")
        r = req(); r["agents"][0]["traits"] = LT(["t"])
        self.assertEqual(code(r), P + "BAD_TYPE:request")
        self.assertEqual((LL.reads, LT.reads), (0, 0))

    def test_oversized_exact_containers_refused_without_materializing_further(self):
        # a huge exact list is refused on its length; its items are never scanned for keys
        r = req(extra=[{"publish": 1}] + [None] * 100000)
        self.assertEqual(code(r), P + "OVERSIZE:request")

    def test_str_values_never_scanned_as_keys(self):
        self.assertIsNone(code(req(agents=[agent(name="publish")])))


class Keys(unittest.TestCase):
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
            __hash__ = str.__hash__
        k = K("publish")
        K.touched = 0
        r = req(); r["agents"][0][k] = 1
        for q in (req(**{k: 1}), r, req(scenario={k: 1}), req(world={k: 1})):
            self.assertEqual(code(q), P + "BAD_TYPE:request")
        self.assertEqual(K.touched, 0)
        class K2(str):
            pass
        self.assertEqual(code(req(**{"login": 1, K2("a"): 1})), P + "BAD_TYPE:request")

    def test_raw_key_cap_200_201(self):
        self.assertEqual(code(req(**{"a" * 200: 1})), P + "UNKNOWN:request")
        self.assertEqual(code(req(**{"a" * 201: 1})), P + "OVERSIZE:request")
        r = req(); r["agents"][0]["a" * 201] = 1
        self.assertEqual(code(r), P + "OVERSIZE:request")
        self.assertEqual(code(req(**{"a" * 201: 1, "likeness": 1})), P + "OVERSIZE:request")
        self.assertEqual(code(req(**{"a" * 200: 1, "likeness": 1})), P + "DECEPTIVE:likeness")

    def test_overlong_key_never_normalized_allocation_pin(self):
        import tracemalloc
        r = req(extra={"A" * 20000000: 1})
        tracemalloc.start()
        try:
            got = code(r)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(got, P + "OVERSIZE:request")
        self.assertLess(peak, 2000000)

    def test_normalization_for_bounded_keys(self):
        self.assertEqual(code(req(**{"VOICE-CLONE": 1})), P + "DECEPTIVE:voice_clone")


class KindEnum(unittest.TestCase):
    def kind(self, v):
        return req(scenario={"kind": v, "product": "P"})

    def test_raw_cap_64_65_before_membership(self):
        self.assertEqual(code(self.kind("a" * 64)), P + "UNKNOWN:kind")
        self.assertEqual(code(self.kind("a" * 63)), P + "UNKNOWN:kind")
        self.assertEqual(code(self.kind("a" * 65)), P + "OVERSIZE:kind")
        self.assertEqual(code(self.kind("a" * 1000000)), P + "OVERSIZE:kind")
        # an overlong value that would also be a non-member refuses by cap, not membership
        self.assertEqual(code(self.kind("commercial_storyboard" + " " * 50)), P + "OVERSIZE:kind")

    def test_valid_kinds_and_non_members(self):
        for k in ("commercial_storyboard", "daily_life"):
            self.assertIsNone(code(self.kind(k)))
        for k in ("", "news", "Daily_Life", "daily_life "):
            self.assertEqual(code(self.kind(k)), P + "UNKNOWN:kind", k)

    def test_str_subclass_kind_refused_untouched(self):
        class K(str):
            touched = 0

            def __len__(self):
                type(self).touched += 1
                return str.__len__(self)

            def __eq__(self, o):
                type(self).touched += 1
                return str.__eq__(self, o)

            def __hash__(self):
                type(self).touched += 1
                return str.__hash__(self)
        k = K("daily_life")
        K.touched = 0
        self.assertEqual(code(self.kind(k)), P + "BAD_TYPE:kind")
        self.assertEqual(K.touched, 0)

    def test_non_str_kind(self):
        for v in (1, None, ["daily_life"], True):
            self.assertEqual(code(self.kind(v)), P + "BAD_TYPE:kind")


class NoEffects(unittest.TestCase):
    def test_module_exposes_only_run(self):
        public = {n for n in dir(w) if not n.startswith("_") and callable(getattr(w, n))}
        self.assertEqual(public, {"run"})

    def test_no_network_file_or_effect_imports(self):
        tree = ast.parse((_ROOT / "backend/app/modules/c36/world.py").read_text())
        mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertEqual(mods - {"__future__", "re", "app"}, set())
        calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertFalse(calls & {"open", "exec", "eval", "compile", "__import__", "print", "input"})

    def test_scope_has_limits(self):
        sc = w.run(req())["scope"]
        blob = json.dumps(sc)
        for token in ("real-person check", "media generation"):
            self.assertIn(token, blob)

    def test_input_not_mutated(self):
        r = req()
        before = json.dumps(r, sort_keys=True)
        w.run(r)
        self.assertEqual(json.dumps(r, sort_keys=True), before)


class Determinism(unittest.TestCase):
    def test_byte_identical_and_sorted(self):
        a = json.dumps(w.run(req()), sort_keys=True, ensure_ascii=False)
        b = json.dumps(w.run(json.loads(json.dumps(req()))), sort_keys=True, ensure_ascii=False)
        self.assertEqual(a, b)

    def test_seed_change_changes_output(self):
        self.assertNotEqual(json.dumps(w.run(req(seed=7))), json.dumps(w.run(req(seed=8))))


if __name__ == "__main__":
    unittest.main()
