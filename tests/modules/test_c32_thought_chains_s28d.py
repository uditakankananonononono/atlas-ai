"""S2.8-delta / c32.thought_chains tests. Hermetic, stdlib unittest."""
import importlib.util
import json
import pathlib
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_P = _ROOT / "backend/app/modules/c32/thought_chains.py"
_spec = importlib.util.spec_from_file_location("c32_thought_chains_mod", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c32_thought_chains_mod"] = m
_spec.loader.exec_module(m)

_L = _ROOT / "backend/app/modules/c32/thought.py"
_ls = importlib.util.spec_from_file_location("c32_thought_legacy_for_chains", _L)
legacy = importlib.util.module_from_spec(_ls)
sys.modules["c32_thought_legacy_for_chains"] = legacy
_ls.loader.exec_module(legacy)

FIXTURE = _ROOT / "tests/modules/fixtures/c32_thought_chains_120.json"
CONTRACT = _ROOT / "docs/contracts/S2.8-delta.md"
MOVES = ("analogy", "first_principles", "heuristic", "inversion", "narrative", "systems")
TEMPLATE = ("This analyzer tags reasoning-move cues using a fixed word list. Counts show where cues appear in the "
            "supplied text, not whether anyone reasoned well or originally. Precision and recall are agreement with "
            "synthetic labels written for this fixture, not validation of human thinking. Audio is not transcribed. "
            "Only the media supplied are covered: {media}.")


def D(text, id="d1", kind="text", medium="essay", **kw):
    d = {"id": id, "kind": kind, "medium": medium, "text": text}
    d.update(kw)
    return d


def run(*docs):
    return m.run({"docs": list(docs)})


def one(text, **kw):
    return run(D(text, **kw))["docs"][0]


def err(fn, *a, **k):
    try:
        fn(*a, **k)
    except ValueError as exc:
        return str(exc)
    raise AssertionError("no ValueError")


def hits(doc):
    return {k: v["hits"] for k, v in doc["moves"].items() if v["hits"]}


class Entry(unittest.TestCase):
    def test_analyze_v2_is_run_alias(self):
        self.assertIs(m.analyze_v2, m.run)

    def test_request_shape_refusals(self):
        for bad in (None, [], "x", 5, True):
            self.assertEqual(err(m.run, bad), "TREND_REFUSED_BAD_TYPE:request")
        for bad in (None, "x", {"a": 1}, 5, True):
            self.assertEqual(err(m.run, {"docs": bad}), "TREND_REFUSED_BAD_TYPE:docs")
        self.assertEqual(err(m.run, {"docs": []}), "TREND_REFUSED_EMPTY:docs")
        self.assertEqual(err(m.run, {}), "TREND_REFUSED_BAD_TYPE:docs")
        self.assertEqual(err(m.run, {"docs": [D("a")] * (m.MAX_TEXTS + 1)}), "TREND_REFUSED_OVERSIZE:docs")
        self.assertEqual(err(m.run, {"docs": [5]}), "TREND_REFUSED_BAD_TYPE:docs")

    def test_audio_and_kind_and_text_refusals(self):
        self.assertEqual(err(run, D("x", kind="audio")), "TREND_REFUSED_AUDIO")
        self.assertEqual(err(run, D("x", kind="video")), "TREND_REFUSED_BAD_TYPE:kind")
        self.assertEqual(err(run, D("x\x00")), "TREND_REFUSED_CONTROL_CHARS:text")
        self.assertEqual(err(run, D("x", id="a\x00")), "TREND_REFUSED_BAD_TYPE:id")
        self.assertEqual(err(run, D("   ")), "TREND_REFUSED_EMPTY:text")
        self.assertEqual(err(run, D("x" * 200001)), "TREND_REFUSED_OVERSIZE:text")
        self.assertEqual(err(run, D(5)), "TREND_REFUSED_BAD_TYPE:text")
        self.assertEqual(err(run, D("x", id="i" * 65)), "TREND_REFUSED_OVERSIZE:id")
        self.assertEqual(m.MAX_TEXTS, 10000)

    def test_kind_defaults_to_text_and_newlines_allowed(self):
        d = {"id": "a", "medium": "lyrics", "text": "I loop\nA story"}
        self.assertEqual(m.run({"docs": [d]})["docs"][0]["kind"], "text")

    def test_medium_enum(self):
        self.assertEqual(m.MEDIA, ("podcast", "audiobook", "book", "article", "essay", "speech", "lecture",
                                   "interview", "lyrics", "poem", "other"))
        for ok in m.MEDIA:
            self.assertEqual(one("hello world", medium=ok)["medium"], ok)
        self.assertEqual(err(run, D("x", medium="tiktok")), "TREND_REFUSED_BAD_TYPE:medium")
        self.assertEqual(err(run, D("x", medium=None)), "TREND_REFUSED_BAD_TYPE:medium")
        self.assertEqual(err(run, {"id": "a", "text": "x"}), "TREND_REFUSED_BAD_TYPE:medium")
        self.assertEqual(err(run, D("x", medium="Podcast")), "TREND_REFUSED_BAD_TYPE:medium")
        self.assertEqual(err(run, D("x", medium=5)), "TREND_REFUSED_BAD_TYPE:medium")


class Tagging(unittest.TestCase):
    def test_four_sentence_chain_hand_computed(self):
        text = "Think from first principles. It is like a loop. Nothing here. A story tends to repeat."
        d = one(text)
        s1, s3 = text.index("It is"), text.index("A story")
        self.assertEqual(d["sentence_count"], 4)
        self.assertEqual(d["chains"], [
            {"sentence": 0, "offset": 0, "moves": ["first_principles"]},
            {"sentence": 1, "offset": s1, "moves": ["analogy", "systems"]},
            {"sentence": 3, "offset": s3, "moves": ["narrative", "heuristic"]}])
        self.assertEqual(d["transitions"], {"analogy": {"systems": 1}, "first_principles": {"analogy": 1},
                                            "narrative": {"heuristic": 1}, "systems": {"narrative": 1}})
        self.assertEqual(d["longest_run"], 2)
        self.assertEqual(hits(d), {"first_principles": 1, "analogy": 1, "systems": 1, "narrative": 1, "heuristic": 1})
        self.assertEqual(d["move_total"], 5)

    def test_corpus_transitions_sum_docs(self):
        r = run(D("A loop. A story.", id="a"), D("A loop. A story.", id="b"))
        self.assertEqual(r["transitions"], {"systems": {"narrative": 2}})
        self.assertEqual(r["doc_count"], 2)

    def test_hits_vs_sentences_with_move(self):
        d = one("The loop loop loop. Another loop here.")
        self.assertEqual(d["moves"]["systems"]["hits"], 4)
        self.assertEqual(d["moves"]["systems"]["sentences_with_move"], 2)

    def test_same_move_twice_one_sentence_no_self_transition_inflation(self):
        d = one("A loop and a system.")
        self.assertEqual(d["chains"][0]["moves"], ["systems"])
        self.assertEqual(d["transitions"], {})

    def test_longest_run_breaks_on_untagged(self):
        d = one("A loop. A story. Plain words. A loop. A story. A system. Plain.")
        self.assertEqual(d["longest_run"], 3)
        self.assertEqual(one("Nothing at all here.")["longest_run"], 0)

    def test_run_between_non_adjacent_tagged_sentences_links(self):
        d = one("A loop. Plain. A story.")
        self.assertEqual(d["transitions"], {"systems": {"narrative": 1}})
        self.assertEqual(d["longest_run"], 1)

    def test_sentence_boundaries(self):
        self.assertEqual(one("No terminal punctuation here")["sentence_count"], 1)
        self.assertEqual(one("One. Two! Three? Four")["sentence_count"], 4)
        self.assertEqual(one("a.b is one token\nsecond line")["sentence_count"], 2)   # "." needs whitespace after
        self.assertEqual(one("Wait... what")["sentence_count"], 2)

    def test_word_boundary_not_substring(self):
        text = "A sconce hung there."
        self.assertEqual(hits(one(text)), {})
        self.assertEqual(one(text)["legacy_comparison"]["narrative"], 1)   # legacy substring "once"
        self.assertEqual(hits(one("Once upon a time.")), {"narrative": 1})
        self.assertEqual(hits(one("Systems and systemic risk")), {"systems": 1})   # "systemic" is no cue

    def test_inflections_listed(self):
        for text, mv in (("Teams tend to copy.", "heuristic"), ("She tended to", "heuristic"),
                         ("rules of thumb", "heuristic"), ("two stories", "narrative"),
                         ("networks and loops", "systems"), ("like an owl", "analogy"),
                         ("fundamentals", "first_principles"), ("Why are we here", "first_principles"),
                         ("opposites attract", "inversion")):
            self.assertGreaterEqual(one(text)["moves"][mv]["hits"], 1, text)

    def test_case_insensitive_and_unicode_words(self):
        self.assertEqual(hits(one("FIRST PRINCIPLES")), {"first_principles": 1})
        self.assertEqual(hits(one("A l\u00f3op story")), {"narrative": 1})

    def test_apostrophe_kept_inside_words(self):
        self.assertEqual(hits(one("It's a story's end")), {})   # "story's" is one word, not "story"

    def test_legacy_comparison_matches_analyze(self):
        text = "Work from first principles. It is like a lever. A feedback loop emerges."
        d = one(text)
        ref = legacy.analyze([{"id": "d1", "kind": "text", "text": text}])["docs"][0]["moves"]
        self.assertEqual(d["legacy_comparison"], ref)

    def test_legacy_comparison_on_lyrics_with_newlines(self):
        text = "A feedback loop\nonce more"
        self.assertEqual(err(legacy.analyze, [{"id": "d", "text": text}]), "TREND_REFUSED_CONTROL_CHARS:text")
        d = one(text, kind="lyrics", medium="lyrics")
        self.assertEqual(d["legacy_comparison"]["systems"], 2)
        self.assertEqual(d["legacy_comparison"]["narrative"], 1)
        self.assertEqual(hits(d), {"systems": 2, "narrative": 1})

    def test_evidence_spans_cap_and_offsets(self):
        text = " ".join("A loop %d." % i for i in range(7))
        d = one(text, id="zz")
        ev = d["evidence"]["systems"]
        self.assertEqual(len(ev), 5)
        self.assertEqual(d["moves"]["systems"]["sentences_with_move"], 7)
        for e in ev:
            self.assertEqual(e["doc"], "zz")
            self.assertEqual(text[e["offset"]:e["offset"] + len(e["sentence"])], e["sentence"])
        self.assertEqual([e["offset"] for e in ev], sorted(e["offset"] for e in ev))
        self.assertEqual(ev[0]["offset"], 0)
        self.assertEqual(d["evidence"]["analogy"], [])


class Exclusions(unittest.TestCase):
    def test_negation_window_boundary(self):
        self.assertEqual(hits(one("It is not like a machine.")), {})
        self.assertEqual(one("It is not like a machine.")["excluded_hits"], {"negated": 1, "quoted": 0})
        self.assertEqual(hits(one("It is not w x y like a machine.")), {"analogy": 1})   # w x y precede; not is 4 back
        self.assertEqual(hits(one("not w x y like a machine")), {"analogy": 1})        # not is 4 words back
        self.assertEqual(hits(one("not x y like a machine")), {})                      # not is 3 words back
        self.assertEqual(hits(one("never x like a machine")), {})
        self.assertEqual(hits(one("no like a machine")), {})

    def test_negation_contraction_and_sentence_scope(self):
        self.assertEqual(hits(one("It isn't like a machine.")), {})
        self.assertEqual(hits(one("It doesn't matter if like a machine.")), {})
        self.assertEqual(hits(one("Not now. It is like a machine.")), {"analogy": 1})
        self.assertEqual(hits(one("not\nlike a machine")), {"analogy": 1})   # newline starts a new sentence

    def test_negation_word_must_be_whole_word(self):
        self.assertEqual(hits(one("It is nothing like a machine.")), {"analogy": 1})
        self.assertEqual(hits(one("It is nobody like a machine.")), {"analogy": 1})
        self.assertEqual(hits(one("Another like a machine.")), {"analogy": 1})

    def test_negation_applies_to_each_cue_independently(self):
        d = one("It is not like a machine but similar to a garden.")
        self.assertEqual(hits(d), {"analogy": 1})
        self.assertEqual(d["excluded_hits"]["negated"], 1)

    def test_negation_before_multiword_cue_uses_first_word(self):
        self.assertEqual(hits(one("never from first principles")), {})
        self.assertEqual(hits(one("from first principles never")), {"first_principles": 1})

    def test_quote_exclusion_straight_and_curly(self):
        d = one('He said "like a rock" today.')
        self.assertEqual((hits(d), d["excluded_hits"]), ({}, {"negated": 0, "quoted": 1}))
        d = one("The sign read \u201cfeedback welcome\u201d and a story.")
        self.assertEqual((hits(d), d["excluded_hits"]["quoted"]), ({"narrative": 1}, 1))
        self.assertEqual(hits(one('"a story" and a story and "a story"')), {"narrative": 1})

    def test_quote_spans_cross_sentences(self):
        d = one('He said "stop. a loop. go" then a story.')
        self.assertEqual((hits(d), d["excluded_hits"]["quoted"]), ({"narrative": 1}, 1))

    def test_unmatched_quotes(self):
        d = one('He said "like a rock today.')
        self.assertEqual((hits(d), d["unmatched_quote_marks"]), ({"analogy": 1}, 1))
        d = one("A story\u201d here.")
        self.assertEqual((hits(d), d["unmatched_quote_marks"]), ({"narrative": 1}, 1))
        d = one('A "story" ends " here a loop')
        self.assertEqual((hits(d), d["unmatched_quote_marks"]), ({"systems": 1}, 1))
        self.assertEqual(one("no quotes")["unmatched_quote_marks"], 0)

    def test_apostrophes_and_single_quotes_never_open_spans(self):
        d = one("She said 'a story' and it's a loop")
        self.assertEqual((hits(d), d["excluded_hits"]["quoted"]), ({"narrative": 1, "systems": 1}, 0))

    def test_quoted_beats_negated_and_counts_once(self):
        d = one('Not "like a rock" at all.')
        self.assertEqual(d["excluded_hits"], {"negated": 0, "quoted": 1})

    def test_corpus_excluded_totals(self):
        r = run(D('"a loop"', id="a"), D("not a loop", id="b"), D('"', id="c"))
        self.assertEqual(r["excluded_hits"], {"negated": 1, "quoted": 1})
        self.assertEqual(r["unmatched_quote_marks"], 1)


class Normalization(unittest.TestCase):
    def test_per_1000_words_long_vs_short(self):
        short = D("A loop.", id="short", kind="text", medium="lyrics")
        long_ = D("A loop " + " ".join(["filler"] * 998) + ".", id="long", kind="text", medium="book")
        r = run(short, long_)
        ds = {d["id"]: d for d in r["docs"]}
        self.assertEqual(ds["short"]["word_count"], 2)
        self.assertEqual(ds["short"]["moves"]["systems"]["per_1000_words"], 500.0)
        self.assertEqual(ds["long"]["word_count"], 1000)
        self.assertEqual(ds["long"]["moves"]["systems"]["per_1000_words"], 1.0)

    def test_rounding_six_places_and_zero_words(self):
        d = one("A loop of three words")        # 5 words, 1 hit -> 200.0
        self.assertEqual(d["moves"]["systems"]["per_1000_words"], 200.0)
        d = one("one two three loop " + "x " * 3)  # 7 words -> 142.857143
        self.assertEqual(d["moves"]["systems"]["per_1000_words"], 142.857143)
        d = one("...")
        self.assertEqual((d["word_count"], d["moves"]["systems"]["per_1000_words"]), (0, 0.0))

    def test_by_kind_and_medium_pooled_rates(self):
        r = run(D("A loop.", id="a", kind="lyrics", medium="lyrics"),
                D("A loop " + "w " * 8 + ".", id="b", kind="text", medium="book"),
                D("Plain " + "w " * 9 + ".", id="c", kind="text", medium="book"))
        bk = r["by_kind"]
        self.assertEqual(bk["lyrics"]["docs"], 1)
        self.assertEqual(bk["lyrics"]["word_count"], 2)
        self.assertEqual(bk["lyrics"]["moves"]["systems"]["per_1000_words"], 500.0)
        self.assertEqual(bk["text"]["docs"], 2)
        self.assertEqual(bk["text"]["word_count"], 20)
        self.assertEqual(bk["text"]["moves"]["systems"]["hits"], 1)
        self.assertEqual(bk["text"]["moves"]["systems"]["per_1000_words"], 50.0)
        bm = r["by_medium"]
        self.assertEqual(sorted(bm), ["book", "lyrics"])
        self.assertEqual(bm["book"]["moves"]["systems"]["per_1000_words"], 50.0)
        self.assertEqual(r["move_totals"]["systems"], 2)
        self.assertEqual(r["word_count"], 22)

    def test_ranking(self):
        r = run(D("plain", id="b"), D("A loop. A story.", id="z"), D("A loop. A story.", id="a"))
        self.assertEqual([d["id"] for d in r["docs"]], ["a", "z", "b"])


class Turns(unittest.TestCase):
    TEXT = "It is like a loop. A story begins."

    def _turns(self, **over):
        t = [{"speaker": "Ann", "text": "It is like a loop. ", "t_start": 0},
             {"speaker": "Bo", "text": "A story begins.", "t_start": 2.5}]
        return t

    def test_speaker_attribution(self):
        d = one(self.TEXT, kind="transcript", medium="podcast", turns=self._turns())
        self.assertEqual(d["speakers"], {"Ann": {"analogy": 1, "systems": 1}, "Bo": {"narrative": 1}})
        self.assertEqual(d["turns"][0]["speaker"], "Ann")
        self.assertEqual(d["turns"][1]["moves"], {"narrative": 1})

    def test_cue_attribution_by_cue_offset(self):
        t = [{"speaker": "A", "text": "It is like"}, {"speaker": "B", "text": " a loop"}]
        d = one("It is like a loop", turns=t)
        self.assertEqual(d["speakers"], {"A": {"analogy": 1}, "B": {"systems": 1}})   # cue "like a" starts in A

    def test_nospeaker(self):
        t = self._turns()
        t[1]["speaker"] = "   "
        self.assertEqual(err(run, D(self.TEXT, turns=t)), "TREND_REFUSED_NOSPEAKER")
        t = self._turns()
        del t[0]["speaker"]
        self.assertEqual(err(run, D(self.TEXT, turns=t)), "TREND_REFUSED_BAD_TYPE:speaker")
        t = self._turns()
        t[0]["speaker"] = 5
        self.assertEqual(err(run, D(self.TEXT, turns=t)), "TREND_REFUSED_BAD_TYPE:speaker")

    def test_partition_must_be_exact(self):
        t = self._turns()
        t[0]["text"] = "It is like a loop."   # separator moved out: no whitespace-join leniency
        self.assertEqual(err(run, D(self.TEXT, turns=t)), "TREND_REFUSED_BAD_SEGMENT")
        t = self._turns()
        t[1]["text"] = "A story begins"
        self.assertEqual(err(run, D(self.TEXT, turns=t)), "TREND_REFUSED_BAD_SEGMENT")
        self.assertEqual(err(run, D(self.TEXT, turns=[])), "TREND_REFUSED_BAD_SEGMENT")
        self.assertEqual(err(run, D(self.TEXT, turns=self._turns() + [{"speaker": "C", "text": "x"}])),
                         "TREND_REFUSED_BAD_SEGMENT")

    def test_turn_shape_and_t_start(self):
        self.assertEqual(err(run, D(self.TEXT, turns="x")), "TREND_REFUSED_BAD_TYPE:turns")
        self.assertEqual(err(run, D(self.TEXT, turns=[5])), "TREND_REFUSED_BAD_TYPE:turns")
        t = self._turns()
        t[0]["text"] = 5
        self.assertEqual(err(run, D(self.TEXT, turns=t)), "TREND_REFUSED_BAD_TYPE:turn_text")
        for bad in (True, "1", -1, float("nan"), float("inf"), None):
            t = self._turns()
            t[1]["t_start"] = bad
            if bad is None:
                self.assertEqual(one(self.TEXT, turns=t)["speakers"]["Bo"], {"narrative": 1})   # t_start optional
                continue
            self.assertEqual(err(run, D(self.TEXT, turns=t)), "TREND_REFUSED_BAD_TYPE:t_start", repr(bad))
        t = self._turns()
        t[0]["t_start"] = 5
        self.assertEqual(err(run, D(self.TEXT, turns=t)), "TREND_REFUSED_BAD_SEGMENT")   # decreasing
        t[0]["t_start"] = 2.5                                                           # equal is non-decreasing
        self.assertEqual(one(self.TEXT, turns=t)["speakers"]["Ann"]["analogy"], 1)
        t = self._turns()
        del t[0]["t_start"]
        self.assertEqual(one(self.TEXT, turns=t)["speakers"]["Bo"], {"narrative": 1})

    def test_lyrics_may_carry_turns(self):
        t = [{"speaker": "chorus", "text": "A loop\n"}, {"speaker": "vocalist", "text": "A story"}]
        d = one("A loop\nA story", kind="lyrics", medium="lyrics", turns=t)
        self.assertEqual(d["speakers"], {"chorus": {"systems": 1}, "vocalist": {"narrative": 1}})
        self.assertEqual(d["transitions"], {"systems": {"narrative": 1}})


class Segments(unittest.TestCase):
    TEXT = "Chapter one. A loop here. Chapter two. A story there."

    def segs(self):
        return [{"label": "ch1", "text": "Chapter one. A loop here. "}, {"label": "ch2", "text": "Chapter two. A story there."}]

    def test_per_chapter_moves(self):
        d = one(self.TEXT, medium="book", segments=self.segs())
        self.assertEqual(d["segments"][0], {"label": "ch1", "moves": {"narrative": 1, "systems": 1}})
        self.assertEqual(d["segments"][1], {"label": "ch2", "moves": {"narrative": 2}})

    def test_inconsistent_segment_bad_segment(self):
        s = self.segs()
        s[1]["text"] = "Chapter two. A story there"
        self.assertEqual(err(run, D(self.TEXT, segments=s)), "TREND_REFUSED_BAD_SEGMENT")
        s = self.segs()
        s[0]["text"] = s[0]["text"].strip()
        self.assertEqual(err(run, D(self.TEXT, segments=s)), "TREND_REFUSED_BAD_SEGMENT")
        self.assertEqual(err(run, D(self.TEXT, segments=self.segs()[:1])), "TREND_REFUSED_BAD_SEGMENT")
        self.assertEqual(err(run, D(self.TEXT, segments=self.segs()[::-1])), "TREND_REFUSED_BAD_SEGMENT")

    def test_segment_shape(self):
        self.assertEqual(err(run, D(self.TEXT, segments="x")), "TREND_REFUSED_BAD_TYPE:segments")
        self.assertEqual(err(run, D(self.TEXT, segments=[5])), "TREND_REFUSED_BAD_TYPE:segments")
        s = self.segs()
        s[0]["label"] = ""
        self.assertEqual(err(run, D(self.TEXT, segments=s)), "TREND_REFUSED_EMPTY:label")
        s = self.segs()
        s[0]["text"] = 5
        self.assertEqual(err(run, D(self.TEXT, segments=s)), "TREND_REFUSED_BAD_TYPE:segment_text")

    def test_turns_and_segments_coexist_only_if_both_partition(self):
        t = [{"speaker": "A", "text": "Chapter one. A loop here. "}, {"speaker": "B", "text": "Chapter two. A story there."}]
        d = one(self.TEXT, turns=t, segments=self.segs())
        self.assertIn("speakers", d)
        self.assertIn("segments", d)
        t[1]["text"] = "Chapter two."
        self.assertEqual(err(run, D(self.TEXT, turns=t, segments=self.segs())), "TREND_REFUSED_BAD_SEGMENT")


class Report(unittest.TestCase):
    def test_caveat_template_pinned_and_rendered(self):
        self.assertEqual(m.REPORT_CAVEAT_TEMPLATE, TEMPLATE)
        r = run(D("a", id="1", medium="podcast"), D("b", id="2", medium="book"), D("c", id="3", medium="podcast"))
        self.assertEqual(r["media"], ["book", "podcast"])
        self.assertEqual(r["report_caveat"], TEMPLATE.replace("{media}", "book, podcast"))
        self.assertTrue(r["report_caveat"].endswith("Only the media supplied are covered: book, podcast."))
        self.assertEqual(r["validity"]["caveat"], r["report_caveat"])
        self.assertEqual(run(D("a"))["report_caveat"].count("essay"), 1)

    def test_contract_carries_template_verbatim_and_pin(self):
        text = CONTRACT.read_text(encoding="utf-8")
        self.assertIn(TEMPLATE, text)
        self.assertIn("{media}", text)
        self.assertIn("## Source scope", text)
        for forbidden in ("wamid", "whatsapp", "WhatsApp", "Analyse intelligent human thinking"):
            self.assertNotIn(forbidden, text)
        self.assertNotIn("understands thinking", text.replace("not claim", "").replace('"understands thinking"', ""))

    def test_scope_and_limits(self):
        s = run(D("a"))["scope"]
        self.assertEqual(set(s), {"implemented", "not_implemented", "data_source", "as_of"})
        self.assertIn("audio transcription (no bundled ASR offline)", s["not_implemented"])
        self.assertIn("all forms of media", s["not_implemented"])
        self.assertEqual(s["data_source"], "supplied transcripts/text/lyrics")

    def test_no_understanding_claim_in_report(self):
        blob = json.dumps(run(D("A loop. A story.")), sort_keys=True).lower()
        self.assertNotIn("understands thinking", blob)
        self.assertNotIn("understands", blob)

    def test_determinism_byte_identical(self):
        req = {"docs": [D("A loop. It is like a story, usually.", id="b"), D("Why is this so? A story.", id="a")]}
        a = json.dumps(m.run(req), sort_keys=True)
        self.assertEqual(a, json.dumps(m.run(json.loads(json.dumps(req))), sort_keys=True))
        self.assertEqual(m.run(req), m.run(req))

    def test_request_not_mutated(self):
        req = {"docs": [D("A loop.", turns=[{"speaker": "a", "text": "A loop."}])]}
        snap = json.dumps(req, sort_keys=True)
        m.run(req)
        self.assertEqual(json.dumps(req, sort_keys=True), snap)

    def test_no_effect_functions_exposed(self):
        pub = sorted(n for n, v in vars(m).items() if callable(v) and not n.startswith("_") and getattr(v, "__module__", None) == m.__name__)
        for n in pub:
            for bad in ("spend", "send", "post", "trade", "buy", "email", "account", "fetch", "scrape", "publish"):
                self.assertNotIn(bad, n.lower())
        self.assertEqual(pub, ["analyze_v2", "run"])    # the alias is the same object

    def test_cue_lists_frozen(self):
        self.assertEqual(tuple(sorted(m.CUES)), MOVES)
        self.assertEqual(m.CUES["heuristic"], ("rule of thumb", "rules of thumb", "usually", "tends to", "tend to",
                                               "tended to", "as a rule"))
        self.assertEqual(m.CUES["analogy"], ("like a", "like an", "as if", "similar to", "reminds", "reminded", "reminding"))
        self.assertEqual(m.CUES["inversion"], ("opposite", "opposites", "in reverse", "instead", "backwards"))
        self.assertEqual(m.CUES["first_principles"], ("first principles", "first principle", "fundamental",
                                                      "fundamentals", "from scratch", "why is", "why are"))
        self.assertEqual(m.CUES["narrative"], ("story", "stories", "journey", "journeys", "once", "chapter", "chapters"))
        self.assertEqual(m.CUES["systems"], ("feedback", "loop", "loops", "system", "systems", "emerges", "emerge",
                                             "emerging", "network", "networks"))


class MutationPins(unittest.TestCase):
    """Pins added for survivors of the first whole-file mutation run (new child commit)."""

    def test_limits_at_exact_boundaries(self):
        self.assertEqual(one("a" * 200000)["word_count"], 1)
        self.assertEqual(err(run, D("a" * 200001)), "TREND_REFUSED_OVERSIZE:text")
        self.assertEqual(one("hello", id="i" * 64)["id"], "i" * 64)
        segs = [{"label": "l" * 64, "text": "hello"}]
        self.assertEqual(one("hello", segments=segs)["segments"][0]["label"], "l" * 64)
        segs = [{"label": "l" * 65, "text": "hello"}]
        self.assertEqual(err(run, D("hello", segments=segs)), "TREND_REFUSED_OVERSIZE:label")

    def test_bad_kind_and_medium_values_are_not_echoed(self):
        self.assertEqual(err(run, D("x", kind="k" * 70)), "TREND_REFUSED_BAD_TYPE:kind")
        self.assertEqual(err(run, D("x", medium="m" * 70)), "TREND_REFUSED_BAD_TYPE:medium")

    def test_sentence_text_keeps_terminal_punctuation_and_trims_trailing_space(self):
        d = one("A loop. B story")
        self.assertEqual([e["sentence"] for e in d["evidence"]["systems"]], ["A loop."])
        d = one("A loop \nB story")
        self.assertEqual(d["evidence"]["systems"][0]["sentence"], "A loop")
        self.assertEqual(d["evidence"]["narrative"][0], {"doc": "d1", "offset": 8, "sentence": "B story"})

    def test_newline_sentence_start_and_word_count(self):
        d = one("one\ntwo story")
        self.assertEqual((d["sentence_count"], d["word_count"]), (2, 3))
        self.assertEqual(d["evidence"]["narrative"][0], {"doc": "d1", "offset": 4, "sentence": "two story"})

    def test_leading_punctuation_sentence(self):
        self.assertEqual(one(". A loop")["sentence_count"], 2)
        self.assertEqual(one("\n\nA loop")["sentence_count"], 1)

    def test_quote_scanning_edge_cases(self):
        self.assertEqual(one('"" a story')["unmatched_quote_marks"], 0)
        self.assertEqual(one('"\u201d')["unmatched_quote_marks"], 2)
        d = one('"a""like a" x')
        self.assertEqual((d["excluded_hits"]["quoted"], d["unmatched_quote_marks"]), (1, 0))

    def test_attribution_at_offset_zero_and_turn_boundary(self):
        t = [{"speaker": "A", "text": "story "}, {"speaker": "B", "text": "loop"}]
        d = one("story loop", turns=t)
        self.assertEqual(d["speakers"], {"A": {"narrative": 1}, "B": {"systems": 1}})
        segs = [{"label": "x", "text": "story "}, {"label": "y", "text": "loop"}]
        d = one("story loop", segments=segs)
        self.assertEqual([s["moves"] for s in d["segments"]], [{"narrative": 1}, {"systems": 1}])

    def test_exactly_max_texts_docs_allowed(self):
        r = m.run({"docs": [D("a", id="d%d" % i) for i in range(m.MAX_TEXTS)]})
        self.assertEqual(r["doc_count"], m.MAX_TEXTS)


def _agreement():
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))
    tp = {k: 0 for k in MOVES}
    fp = dict(tp)
    fn = dict(tp)
    for row in rows:
        d = m.run({"docs": [D(row["text"], id=row["id"])]})["docs"][0]
        pred = {k for k, v in d["moves"].items() if v["hits"]}
        gold = set(row["labels"])
        for k in MOVES:
            tp[k] += k in pred and k in gold
            fp[k] += k in pred and k not in gold
            fn[k] += k not in pred and k in gold
    out = {}
    for k in MOVES:
        p = round(tp[k] / (tp[k] + fp[k]), 6) if tp[k] + fp[k] else None
        r = round(tp[k] / (tp[k] + fn[k]), 6) if tp[k] + fn[k] else None
        out[k] = {"tp": tp[k], "fp": fp[k], "fn": fn[k], "precision": p, "recall": r}
    return len(rows), out


class Fixture(unittest.TestCase):
    def test_fixture_shape(self):
        rows = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(rows), 120)
        self.assertEqual(len({r["id"] for r in rows}), len(rows))
        for r in rows:
            self.assertEqual(set(r), {"id", "text", "labels"})
            self.assertTrue(set(r["labels"]) <= set(MOVES))
            self.assertEqual(r["labels"], sorted(set(r["labels"])))
            self.assertNotIn("\n", r["text"])
        for k in MOVES:
            self.assertGreaterEqual(sum(k in r["labels"] for r in rows), 10, k)
        self.assertGreaterEqual(sum(not r["labels"] for r in rows), 20)

    def test_module_does_not_read_the_fixture(self):
        src = _P.read_text(encoding="utf-8")
        self.assertNotIn("fixtures", src)
        self.assertNotIn("open(", src)
        self.assertNotIn("import json", src)

    def test_validity_constants_match_recomputation(self):
        n, metrics = _agreement()
        v = run(D("a"))["validity"]
        self.assertEqual(v["fixture_sentences"], n)
        self.assertEqual(v["per_move"], metrics)
        self.assertEqual(v["metric_name"], "labeled-fixture agreement metrics")
        self.assertEqual(v["labels"], "synthetic, builder-written")
        for k in MOVES:
            self.assertEqual(set(v["per_move"][k]), {"tp", "fp", "fn", "precision", "recall"})

    def test_contract_lists_the_same_numbers(self):
        text = CONTRACT.read_text(encoding="utf-8")
        _, metrics = _agreement()
        for k, mm in metrics.items():
            self.assertIn("| %s | %d | %d | %d | %s | %s |" % (k, mm["tp"], mm["fp"], mm["fn"], mm["precision"], mm["recall"]), text)

class AliasRepairPins(unittest.TestCase):
    def _run(self):
        return m.run({"docs": [D("Because of this, so what. If we invert it.")]})

    def test_per_move_is_not_module_global(self):
        pm = self._run()["validity"]["per_move"]
        self.assertIsNot(pm, m.FIXTURE_AGREEMENT)
        for k in pm:
            self.assertIsNot(pm[k], m.FIXTURE_AGREEMENT[k])
        self.assertEqual(pm, m.FIXTURE_AGREEMENT)

    def test_mutating_output_does_not_leak_into_next_run(self):
        snap = json.loads(json.dumps(m.FIXTURE_AGREEMENT))
        r1 = self._run()
        r1["validity"]["per_move"]["analogy"]["tp"] = -99
        r1["validity"]["per_move"]["new"] = {}
        self.assertEqual(m.FIXTURE_AGREEMENT, snap)
        self.assertEqual(self._run()["validity"]["per_move"], snap)

    def test_two_runs_do_not_share_per_move(self):
        a = self._run()["validity"]["per_move"]
        b = self._run()["validity"]["per_move"]
        self.assertIsNot(a, b)
        self.assertIsNot(a["analogy"], b["analogy"])

_ABSENT = object()


class TStartPresencePins(unittest.TestCase):
    TEXT = "It is like a loop. A story begins."

    def _rows(self, a, b):
        t = [{"speaker": "Ann", "text": "It is like a loop. "}, {"speaker": "Bo", "text": "A story begins."}]
        for row, ts in zip(t, (a, b)):
            if ts is not _ABSENT:
                row["t_start"] = ts
        return one(self.TEXT, turns=t)["turns"]

    def test_supplied_value_is_retained_as_is(self):
        rows = self._rows(1.5, 7)
        self.assertEqual(rows[0]["t_start"], 1.5)
        self.assertEqual(rows[1]["t_start"], 7)
        self.assertIs(type(rows[0]["t_start"]), float)
        self.assertIs(type(rows[1]["t_start"]), int)

    def test_zero_is_present_not_dropped(self):
        rows = self._rows(0, 0.0)
        self.assertIn("t_start", rows[0])
        self.assertIn("t_start", rows[1])
        self.assertEqual(rows[0]["t_start"], 0)
        self.assertEqual(rows[1]["t_start"], 0.0)

    def test_absent_or_none_leaves_no_key(self):
        rows = self._rows(_ABSENT, None)
        self.assertNotIn("t_start", rows[0])
        self.assertNotIn("t_start", rows[1])
        self.assertEqual(set(rows[0]), {"speaker", "moves"})

    def test_presence_is_per_turn(self):
        rows = self._rows(_ABSENT, 3)
        self.assertNotIn("t_start", rows[0])
        self.assertEqual(rows[1]["t_start"], 3)


if __name__ == "__main__":
    unittest.main()
