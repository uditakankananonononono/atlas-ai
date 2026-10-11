"""Tests for the m23 polymath roadmap builder. All data is fictional.

Run with: pytest --noconftest tests/modules/test_m23_polymath_roadmap.py
"""
import copy
import datetime as dt
import importlib.util
import json
import pathlib
import sys

import pytest

_PATH = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m23_study_abroad/polymath_roadmap.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


R = _load(_PATH, "polymath_roadmap_under_test")
TODAY = dt.date(2026, 10, 11)


def ev(title="work", date="2026-03-01", kind="project"):
    return {"title": title, "kind": kind, "date": date}


def curriculum():
    return {
        "domains": [{"id": "math", "name": "Mathematics"}, {"id": "bio", "name": "Biology"},
                    {"id": "art", "name": "Visual art"}, {"id": "cs", "name": "Computing"}],
        "steps": [
            {"id": "m1", "domain": "math", "title": "Linear algebra basics", "hours": 20, "after": []},
            {"id": "m2", "domain": "math", "title": "Probability", "hours": 30, "after": ["m1"]},
            {"id": "b1", "domain": "bio", "title": "Cell biology notes", "hours": 10, "after": []},
            {"id": "b2", "domain": "bio", "title": "Population model", "hours": 20, "after": ["b1", "m2"]},
            {"id": "a1", "domain": "art", "title": "Portfolio piece 1", "hours": 15, "after": []},
            {"id": "c1", "domain": "cs", "title": "Python data project", "hours": 25, "after": []},
        ],
    }


def profile(**kw):
    p = {"weekly_hours": 10, "wanted_domains": ["math", "bio"], "goals": ["understand living systems with maths"],
         "domains": [
             {"domain": "math", "level": "advanced", "evidence": [ev("olympiad", "2026-01-10", "competition"), ev("notes")]},
             {"domain": "art", "level": "intermediate", "evidence": [ev("sketchbook", "2026-02-01")]},
             {"domain": "cs", "level": "beginner", "evidence": [ev("scripts", "2026-04-01")]},
         ]}
    p.update(kw)
    return p


def bridges():
    return [{"a": "math", "b": "bio", "theme": "population models"}, {"a": "art", "b": "cs", "theme": "generative art"},
            {"a": "bio", "b": "cs", "theme": "bioinformatics"}]


def flags(**kw):
    f = {"open_curriculum": False, "double_major": False, "interdisciplinary_major": False,
         "research_for_undergrads": False}
    f.update(kw)
    return f


def colleges():
    return [
        {"id": "u1", "name": "Example University", "country": "US", "source_url": "https://example.invalid/u1",
         "checked_at": "2026-09-01", "flags": flags(open_curriculum=True, double_major=True),
         "programs": ["math", "bio", "cs"]},
        {"id": "u2", "name": "Sample Institute", "country": "UK", "source_url": "https://example.invalid/u2",
         "checked_at": "2024-01-01", "flags": flags(interdisciplinary_major=True), "programs": ["math"]},
        {"id": "u3", "name": "Demo College", "country": "CA", "source_url": "https://example.invalid/u3",
         "checked_at": "2026-10-01", "flags": flags(open_curriculum=True, double_major=True,
                                                   interdisciplinary_major=True, research_for_undergrads=True),
         "programs": ["math", "bio"]},
    ]


def build(**kw):
    args = dict(profile=profile(), curriculum=curriculum(), bridges=bridges(), colleges=colleges(), today=TODAY)
    args.update(kw)
    return R.build_roadmap(**args)


def dom(rep, did):
    return next(d for d in rep["domains"] if d["id"] == did)


# ---- depth tiers and shape ---------------------------------------------------------
def test_domain_rows_cover_every_curriculum_domain_in_order():
    rep = build()
    assert [d["id"] for d in rep["domains"]] == ["math", "bio", "art", "cs"]
    assert dom(rep, "bio")["level"] is None and dom(rep, "bio")["depth_tier"] == "none"


def test_tiers():
    rep = build()
    assert dom(rep, "math")["depth_tier"] == "deep" and dom(rep, "math")["dated_evidence_count"] == 2
    assert dom(rep, "art")["depth_tier"] == "developing"
    assert dom(rep, "cs")["depth_tier"] == "started"


@pytest.mark.parametrize("level,n,tier", [
    ("beginner", 0, "none"), ("advanced", 0, "none"), ("beginner", 1, "started"), ("beginner", 3, "started"),
    ("intermediate", 1, "developing"), ("intermediate", 5, "developing"), ("advanced", 1, "developing"),
    ("advanced", 2, "deep"), ("advanced", 3, "deep"),
])
def test_tier_table(level, n, tier):
    p = profile(domains=[{"domain": "math", "level": level, "evidence": [ev(f"e{i}") for i in range(n)]}])
    assert dom(build(profile=p), "math")["depth_tier"] == tier


def test_future_dated_evidence_is_not_counted():
    p = profile(domains=[{"domain": "math", "level": "advanced",
                          "evidence": [ev("a", "2026-01-01"), ev("b", "2026-10-11"), ev("c", "2026-10-12")]}])
    d = dom(build(profile=p), "math")
    assert d["evidence_count"] == 3 and d["dated_evidence_count"] == 2 and d["future_dated_evidence_count"] == 1


@pytest.mark.parametrize("doms,pattern", [
    ([], "no_evidence"),
    ([("math", "advanced", 2)], "single_domain"),
    ([("math", "beginner", 1), ("art", "beginner", 1)], "broad_shallow"),
    ([("math", "advanced", 2), ("art", "beginner", 1)], "one_deep_few_others"),
    ([("math", "advanced", 2), ("art", "beginner", 1), ("cs", "beginner", 1)], "t_shaped"),
    ([("math", "advanced", 2), ("art", "advanced", 2)], "multi_deep"),
    ([("math", "advanced", 2), ("art", "advanced", 2), ("cs", "beginner", 1)], "multi_deep"),
    ([("math", "advanced", 0), ("art", "advanced", 0)], "no_evidence"),
])
def test_shape_patterns(doms, pattern):
    p = profile(domains=[{"domain": d, "level": lv, "evidence": [ev(f"e{i}") for i in range(n)]}
                         for d, lv, n in doms])
    rep = build(profile=p)
    assert rep["shape"]["pattern"] == pattern


def test_shape_counts():
    s = build()["shape"]
    assert s["evidenced_domains"] == 3 and s["deep_domains"] == 1 and s["pattern"] == "t_shaped"
    assert s["thresholds"] == {"breadth_min": 3, "deep_min_dated_evidence": 2}
    assert "heuristic" in s["thresholds_note"]


def test_gaps():
    g = build()["gaps"]
    assert g["wanted_without_evidence"] == ["bio"]
    p = profile(wanted_domains=["math", "art", "bio"])
    assert build(profile=p)["gaps"]["wanted_without_evidence"] == ["bio"]


# ---- schedule --------------------------------------------------------------------
def sched(rep):
    return {s["id"]: (s["start_week"], s["end_week"]) for s in rep["schedule"]["steps"]}


def test_schedule_order_round_robin_with_prerequisite_closure():
    rep = build()
    order = [s["id"] for s in rep["schedule"]["steps"]]
    assert order == ["m1", "b1", "m2", "b2"]
    assert rep["schedule"]["unscheduled"] == []
    assert rep["schedule"]["total_hours"] == 80


def test_schedule_weeks_from_weekly_hours():
    s = sched(build())
    assert s == {"m1": (1, 2), "b1": (3, 3), "m2": (4, 6), "b2": (7, 8)}


def test_weekly_hours_change_the_schedule():
    s = sched(build(profile=profile(weekly_hours=40)))
    assert s == {"m1": (1, 1), "b1": (1, 1), "m2": (1, 2), "b2": (2, 2)}


def test_fractional_hours_and_exact_boundaries():
    c = curriculum()
    for st in c["steps"]:
        st["hours"] = 5
        st["after"] = []
    s = sched(build(profile=profile(weekly_hours=10, wanted_domains=["math"]), curriculum=c))
    assert s == {"m1": (1, 1), "m2": (1, 1)}
    c["steps"][0]["hours"] = 7.5
    s = sched(build(profile=profile(weekly_hours=10, wanted_domains=["math"]), curriculum=c))
    assert s == {"m1": (1, 1), "m2": (1, 2)}


def test_prerequisite_from_unwanted_domain_is_pulled_in_and_marked():
    rep = build(profile=profile(wanted_domains=["bio"]))
    steps = {s["id"]: s for s in rep["schedule"]["steps"]}
    assert set(steps) == {"b1", "b2", "m1", "m2"}
    assert steps["m1"]["pulled_in_as_prerequisite"] is True and steps["b1"]["pulled_in_as_prerequisite"] is False


def test_each_step_comes_after_its_prerequisites():
    rep = build(profile=profile(wanted_domains=["bio", "math", "art", "cs"]))
    pos = {s["id"]: i for i, s in enumerate(rep["schedule"]["steps"])}
    for st in curriculum()["steps"]:
        for a in st["after"]:
            assert pos[a] < pos[st["id"]]
    assert len(pos) == 6


def test_beyond_horizon_goes_to_unscheduled_with_reason():
    rep = build(horizon_weeks=4)
    assert [s["id"] for s in rep["schedule"]["steps"]] == ["m1", "b1"]
    assert rep["schedule"]["unscheduled"] == [{"id": "m2", "reason": "beyond_horizon"},
                                              {"id": "b2", "reason": "beyond_horizon"}]
    assert rep["schedule"]["horizon_weeks"] == 4


def test_no_wanted_domains_means_empty_schedule():
    rep = build(profile=profile(wanted_domains=[]))
    assert rep["schedule"]["steps"] == [] and rep["schedule"]["total_hours"] == 0


def test_cycle_is_refused():
    c = curriculum()
    c["steps"][0]["after"] = ["m2"]
    with pytest.raises(R.RoadmapInputError, match="cycle"):
        build(curriculum=c)


# ---- bridges ---------------------------------------------------------------------
def test_bridges_ready_or_missing():
    b = build()["bridges"]
    assert b[0] == {"a": "math", "b": "bio", "theme": "population models", "status": "needs", "missing": ["bio"]}
    assert b[1]["status"] == "ready" and b[1]["missing"] == []
    assert b[2]["missing"] == ["bio"]
    p = profile(domains=profile()["domains"] + [{"domain": "bio", "level": "beginner", "evidence": [ev("b")]}])
    assert [x["status"] for x in build(profile=p)["bridges"]] == ["ready", "ready", "ready"]


def test_bridge_unknown_domain_or_self_pair_refused():
    with pytest.raises(R.RoadmapInputError):
        build(bridges=[{"a": "math", "b": "ghost", "theme": "t"}])
    with pytest.raises(R.RoadmapInputError):
        build(bridges=[{"a": "math", "b": "math", "theme": "t"}])
    with pytest.raises(R.RoadmapInputError):
        build(bridges=[{"a": "math", "b": "bio", "theme": " "}])


# ---- colleges ---------------------------------------------------------------------
def test_college_rows_and_order():
    cs = build()["colleges"]
    assert [c["id"] for c in cs] == ["u1", "u3", "u2"] or [c["id"] for c in cs] == ["u3", "u1", "u2"]
    by = {c["id"]: c for c in cs}
    assert by["u1"]["covered_wanted"] == ["math", "bio"] and by["u1"]["missing_wanted"] == []
    assert by["u2"]["covered_wanted"] == ["math"] and by["u2"]["missing_wanted"] == ["bio"]
    assert by["u3"]["flag_count"] == 4 and by["u1"]["flag_count"] == 2 and by["u2"]["flag_count"] == 1
    assert by["u1"]["flags_true"] == ["open_curriculum", "double_major"]


def test_order_is_coverage_then_flags_then_id():
    assert [c["id"] for c in build()["colleges"]] == ["u3", "u1", "u2"]
    c = colleges()
    c[0]["flags"] = flags(open_curriculum=True, double_major=True, interdisciplinary_major=True,
                          research_for_undergrads=True)
    assert [x["id"] for x in build(colleges=c)["colleges"]] == ["u1", "u3", "u2"]
    c = colleges()
    c[1]["programs"] = ["math", "bio"]
    c[1]["flags"] = flags()
    assert [x["id"] for x in build(colleges=c)["colleges"]] == ["u3", "u1", "u2"]
    c[0]["programs"] = ["cs"]
    assert [x["id"] for x in build(colleges=c)["colleges"]][-1] == "u1"


def test_staleness():
    by = {c["id"]: c for c in build()["colleges"]}
    assert by["u2"]["stale"] is True and by["u2"]["age_days"] == (TODAY - dt.date(2024, 1, 1)).days
    assert by["u1"]["stale"] is False and by["u1"]["age_days"] == 40
    c = colleges()
    c[0]["checked_at"] = (TODAY - dt.timedelta(days=365)).isoformat()
    assert {x["id"]: x["stale"] for x in build(colleges=c)["colleges"]}["u1"] is False
    c[0]["checked_at"] = (TODAY - dt.timedelta(days=366)).isoformat()
    assert {x["id"]: x["stale"] for x in build(colleges=c)["colleges"]}["u1"] is True


def test_college_provenance_is_stated_not_verified():
    c = build()["colleges"][0]
    assert c["provenance"] == "caller-supplied table; not verified by this module"
    assert c["source_url"].startswith("https://")


@pytest.mark.parametrize("mut", [
    lambda c: c.__setitem__("flags", {"open_curriculum": True}),
    lambda c: c["flags"].__setitem__("open_curriculum", "yes"),
    lambda c: c["flags"].__setitem__("surprise", True),
    lambda c: c.__setitem__("programs", ["ghost"]),
    lambda c: c.__setitem__("programs", "math"),
    lambda c: c.__setitem__("source_url", "http://example.invalid/x"),
    lambda c: c.__setitem__("source_url", ""),
    lambda c: c.__setitem__("checked_at", "2026-13-01"),
    lambda c: c.__setitem__("checked_at", "2026-10-12"),
    lambda c: c.__setitem__("checked_at", 5),
    lambda c: c.__setitem__("id", ""),
    lambda c: c.__setitem__("name", " "),
    lambda c: c.__setitem__("country", None),
])
def test_bad_college_rows_refused(mut):
    cs = colleges()
    mut(cs[0])
    with pytest.raises(R.RoadmapInputError):
        build(colleges=cs)


def test_duplicate_college_ids_refused():
    cs = colleges()
    cs[1]["id"] = "u1"
    with pytest.raises(R.RoadmapInputError):
        build(colleges=cs)


# ---- input validation -----------------------------------------------------------
@pytest.mark.parametrize("mut", [
    lambda p: p.__setitem__("weekly_hours", 0),
    lambda p: p.__setitem__("weekly_hours", -3),
    lambda p: p.__setitem__("weekly_hours", True),
    lambda p: p.__setitem__("weekly_hours", "10"),
    lambda p: p.__setitem__("weekly_hours", 101),
    lambda p: p.__setitem__("wanted_domains", ["ghost"]),
    lambda p: p.__setitem__("wanted_domains", ["math", "math"]),
    lambda p: p.__setitem__("wanted_domains", "math"),
    lambda p: p.__setitem__("goals", "x"),
    lambda p: p.__setitem__("goals", [1]),
    lambda p: p["domains"][0].__setitem__("level", "expert"),
    lambda p: p["domains"][0].__setitem__("domain", "ghost"),
    lambda p: p["domains"].append(copy.deepcopy(p["domains"][0])),
    lambda p: p["domains"][0]["evidence"][0].__setitem__("date", "yesterday"),
    lambda p: p["domains"][0]["evidence"][0].__setitem__("title", ""),
    lambda p: p["domains"][0]["evidence"][0].__setitem__("kind", "vibes"),
    lambda p: p["domains"][0].__setitem__("evidence", "none"),
    lambda p: p.pop("weekly_hours"),
    lambda p: p.pop("wanted_domains"),
    lambda p: p.pop("domains"),
])
def test_bad_profiles_refused(mut):
    p = profile()
    mut(p)
    with pytest.raises(R.RoadmapInputError):
        build(profile=p)


@pytest.mark.parametrize("mut", [
    lambda c: c["steps"][0].__setitem__("hours", 0),
    lambda c: c["steps"][0].__setitem__("hours", True),
    lambda c: c["steps"][0].__setitem__("hours", "5"),
    lambda c: c["steps"][0].__setitem__("domain", "ghost"),
    lambda c: c["steps"][0].__setitem__("after", ["ghost"]),
    lambda c: c["steps"][0].__setitem__("after", ["m1"]),
    lambda c: c["steps"][1].__setitem__("id", "m1"),
    lambda c: c["steps"][0].__setitem__("title", ""),
    lambda c: c["domains"].append(dict(c["domains"][0])),
    lambda c: c["domains"][0].__setitem__("name", ""),
    lambda c: c.pop("steps"),
    lambda c: c.pop("domains"),
])
def test_bad_curriculum_refused(mut):
    c = curriculum()
    mut(c)
    with pytest.raises(R.RoadmapInputError):
        build(curriculum=c)


@pytest.mark.parametrize("kw", [
    {"today": "2026-10-11"}, {"today": dt.datetime(2026, 10, 11, 1, 2)}, {"horizon_weeks": 0},
    {"horizon_weeks": True}, {"horizon_weeks": 1.5}, {"horizon_weeks": 521}, {"profile": []},
    {"curriculum": None}, {"bridges": {}}, {"colleges": "x"},
])
def test_bad_top_level_args_refused(kw):
    with pytest.raises(R.RoadmapInputError):
        build(**kw)


def test_empty_bridges_and_colleges_are_allowed():
    rep = build(bridges=[], colleges=[])
    assert rep["bridges"] == [] and rep["colleges"] == []


# ---- honesty / purity ------------------------------------------------------------
def test_boundary_and_flags():
    rep = build()
    assert rep["requires_approval_before_any_external_action"] is True
    assert rep["makes_ability_claim"] is False
    b = rep["boundary"]
    for frag in ("not a prediction of admission", "does not verify", "No message was sent", "caller-supplied"):
        assert frag in b


def test_goals_are_echoed_unchanged():
    assert build()["goals"] == ["understand living systems with maths"]


def test_inputs_not_mutated_and_output_is_json_and_deterministic():
    p, c, b, cs = profile(), curriculum(), bridges(), colleges()
    snap = copy.deepcopy((p, c, b, cs))
    r1 = R.build_roadmap(p, c, b, cs, TODAY)
    assert (p, c, b, cs) == snap
    assert json.loads(json.dumps(r1)) == r1
    assert R.build_roadmap(copy.deepcopy(p), copy.deepcopy(c), copy.deepcopy(b), copy.deepcopy(cs), TODAY) == r1
    r1["schedule"]["steps"].clear()
    assert build()["schedule"]["steps"]


def test_module_imports_only_stdlib_and_has_no_network_or_send_names():
    import ast
    tree = ast.parse(_PATH.read_text())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            assert n.level == 0
            mods.add((n.module or "").split(".")[0])
    assert mods <= {"datetime", "math", "re", "__future__", "typing"}, mods
    src = _PATH.read_text()
    for bad in ("requests", "urllib", "socket", "smtplib", "subprocess", "open(", "eval(", "exec("):
        assert bad not in src, bad


# ---- added after the first mutant run (survivor-driven) -------------------------
def test_equal_keys_are_ordered_by_id_not_input_order():
    cs = colleges()
    for c in cs:
        c["programs"] = ["math", "bio"]
        c["flags"] = flags()
    cs.reverse()
    assert [c["id"] for c in build(colleges=cs)["colleges"]] == ["u1", "u2", "u3"]


def test_tiny_step_after_an_exact_week_boundary_still_ends_in_its_start_week():
    c = curriculum()
    c["steps"] = [{"id": "m1", "domain": "math", "title": "t", "hours": 10, "after": []},
                  {"id": "m2", "domain": "math", "title": "t2", "hours": 1e-12, "after": ["m1"]}]
    s = sched(build(profile=profile(weekly_hours=10, wanted_domains=["math"]), curriculum=c))
    assert s["m2"] == (2, 2)


def test_step_ending_exactly_at_the_horizon_is_scheduled():
    rep = build(horizon_weeks=8)
    assert sched(rep)["b2"] == (7, 8) and rep["schedule"]["unscheduled"] == []


def test_domains_are_taken_in_wanted_order():
    rep = build(profile=profile(wanted_domains=["bio", "math"]))
    assert [s["id"] for s in rep["schedule"]["steps"]][:2] == ["b1", "m1"]


def test_cycle_in_a_domain_nobody_wants_is_still_refused():
    c = curriculum()
    c["steps"][4]["after"] = ["c1"]
    c["steps"][5]["after"] = ["a1"]
    with pytest.raises(R.RoadmapInputError, match="cycle"):
        build(curriculum=c)


def test_self_dependency_and_duplicate_step_messages():
    c = curriculum()
    c["steps"][0]["after"] = ["m1"]
    with pytest.raises(R.RoadmapInputError, match="itself"):
        build(curriculum=c)
    c = curriculum()
    c["steps"].append({"id": "m1", "domain": "math", "title": "dup", "hours": 1, "after": []})
    with pytest.raises(R.RoadmapInputError, match="duplicate step"):
        build(curriculum=c)


@pytest.mark.parametrize("bad", [float("inf"), float("nan"), float("-inf")])
def test_non_finite_numbers_refused(bad):
    with pytest.raises(R.RoadmapInputError):
        build(profile=profile(weekly_hours=bad))
    c = curriculum()
    c["steps"][0]["hours"] = bad
    with pytest.raises(R.RoadmapInputError):
        build(curriculum=c)


def test_total_hours_type():
    assert type(build()["schedule"]["total_hours"]) is int
    c = curriculum()
    c["steps"][0]["hours"] = 7.5
    t = build(curriculum=c)["schedule"]["total_hours"]
    assert t == 67.5 and type(t) is float


# ---- second hardening pass (tests only; runtime unchanged) ----------------------
def test_default_horizon_is_104_weeks():
    c = curriculum()
    c["steps"] = [{"id": "m1", "domain": "math", "title": "long", "hours": 104, "after": []},
                  {"id": "m2", "domain": "math", "title": "one more", "hours": 1, "after": ["m1"]}]
    rep = R.build_roadmap(profile(weekly_hours=1, wanted_domains=["math"]), c, [], [], TODAY)
    assert rep["schedule"]["horizon_weeks"] == 104
    assert sched(rep) == {"m1": (1, 104)}
    assert rep["schedule"]["unscheduled"] == [{"id": "m2", "reason": "beyond_horizon"}]


def test_step_after_entries_must_be_strings():
    for bad in ([["m1"]], [1], "m1"):
        c = curriculum()
        c["steps"][1]["after"] = bad
        with pytest.raises(R.RoadmapInputError):
            build(curriculum=c)


def test_wanted_domain_entries_must_be_strings():
    for bad in ([["math"]], [1], [None]):
        with pytest.raises(R.RoadmapInputError):
            build(profile=profile(wanted_domains=bad))


def test_goals_and_after_may_be_omitted():
    p = profile()
    del p["goals"]
    c = curriculum()
    for st in c["steps"]:
        if not st["after"]:
            del st["after"]
    rep = build(profile=p, curriculum=c)
    assert rep["goals"] == []
    assert [s["id"] for s in rep["schedule"]["steps"]] == ["m1", "b1", "m2", "b2"]


def test_scheduled_step_echoes_its_fields():
    s = {x["id"]: x for x in build()["schedule"]["steps"]}
    assert s["m2"]["hours"] == 30 and s["m2"]["title"] == "Probability" and s["m2"]["domain"] == "math"
    assert s["b1"]["hours"] == 10 and s["b1"]["domain"] == "bio"


def test_schedule_echoes_weekly_hours_and_default_horizon():
    sc = build(profile=profile(weekly_hours=12.5))["schedule"]
    assert sc["weekly_hours"] == 12.5 and sc["horizon_weeks"] == 104


def test_domain_rows_echo_name_and_level():
    rep = build()
    assert dom(rep, "math")["name"] == "Mathematics" and dom(rep, "math")["level"] == "advanced"
    assert dom(rep, "art")["name"] == "Visual art" and dom(rep, "art")["level"] == "intermediate"
    assert dom(rep, "cs")["level"] == "beginner"


def test_college_rows_echo_country_checked_at_name_and_url():
    by = {c["id"]: c for c in build()["colleges"]}
    assert by["u1"]["country"] == "US" and by["u2"]["country"] == "UK" and by["u3"]["country"] == "CA"
    assert by["u1"]["checked_at"] == "2026-09-01" and by["u2"]["checked_at"] == "2024-01-01"
    assert by["u1"]["name"] == "Example University" and by["u3"]["source_url"] == "https://example.invalid/u3"


@pytest.mark.parametrize('hours', [10**1000, 5e-324, float('inf'), float('nan')])
def test_repair_weekly_arithmetic_clean_refusal(hours):
    with pytest.raises(R.RoadmapInputError):
        build(profile=profile(weekly_hours=hours))


@pytest.mark.parametrize('hours', [10**1000, 1e308])
def test_repair_step_arithmetic_clean_refusal(hours):
    c = curriculum()
    c['steps'][0]['hours'] = hours
    with pytest.raises(R.RoadmapInputError):
        build(curriculum=c)


class ExactProfileD(dict):
    pass


class ExactList(list):
    pass


class ExactStr(str):
    pass


@pytest.mark.parametrize('target', ['profile', 'goals', 'feature_text'])
def test_repair_subclasses_refused(target):
    p = profile()
    if target == 'profile':
        p = ExactProfileD(p)
    elif target == 'goals':
        p['goals'] = ExactList(p['goals'])
    else:
        p['goals'] = [ExactStr('goal')]
    with pytest.raises(R.RoadmapInputError):
        build(profile=p)


@pytest.mark.parametrize('value', ['20260901', '2026-09-01' + 'x'*10000, '２０２６-０９-０１'])
def test_repair_date_raw_ascii_grammar(value):
    c = colleges()
    c[0]['checked_at'] = value
    with pytest.raises(R.RoadmapInputError) as caught:
        build(colleges=c)
    assert len(str(caught.value)) <= 512


def test_repair_goals_cap():
    with pytest.raises(R.RoadmapInputError):
        build(profile=profile(goals=['g']*65))
    assert len(build(profile=profile(goals=['g']*64))['goals']) == 64


def test_repair_text_cap():
    with pytest.raises(R.RoadmapInputError):
        build(profile=profile(goals=['x'*513]))
    assert build(profile=profile(goals=['x'*512]))['goals'] == ['x'*512]


def test_repair_long_reverse_chain_iterative():
    c = curriculum()
    c['steps'] = [{'id': 's%d' % i, 'domain': 'math', 'title': 'step', 'hours': 1,
                   'after': ['s%d' % (i+1)] if i < 1499 else []} for i in range(1500)]
    out = build(curriculum=c)
    assert out['schedule']['steps'][0]['id'] == 's1499'
    assert len(out['schedule']['steps']) + len(out['schedule']['unscheduled']) == 1500


@pytest.mark.parametrize('field,cap', [
    ('curriculum.domains',64), ('curriculum.steps',2048), ('step.after',256),
    ('wanted_domains',64), ('goals',64), ('profile.domains',64), ('evidence',256),
    ('bridges',256), ('colleges',256), ('programs',64),
])
def test_repair_every_list_cap_exact(field, cap):
    data = [None]*cap
    assert R._list(data, field) is data
    with pytest.raises(R.RoadmapInputError, match='^' + field.replace('.', r'\.') + ' exceeds'):
        R._list(data + [None], field)


def test_repair_object_cap_and_key_types():
    assert len(R._dict({'k%d'%i:None for i in range(64)}, 'profile')) == 64
    for data in ({'k%d'%i:None for i in range(65)}, {1:None}, {ExactStr('key'):None}, {'k'*513:None}):
        with pytest.raises(R.RoadmapInputError):
            R._dict(data, 'profile')


@pytest.mark.parametrize('field', ['wanted_domains', 'level', 'kind', 'domain', 'url', 'after', 'program', 'bridge'])
def test_repair_all_reference_strings_exact(field):
    p,c,bs,cs = profile(),curriculum(),bridges(),colleges()
    if field == 'wanted_domains': p['wanted_domains'][0] = ExactStr('math')
    elif field == 'level': p['domains'][0]['level'] = ExactStr('advanced')
    elif field == 'kind': p['domains'][0]['evidence'][0]['kind'] = ExactStr('competition')
    elif field == 'domain': c['steps'][0]['domain'] = ExactStr('math')
    elif field == 'url': cs[0]['source_url'] = ExactStr(cs[0]['source_url'])
    elif field == 'after': c['steps'][1]['after'][0] = ExactStr('m1')
    elif field == 'program': cs[0]['programs'][0] = ExactStr('math')
    else: bs[0]['a'] = ExactStr('math')
    with pytest.raises(R.RoadmapInputError):
        build(profile=p,curriculum=c,bridges=bs,colleges=cs)


def test_repair_date_subclass():
    with pytest.raises(R.RoadmapInputError):
        R._date(ExactStr('2026-09-01'), 'date')


def test_repair_url_cap_pair():
    cs = colleges()
    cs[0]['source_url'] = 'https://' + 'x'*2040
    assert build(colleges=cs)['colleges'][1]['source_url'] == cs[0]['source_url']
    cs[0]['source_url'] += 'x'
    with pytest.raises(R.RoadmapInputError):
        build(colleges=cs)


def test_repair_numeric_bounds():
    assert build(profile=profile(weekly_hours=1e-6))['schedule']['weekly_hours'] == 1e-6
    c=curriculum();c['steps'][0]['hours']=1_000_000
    assert build(curriculum=c)['schedule']['total_hours'] == 1_000_060
    for val in [1_000_001, float('inf'), float('nan')]:
        c['steps'][0]['hours'] = val
        with pytest.raises(R.RoadmapInputError): build(curriculum=c)


def test_repair_echo_bounded():
    with pytest.raises(R.RoadmapInputError) as caught:
        build(profile=profile(domains=[{'domain':'x'*100000}]))
    assert len(str(caught.value)) <= 512


def test_u17_pin_repeated_dependency_dag_resource_budget():
    c = curriculum()
    c['steps'] = [{'id': 's%d' % i, 'domain': 'math', 'title': 'step', 'hours': 1,
                   'after': ['s%d' % (i-1)]*4 if i else []} for i in range(12)]
    count = 0
    def trace(frame, event, arg):
        nonlocal count
        if event == 'line' and frame.f_code.co_filename == str(_PATH) and frame.f_code.co_name in ('_no_cycle', '_schedule'):
            count += 1
            if count > 10000:
                raise AssertionError('repeated-dependency traversal exceeded 10000 line events')
        return trace
    previous = sys.gettrace()
    try:
        sys.settrace(trace)
        result = build(curriculum=c)
    finally:
        sys.settrace(previous)
    assert [s['id'] for s in result['schedule']['steps']] == ['s%d'%i for i in range(12)]
    assert count <= 10000


def test_u17_pin_duplicate_str_id_echo():
    c = curriculum()
    c['domains'].append({'id': 'math', 'name': 'duplicate'})
    with pytest.raises(R.RoadmapInputError) as caught:
        build(curriculum=c)
    assert str(caught.value) == "duplicate domain id 'math'"


def test_u17_pin_invalid_profile_domain_marker():
    with pytest.raises(R.RoadmapInputError) as caught:
        build(profile=profile(domains=[{'domain': 42}]))
    assert str(caught.value) == 'profile domain <invalid value> is not in the curriculum'


def test_u17_pin_weekly_literal_100_101():
    assert build(profile=profile(weekly_hours=100))['schedule']['weekly_hours'] == 100
    with pytest.raises(R.RoadmapInputError):
        build(profile=profile(weekly_hours=101))


def test_u17_pin_horizon_literal_520_521():
    assert build(horizon_weeks=520)['schedule']['horizon_weeks'] == 520
    with pytest.raises(R.RoadmapInputError):
        build(horizon_weeks=521)


def test_u17_pin_short_url():
    cs = colleges()
    cs[0]['source_url'] = 'https://x'
    assert next(row for row in build(colleges=cs)['colleges'] if row['id'] == 'u1')['source_url'] == 'https://x'
    cs[0]['source_url'] = 'https://'
    with pytest.raises(R.RoadmapInputError):
        build(colleges=cs)


def test_u17_pin_long_duplicate_echo_128():
    c = curriculum()
    identifier = 'x'*130
    c['domains'] = [{'id':identifier,'name':'one'}, {'id':identifier,'name':'two'}]
    with pytest.raises(R.RoadmapInputError) as caught:
        build(curriculum=c)
    assert str(caught.value) == "duplicate domain id '" + 'x'*128 + "'"


def test_u17_pin_public_error_constructor_cap():
    assert str(R.RoadmapInputError('x'*512)) == 'x'*512
    assert str(R.RoadmapInputError('x'*513)) == 'x'*512


def test_u17_pin_horizon_lower_literal_1_0():
    assert build(horizon_weeks=1)['schedule']['horizon_weeks'] == 1
    with pytest.raises(R.RoadmapInputError):
        build(horizon_weeks=0)


def test_u17_pin_thresholds_note_literal():
    expected = 'breadth and depth thresholds are heuristics named in this module, not standards'
    assert R.THRESHOLDS_NOTE == expected
    assert build()['shape']['thresholds_note'] == expected


def test_u17_pin_boundary_literal():
    expected = (
        'This roadmap is computed only from caller-supplied data. It is not a prediction of admission, '
        'it does not verify any college row, source or evidence item, and it makes no claim about ability. '
        'No message was sent and nothing was submitted; any external action needs separate approval.'
    )
    assert R.BOUNDARY == expected
    assert build()['boundary'] == expected


@pytest.mark.parametrize('kind', ['project', 'course', 'publication', 'competition', 'other'])
def test_u17_pin_literal_evidence_enum_acceptance(kind):
    p = profile(domains=[{'domain':'math','level':'advanced','evidence':[ev(kind=kind)]}])
    assert dom(build(profile=p),'math')['dated_evidence_count'] == 1


@pytest.mark.parametrize('field', ['curriculum', 'profile'])
def test_u17_pin_wrong_container_exact_field(field):
    with pytest.raises(R.RoadmapInputError) as caught:
        build(**{field: []})
    assert str(caught.value) == field + ' must be an object'


@pytest.mark.parametrize('target,label', [
    ('domain','domain'), ('step','step'), ('profile_domain','profile domain'),
    ('bridge','bridge'), ('college','college'), ('flags','flags'),
    ('evidence','evidence item'),
])
def test_u17_pin_nested_object_field_labels(target, label):
    p,c,bs,cs = profile(),curriculum(),bridges(),colleges()
    if target == 'domain': c['domains'][0] = []
    elif target == 'step': c['steps'][0] = []
    elif target == 'profile_domain': p['domains'][0] = []
    elif target == 'bridge': bs[0] = []
    elif target == 'college': cs[0] = []
    elif target == 'flags': cs[0]['flags'] = []
    else: p['domains'][0]['evidence'][0] = []
    with pytest.raises(R.RoadmapInputError) as caught:
        build(profile=p,curriculum=c,bridges=bs,colleges=cs)
    assert str(caught.value) == label + ' must be an object'


@pytest.mark.parametrize('target,label', [('college','checked_at'), ('evidence','evidence date')])
def test_u17_pin_date_field_labels(target,label):
    p,cs = profile(),colleges()
    if target == 'college': cs[0]['checked_at'] = None
    else: p['domains'][0]['evidence'][0]['date'] = None
    with pytest.raises(R.RoadmapInputError) as caught:
        build(profile=p,colleges=cs)
    assert str(caught.value) == label + ' must be an ISO date string'
