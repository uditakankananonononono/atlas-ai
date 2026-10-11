"""V2 / c37.patents claim-draft tests. Hermetic, stdlib unittest, no network."""
import copy, importlib.util, inspect, json, pathlib, sys, unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "backend/app/modules/c37/patents.py"
DOC = ROOT / "docs/contracts/V2-patent-application-drafter.md"
sys.path.insert(0, str(ROOT / "backend"))
DRAFT = "DRAFT NOT FOR FILING"


def load(source=None, name="c37_patents_v2"):
    spec = importlib.util.spec_from_file_location(name, SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    if source is None:
        spec.loader.exec_module(mod)
    else:
        exec(compile(source, str(SRC), "exec"), mod.__dict__)
    return mod


def req(**over):
    r = {"as_of": "2026-10-11",
         "invention": {"id": "i1", "owner": "self", "title": "adaptive widget",
                       "summary": "A widget that adapts.",
                       "components": ["a sensor", "a controller", "an actuator", "a housing"],
                       "novel_features": ["the sensor is optical", "the controller is cached",
                                          "the housing is modular"]},
         "prior_art": [{"id": "pa%d" % i, "title": "Prior %d" % i, "url": "https://example.org/p%d" % i}
                       for i in range(1, 6)],
         "novelty_input": {"source": "c32.ideate", "value": 0.7}}
    r.update(over)
    return r


def inv(**kw):
    d = copy.deepcopy(req()["invention"])
    d.update(kw)
    return d


class Base(unittest.TestCase):
    mod = None

    @classmethod
    def setUpClass(cls):
        cls.mod = load()

    def run_(self, r):
        return self.mod.run(r)

    def refuse(self, r, expect):
        with self.assertRaises(ValueError) as cm:
            self.mod.run(r)
        self.assertEqual(str(cm.exception), expect)


class TestHappy(Base):
    def test_claims_exact(self):
        out = self.run_(req())
        texts = [c["text"] for c in out["claims"]]
        self.assertEqual(texts, [
            "1. A adaptive widget comprising: a sensor; a controller; an actuator; and a housing.",
            "2. The adaptive widget of claim 1, wherein the sensor is optical.",
            "3. The adaptive widget of claim 1, wherein the controller is cached.",
            "4. The adaptive widget of claim 1, wherein the housing is modular."])
        self.assertEqual(out["claim_count"], 4)
        self.assertEqual([c["number"] for c in out["claims"]], [1, 2, 3, 4])

    def test_one_and_two_components(self):
        o1 = self.run_(req(invention=inv(components=["x"])))
        self.assertEqual(o1["claims"][0]["text"], "1. A adaptive widget comprising: x.")
        o2 = self.run_(req(invention=inv(components=["x", "y"])))
        self.assertEqual(o2["claims"][0]["text"], "1. A adaptive widget comprising: x; and y.")

    def test_draft_label_on_every_claim_and_set(self):
        out = self.run_(req())
        self.assertEqual(out["draft_label"], DRAFT)
        for c in out["claims"]:
            self.assertEqual(c["label"], DRAFT)

    def test_passthrough_untouched_in_order(self):
        r = req()
        out = self.run_(r)
        self.assertEqual(out["prior_art_passthrough"], r["prior_art"])
        self.assertEqual(len(out["prior_art_passthrough"]), 5)

    def test_novelty_echo_labelled_and_never_used(self):
        a = self.run_(req(novelty_input={"source": "c32.ideate", "value": 0.0}))
        b = self.run_(req(novelty_input={"source": "c32.ideate", "value": 1}))
        self.assertEqual(a["novelty_input_echo"],
                         {"source": "c32.ideate", "value": 0.0, "label": "caller_supplied, unverified"})
        self.assertEqual(b["novelty_input_echo"]["value"], 1)
        self.assertEqual(a["claims"], b["claims"])
        self.assertEqual(a["claim_count"], b["claim_count"])
        r = req(); del r["novelty_input"]
        self.assertIsNone(self.run_(r)["novelty_input_echo"])
        self.assertIsNone(self.run_(req(novelty_input=None))["novelty_input_echo"])

    def test_novelty_value_rounded_six_places(self):
        out = self.run_(req(novelty_input={"source": "c32.ideate", "value": 0.123456789}))
        self.assertEqual(out["novelty_input_echo"]["value"], 0.123457)

    def test_owner_assertion_and_scope(self):
        out = self.run_(req())
        self.assertEqual(out["owner_assertion"], "caller_supplied, unverified")
        sc = out["scope"]
        self.assertEqual(sc["as_of"], "2026-10-11")
        self.assertTrue(sc["implemented"] and sc["not_implemented"] and sc["data_source"])
        self.assertEqual(set(out), {"claims", "claim_count", "prior_art_passthrough",
                                    "novelty_input_echo", "owner_assertion", "scope", "draft_label"})

    def test_deterministic_json(self):
        a = json.dumps(self.run_(req()), sort_keys=True)
        b = json.dumps(self.run_(req()), sort_keys=True)
        self.assertEqual(a, b)

    def test_input_not_mutated(self):
        r = req(); snap = copy.deepcopy(r)
        self.run_(r)
        self.assertEqual(r, snap)

    def test_output_has_no_forbidden_words(self):
        text = json.dumps(self.run_(req())).lower()
        for w in ("patentable", "guaranteed", "overlap"):
            self.assertNotIn(w, text)

    def test_scope_policy_is_real(self):
        from app.modules.c30 import policy
        self.assertIs(self.mod.policy, policy)


class TestRefusals(Base):
    def test_not_owner(self):
        for v in ("other", "Self", "", None, True, 1, ["self"]):
            self.refuse(req(invention=inv(owner=v)), "INTEL_REFUSED_NOT_OWNER:owner")

    def test_owner_missing(self):
        i = inv(); del i["owner"]
        self.refuse(req(invention=i), "INTEL_REFUSED_NOT_OWNER:owner")

    def test_owner_value_never_echoed(self):
        with self.assertRaises(ValueError) as cm:
            self.run_(req(invention=inv(owner="SECRETVALUE")))
        self.assertNotIn("SECRETVALUE", str(cm.exception))

    def test_prior_art_missing_variants(self):
        r = req(); del r["prior_art"]
        self.refuse(r, "INTEL_REFUSED_PRIORART_MISSING:prior_art")
        self.refuse(req(prior_art=None), "INTEL_REFUSED_PRIORART_MISSING:prior_art")
        self.refuse(req(prior_art=[]), "INTEL_REFUSED_PRIORART_MISSING:prior_art")

    def test_prior_art_not_list(self):
        for v in ("x", {}, 5, True):
            self.refuse(req(prior_art=v), "INTEL_REFUSED_BAD_TYPE:prior_art")

    def test_bad_url(self):
        for url in ("http://example.org/x", "ftp://example.org", "https://", "https:///p",
                    "https://exa mple.org", "https://example.org/a b", "https://example.org/\x07",
                    "example.org", "", None, 5):
            pa = [{"id": "pa1", "title": "T", "url": url}]
            self.refuse(req(prior_art=pa), "INTEL_REFUSED_BAD_TYPE:prior_art")

    def test_bad_entries(self):
        for e in ({"id": "", "title": "T", "url": "https://e.org"}, {"id": "a", "title": " ", "url": "https://e.org"},
                  {"id": 1, "title": "T", "url": "https://e.org"}, {"id": "a", "title": 2, "url": "https://e.org"},
                  {"title": "T", "url": "https://e.org"}, {"id": "a", "url": "https://e.org"},
                  {"id": "a", "title": "T"}, "str", None, ["x"]):
            self.refuse(req(prior_art=[e]), "INTEL_REFUSED_BAD_TYPE:prior_art")

    def test_duplicate_prior_art_ids(self):
        pa = [{"id": "d", "title": "A", "url": "https://e.org/1"}, {"id": "d", "title": "B", "url": "https://e.org/2"}]
        self.refuse(req(prior_art=pa), "INTEL_REFUSED_BAD_TYPE:prior_art")

    def test_file_key(self):
        for k in ("file", "submit", "uspto_submit", "epo_submit", "grant"):
            r = req(); r[k] = True
            self.refuse(r, "INTEL_REFUSED_FILE:" + k)

    def test_file_key_nested_and_normalized(self):
        r = req(); r["invention"]["Uspto-Submit"] = 1
        self.refuse(r, "INTEL_REFUSED_FILE:uspto_submit")
        r = req(); r["prior_art"][2]["GRANT"] = 1
        self.refuse(r, "INTEL_REFUSED_FILE:grant")
        r = req(); r["novelty_input"]["file"] = 1
        self.refuse(r, "INTEL_REFUSED_FILE:file")

    def test_send_key(self):
        r = req(); r["token"] = "x"
        self.refuse(r, "INTEL_REFUSED_SEND:token")
        r = req(); r["invention"]["approval_token"] = "x"
        self.refuse(r, "INTEL_REFUSED_SEND:approval_token")

    def test_spend_and_nocreds(self):
        r = req(); r["pay"] = 1
        self.refuse(r, "INTEL_REFUSED_SPEND:pay")
        r = req(); r["password"] = "x"
        self.refuse(r, "INTEL_REFUSED_NOCREDS:password")

    def test_all_table_keys(self):
        send = "send approve approved approval approval_token smtp token email_send sender smtp_host smtp_port smtp_user".split()
        spend = "pay purchase spend buy checkout card_number".split()
        creds = "login password username credentials otp api_key access_token refresh_token bearer pass passwd".split()
        for k in send:
            self.refuse(dict(req(), **{k: 1}), "INTEL_REFUSED_SEND:" + k)
        for k in spend:
            self.refuse(dict(req(), **{k: 1}), "INTEL_REFUSED_SPEND:" + k)
        for k in creds:
            self.refuse(dict(req(), **{k: 1}), "INTEL_REFUSED_NOCREDS:" + k)

    def test_key_normalization_not_substring(self):
        r = req(); r["sender_note"] = 1      # not an exact table key, so UNKNOWN not SEND
        self.refuse(r, "INTEL_REFUSED_UNKNOWN:request")
        r = req(); r["API-KEY"] = 1
        self.refuse(r, "INTEL_REFUSED_NOCREDS:api_key")

    def test_precedence_across_classes(self):
        r = req(); r.update({"password": 1, "grant": 1, "pay": 1, "token": 1})
        self.refuse(r, "INTEL_REFUSED_SEND:token")
        r = req(); r.update({"password": 1, "grant": 1, "pay": 1})
        self.refuse(r, "INTEL_REFUSED_SPEND:pay")
        r = req(); r.update({"password": 1, "grant": 1})
        self.refuse(r, "INTEL_REFUSED_FILE:grant")

    def test_alphabetical_within_class(self):
        r = req(); r.update({"submit": 1, "file": 1})
        self.refuse(r, "INTEL_REFUSED_FILE:file")
        r = req(); r.update({"smtp": 1, "approve": 1, "send": 1})
        self.refuse(r, "INTEL_REFUSED_SEND:approve")
        r = req(); r.update({"pay": 1, "buy": 1})
        self.refuse(r, "INTEL_REFUSED_SPEND:buy")
        r = req(); r.update({"login": 1, "bearer": 1})
        self.refuse(r, "INTEL_REFUSED_NOCREDS:bearer")

    def test_forbidden_scan_beats_type_and_unknown(self):
        r = req(); r["zzz_unknown"] = 1; r[5] = 1; r["grant"] = 1
        self.refuse(r, "INTEL_REFUSED_BAD_TYPE:key")

    def test_forbidden_key_inside_list_items_of_values(self):
        r = req(); r["invention"]["components"] = [{"file": 1}]
        self.refuse(r, "INTEL_REFUSED_FILE:file")

    def test_non_str_key(self):
        r = req(); r[5] = 1
        self.refuse(r, "INTEL_REFUSED_BAD_TYPE:key")
        r = req(); r["invention"][5] = 1
        self.refuse(r, "INTEL_REFUSED_BAD_TYPE:key")

    def test_unknown_keys_by_level(self):
        r = req(); r["zzz"] = 1
        self.refuse(r, "INTEL_REFUSED_UNKNOWN:request")
        r = req(); r["invention"]["zzz"] = 1
        self.refuse(r, "INTEL_REFUSED_UNKNOWN:invention")
        r = req(); r["prior_art"][0]["zzz"] = 1
        self.refuse(r, "INTEL_REFUSED_UNKNOWN:prior_art")
        r = req(); r["novelty_input"]["zzz"] = 1
        self.refuse(r, "INTEL_REFUSED_UNKNOWN:novelty_input")

    def test_unknown_reason_never_echoes_key(self):
        r = req(); r["LEAKYKEY"] = 1
        with self.assertRaises(ValueError) as cm:
            self.run_(r)
        self.assertNotIn("LEAKY", str(cm.exception).upper())

    def test_bad_request_type(self):
        for v in (None, [], "x", 5, ()):
            self.refuse(v, "INTEL_REFUSED_BAD_TYPE:request")

    def test_as_of(self):
        for v in ("2026-13-01", "2026-10-1", "20261011", "", None, 5, "2026-10-11T00:00", "2026-02-30"):
            self.refuse(req(as_of=v), "INTEL_REFUSED_BAD_TYPE:as_of")
        r = req(); del r["as_of"]
        self.refuse(r, "INTEL_REFUSED_BAD_TYPE:as_of")

    def test_invention_type(self):
        for v in (None, [], "x"):
            self.refuse(req(invention=v), "INTEL_REFUSED_BAD_TYPE:invention")

    def test_empty_lists(self):
        self.refuse(req(invention=inv(components=[])), "INTEL_REFUSED_EMPTY:components")
        self.refuse(req(invention=inv(novel_features=[])), "INTEL_REFUSED_EMPTY:novel_features")

    def test_list_field_types_and_blank_items(self):
        for f in ("components", "novel_features"):
            for v in ("x", None, {}, 5):
                self.refuse(req(invention=inv(**{f: v})), "INTEL_REFUSED_BAD_TYPE:" + f)
            for item in ("", "  ", 5, None, "a\x00b"):
                self.refuse(req(invention=inv(**{f: ["ok", item]})), "INTEL_REFUSED_BAD_TYPE:" + f)

    def test_invention_text_fields(self):
        for f in ("id", "title", "summary"):
            for v in (5, None, "", "  "):
                with self.assertRaises(ValueError) as cm:
                    self.run_(req(invention=inv(**{f: v})))
                self.assertTrue(str(cm.exception).startswith("INTEL_REFUSED_"))
                self.assertTrue(str(cm.exception).endswith(":" + f))
            self.refuse(req(invention=inv(**{f: "a\x07b"})), "INTEL_REFUSED_BAD_TYPE:" + f)

    def test_novelty_input_bad(self):
        for v in ({"source": "other", "value": 0.5}, {"source": "c32.ideate", "value": True},
                  {"source": "c32.ideate", "value": -0.1}, {"source": "c32.ideate", "value": 1.1},
                  {"source": "c32.ideate", "value": float("nan")}, {"source": "c32.ideate", "value": float("inf")},
                  {"source": "c32.ideate", "value": "0.5"}, {"source": "c32.ideate"}, {"value": 0.5},
                  "x", [], 5):
            self.refuse(req(novelty_input=v), "INTEL_REFUSED_BAD_TYPE:novelty_input")

    def test_novelty_boundaries_accepted(self):
        for v in (0, 0.0, 1, 1.0):
            self.run_(req(novelty_input={"source": "c32.ideate", "value": v}))

    def test_caps_accept_at_limit(self):
        self.run_(req(invention=inv(id="i" * 500, title="t" * 500, summary="s" * 500)))
        self.run_(req(invention=inv(components=["c%d" % i for i in range(30)],
                                    novel_features=["f" * 500] * 30)))
        pa = [{"id": "p%d" % i, "title": "t" * 500, "url": "https://e.org/" + "u" * 1980} for i in range(200)]
        pa[0]["id"] = "i" * 500
        self.assertEqual(len(self.run_(req(prior_art=pa))["prior_art_passthrough"]), 200)

    def test_caps_refuse_over_limit(self):
        for f in ("id", "title", "summary"):
            self.refuse(req(invention=inv(**{f: "x" * 501})), "INTEL_REFUSED_OVERSIZE:" + f)
        self.refuse(req(invention=inv(components=["c%d" % i for i in range(31)])), "INTEL_REFUSED_OVERSIZE:components")
        self.refuse(req(invention=inv(novel_features=["f%d" % i for i in range(31)])), "INTEL_REFUSED_OVERSIZE:novel_features")
        self.refuse(req(invention=inv(components=["x" * 501])), "INTEL_REFUSED_OVERSIZE:components")
        self.refuse(req(invention=inv(novel_features=["x" * 501])), "INTEL_REFUSED_OVERSIZE:novel_features")
        pa = [{"id": "p%d" % i, "title": "t", "url": "https://e.org/%d" % i} for i in range(201)]
        self.refuse(req(prior_art=pa), "INTEL_REFUSED_OVERSIZE:prior_art")
        for k, v in (("id", "x" * 501), ("title", "x" * 501), ("url", "https://e.org/" + "u" * 1987)):
            e = {"id": "a", "title": "t", "url": "https://e.org/1"}
            e[k] = v
            self.refuse(req(prior_art=[e]), "INTEL_REFUSED_OVERSIZE:" + k)

    def test_prior_art_leaf_oversize_precedes_hygiene(self):
        # ruling 2: over-cap leaf is OVERSIZE:<leaf>, checked before hygiene (blank/control/http/duplicate)
        bad = {"id": "a", "title": "\x07" * 501, "url": "http://e.org/1"}
        self.refuse(req(prior_art=[bad]), "INTEL_REFUSED_OVERSIZE:title")
        bad = {"id": "\n" * 501, "title": "t", "url": "https://e.org/1"}
        self.refuse(req(prior_art=[bad]), "INTEL_REFUSED_OVERSIZE:id")
        bad = {"id": "a", "title": "t", "url": "http://" + "u" * 2000}
        self.refuse(req(prior_art=[bad]), "INTEL_REFUSED_OVERSIZE:url")
        # list length cap is OVERSIZE:prior_art even when entries are junk
        self.refuse(req(prior_art=[5] * 201), "INTEL_REFUSED_OVERSIZE:prior_art")

    def test_prior_art_hygiene_is_always_bad_type_prior_art(self):
        for e in ({"id": "a\x07", "title": "T", "url": "https://e.org"}, {"id": "a", "title": "T\n", "url": "https://e.org"},
                  {"id": "a", "title": "T", "url": "https://e.org/\t"}, {"id": " ", "title": "T", "url": "https://e.org"}):
            self.refuse(req(prior_art=[e]), "INTEL_REFUSED_BAD_TYPE:prior_art")

    def test_claim_objects_have_exactly_number_text_label(self):
        for c in self.run_(req())["claims"]:
            self.assertEqual(set(c), {"number", "text", "label"})
            self.assertEqual(c["label"], "DRAFT NOT FOR FILING")
        self.assertEqual(self.run_(req())["draft_label"], "DRAFT NOT FOR FILING")

    def test_text_too_long_never_surfaces(self):
        for f in ("id", "title", "summary"):
            with self.assertRaises(ValueError) as cm:
                self.run_(req(invention=inv(**{f: "x" * 9999})))
            self.assertNotIn("TEXT_TOO_LONG", str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            self.run_(req(invention=inv(components=["x" * 9999])))
        self.assertNotIn("TEXT_TOO_LONG", str(cm.exception))

    def test_oversize_checked_before_text_hygiene(self):
        for f in ("id", "title", "summary"):
            self.refuse(req(invention=inv(**{f: "\x07" * 501})), "INTEL_REFUSED_OVERSIZE:" + f)

    def test_validation_order_forbidden_before_not_owner(self):
        r = req(invention=inv(owner="x")); r["file"] = 1
        self.refuse(r, "INTEL_REFUSED_FILE:file")

    def test_priorart_missing_beats_not_owner_order(self):
        # step 5 (lists present) runs before step 7 (owner)
        self.refuse(req(invention=inv(owner="x"), prior_art=[]), "INTEL_REFUSED_PRIORART_MISSING:prior_art")

    def test_reasons_carry_only_schema_names(self):
        r = req(prior_art=[{"id": "SECRETID", "title": "T", "url": "http://e.org/SECRETPATH"}])
        with self.assertRaises(ValueError) as cm:
            self.run_(r)
        self.assertNotIn("SECRET", str(cm.exception))


class TestNoEffects(Base):
    def test_no_effect_functions_or_imports(self):
        names = [n for n, o in vars(self.mod).items() if inspect.isfunction(o) and o.__module__ == self.mod.__name__]
        bad = ("send", "pay", "spend", "post", "publish", "file", "submit", "create_account", "smtp", "request", "open")
        for n in names:
            if n == "run":
                continue
            for b in bad:
                self.assertNotIn(b, n.lstrip("_").lower().split("_"))
        src = SRC.read_text()
        for w in ("import socket", "import subprocess", "import urllib", "import http", "import requests",
                  "import smtplib", "open(", "policy.check", "datetime.now", "time.time", "datetime.utcnow"):
            self.assertNotIn(w, src)
        self.assertNotIn("__init__", [p.name for p in SRC.parent.glob("patents*") if p.name == "__init__.py"])

    def test_run_only_public_entry(self):
        pub = [n for n, o in vars(self.mod).items() if inspect.isfunction(o) and not n.startswith("_")
               and o.__module__ == self.mod.__name__]
        self.assertEqual(pub, ["run"])


class TestDoc(unittest.TestCase):
    def test_doc_has_required_sections_and_no_identifiers(self):
        t = DOC.read_text()
        for w in ("HER WORDS", "see new ideas/ventures and develop its own patent applications", "LIMITS",
                  "cross-account builder package, provenance held privately", DRAFT,
                  "INTEL_REFUSED_FILE", "INTEL_REFUSED_PRIORART_MISSING", "INTEL_REFUSED_NOT_OWNER",
                  "INTEL_REFUSED_SEND", "INTEL_REFUSED_SPEND", "INTEL_REFUSED_NOCREDS", "INTEL_REFUSED_UNKNOWN",
                  "INTEL_REFUSED_OVERSIZE", "INTEL_REFUSED_BAD_TYPE", "INTEL_REFUSED_EMPTY",
                  "policy not applicable"):
            self.assertIn(w, t)
        for w in ("wamid", "offset", "HBgM"):
            self.assertNotIn(w, t)



class TestResolvedOutputPins(Base):
    def test_output_keys_exact_and_claims_exact(self):
        out=self.run_(req())
        self.assertEqual(set(out),{'claims','claim_count','draft_label','prior_art_passthrough','novelty_input_echo','owner_assertion','scope'})
        for c in out['claims']:self.assertEqual(set(c),{'number','text','label'})
        self.assertEqual(out['scope'],{'implemented':['claim text drafts from supplied components and features','pass-through of supplied prior-art records'],'not_implemented':['prior-art comparison or novelty scoring','ownership or inventorship verification','legal advice','prior-art search','filing'],'data_source':'caller-supplied invention and prior-art records, unverified','as_of':'2026-10-11'})
    def test_real_policy_helpers_invoked(self):
        from unittest.mock import patch
        from app.modules.c30 import policy
        with patch.object(policy,'clean_text',wraps=policy.clean_text) as clean,patch.object(policy,'scope',wraps=policy.scope) as scope:
            self.run_(req());self.assertGreater(clean.call_count,0);scope.assert_called_once()
        self.assertIs(self.mod.policy,policy)
    def test_prior_art_spaces_and_control_whitespace(self):
        good={'id':'patent number one','title':'Title with ordinary spaces','url':'https://example.org/p'}
        self.assertEqual(self.run_(req(prior_art=[good]))['prior_art_passthrough'],[good])
        for leaf in ['id','title','url']:
            for char in ['\t','\n','\r','\x00','\x7f']:
                bad=dict(good);bad[leaf]+=char
                self.refuse(req(prior_art=[bad]),'INTEL_REFUSED_BAD_TYPE:prior_art')
    def test_required_lists_and_first_failure(self):
        for field in ['components','novel_features']:
            for value in [None,1,'x',[None],['']]:self.refuse(req(invention=inv(**{field:value})),'INTEL_REFUSED_BAD_TYPE:'+field)
            self.refuse(req(invention=inv(**{field:[]})),'INTEL_REFUSED_EMPTY:'+field)
        self.refuse(req(prior_art=[1]*201),'INTEL_REFUSED_OVERSIZE:prior_art')
    def test_types_dates_and_novelty(self):
        for value in ['2026-02-30','2026-10-11x',None,1]:self.refuse(req(as_of=value),'INTEL_REFUSED_BAD_TYPE:as_of')
        for value in [True,-1,2,float('nan'),float('inf'),'0.5']:
            self.refuse(req(novelty_input={'source':'c32.ideate','value':value}),'INTEL_REFUSED_BAD_TYPE:novelty_input')
        self.assertEqual(self.run_(req(novelty_input={'source':'c32.ideate','value':0.123456789}))['novelty_input_echo'],{'source':'c32.ideate','value':0.123457,'label':'caller_supplied, unverified'})
    def test_forbidden_normalization_and_precedence(self):
        self.refuse(req(invention=inv(components=[{'PAY':1,'Email-Send':1,'APPROVE':1,'file':1,'password':1}])),'INTEL_REFUSED_SEND:approve')
        self.refuse(req(invention=inv(components=[{'pay':1,'FILE':1,'password':1}])),'INTEL_REFUSED_SPEND:pay')
        self.refuse(req(invention=inv(components=[{'USpto-Submit':1,'password':1}])),'INTEL_REFUSED_FILE:uspto_submit')
    def test_input_unchanged_and_deterministic(self):
        request=req();before=copy.deepcopy(request);first=self.run_(request)
        self.assertEqual(request,before);self.assertEqual(json.dumps(first,sort_keys=True),json.dumps(self.run_(request),sort_keys=True))

class TestUnicodeExtension(Base):
    def test_every_echoed_text_path_category_refused(self):
        for char in ['\u202e','\u200b','\x07','\u2028','\u2029']:
            cases=[]
            for field in ['id','title','summary']:cases.append((req(invention=inv(**{field:'x'+char})),field))
            for field in ['components','novel_features']:cases.append((req(invention=inv(**{field:['x'+char]})),field))
            for field in ['id','title','url']:
                art={'id':'id','title':'title','url':'https://example.org/x'};art[field]+=char;cases.append((req(prior_art=[art]),'prior_art'))
            cases.append((req(as_of='2026-10-11'+char),'as_of'))
            cases.append((req(novelty_input={'source':'c32.ideate'+char,'value':.5}),'novelty_input'))
            for payload,field in cases:
                with self.subTest(char=repr(char),field=field):
                    self.refuse(payload,'INTEL_REFUSED_BAD_TYPE:'+field)
                    try:self.run_(payload)
                    except ValueError as exc:
                        self.assertNotIn(char,str(exc));self.assertNotIn('U+',str(exc));self.assertNotIn(hex(ord(char)),str(exc))
    def test_zs_text_allowed_url_refused(self):
        for char in ['\u00a0','\u3000']:
            title='a'+char+'b';art={'id':'a'+char+'b','title':title,'url':'https://example.org/x'}
            out=self.run_(req(invention=inv(title=title,summary=title,id=title,components=[title],novel_features=[title]),prior_art=[art]))
            self.assertIn(title,out['claims'][0]['text']);self.assertEqual(out['prior_art_passthrough'],[art])
            art['url']+=char;self.refuse(req(prior_art=[art]),'INTEL_REFUSED_BAD_TYPE:prior_art')
    def test_cap_before_unicode(self):
        for field in ['id','title','summary']:self.refuse(req(invention=inv(**{field:'x'*500+'\u202e'})),'INTEL_REFUSED_OVERSIZE:'+field)
        for field in ['components','novel_features']:self.refuse(req(invention=inv(**{field:['x'*500+'\u200b']})),'INTEL_REFUSED_OVERSIZE:'+field)
        for field,cap in [('id',500),('title',500),('url',2000)]:
            art={'id':'x','title':'x','url':'https://example.org/x'};art[field]='x'*cap+'\u202e'
            self.refuse(req(prior_art=[art]),'INTEL_REFUSED_OVERSIZE:'+field)
    def test_nonstring_text(self):
        for field in ['id','title','summary']:self.refuse(req(invention=inv(**{field:1})),'INTEL_REFUSED_BAD_TYPE:'+field)
        for field in ['id','title','url']:
            art={'id':'x','title':'x','url':'https://example.org/x'};art[field]=1;self.refuse(req(prior_art=[art]),'INTEL_REFUSED_BAD_TYPE:prior_art')
    def test_request_keys_not_echoed(self):
        for char in ['\u202e','\u200b','\x07','\u2028','\u2029']:
            payload=req();payload['unknown'+char]=1;self.refuse(payload,'INTEL_REFUSED_UNKNOWN:request')

class TestRemainingMutationPins(Base):
    def test_nested_nonstring_keys_precede_unknown_and_types(self):
        self.refuse(req(invention=inv(components=[{1:'x'}])),'INTEL_REFUSED_BAD_TYPE:key')
        self.refuse(req(invention=inv(components=[[{1:'x'}]])),'INTEL_REFUSED_BAD_TYPE:key')
    def test_shared_helper_failure_maps_to_unit_field(self):
        from unittest.mock import patch
        from app.modules.c30 import policy
        with patch.object(policy,'clean_text',side_effect=ValueError('POLICY_REFUSED_TEXT_TOO_LONG:private')):
            self.refuse(req(),'INTEL_REFUSED_BAD_TYPE:id')
    def test_forbidden_classes_exact_complete_tables(self):
        tables={'SEND':['send','approve','approved','approval','approval_token','smtp','token','email_send','sender','smtp_host','smtp_port','smtp_user'],'SPEND':['pay','purchase','spend','buy','checkout','card_number'],'FILE':['file','submit','uspto_submit','epo_submit','grant'],'NOCREDS':['login','password','username','credentials','otp','api_key','access_token','refresh_token','bearer','pass','passwd']}
        for reason,keys in tables.items():
            for key in keys:
                request=req();request['invention']['components']=[{key:False}]
                self.refuse(request,'INTEL_REFUSED_'+reason+':'+key)


class TestCallerBoundaryRepair(Base):
    def test_exact_builtin_types(self):
        class D(dict):pass
        class L(list):pass
        class S(str):pass
        self.refuse(D(req()),'INTEL_REFUSED_BAD_TYPE:request')
        self.refuse(req(invention=D(inv())),'INTEL_REFUSED_BAD_TYPE:invention')
        self.refuse(req(invention=inv(components=L(['a']))),'INTEL_REFUSED_BAD_TYPE:components')
        self.refuse(req(invention=inv(novel_features=L(['a']))),'INTEL_REFUSED_BAD_TYPE:novel_features')
        r=req();r[S('as_of')]=r.pop('as_of');self.refuse(r,'INTEL_REFUSED_BAD_TYPE:key')
        self.refuse(req(as_of=S('2026-10-11')),'INTEL_REFUSED_BAD_TYPE:as_of')
        self.refuse(req(invention=inv(title=S('x'))),'INTEL_REFUSED_BAD_TYPE:title')
        self.refuse(req(prior_art=L(req()['prior_art'])),'INTEL_REFUSED_BAD_TYPE:prior_art')
        self.refuse(req(novelty_input=D({'source':'c32.ideate','value':.5})),'INTEL_REFUSED_BAD_TYPE:novelty_input')
    def test_cycles_safe_refused(self):
        r=req();r['unknown']=r;self.refuse(r,'INTEL_REFUSED_BAD_TYPE:request')
        r=req();v=[];v.append(v);r['unknown']=v;self.refuse(r,'INTEL_REFUSED_BAD_TYPE:request')
    def test_huge_novelty_integer(self):
        for value in [10**1000,-10**1000]:self.refuse(req(novelty_input={'source':'c32.ideate','value':value}),'INTEL_REFUSED_BAD_TYPE:novelty_input')

class TestResourcePins(Base):
    def test_depth_exact_boundary(self):
        value=0
        for _ in range(32):value=[value]
        self.mod._preflight(value)
        self.refuse({'as_of':'2026-10-11','invention':inv(),'prior_art':req()['prior_art'],'novelty_input':None,'unknown':value},'INTEL_REFUSED_OVERSIZE:request')
        value=[value]
        with self.assertRaises(ValueError) as cm:self.mod._preflight(value)
        self.assertEqual(str(cm.exception),'INTEL_REFUSED_OVERSIZE:request')
    def test_nodes_exact_boundary(self):
        # Dict key counts as a node: 2 root + 1 outer + 100 sublists +9897 leaves.
        value={'x':[[0]*98 for _ in range(99)]+[[0]*195]}
        self.mod._preflight(value)
        value['x'][-1].append(0)
        with self.assertRaises(ValueError) as cm:self.mod._preflight(value)
        self.assertEqual(str(cm.exception),'INTEL_REFUSED_OVERSIZE:request')
    def test_collection_count_before_copy_and_scan(self):
        self.refuse(req(invention=inv(components=[{'file':1}]*31)),'INTEL_REFUSED_OVERSIZE:components')
        self.refuse(req(prior_art=[{'send':1}]*201),'INTEL_REFUSED_OVERSIZE:prior_art')
        self.refuse(req(invention=inv(components=[{'x':list(range(201))}])),'INTEL_REFUSED_OVERSIZE:components')
    def test_subclasses_all_boundaries(self):
        class S(str):pass
        class I(int):pass
        class F(float):pass
        class D(dict):pass
        for field in ['id','title','summary']:self.refuse(req(invention=inv(**{field:S('x')})),'INTEL_REFUSED_BAD_TYPE:'+field)
        self.refuse(req(invention=inv(owner=S('self'))),'INTEL_REFUSED_NOT_OWNER:owner')
        for field in ['components','novel_features']:self.refuse(req(invention=inv(**{field:[S('x')]})),'INTEL_REFUSED_BAD_TYPE:'+field)
        for value in [I(0),F(.5)]:self.refuse(req(novelty_input={'source':'c32.ideate','value':value}),'INTEL_REFUSED_BAD_TYPE:novelty_input')
        self.refuse(req(novelty_input={'source':S('c32.ideate'),'value':.5}),'INTEL_REFUSED_BAD_TYPE:novelty_input')
        self.refuse(req(prior_art=[D(req()['prior_art'][0])]),'INTEL_REFUSED_BAD_TYPE:prior_art')
    def test_shape_first_precedence(self):
        r=req();r[1]='x';r['grant']=1;self.refuse(r,'INTEL_REFUSED_BAD_TYPE:key')
        r=req();r['grant']=1;self.refuse(r,'INTEL_REFUSED_FILE:grant')
        r=req();r['unknown']=1;self.refuse(r,'INTEL_REFUSED_UNKNOWN:request')


class TestPreflightSeamPins(Base):
    def test_depth_and_node_exact_seams(self):
        chain=0
        for _ in range(32):chain=[chain]
        self.mod._preflight(chain)
        leaves=[[] for _ in range(200)]
        self.mod._preflight(leaves)
        # 1 root + 50 lists + 9949 leaves = 10000.
        nodes=[[0]*199 for _ in range(49)]+[[0]*198]
        self.mod._preflight(nodes)
        nodes[-1].append(0)
        with self.assertRaises(ValueError) as cm:self.mod._preflight(nodes)
        self.assertEqual(str(cm.exception),'INTEL_REFUSED_OVERSIZE:request')
    def test_shared_noncyclic_alias_is_not_cycle(self):
        shared={'x':1};self.mod._preflight([shared,shared])
    def test_nested_dict_count(self):
        # A data dictionary under components is not a schema envelope.
        value=req(invention=inv(components=[{str(i):0 for i in range(201)}]))
        self.refuse(value,'INTEL_REFUSED_OVERSIZE:components')
        value=req(invention=inv(components=[{str(i):0 for i in range(200)}]))
        self.refuse(value,'INTEL_REFUSED_BAD_TYPE:components')
    def test_list_count_admission_before_content_refusal(self):
        for field in ['components','novel_features']:
            self.refuse(req(invention=inv(**{field:[{'send':1}]*31})),'INTEL_REFUSED_OVERSIZE:'+field)
        self.refuse(req(prior_art=[{'send':1}]*201),'INTEL_REFUSED_OVERSIZE:prior_art')
    def test_preflight_subclass_guard_direct(self):
        class D(dict):pass
        class L(list):pass
        for node in [D(),L()]:
            with self.assertRaises(ValueError) as cm:self.mod._preflight([node])
            self.assertEqual(str(cm.exception),'INTEL_REFUSED_BAD_TYPE:request')


class TestRoundTwoRED(Base):
    def test_raw_key_cap_before_normalization(self):
        r=req();r['x'*10000000]=1
        self.refuse(r,'INTEL_REFUSED_OVERSIZE:key')
    def test_prospective_check_precedes_child_inspection(self):
        # 9999 admitted nodes before final child container; its two entries
        # exceed the global budget and must refuse before inspecting bad key.
        value={'x':[[0]*199 for _ in range(49)]+[[0]*193,[{1:0},0,0]]}
        with self.assertRaises(ValueError) as cm:self.mod._preflight(value)
        self.assertEqual(str(cm.exception),'INTEL_REFUSED_OVERSIZE:request')

class TestRoundTwoAllocationOrder(Base):
    def test_prospective_guard_before_children_allocation(self):
        import ast
        tree=ast.parse(inspect.getsource(self.mod._preflight))
        children_lines=[n.lineno for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='children' for t in n.targets)]
        guard_lines=[n.lineno for n in ast.walk(tree) if isinstance(n,ast.If) and 'nodes + len(node)' in ast.unparse(n.test)]
        self.assertTrue(guard_lines,'prospective guard must use raw container length')
        self.assertLess(min(guard_lines),min(children_lines))
    def test_raw_key_exact_boundaries(self):
        r=req();r['x'*200]=1;self.refuse(r,'INTEL_REFUSED_UNKNOWN:request')
        r=req();r['x'*201]=1;self.refuse(r,'INTEL_REFUSED_OVERSIZE:key')

class TestEnvelopeAdmissionPins(Base):
    def check_envelope(self, field):
        def build(forbidden):
            r=req()
            envelope=(r if field=='request' else r['prior_art'][0] if field=='prior_art' else r[field])
            for i in range(202-len(envelope)):
                envelope['unknown_%03d'%i]=0
            if forbidden:
                envelope.pop(next(k for k in envelope if k.startswith('unknown_')))
                envelope['send']=1
            self.assertEqual(len(envelope),202)
            return r
        # Unknown-only envelope is admitted by resource preflight, then schema refuses.
        self.refuse(build(False),'INTEL_REFUSED_UNKNOWN:'+field)
        # Same size with a forbidden key reaches forbidden scan before schema refusal.
        self.refuse(build(True),'INTEL_REFUSED_SEND:send')

    def test_total_nodes_deferred_final_scalar_10000_10001(self):
        admitted=[[[0]*199 for _ in range(49)]+[[0]*196],0]
        self.mod._preflight(admitted)
        rejected=[[[0]*199 for _ in range(49)]+[[0]*197],0]
        with self.assertRaises(ValueError) as cm:
            self.mod._preflight(rejected)
        self.assertEqual(str(cm.exception),'INTEL_REFUSED_OVERSIZE:request')

    def test_default_nested_list_200_201_precedence(self):
        self.refuse(req(unknown=[{'send':1}]+[0]*199),'INTEL_REFUSED_SEND:send')
        self.refuse(req(unknown=[{'send':1}]+[0]*200),'INTEL_REFUSED_OVERSIZE:request')
        self.refuse(req(unknown=[0]*200),'INTEL_REFUSED_UNKNOWN:request')
        self.refuse(req(unknown=[0]*201),'INTEL_REFUSED_OVERSIZE:request')

    def test_request_envelope_over_200(self):
        self.check_envelope('request')

    def test_invention_envelope_over_200(self):
        self.check_envelope('invention')

    def test_prior_art_envelope_over_200(self):
        self.check_envelope('prior_art')

    def test_novelty_input_envelope_over_200(self):
        self.check_envelope('novelty_input')

if __name__ == "__main__":
    unittest.main()
