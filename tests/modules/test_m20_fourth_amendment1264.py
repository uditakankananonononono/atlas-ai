"""Row 1264 Fourth Amendment: declared search and seizure bookkeeping."""
import copy, importlib.util, pathlib, sys, tracemalloc
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "backend/app/modules/m20_general_cognitive_worker/fourth_amendment1264.py"
DOC = ROOT / "docs/M20_FOURTH_AMENDMENT1264_CONTRACT.md"
P = "FOURTH1264: "


def load(source=None, name="fourth1264"):
    spec = importlib.util.spec_from_file_location(name, SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    if source is None:
        spec.loader.exec_module(mod)
    else:
        exec(compile(source, str(SRC), "exec"), mod.__dict__)
    return mod


MOD = load()
run = MOD.map_fourth_amendment


def auth(i="a1", checked="2026-01-02"):
    return {"id": i, "citation": "Sample v. Sample", "source": "caller supplied", "last_checked": checked}


def base(**over):
    p = {"matter_id": "m-1", "jurisdiction": "Sample State", "as_of": "2026-01-01",
         "conduct": {"actor": "government", "activity": "search", "description": "vehicle opened at roadside"},
         "authorities": [auth()]}
    p.update(over)
    return p


def full():
    return base(
        standing={"claimant_label": "claimant 1", "basis": "property"},
        warrant={"status": "issued", "authority_ids": ["a1"]},
        exceptions=[{"name": "consent", "asserted_by": "prosecution", "authority_ids": ["a1"]}],
        scope_items=[{"item": "glove box", "limit_source": "consent_terms"}],
        suppression_questions=[{"question": "was the scope exceeded", "authority_ids": ["a1"]}],
        sourced_facts=[{"text": "stop at 10:00", "source_ids": ["a1"]}],
        assertions=["claimant says no consent"])


def refuse(payload, message):
    with pytest.raises(ValueError) as ei:
        run(payload)
    assert str(ei.value) == P + message


def test_complete_declaration_is_counsel_review_and_decides_nothing():
    out = run(full())
    assert out["review_state"] == "counsel_review_required"
    assert out["open_elements"] == [] and out["needs_authority_link"] == [] and out["stale_authority_ids"] == []
    assert out["government_actor_declared"] is True
    assert out["legal_conclusion"] is None and out["reasonableness_decided"] is False
    assert out["suppression_decided"] is False and out["authority_independently_verified"] is False
    assert out["filing_or_external_effect"] is False and out["requires_licensed_counsel"] is True
    assert out["authorities"][0]["independently_verified"] is False
    assert out["boundary"].startswith("Legal work product for review, not legal advice.")
    assert out["row"] == 1264 and out["status"] == "declared_bookkeeping_only"


def test_minimal_declaration_lists_every_open_element():
    out = run(base())
    assert out["open_elements"] == ["standing", "warrant", "exception", "scope", "suppression"]
    assert out["review_state"] == "incomplete"


def test_unlinked_items_stale_and_private_actor_keep_it_incomplete():
    p = full()
    p["warrant"]["authority_ids"] = []
    p["exceptions"][0]["authority_ids"] = []
    p["suppression_questions"][0]["authority_ids"] = []
    out = run(p)
    assert out["needs_authority_link"] == ["warrant", "exception:consent", "suppression_question:1"]
    assert out["review_state"] == "incomplete"
    p = full(); p["authorities"] = [auth(checked="2025-12-31")]
    out = run(p)
    assert out["stale_authority_ids"] == ["a1"] and out["review_state"] == "incomplete"
    p = full(); p["conduct"]["actor"] = "private"
    out = run(p)
    assert out["government_actor_declared"] is False and out["review_state"] == "incomplete"


def test_warrant_none_needs_no_authority_link():
    p = full(); p["warrant"] = {"status": "none"}
    assert "warrant" not in run(p)["needs_authority_link"]


def test_input_is_not_mutated_and_output_is_independent():
    p = full(); before = copy.deepcopy(p)
    out = run(p)
    assert p == before
    out["exceptions"][0]["authority_ids"].append("x")
    assert p == before


@pytest.mark.parametrize("bad", [None, [], "x", 5, ()])
def test_payload_must_be_an_object(bad):
    refuse(bad, "invalid_payload: payload requires an object")


def test_unknown_and_missing_top_level_fields():
    refuse(base(ruling="reasonable"), "invalid_payload: payload has unsupported fields")
    for k in ("matter_id", "jurisdiction", "as_of", "conduct", "authorities"):
        p = base(); del p[k]
        refuse(p, f"invalid_{k}: {k} is required")


def test_text_rules_order_and_no_echo():
    secret = "TOPSECRET"
    for field, make in (("matter_id", lambda v: base(matter_id=v)), ("jurisdiction", lambda v: base(jurisdiction=v))):
        refuse(make(5), f"invalid_{field}: {field} requires text")
        refuse(make("x" * 201), f"invalid_{field}: {field} exceeds 200 characters")
        refuse(make(" " * 201), f"invalid_{field}: {field} exceeds 200 characters")
        refuse(make("   "), f"invalid_{field}: {field} requires non-blank text")
        refuse(make("a\u202eb"), f"invalid_{field}: {field} contains disallowed characters")
        refuse(make(secret + "\x00"), f"invalid_{field}: {field} contains disallowed characters")
        for ch in ("\x7f", "\u2028", "\u2029", "\u200b", "\ufeff", "\u2066", "\n"):
            refuse(make("a" + ch), f"invalid_{field}: {field} contains disallowed characters")
        assert run(make("x" * 200))["matter_id"] is not None
        assert run(make("caf\u00e9 \u4e2d"))


def test_oversize_text_refused_without_scanning():
    payload = base(matter_id="x" * (10 * 1024 * 1024))
    tracemalloc.start()
    with pytest.raises(ValueError) as ei:
        run(payload)
    _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    assert str(ei.value) == P + "invalid_matter_id: matter_id exceeds 200 characters" and peak < 1_000_000


@pytest.mark.parametrize("bad", ["2026-1-1", "2026-13-01", "2026-02-30", "20260101", "2026-01-01 ", "\u0662026-01-01",
                                 "2026-01-01T00:00", "", 5, None])
def test_as_of_strict_iso_date(bad):
    with pytest.raises(ValueError) as ei:
        run(base(as_of=bad))
    assert str(ei.value).startswith(P + "invalid_as_of: as_of requires")


def test_as_of_leap_day_accepted():
    assert run(base(as_of="2028-02-29", authorities=[auth(checked="2028-03-01")]))["as_of"] == "2028-02-29"


def test_conduct_rules():
    refuse(base(conduct="x"), "invalid_conduct: conduct requires an object")
    refuse(base(conduct={"actor": "government", "activity": "search"}), "invalid_conduct: conduct requires actor, activity and description")
    refuse(base(conduct={"actor": "government", "activity": "search", "description": "d", "extra": 1}), "invalid_count: conduct exceeds 3 fields")
    for field in ("actor", "activity"):
        c = {"actor": "government", "activity": "search", "description": "d"}
        c[field] = "police"
        refuse(base(conduct=c), "invalid_conduct: conduct requires a declared label")
        c[field] = ["government"]
        refuse(base(conduct=c), "invalid_conduct: conduct requires a declared label")
    refuse(base(conduct={"actor": "government", "activity": "search", "description": "d" * 201}), "invalid_conduct: conduct exceeds 200 characters")


def test_authorities_rules():
    refuse(base(authorities=[]), "invalid_count: authorities requires at least 1 entries")
    refuse(base(authorities="a"), "invalid_authorities: authorities requires a list")
    refuse(base(authorities=[auth(str(i)) for i in range(21)]), "invalid_count: authorities exceeds 20 entries")
    assert len(run(base(authorities=[auth(str(i)) for i in range(20)]))["authorities"]) == 20
    refuse(base(authorities=[auth(), auth()]), "invalid_authorities: authorities require distinct ids")
    refuse(base(authorities=[{"id": "a"}]), "invalid_authorities: authorities entries require id, citation, source and last_checked")
    refuse(base(authorities=[dict(auth(), x=1)]), "invalid_count: authorities exceeds 4 fields")
    refuse(base(authorities=[{"id": "a", "citation": "c", "source": "s", "bogus": "d"}]), "invalid_authorities: authorities has unsupported fields")
    refuse(base(authorities=[dict(auth(), last_checked="2026-02-30")]), "invalid_authorities: authorities requires an ISO date")
    refuse(base(authorities=["a"]), "invalid_authorities: authorities requires an object")


def test_list_caps_are_checked_before_entries():
    class Boom:
        def _no(self, *a, **k):
            raise AssertionError("touched")
        __hash__ = __eq__ = __repr__ = __iter__ = __len__ = __getitem__ = _no
    for field, cap in (("exceptions", 10), ("scope_items", 10), ("suppression_questions", 10),
                       ("sourced_facts", 20), ("assertions", 20)):
        refuse(base(**{field: [Boom()] * (cap + 1)}), f"invalid_count: {field} exceeds {cap} entries")
        refuse(base(**{field: [Boom()] * 10 ** 6}), f"invalid_count: {field} exceeds {cap} entries")
        refuse(base(**{field: "x"}), f"invalid_{field}: {field} requires a list")
        refuse(base(**{field: ("a",)}), f"invalid_{field}: {field} requires a list")


def test_list_subclass_is_refused_without_calling_its_methods():
    class Evil(list):
        def __iter__(self): raise AssertionError("iterated")
        def __len__(self): raise AssertionError("len")
    refuse(base(exceptions=Evil()), "invalid_exceptions: exceptions requires a list")


def test_standing_warrant_exception_scope_question_rules():
    refuse(base(standing={"claimant_label": "c"}), "invalid_standing: standing requires claimant_label and basis")
    refuse(base(standing={"claimant_label": "c", "basis": "x"}), "invalid_standing: standing requires a declared label")
    refuse(base(standing={"claimant_label": "c", "basis": "property", "z": 1}), "invalid_count: standing exceeds 2 fields")
    refuse(base(standing={"claimant_label": "c", "z": 1}), "invalid_standing: standing has unsupported fields")
    refuse(base(warrant={}), "invalid_warrant: warrant requires status")
    refuse(base(warrant={"status": "maybe"}), "invalid_warrant: warrant requires a declared label")
    refuse(base(warrant={"status": "issued", "authority_ids": ["zz"]}), "invalid_reference: warrant must name supplied authorities")
    refuse(base(warrant={"status": "issued", "authority_ids": ["a1", "a1"]}), "invalid_reference: warrant must name distinct authorities")
    refuse(base(warrant={"status": "issued", "authority_ids": [1]}), "invalid_reference: warrant must name supplied authorities")
    refuse(base(warrant={"status": "issued", "authority_ids": ["a1"] * 11}), "invalid_count: warrant exceeds 10 entries")
    refuse(base(exceptions=[{"name": "consent"}]), "invalid_exceptions: exceptions entries require name and asserted_by")
    refuse(base(exceptions=[{"name": "hot_pursuit", "asserted_by": "defense"}]), "invalid_exceptions: exceptions requires a declared label")
    refuse(base(exceptions=[{"name": "consent", "asserted_by": "judge"}]), "invalid_exceptions: exceptions requires a declared label")
    refuse(base(scope_items=[{"item": "x"}]), "invalid_scope_items: scope_items entries require item and limit_source")
    refuse(base(scope_items=[{"item": "x", "limit_source": "vibes"}]), "invalid_scope_items: scope_items requires a declared label")
    refuse(base(suppression_questions=[{}]), "invalid_suppression_questions: suppression_questions entries require question")
    refuse(base(suppression_questions=[{"question": "q", "authority_ids": ["nope"]}]), "invalid_reference: suppression_questions must name supplied authorities")
    refuse(base(exceptions=[{"name": "consent", "asserted_by": "defense", "authority_ids": ["nope"]}]), "invalid_reference: exceptions must name supplied authorities")


def test_facts_and_assertions_are_kept_apart():
    refuse(base(sourced_facts=[{"text": "t", "source_ids": []}]), "invalid_sourced_facts: sourced_facts entries require at least one source")
    refuse(base(sourced_facts=[{"text": "t", "source_ids": ["nope"]}]), "invalid_reference: sourced_facts must name supplied authorities")
    refuse(base(sourced_facts=[{"text": "t"}]), "invalid_sourced_facts: sourced_facts entries require text and source_ids")
    refuse(base(assertions=[5]), "invalid_assertions: assertions requires text")
    out = run(full())
    assert out["sourced_facts"][0]["source_ids"] == ["a1"] and out["user_assertions"] == ["claimant says no consent"]
    assert "claimant says no consent" not in str(out["sourced_facts"])


def test_refusals_never_echo_values_or_indexes():
    secret = "TOPSECRET"
    cases = [base(matter_id=secret * 100), base(jurisdiction=secret + "\x00"), base(as_of=secret),
             base(conduct={"actor": secret, "activity": "search", "description": "d"}),
             base(standing={"claimant_label": "c", "basis": secret}),
             base(warrant={"status": "issued", "authority_ids": [secret]}),
             base(exceptions=[{"name": secret, "asserted_by": "defense"}]),
             base(authorities=[dict(auth(), x=secret)]), base(**{secret: 1}),
             base(suppression_questions=[{"question": "q", "authority_ids": [secret]}])]
    for p in cases:
        with pytest.raises(ValueError) as ei:
            run(p)
        msg = str(ei.value)
        assert msg.startswith(P) and secret not in msg


def test_decision_words_never_appear_as_true_flags():
    out = run(full())
    assert out["legal_conclusion"] is None
    text = SRC.read_text()
    for word in ("suppress_granted", "reasonable_search", "unconstitutional"):
        assert word not in text


def test_text_helper_checks_type_then_length_first():
    src = SRC.read_text()
    body = src[src.index("def _text"):src.index("def _label")]
    ops = [l.strip() for l in body.split("\n") if l.strip().startswith("if ")]
    assert ops[0] == "if type(value) is not str:" and ops[1] == "if len(value) > MAX_TEXT:"
    body = src[src.index("def _list"):src.index("def _date")]
    ops = [l.strip() for l in body.split("\n") if l.strip().startswith("if ")]
    assert ops[0] == "if type(value) is not list:" and ops[1] == "if len(value) > cap:"


def test_doc_opens_with_pin_and_ends_with_limits():
    text = DOC.read_text()
    assert "audits/coverage-register.json" in "\n".join(text.split("\n")[:8])
    assert "legal_support_1260_1309.py:21" in text
    assert text.split("\n## ")[-1].startswith("LIMITS")
    assert "cross-account" not in text and "source_document_id" not in text and "ls-remote, 21:" not in text
    assert "no Unicode control, line/paragraph separator or bidi/format characters" in text
    assert "Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use." in text
    assert "policy not applicable: pure offline" in text


def test_full_cf_category_refused_and_zs_accepted():
    import unicodedata
    for ch in ("\u00ad", "\u2060", "\u2061", "\u2064", "\u206a", "\u206f", "\u061c", "\u180e", "\U000e0001",
               "\u200b", "\u200c", "\u200d", "\u200e", "\u200f", "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
               "\u2066", "\u2067", "\u2068", "\u2069", "\ufeff", "\x7f", "\x00", "\n", "\u2028", "\u2029", "\x85"):
        assert unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp")
        refuse(base(matter_id="a" + ch), "invalid_matter_id: matter_id contains disallowed characters")
    for ch in ("\u00a0", "\u2000", "\u200a", "\u202f", "\u3000", "\u2010", "\u00e9", "\u4e2d", "\ue000", "\ufefe", "\ud800"):
        assert unicodedata.category(ch) in ("Zs", "Pd", "Ll", "Lo", "Co", "Cn", "Cs")
        assert run(base(matter_id="a" + ch))["matter_id"] == "a" + ch


def test_every_cf_code_point_is_refused():
    import sys, unicodedata
    cf = [chr(c) for c in range(sys.maxunicode + 1) if unicodedata.category(chr(c)) == "Cf"]
    assert len(cf) > 100
    for ch in cf:
        with pytest.raises(ValueError):
            run(base(jurisdiction="x" + ch))


def test_label_requires_exact_str():
    class S(str):
        pass
    refuse(base(conduct={"actor": S("government"), "activity": "search", "description": "d"}),
           "invalid_conduct: conduct requires a declared label")


def test_as_of_equal_to_last_checked_is_not_stale_and_arabic_digits_refused():
    out = run(base(as_of="2026-01-02"))
    assert out["stale_authority_ids"] == []
    refuse(base(as_of="\u0662\u0660\u0662\u0666-\u0660\u0661-\u0660\u0661"), "invalid_as_of: as_of requires an ISO date")


def test_warrant_issued_without_authority_is_flagged_and_defaults_are_empty():
    out = run(base(warrant={"status": "issued"}))
    assert out["warrant"]["authority_ids"] == [] and out["needs_authority_link"] == ["warrant"]
    assert run(base(warrant={"status": "requested"}))["needs_authority_link"] == ["warrant"]
    assert run(base(warrant={"status": "unknown"}))["needs_authority_link"] == []


def test_payload_is_never_mutated_on_refusal_either():
    p = full(); p["exceptions"].append({"name": "x"})
    before = copy.deepcopy(p)
    with pytest.raises(ValueError):
        run(p)
    assert p == before


class Hashy:
    calls = 0
    def __hash__(self):
        Hashy.calls += 1
        return 1
    def __eq__(self, other):
        Hashy.calls += 1
        return False


class SKey(str):
    pass


def hashy_dict(n=50):
    d = {}
    for _ in range(n):
        d[Hashy()] = 1
    Hashy.calls = 0
    return d


def test_dict_count_is_checked_before_any_key_is_hashed_or_scanned():
    refuse({i: 0 for i in range(10 ** 6)}, "invalid_count: payload exceeds 12 fields")
    d = hashy_dict()
    refuse(d, "invalid_count: payload exceeds 12 fields")
    assert Hashy.calls == 0
    big = {"actor": "government", "activity": "search", "description": "d"}
    big.update({f"x{i}": 1 for i in range(5000)})
    refuse(base(conduct=big), "invalid_count: conduct exceeds 3 fields")
    for field, wrap, n in (("conduct", lambda d: d, 3), ("standing", lambda d: d, 2), ("warrant", lambda d: d, 2),
                           ("exceptions", lambda d: [d], 3), ("scope_items", lambda d: [d], 2),
                           ("suppression_questions", lambda d: [d], 2), ("sourced_facts", lambda d: [d], 2),
                           ("authorities", lambda d: [d], 4)):
        d = hashy_dict()
        refuse(base(**{field: wrap(d)}), f"invalid_count: {field} exceeds {n} fields")
        assert Hashy.calls == 0


def test_keys_must_be_exact_str_before_the_allowlist():
    refuse(dict(base(), **{}) | {5: 1}, "invalid_payload: payload has unsupported fields")
    refuse(base() | {SKey("standing"): {"claimant_label": "c", "basis": "property"}}, "invalid_payload: payload has unsupported fields")
    p = base(); p[SKey("matter_id")] = p.pop("matter_id")
    refuse(p, "invalid_payload: payload has unsupported fields")
    refuse(base(conduct={5: "x", "activity": "search", "description": "d"}), "invalid_conduct: conduct has unsupported fields")
    refuse(base(conduct={SKey("actor"): "government", "activity": "search", "description": "d"}), "invalid_conduct: conduct has unsupported fields")
    hk = {Hashy(): 1, "activity": "search", "description": "d"}
    Hashy.calls = 0
    refuse(base(conduct=hk), "invalid_conduct: conduct has unsupported fields")
    assert Hashy.calls == 0
    refuse(base(authorities=[{"citation": "c", "source": "s", "last_checked": "2026-01-02", SKey("id"): "z"}]), "invalid_authorities: authorities has unsupported fields")


def test_dict_helper_source_shape():
    src = SRC.read_text()
    body = src[src.index("def _record"):src.index("def _list")]
    ops = [l.strip() for l in body.split("\n") if l.strip().startswith("if ")]
    assert ops[0] == "if type(value) is not dict:" and ops[1] == "if len(value) > len(keys):"
    assert any(l.strip().startswith("if any(type(k) is not str") for l in body.split("\n"))
    top = src[src.index("def map_fourth_amendment"):]
    ops = [l.strip() for l in top.split("\n") if l.strip().startswith("if ")]
    assert ops[0] == "if type(payload) is not dict:" and ops[1] == "if len(payload) > len(TOP_KEYS):"
    assert ops[2].startswith("if any(type(k) is not str")
    assert "_BAD_FORMAT" not in src and "'Cf'" in src


def test_label_raw_cap_comes_before_membership():
    c = {"actor": "g" * 32, "activity": "search", "description": "d"}
    refuse(base(conduct=c), "invalid_conduct: conduct requires a declared label")
    c["actor"] = "g" * 33
    refuse(base(conduct=c), "invalid_conduct: conduct labels exceed 32 characters")
    c["actor"] = "g" * (10 * 1024 * 1024)
    tracemalloc.start()
    with pytest.raises(ValueError) as ei:
        run(base(conduct=c))
    _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    assert str(ei.value) == P + "invalid_conduct: conduct labels exceed 32 characters" and peak < 1_000_000
    refuse(base(warrant={"status": "x" * 33}), "invalid_warrant: warrant labels exceed 32 characters")
    refuse(base(standing={"claimant_label": "c", "basis": "x" * 33}), "invalid_standing: standing labels exceed 32 characters")
    refuse(base(exceptions=[{"name": "consent", "asserted_by": "x" * 33}]), "invalid_exceptions: exceptions labels exceed 32 characters")
    refuse(base(scope_items=[{"item": "i", "limit_source": "x" * 33}]), "invalid_scope_items: scope_items labels exceed 32 characters")
    longest = max(len(v) for tup in (MOD.ACTORS, MOD.ACTIVITIES, MOD.STANDING_BASES, MOD.WARRANT_STATUSES, MOD.EXCEPTIONS,
                                     MOD.ASSERTED_BY, MOD.LIMIT_SOURCES) for v in tup)
    assert longest <= 32 and MOD.MAX_LABEL == 32
    assert run(base(exceptions=[{"name": "search_incident_to_arrest", "asserted_by": "defense"}]))["exceptions"]


def test_label_source_shape():
    src = SRC.read_text()
    body = src[src.index("def _label"):src.index("def _record")]
    ops = [l.strip() for l in body.split("\n") if l.strip().startswith("if ")]
    assert ops[0] == "if type(value) is not str:" and ops[1] == "if len(value) > MAX_LABEL:"
    assert ops[2] == "if value not in allowed:"


def test_refs_raw_cap_comes_before_membership():
    ok = "i" * 200
    p = base(authorities=[auth(ok)], warrant={"status": "issued", "authority_ids": [ok]})
    assert run(p)["warrant"]["authority_ids"] == [ok]
    refuse(base(warrant={"status": "issued", "authority_ids": ["z" * 200]}), "invalid_reference: warrant must name supplied authorities")
    refuse(base(warrant={"status": "issued", "authority_ids": ["z" * 201]}), "invalid_reference: warrant references exceed 200 characters")
    big = "z" * (10 * 1024 * 1024)
    payload = base(suppression_questions=[{"question": "q", "authority_ids": [big]}])
    tracemalloc.start()
    with pytest.raises(ValueError) as ei:
        run(payload)
    _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    assert str(ei.value) == P + "invalid_reference: suppression_questions references exceed 200 characters" and peak < 1_000_000
    refuse(base(exceptions=[{"name": "consent", "asserted_by": "defense", "authority_ids": ["z" * 201]}]), "invalid_reference: exceptions references exceed 200 characters")
    refuse(base(sourced_facts=[{"text": "t", "source_ids": ["z" * 201]}]), "invalid_reference: sourced_facts references exceed 200 characters")
    refuse(base(warrant={"status": "issued", "authority_ids": [5]}), "invalid_reference: warrant must name supplied authorities")


def test_refs_source_shape():
    src = SRC.read_text()
    body = src[src.index("def _refs"):src.index("def map_fourth_amendment")]
    ops = [l.strip() for l in body.split("\n") if l.strip().startswith("if ")]
    assert ops[0] == "if type(r) is not str:" and ops[1] == "if len(r) > MAX_TEXT:" and ops[2] == "if r not in known:"


def test_date_raw_length_ten_comes_first():
    for field_payload in (lambda v: base(as_of=v), lambda v: base(authorities=[auth(checked=v)])):
        field = "as_of" if field_payload("x").get("as_of") == "x" else "authorities"
        msg = P + (f"invalid_as_of: as_of requires an ISO date" if field == "as_of" else "invalid_authorities: authorities requires an ISO date")
        for bad in ("2026-01-0", "2026-01-011", "x" * 11, "x" * 201, "x" * 9, " " * 10, "\u202e" * 10, "2026-01-0\n"):
            with pytest.raises(ValueError) as ei:
                run(field_payload(bad))
            assert str(ei.value) == msg
    big = "9" * (10 * 1024 * 1024)
    payload = base(as_of=big)
    tracemalloc.start()
    with pytest.raises(ValueError) as ei:
        run(payload)
    _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    assert str(ei.value) == P + "invalid_as_of: as_of requires an ISO date" and peak < 1_000_000
    assert run(base(as_of="2026-01-01"))["as_of"] == "2026-01-01"
    refuse(base(as_of=None), "invalid_as_of: as_of requires text")


def test_date_source_shape():
    src = SRC.read_text()
    body = src[src.index("def _date"):src.index("def _refs")]
    ops = [l.strip() for l in body.split("\n") if l.strip().startswith("if ")]
    assert ops[0] == "if type(value) is not str:" and ops[1] == "if len(value) != 10:"
    assert "_text(" not in body
