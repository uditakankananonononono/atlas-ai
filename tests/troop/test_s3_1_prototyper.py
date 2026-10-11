"""S3.1 trend-to-product prototyper tests. Stdlib only, hermetic.

"""
import copy
import html as htmllib
import pathlib
import re
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
from app.troop import s3_1_prototyper as m  # noqa: E402

BRIEF = {
    "name": "Pocket Lumen",
    "trend": "low-power ambient desk lighting",
    "audience": "students in small rooms",
    "features": ["dimmable warm light", "usb-c power", "foldable arm"],
    "components": [
        {"name": "LED strip", "qty": 2, "unit_cost_cents": 450},
        {"name": "USB-C board", "qty": 1, "unit_cost_cents": 300},
    ],
    "tools": [
        {"name": "PremiumSiteStudio", "kind": "site", "paid": True},
        {"name": "FreeSheet", "kind": "bom", "paid": False},
    ],
}
P = {"as_of": "2026-10-11", "brief": BRIEF}


def payload(**brief_changes):
    p = copy.deepcopy(P)
    for k, v in brief_changes.items():
        if v is m:  # sentinel: delete the key
            del p["brief"][k]
        else:
            p["brief"][k] = v
    return p


def refuses(code, p):
    with pytest.raises(ValueError) as exc:
        m.run_prototype(p)
    assert str(exc.value) == code
    assert "\n" not in str(exc.value)


class TestHappyPath:
    def test_result_shape_and_scope(self):
        r = m.run_prototype(P)
        assert set(r) == {"unit", "spec", "site_html", "gadget", "build_plan", "scope"}
        assert r["unit"] == "S3.1"
        assert r["scope"]["as_of"] == "2026-10-11"
        assert r["scope"]["data_source"] == "supplied"
        assert set(r["scope"]) == {"implemented", "not_implemented", "data_source", "as_of"}
        assert r["scope"]["not_implemented"] == [
            "trend discovery: the trend is supplied by the caller, not fetched or verified",
            "novelty or creativity: nothing here assesses whether the product is new",
            "physical prototype, CAD, or part ordering: output is a spec, a BOM and a static mockup",
            "spend: no purchase, paid tool or live API call is made",
        ]
        assert re.search(r"\b(all|every)\b", " ".join(r["scope"]["implemented"].split()), re.I) is None

    def test_bom_arithmetic_in_cents(self):
        g = m.run_prototype(P)["gadget"]
        assert g["bom"] == [
            {"name": "LED strip", "qty": 2, "unit_cost_cents": 450, "line_total_cents": 900},
            {"name": "USB-C board", "qty": 1, "unit_cost_cents": 300, "line_total_cents": 300},
        ]
        assert g["total_cents"] == 1200
        assert g["currency"] == "USD"
        assert g["spec"] == [
            "Name: Pocket Lumen",
            "Trend: low-power ambient desk lighting",
            "Audience: students in small rooms",
            "Feature 1: dimmable warm light",
            "Feature 2: usb-c power",
            "Feature 3: foldable arm",
        ]

    def test_no_components_gives_empty_bom_zero_total(self):
        g = m.run_prototype(payload(components=[]))["gadget"]
        assert g["bom"] == [] and g["total_cents"] == 0

    def test_components_default_to_empty(self):
        r = m.run_prototype(payload(components=m, tools=m))
        assert r["gadget"]["bom"] == [] and r["build_plan"]["tools"] == []

    def test_paid_tool_is_replaced_by_in_repo_substitute_at_zero_cost(self):
        plan = m.run_prototype(P)["build_plan"]
        assert plan["tools"] == [
            {"name": "PremiumSiteStudio", "kind": "site", "paid": True,
             "used": "in-repo:site_html_generator", "cost_cents": 0},
            {"name": "FreeSheet", "kind": "bom", "paid": False,
             "used": "in-repo:bom_generator", "cost_cents": 0},
        ]
        assert [s["step"] for s in plan["steps"]] == [1, 2, 3, 4]
        assert [s["action"] for s in plan["steps"]] == [
            "write product spec", "generate static mockup site", "compute bill of materials",
            "review with owner before any build or purchase"]

    def test_site_is_static_and_self_contained(self):
        h = m.run_prototype(P)["site_html"]
        assert h.startswith("<!doctype html>\n")
        assert "<h1>Pocket Lumen</h1>" in h
        assert "<li>dimmable warm light</li>" in h
        for banned in ("<script", "http://", "https://", "src=", "href=", "<link", "<iframe", "onerror"):
            assert banned not in h.lower()

    def test_deterministic_and_inputs_not_mutated(self):
        p = copy.deepcopy(P)
        a = m.run_prototype(p)
        assert p == P
        assert a == m.run_prototype(copy.deepcopy(P))

    def test_spec_markdown_line_invariant(self):
        r = m.run_prototype(P)
        assert r["spec"] == "# Product spec\n\n" + "\n".join(r["gadget"]["spec"]) + "\n"
        assert r["spec"].count("\n") == 2 + len(r["gadget"]["spec"])
        assert r["site_html"].count("\n") == 14 + 3

    def test_currency_override(self):
        p = payload(currency="EUR")
        assert m.run_prototype(p)["gadget"]["currency"] == "EUR"
        refuses("PROTO_REFUSED_BAD_VALUE:currency", payload(currency="usd"))
        refuses("PROTO_REFUSED_BAD_VALUE:currency", payload(currency="EURO"))


class TestHostileContent:
    HOSTILE = '<script>alert(1)</script> & "q" \'s\' </li><li>x'

    def test_html_is_escaped_and_line_count_unchanged(self):
        p = payload(name=self.HOSTILE, features=[self.HOSTILE, "b"])
        r = m.run_prototype(p)
        h = r["site_html"]
        assert "<script" not in h and "</li><li>x" not in h
        assert htmllib.escape(self.HOSTILE) in h
        for field in ("trend", "audience"):
            q = m.run_prototype(payload(**{field: self.HOSTILE}))["site_html"]
            assert "<script" not in q and htmllib.escape(self.HOSTILE) in q
        assert h.count("\n") == 14 + 2
        assert r["spec"].count("\n") == 2 + len(r["gadget"]["spec"]) == 2 + 3 + 2

    @pytest.mark.parametrize("ch", ["\n", "\r", "\t", "\x00", "\x1b", "\u2028", "\u2029", "\x85"])
    def test_control_and_line_separators_refused_in_every_text_field(self, ch):
        bad = "a" + ch + "b"
        for field, code in (("name", "name"), ("trend", "trend"), ("audience", "audience")):
            refuses("PROTO_REFUSED_UNSAFE_CHARS:" + code, payload(**{field: bad}))
        refuses("PROTO_REFUSED_UNSAFE_CHARS:features[1]", payload(features=["ok", bad]))
        c = copy.deepcopy(BRIEF["components"]); c[1]["name"] = bad
        refuses("PROTO_REFUSED_UNSAFE_CHARS:components[1].name", payload(components=c))
        t = copy.deepcopy(BRIEF["tools"]); t[0]["name"] = bad
        refuses("PROTO_REFUSED_UNSAFE_CHARS:tools[0].name", payload(tools=t))
        p = payload(); p["as_of"] = bad
        refuses("PROTO_REFUSED_UNSAFE_CHARS:as_of", p)

    def test_error_text_never_echoes_input(self):
        with pytest.raises(ValueError) as exc:
            m.run_prototype(payload(name="bad\nSECRET-TOKEN"))
        assert "SECRET-TOKEN" not in str(exc.value)


class TestSpendRefusals:
    @pytest.mark.parametrize("key", ["purchase", "spend", "order_parts", "live_api", "buy_paid_tools"])
    def test_truthy_spend_flags_refused(self, key):
        p = copy.deepcopy(P); p[key] = True
        refuses("PROTO_REFUSED_SPEND:no_purchase_paid_tool_or_live_api", p)

    @pytest.mark.parametrize("key", ["purchase", "spend", "order_parts", "live_api", "buy_paid_tools"])
    def test_falsy_spend_flags_allowed(self, key):
        p = copy.deepcopy(P); p[key] = False
        m.run_prototype(p)

    def test_spend_checked_before_other_value_errors(self):
        p = payload(name=""); p["spend"] = 1
        refuses("PROTO_REFUSED_SPEND:no_purchase_paid_tool_or_live_api", p)

    def test_spend_flag_in_brief_is_unknown_field(self):
        p = payload(); p["brief"]["spend"] = True
        refuses("PROTO_REFUSED_UNKNOWN_FIELDS:brief", p)


class TestUnsafeRefusals:
    @pytest.mark.parametrize("word", ["weapon", "Weapons", "FIREARM", "explosive", "bomb", "poison",
                                      "malware", "ransomware", "spyware", "stalkerware"])
    def test_denylisted_word_in_each_field(self, word):
        refuses("PROTO_REFUSED_UNSAFE:name", payload(name="Super " + word + " kit"))
        refuses("PROTO_REFUSED_UNSAFE:trend", payload(trend="trend of " + word))
        refuses("PROTO_REFUSED_UNSAFE:audience", payload(audience=word))
        refuses("PROTO_REFUSED_UNSAFE:features[1]", payload(features=["ok", "has " + word]))
        c = copy.deepcopy(BRIEF["components"]); c[0]["name"] = word
        refuses("PROTO_REFUSED_UNSAFE:components[0].name", payload(components=c))

    @pytest.mark.parametrize("word", ["firebomb", "bioweapon", "cyberweapons", "darkmalware"])
    def test_compound_words_are_refused(self, word):
        refuses("PROTO_REFUSED_UNSAFE:name", payload(name=word))

    def test_first_unsafe_field_in_order_is_reported(self):
        refuses("PROTO_REFUSED_UNSAFE:name", payload(name="bomb", trend="bomb", audience="bomb"))
        refuses("PROTO_REFUSED_UNSAFE:trend", payload(trend="bomb", audience="bomb"))
        refuses("PROTO_REFUSED_UNSAFE:audience", payload(audience="bomb", features=["bomb"]))
        refuses("PROTO_REFUSED_UNSAFE:features[0]", payload(features=["bomb"], components=[
            {"name": "bomb", "qty": 1, "unit_cost_cents": 1}]))
        refuses("PROTO_REFUSED_UNSAFE:components[0].name", payload(
            components=[{"name": "bomb", "qty": 1, "unit_cost_cents": 1}],
            tools=[{"name": "bomb", "kind": "bom", "paid": False}]))

    def test_word_boundaries_no_false_positive(self):
        m.run_prototype(payload(name="Bombay lamp", trend="weaponless design", audience="poisonous-free"))

    def test_error_does_not_echo_matched_word(self):
        with pytest.raises(ValueError) as exc:
            m.run_prototype(payload(name="a bomb"))
        assert "bomb" not in str(exc.value)

    def test_unsafe_checked_after_shape_errors(self):
        refuses("PROTO_REFUSED_BAD_TYPE:features", payload(features="bomb"))


class TestValidation:
    def test_payload_shape(self):
        refuses("PROTO_REFUSED_BAD_TYPE:payload", [])
        refuses("PROTO_REFUSED_BAD_TYPE:payload", None)
        refuses("PROTO_REFUSED_UNKNOWN_FIELDS:payload", dict(P, extra=1))
        refuses("PROTO_REFUSED_BAD_TYPE:as_of", {"brief": BRIEF, "as_of": 5})
        refuses("PROTO_REFUSED_EMPTY_FIELD:as_of", {"brief": BRIEF})
        refuses("PROTO_REFUSED_EMPTY_FIELD:brief", {"as_of": "2026-10-11"})
        refuses("PROTO_REFUSED_BAD_TYPE:brief", {"as_of": "2026-10-11", "brief": []})

    def test_as_of_bounds(self):
        p = dict(P); p["as_of"] = "x" * 64
        m.run_prototype(p)
        p["as_of"] = "x" * 65
        refuses("PROTO_REFUSED_TEXT_TOO_LONG:as_of", p)
        p["as_of"] = ""
        refuses("PROTO_REFUSED_EMPTY_FIELD:as_of", p)
        p["as_of"] = " x"
        refuses("PROTO_REFUSED_EMPTY_FIELD:as_of", p)

    def test_text_limits(self):
        m.run_prototype(payload(name="n" * 80))
        refuses("PROTO_REFUSED_TEXT_TOO_LONG:name", payload(name="n" * 81))
        m.run_prototype(payload(trend="t" * 200))
        refuses("PROTO_REFUSED_TEXT_TOO_LONG:trend", payload(trend="t" * 201))
        m.run_prototype(payload(audience="a" * 120))
        refuses("PROTO_REFUSED_TEXT_TOO_LONG:audience", payload(audience="a" * 121))
        m.run_prototype(payload(features=["f" * 120]))
        refuses("PROTO_REFUSED_TEXT_TOO_LONG:features[0]", payload(features=["f" * 121]))

    @pytest.mark.parametrize("field", ["name", "trend", "audience"])
    def test_required_text_fields(self, field):
        refuses("PROTO_REFUSED_EMPTY_FIELD:" + field, payload(**{field: m}))
        refuses("PROTO_REFUSED_EMPTY_FIELD:" + field, payload(**{field: ""}))
        refuses("PROTO_REFUSED_EMPTY_FIELD:" + field, payload(**{field: "   "}))
        refuses("PROTO_REFUSED_EMPTY_FIELD:" + field, payload(**{field: " x"}))
        refuses("PROTO_REFUSED_BAD_TYPE:" + field, payload(**{field: 5}))

    def test_feature_count_bounds(self):
        m.run_prototype(payload(features=["f%d" % i for i in range(8)]))
        refuses("PROTO_REFUSED_OUT_OF_RANGE:features", payload(features=["f%d" % i for i in range(9)]))
        refuses("PROTO_REFUSED_OUT_OF_RANGE:features", payload(features=[]))
        refuses("PROTO_REFUSED_EMPTY_FIELD:features", payload(features=m))
        refuses("PROTO_REFUSED_BAD_TYPE:features[0]", payload(features=[5]))
        refuses("PROTO_REFUSED_DUPLICATE:features[1]", payload(features=["a", "a"]))

    def test_component_bounds(self):
        one = {"name": "x", "qty": 1, "unit_cost_cents": 0}
        m.run_prototype(payload(components=[dict(one, name="c%d" % i) for i in range(30)]))
        refuses("PROTO_REFUSED_OUT_OF_RANGE:components",
                payload(components=[dict(one, name="c%d" % i) for i in range(31)]))
        m.run_prototype(payload(components=[dict(one, qty=10000)]))
        refuses("PROTO_REFUSED_OUT_OF_RANGE:components[0].qty", payload(components=[dict(one, qty=10001)]))
        refuses("PROTO_REFUSED_OUT_OF_RANGE:components[0].qty", payload(components=[dict(one, qty=0)]))
        m.run_prototype(payload(components=[dict(one, unit_cost_cents=10000000)]))
        refuses("PROTO_REFUSED_OUT_OF_RANGE:components[0].unit_cost_cents",
                payload(components=[dict(one, unit_cost_cents=10000001)]))
        refuses("PROTO_REFUSED_OUT_OF_RANGE:components[0].unit_cost_cents",
                payload(components=[dict(one, unit_cost_cents=-1)]))
        for bad in (True, 1.5, "1"):
            refuses("PROTO_REFUSED_BAD_TYPE:components[0].qty", payload(components=[dict(one, qty=bad)]))
            refuses("PROTO_REFUSED_BAD_TYPE:components[0].unit_cost_cents",
                    payload(components=[dict(one, unit_cost_cents=bad)]))
        refuses("PROTO_REFUSED_UNKNOWN_FIELDS:components[0]", payload(components=[dict(one, x=1)]))
        refuses("PROTO_REFUSED_EMPTY_FIELD:components[0].qty", payload(components=[{"name": "x", "unit_cost_cents": 1}]))
        refuses("PROTO_REFUSED_BAD_TYPE:components[0]", payload(components=["x"]))
        refuses("PROTO_REFUSED_BAD_TYPE:components", payload(components="x"))
        refuses("PROTO_REFUSED_DUPLICATE:components[1].name",
                payload(components=[one, dict(one)]))

    def test_total_is_summed_exactly_at_the_cap(self):
        c = [{"name": "a", "qty": 10000, "unit_cost_cents": 10000000},
             {"name": "b", "qty": 10000, "unit_cost_cents": 10000000}]
        assert m.run_prototype(payload(components=c))["gadget"]["total_cents"] == 2 * 10000 * 10000000

    def test_tool_rules(self):
        t = lambda **k: [dict({"name": "T", "kind": "site", "paid": False}, **k)]
        m.run_prototype(payload(tools=[dict(name="t%d" % i, kind="spec", paid=False) for i in range(10)]))
        refuses("PROTO_REFUSED_OUT_OF_RANGE:tools",
                payload(tools=[dict(name="t%d" % i, kind="spec", paid=False) for i in range(11)]))
        for kind in ("site", "bom", "spec"):
            assert m.run_prototype(payload(tools=t(kind=kind)))["build_plan"]["tools"][0]["used"] == \
                "in-repo:%s_generator" % ("site_html" if kind == "site" else kind)
        refuses("PROTO_REFUSED_BAD_KIND:cad", payload(tools=t(kind="cad")))
        refuses("PROTO_REFUSED_BAD_TYPE:tools[0].paid", payload(tools=t(paid="yes")))
        refuses("PROTO_REFUSED_BAD_TYPE:tools[0].kind", payload(tools=t(kind=5)))
        refuses("PROTO_REFUSED_UNKNOWN_FIELDS:tools[0]", payload(tools=t(x=1)))
        refuses("PROTO_REFUSED_DUPLICATE:tools[1].name", payload(tools=t() + t()))
        refuses("PROTO_REFUSED_BAD_TYPE:tools", payload(tools="x"))
        refuses("PROTO_REFUSED_UNSAFE:tools[0].name", payload(tools=t(name="malware builder")))

    def test_bad_kind_never_echoes_hostile_text(self):
        t = lambda k: [{"name": "T", "kind": k, "paid": False}]
        for bad in ("cad\nSECRET", "CAD", "a" * 17, "", "c ad", "<x>"):
            refuses("PROTO_REFUSED_BAD_KIND:invalid", payload(tools=t(bad)))
        refuses("PROTO_REFUSED_BAD_KIND:" + "a" * 16, payload(tools=t("a" * 16)))

    def test_unknown_brief_field(self):
        p = payload(); p["brief"]["color"] = "red"
        refuses("PROTO_REFUSED_UNKNOWN_FIELDS:brief", p)


class TestSourceHygiene:
    SRC = (_ROOT / "backend/app/troop/s3_1_prototyper.py").read_text()

    def test_stdlib_only_and_offline(self):
        imports = set(re.findall(r"^(?:from|import)\s+([A-Za-z_][\w.]*)", self.SRC, re.M))
        assert imports <= {"html", "re", "unicodedata", "__future__", "app.modules.c30"}
        stripped = re.sub(r"\"[^\"\n]*\"|'[^'\n]*'", "", self.SRC)
        for banned in ("socket", "urllib", "requests", "subprocess", "random", "datetime", "os.", "open("):
            assert banned not in stripped

    def test_no_em_dash_in_source(self):
        assert "\u2014" not in self.SRC


def test_tools_non_dict_exact_refusal():
    refuses('PROTO_REFUSED_BAD_TYPE:tools[0]',payload(tools=[0]))

@pytest.mark.parametrize('ch',['\u200b','\u200c','\u200d','\u2060','\u00ad','\u202e'])
def test_cf_obfuscated_denylist_refused(ch):
    refuses('PROTO_REFUSED_CONTROL_CHARS:trend',payload(trend='wea'+ch+'pons'))

@pytest.mark.parametrize('field',['as_of','name','trend','audience','features','components','tools'])
def test_cf_hygiene_all_text_paths(field):
    d=payload();bad='a\u200bb';path=field
    if field=='as_of':d[field]=bad
    elif field in ('name','trend','audience'):d['brief'][field]=bad
    elif field=='features':d['brief'][field]=[bad];path='features[0]'
    else:d['brief'][field][0]['name']=bad;path=field+'[0].name'
    refuses('PROTO_REFUSED_CONTROL_CHARS:'+path,d)

class DictSubclass(dict):pass
class StrSubclass(str):pass
class ListSubclass(list):pass
class IntSubclass(int):pass

@pytest.mark.parametrize('field',['payload','brief','components','tools','features','name','kind','currency','qty'])
def test_exact_builtin_subclasses_refused(field):
    d=payload();path=field
    if field=='payload':d=DictSubclass(d)
    elif field=='brief':d[field]=DictSubclass(d[field])
    elif field in ('components','tools'):d['brief'][field][0]=DictSubclass(d['brief'][field][0]);path=field+'[0]'
    elif field=='features':d['brief'][field]=ListSubclass(d['brief'][field])
    elif field=='name':d['brief'][field]=StrSubclass(d['brief'][field])
    elif field=='kind':d['brief']['tools'][0][field]=StrSubclass('site');path='tools[0].kind'
    elif field=='currency':d['brief'][field]=StrSubclass('USD')
    else:d['brief']['components'][0][field]=IntSubclass(1);path='components[0].qty'
    refuses('PROTO_REFUSED_BAD_TYPE:'+path,d)

@pytest.mark.parametrize('key,value',[('purchase',0),('spend',[]),('live_api',{}),('buy_paid_tools',''),('order_parts',None)])
def test_falsy_spend_intent(key,value):
    d=payload();d[key]=value
    assert m.run_prototype(d)==m.run_prototype(payload())

@pytest.mark.parametrize('field',['as_of','trend','audience','features','components','tools'])
def test_exact_text_subclasses_all_paths(field):
    d=payload();path=field
    if field=='as_of':d[field]=StrSubclass(d[field])
    elif field in ('trend','audience'):d['brief'][field]=StrSubclass(d['brief'][field])
    elif field=='features':d['brief'][field][0]=StrSubclass(d['brief'][field][0]);path+='[0]'
    else:d['brief'][field][0]['name']=StrSubclass(d['brief'][field][0]['name']);path+='[0].name'
    refuses('PROTO_REFUSED_BAD_TYPE:'+path,d)

@pytest.mark.parametrize('field',['components','tools'])
def test_exact_list_subclasses_other_paths(field):
    d=payload();d['brief'][field]=ListSubclass(d['brief'][field])
    refuses('PROTO_REFUSED_BAD_TYPE:'+field,d)
