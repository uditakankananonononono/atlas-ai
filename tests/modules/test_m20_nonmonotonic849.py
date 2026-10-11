"""Row 849 Non-Monotonic Reasoning front door: hermetic stdlib tests (test-first; RED before the module existed)."""
import copy
import pytest
from app.modules.m20_general_cognitive_worker import nonmonotonic849 as nm
from app.modules.m20_general_cognitive_worker import defeasible_reasoning as engine

P = "NONMON849"
FLY = {"id": "fly", "if": ["bird"], "unless": ["penguin"], "then": "flies"}


def req(**kw):
    d = {"facts": ["bird"], "rules": [dict(FLY)], "added_facts": [], "removed_facts": [], "query_atoms": []}
    d.update(kw)
    return d


def refusal(p):
    with pytest.raises(ValueError) as e:
        nm.revise(p)
    return str(e.value)


def test_prefix_and_caps_pinned():
    assert nm.PREFIX == P
    assert (nm.MAX_FACTS, nm.MAX_RULES, nm.MAX_PREMISES, nm.MAX_ATOM, nm.MAX_ADDED, nm.MAX_REMOVED, nm.MAX_QUERIES,
            nm.MAX_KEYS, nm.MAX_OPTIONAL_ATOMS) == (32, 16, 8, 64, 16, 16, 16, 16, 12)


def test_exception_arrives_conclusion_retracted():
    r = nm.revise(req(added_facts=["penguin"]))
    assert r["row"] == 849 and r["status"] == "recomputed_exact_stable_models_only"
    assert r["revision"] == {"added_facts": ["penguin"], "removed_facts": []}
    assert r["before"]["cautious_conclusions"] == ["bird", "flies"] and r["before"]["model_count"] == 1
    assert r["cautious_conclusions"] == ["bird", "penguin"] and r["retracted_conclusions"] == ["flies"]
    assert r["new_conclusions"] == ["penguin"] and r["revision_comparable"] is True


def test_exception_removed_conclusion_restored():
    r = nm.revise(req(facts=["bird", "penguin"], removed_facts=["penguin"]))
    assert r["before"]["cautious_conclusions"] == ["bird", "penguin"]
    assert r["new_conclusions"] == ["flies"] and r["retracted_conclusions"] == ["penguin"]
    assert r["revision"]["removed_facts"] == ["penguin"]


def test_no_revision_changes_nothing():
    r = nm.revise(req())
    assert r["retracted_conclusions"] == [] and r["new_conclusions"] == []
    assert r["stable_models"] == [["bird", "flies"]] and r["consistent"] is True


def test_matches_engine_exactly_on_revised_input():
    p = req(facts=["bird", "penguin"], removed_facts=["penguin"], added_facts=["x"], query_atoms=["flies", "z"])
    e = engine.default_inference({"facts": p["facts"], "defaults": p["rules"], "added_facts": ["x"],
                                  "removed_facts": ["penguin"], "query_atoms": ["flies", "z"]})
    r = nm.revise(p)
    for k in ("stable_models", "model_count", "cautious_conclusions", "possible_conclusions", "ambiguous_conclusions",
              "consistent", "queries", "retracted_conclusions", "new_conclusions"):
        assert r[k] == e[k], k


def test_ambiguity_is_kept_not_resolved_and_queries_carry_models():
    rules = [{"id": "a", "if": [], "unless": ["b"], "then": "a"}, {"id": "b", "if": [], "unless": ["a"], "then": "b"}]
    r = nm.revise(req(facts=[], rules=rules, query_atoms=["a", "q"]))
    assert r["model_count"] == 2 and r["cautious_conclusions"] == [] and r["ambiguous_conclusions"] == ["a", "b"]
    qa = r["queries"][0]
    assert qa["status"] == "ambiguous" and qa["supporting_model"] == ["a"] and qa["countermodel"] == ["b"]
    qq = r["queries"][1]
    assert qq["status"] == "not_entailed" and qq["not_entailed_does_not_mean_false"] is True


def test_inconsistent_program_not_comparable_and_no_false_retractions():
    rules = [{"id": "r", "if": [], "unless": ["a"], "then": "a"}]
    r = nm.revise(req(facts=[], rules=rules, query_atoms=["a"]))
    assert r["consistent"] is False and r["model_count"] == 0
    assert r["revision_comparable"] is False
    assert r["retracted_conclusions"] is None and r["new_conclusions"] is None
    assert r["queries"][0]["status"] == "inconsistent_program"


def test_before_inconsistent_after_consistent_also_not_comparable():
    rules = [{"id": "r", "if": ["t"], "unless": ["a"], "then": "a"}]
    r = nm.revise(req(facts=["t"], rules=rules, removed_facts=["t"]))
    assert r["before"]["consistent"] is False and r["consistent"] is True
    assert r["revision_comparable"] is False and r["new_conclusions"] is None and r["retracted_conclusions"] is None


def test_honesty_fields():
    r = nm.revise(req())
    assert r["no_real_world_truth_claim"] is True and r["default_priority_applied"] is False
    assert r["boundary"] == nm.BOUNDARY and "stable model" in nm.BOUNDARY


def test_input_not_mutated_and_deterministic():
    p = req(added_facts=["penguin"], query_atoms=["flies"])
    b = copy.deepcopy(p)
    r1 = nm.revise(p)
    assert p == b and nm.revise(p) == r1


# ---- types
def test_payload_exact_dict_and_subclass_untouched():
    class D(dict):
        touched = 0

        def __len__(self):
            D.touched += 1
            return 0

        def __iter__(self):
            D.touched += 1
            return iter(())

        def __getitem__(self, k):
            D.touched += 1
            raise KeyError

        def get(self, *a):
            D.touched += 1

        def __contains__(self, k):
            D.touched += 1
            return False
    assert refusal([]) == P + ":BAD_TYPE:payload"
    assert refusal(None) == P + ":BAD_TYPE:payload"
    assert refusal(D(req())) == P + ":BAD_TYPE:payload"
    assert D.touched == 0


def test_lists_exact_list_subclass_untouched_and_tuple_refused():
    class L(list):
        touched = 0

        def __len__(self):
            L.touched += 1
            return 1

        def __iter__(self):
            L.touched += 1
            return iter(())

        def __getitem__(self, i):
            L.touched += 1
            raise IndexError
    for key in ("facts", "rules", "added_facts", "removed_facts", "query_atoms"):
        assert refusal(req(**{key: L(["bird"])})) == P + ":BAD_TYPE:" + key
        assert refusal(req(**{key: ("bird",)})) == P + ":BAD_TYPE:" + key
        assert refusal(req(**{key: None})) == P + ":BAD_TYPE:" + key
    assert refusal(req(rules=[dict(FLY, **{"if": L(["bird"])})])) == P + ":BAD_TYPE:if"
    assert refusal(req(rules=[dict(FLY, unless=L([]))])) == P + ":BAD_TYPE:unless"
    assert L.touched == 0


def test_rule_exact_dict_and_subclass():
    class D(dict):
        pass
    assert refusal(req(rules=[D(FLY)])) == P + ":BAD_TYPE:rule"
    assert refusal(req(rules=["x"])) == P + ":BAD_TYPE:rule"


def test_atoms_exact_str_empty_and_subclass():
    class S(str):
        pass
    for key in ("facts", "added_facts", "query_atoms"):
        assert refusal(req(**{key: [3]})) == P + ":BAD_TYPE:atom"
        assert refusal(req(**{key: [S("x")]})) == P + ":BAD_TYPE:atom"
        assert refusal(req(**{key: [""]})) == P + ":EMPTY:atom"
        assert refusal(req(**{key: ["  "]})) == P + ":EMPTY:atom"
    assert refusal(req(rules=[dict(FLY, then=5)])) == P + ":BAD_TYPE:atom"
    assert refusal(req(rules=[dict(FLY, then=S("f"))])) == P + ":BAD_TYPE:atom"
    assert refusal(req(rules=[dict(FLY, **{"if": [None]})])) == P + ":BAD_TYPE:atom"
    assert refusal(req(rules=[dict(FLY, unless=[S("p")])])) == P + ":BAD_TYPE:atom"


def test_atom_cap_n_and_n_plus_1_raw_before_scan():
    ok = "a" * 64
    assert nm.revise(req(facts=[ok]))["revision"]
    assert refusal(req(facts=["a" * 65])) == P + ":TEXT_TOO_LONG:atom"
    assert refusal(req(facts=[" " * 65])) == P + ":TEXT_TOO_LONG:atom"
    assert refusal(req(facts=["\x00" * 65])) == P + ":TEXT_TOO_LONG:atom"
    assert refusal(req(rules=[dict(FLY, then="a" * 65)])) == P + ":TEXT_TOO_LONG:atom"


@pytest.mark.parametrize("ch", ["\x00", "\n", "\x7f", "\u00ad", "\u2060", "\u200b", "\u202e", "\u2028", "\u2029"])
def test_refused_unicode_categories(ch):
    assert refusal(req(facts=["a" + ch])) == P + ":CONTROL_CHARS:atom"
    assert refusal(req(rules=[dict(FLY, id="i" + ch)])) == P + ":CONTROL_CHARS:rule_id"


def test_space_separator_accepted_in_atoms():
    assert nm.revise(req(facts=["bird", "a\u00a0b"]))


def test_refusals_never_echo_content():
    s = "SECRET-TOKEN-9917"
    for p in (req(facts=[s + "\x00"]), req(**{s: 1}), req(rules=[dict(FLY, **{s: 1})]), req(added_facts=[s], removed_facts=[s]),
              req(removed_facts=[s]), req(rules=[dict(FLY, id=s), dict(FLY, id=s)]),
              req(facts=[s, s]), req(rules=[dict(FLY, then=s * 70)])):
        assert s not in refusal(p)


# ---- keys
def test_key_count_cap_before_content_and_boundaries():
    big = {"k%d" % i: 1 for i in range(17)}
    assert refusal(big) == P + ":TOO_MANY:keys"
    pad = req()
    for i in range(16 - len(pad)):
        pad["x%d" % i] = 1
    assert len(pad) == 16 and refusal(pad) == P + ":UNKNOWN_KEY"
    pad["x99"] = 1
    assert refusal(pad) == P + ":TOO_MANY:keys"
    r = dict(FLY)
    for i in range(16 - len(r)):
        r["x%d" % i] = 1
    assert len(r) == 16 and refusal(req(rules=[r])) == P + ":UNKNOWN_KEY"
    r["x99"] = 1
    assert refusal(req(rules=[r])) == P + ":TOO_MANY:keys"


def test_non_str_key_and_str_subclass_key_refused():
    class S(str):
        pass
    p = req()
    p[1] = 2
    assert refusal(p) == P + ":BAD_TYPE:key"
    p = req()
    p[S("zzz")] = 1
    assert refusal(p) == P + ":BAD_TYPE:key"
    r = dict(FLY)
    r[2] = 1
    assert refusal(req(rules=[r])) == P + ":BAD_TYPE:key"


def test_unknown_and_missing_keys():
    assert refusal(req(extra=1)) == P + ":UNKNOWN_KEY"
    for k in ("facts", "rules", "added_facts", "removed_facts", "query_atoms"):
        p = req()
        del p[k]
        assert refusal(p) == P + ":MISSING:" + k
    for k in ("id", "if", "unless", "then"):
        r = dict(FLY)
        del r[k]
        assert refusal(req(rules=[r])) == P + ":MISSING:" + k


@pytest.mark.parametrize("k", ["decide", "conclusion", "determination", "truth", "advice"])
def test_conclusion_style_keys_refused(k):
    assert refusal(req(**{k: True})) == P + ":CONCLUSION_REFUSED"
    assert refusal(req(rules=[dict(FLY, **{k: 1})])) == P + ":CONCLUSION_REFUSED"
    assert refusal(req(**{k: False})) == P + ":UNKNOWN_KEY"


# ---- caps
def test_list_caps_n_and_n_plus_1_and_empty_rules():
    assert refusal(req(rules=[])) == P + ":EMPTY:rules"
    assert nm.revise(req(facts=["f%d" % i for i in range(32)]))
    assert refusal(req(facts=["f%d" % i for i in range(33)])) == P + ":TOO_MANY:facts"
    rs = [{"id": "r%d" % i, "if": [], "unless": [], "then": "t%d" % i} for i in range(12)]
    assert nm.revise(req(rules=rs[:12], facts=[]))
    rs16 = [{"id": "r%d" % i, "if": [], "unless": [], "then": "t0"} for i in range(16)]
    assert nm.revise(req(rules=rs16, facts=[]))
    assert refusal(req(rules=rs16 + [{"id": "r16", "if": [], "unless": [], "then": "t0"}])) == P + ":TOO_MANY:rules"
    assert nm.revise(req(added_facts=["n%d" % i for i in range(16)], facts=["bird"]))
    assert refusal(req(added_facts=["n%d" % i for i in range(17)])) == P + ":TOO_MANY:added_facts"
    facts = ["f%d" % i for i in range(16)]
    assert nm.revise(req(facts=facts, removed_facts=facts))
    assert refusal(req(facts=facts + ["g"], removed_facts=facts + ["g"])) == P + ":TOO_MANY:removed_facts"
    assert nm.revise(req(query_atoms=["q%d" % i for i in range(16)]))
    assert refusal(req(query_atoms=["q%d" % i for i in range(17)])) == P + ":TOO_MANY:query_atoms"
    assert nm.revise(req(rules=[dict(FLY, **{"if": ["p%d" % i for i in range(8)], "unless": []})], facts=[]))
    assert refusal(req(rules=[dict(FLY, **{"if": ["p%d" % i for i in range(9)]})])) == P + ":TOO_MANY:if"
    assert nm.revise(req(rules=[dict(FLY, unless=["u%d" % i for i in range(8)])]))
    assert refusal(req(rules=[dict(FLY, unless=["u%d" % i for i in range(9)])])) == P + ":TOO_MANY:unless"


def test_oversize_beats_content_errors():
    assert refusal(req(facts=[1] * 33)) == P + ":TOO_MANY:facts"
    assert refusal(req(rules=[3] * 17)) == P + ":TOO_MANY:rules"
    assert refusal(req(query_atoms=[None] * 17)) == P + ":TOO_MANY:query_atoms"
    assert refusal(req(rules=[dict(FLY, **{"if": [5] * 9})])) == P + ":TOO_MANY:if"


def test_type_refusals_before_empty_in_compound():
    assert refusal(req(rules=None)) == P + ":BAD_TYPE:rules"
    assert refusal(req(rules=[dict(FLY, id=None)])) == P + ":BAD_TYPE:rule_id"
    assert refusal(req(rules=[dict(FLY, id="")])) == P + ":EMPTY:rule_id"


def test_duplicates_refused():
    assert refusal(req(facts=["a", "a"])) == P + ":DUPLICATE:facts"
    assert refusal(req(added_facts=["a", "a"])) == P + ":DUPLICATE:added_facts"
    assert refusal(req(facts=["a"], removed_facts=["a", "a"])) == P + ":DUPLICATE:removed_facts"
    assert refusal(req(query_atoms=["q", "q"])) == P + ":DUPLICATE:query_atoms"
    assert refusal(req(rules=[dict(FLY), dict(FLY)])) == P + ":DUPLICATE:rule_id"
    assert refusal(req(rules=[dict(FLY, **{"if": ["a", "a"]})])) == P + ":DUPLICATE:if"
    assert refusal(req(rules=[dict(FLY, unless=["a", "a"])])) == P + ":DUPLICATE:unless"


def test_revision_set_rules():
    assert refusal(req(removed_facts=["nothere"])) == P + ":REMOVED_NOT_PRESENT"
    assert refusal(req(added_facts=["bird"])) == P + ":ADDED_ALREADY_PRESENT"
    assert refusal(req(facts=["bird", "x"], added_facts=["y"], removed_facts=["y"])) == P + ":REMOVED_NOT_PRESENT"
    assert refusal(req(facts=["bird"], added_facts=["bird"], removed_facts=["bird"])) == P + ":ADDED_ALREADY_PRESENT"


def test_optional_atom_cap_before_search_n_and_n_plus_1():
    # 12 optional atoms (everything not a fact) is the limit; 13 is refused before any model search.
    def prog(n):
        return [{"id": "r%d" % i, "if": [], "unless": [], "then": "t%d" % i} for i in range(n)]
    assert nm.revise(req(facts=[], rules=prog(12)))["model_count"] == 1
    assert refusal(req(facts=[], rules=prog(13))) == P + ":TOO_MANY:optional_atoms"
    # atoms counted across if/unless/then, not only heads
    r = [{"id": "r", "if": ["p%d" % i for i in range(6)], "unless": ["u%d" % i for i in range(6)], "then": "t"}]
    assert refusal(req(facts=[], rules=r)) == P + ":TOO_MANY:optional_atoms"
    r = [{"id": "r", "if": ["p%d" % i for i in range(5)], "unless": ["u%d" % i for i in range(6)], "then": "t"}]
    assert nm.revise(req(facts=[], rules=r))
    # facts do not count as optional
    r = [{"id": "r", "if": ["p%d" % i for i in range(8)], "unless": ["u%d" % i for i in range(5)], "then": "t"}]
    assert nm.revise(req(facts=["p%d" % i for i in range(8)], rules=r))


def test_optional_cap_applies_to_the_before_state_too():
    # removing facts makes them optional in the revised program; the cap is checked on both states.
    facts = ["f%d" % i for i in range(13)]
    r = [{"id": "r", "if": facts[:8], "unless": facts[8:13], "then": "t"}]
    assert refusal(req(facts=facts[:8] + ["z"], rules=r, removed_facts=facts[:8])) == P + ":TOO_MANY:optional_atoms"


def test_rule_ids_are_explicit_text():
    assert refusal(req(rules=[dict(FLY, id="x" * 257)])) == P + ":TEXT_TOO_LONG:rule_id"
    assert nm.revise(req(rules=[dict(FLY, id="x" * 256)]))


def test_engine_untouched_by_front_door_contract():
    # the unchanged engine still accepts what the front door refuses (why a front door exists)
    class S(str):
        pass
    assert engine.default_inference({"facts": [S("bird")], "defaults": [dict(FLY)]})["model_count"] == 1
    assert refusal(req(facts=[S("bird")])) == P + ":BAD_TYPE:atom"


def test_revision_lists_are_sorted_not_input_order():
    r = nm.revise(req(facts=["bird", "q", "p"], added_facts=["z", "y"], removed_facts=["q", "p"]))
    assert r["revision"] == {"added_facts": ["y", "z"], "removed_facts": ["p", "q"]}


def test_boundary_literal_text():
    assert nm.BOUNDARY == (
        "Exact finite normal logic-program stable models over caller-supplied symbolic rules. Revision recomputes "
        "models after the stated additions and removals; all alternative stable models are kept, no default "
        "priority and no real-world truth claim is made, and absence from a model is not falsity.")
    assert nm.revise(req())["boundary"] == nm.BOUNDARY


def test_before_dict_exact_keys_and_hand_known_values():
    b = nm.revise(req(added_facts=["penguin"]))["before"]
    assert set(b) == {"stable_models", "model_count", "cautious_conclusions", "consistent"}
    assert b == {"stable_models": [["bird", "flies"]], "model_count": 1,
                 "cautious_conclusions": ["bird", "flies"], "consistent": True}
