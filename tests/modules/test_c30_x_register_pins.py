"""c30.x_register pins: golden outputs, cap N/N+1, int bounds, exact refusal codes, guard-first, record shape.
Hermetic, stdlib only. Golden outputs are characterization pins of the code as run (reviewed by hand against the
documented formulas); they are not an independent oracle."""
import copy
import importlib.util
import pathlib
import sys

import pytest

_BACKEND = pathlib.Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
from app.modules.c30 import policy  # canonical

_spec = importlib.util.spec_from_file_location(
    "c30_x_register_pins_under_test", _BACKEND / "app/modules/m20_general_cognitive_worker/c30/x_register.py")
x = importlib.util.module_from_spec(_spec)
sys.modules["c30_x_register_pins_under_test"] = x
_spec.loader.exec_module(x)

A = "2026-10-11"


def P(**kw):
    d = {"as_of": A}
    d.update(kw)
    return d


class ListSub(list):
    """A list subclass: the register accepts exact built-in containers only."""


class DictSub(dict):
    """A dict subclass: refused wherever a payload or mapping is read."""


class StrSub(str):
    """A str subclass: refused as a record key even when equal to an allowed name."""


def call(fn, payload):
    return getattr(x, fn)(payload)


def msg(fn, payload):
    with pytest.raises(ValueError) as e:
        call(fn, payload)
    return str(e.value)


def setp(payload, path, value):
    d = copy.deepcopy(payload)
    cur = d
    for k in path[:-1]:
        cur = cur[k]
    cur[path[-1]] = value
    return d


def delp(payload, path):
    d = copy.deepcopy(payload)
    cur = d
    for k in path[:-1]:
        cur = cur[k]
    del cur[path[-1]]
    return d


BASES = {
    "x01_coverage_ledger": P(shards=[{"shard_id": "s", "source": "a", "records": 1, "checkpoint": "c"}]),
    "x02_corpus_analyzer": P(posts=[{"id": "p", "author": "a", "text": "hello world"}]),
    "x03_drafts_only_content": P(theme="alpha", sources=["beta gamma", "delta beta"]),
    "x04_paper_backtester": P(closes=[10.0, 11.0, 12.0], trades=[{"index": 0, "side": "buy", "qty": 1}], predictions=[{"p": 0.5, "outcome": 1}]),
    "x05_approval_queue": P(drafts=[{"id": "d", "recipient": "r", "text": "t"}], approvals=[{"draft_id": "d", "recipient": "r", "exact_text": "t"}]),
    "x06_prefill_tracker": P(profile={"k": "v"}, opportunities=[{"id": "o", "deadline": "2026-01-01", "eligibility": ["e"], "fee": 0}]),
    "x07_public_record_watcher": P(items=[{"id": "i", "source": "sec", "title": "t", "url": "u"}]),
    "x08_capability_ceiling": P(scores=[{"task": "t", "score": 1, "max_score": 2}]),
    "x09_niche_scorer": P(niches=[{"id": "n", "demand": 1, "competition": 0, "setup_cost": 0}]),
    "x10_preproduction": P(kind="game", title="t", themes=["a"]),
    "x11_ev_ranker": P(opportunities=[{"id": "o", "expected_return": 10, "cost": 1, "probability": 0.5}]),
    "x12_world_sim": P(seed=1, agents=["a"], steps=2),
    "x13_style_lenses": P(idea="alpha beta"),
    "x14_claim_packet": P(unit_id="u", excerpt="e", code_summary="c", tests="t", responses=[{"validator": "claude", "text": "t"}]),
    "x15_shard_planner": P(items=10, shard_size=3),
    "x16_export_analyzer": P(export_kind="pasted", records=[{"id": "i", "kind": "like", "text": "hello there"}]),
    "x17_masterplan_assembler": P(sections=[{"id": "s", "source_ref": "r", "content": "c"}]),
    "x18_scan_to_approval": P(items=[{"id": "i", "text": "hello there"}]),
    "x19_builder_scheduler": P(jobs=10, concurrency_cap=4),
    "x20_measured_deltas": P(axes={"a": {"before": 1, "after": 2}}),
    "x21_concept_registry": P(concepts=[{"name": "n", "test_passed": True}]),
    "x22_prefill_complete": P(application_id="a", fields={"k": "v"}, profile={}),
    "x23_source_legality": P(sites=[{"url": "u", "free_public": True, "tos_checked": True, "license": "l"}]),
    "x24_open_book_collections": P(add=[{"name": "n", "url": "u", "public_domain": True}]),
    "x25_patent_claim_drafter": P(title="t", features=["f"], prior_art_refs=["r"]),
    "x26_hustle_templates": P(paths=["p"]),
    "x27_science_criteria_checker": P(projects=[{"id": "i", "datasets": 120, "tools": 40, "outcome_claims": []}]),
    "x28_release_gate": P(rows=[{"id": "i", "status": "OPEN"}], user_acknowledged_substitutes=False),
    "x29_benchmark_board": P(benchmarks=[{"name": "n", "ours": 2, "baseline": 1}]),
    "x30_install_gate": P(installs=[{"tool": "t", "approved": True}]),
}

# (fn, path, name, limit, refusal when a value of exactly `limit` chars is not itself acceptable (enumerations), else None)
TEXTS = [
 ("x01_coverage_ledger", ("shards", 0, "shard_id"), "shard_id", 64, None),
 ("x01_coverage_ledger", ("shards", 0, "source"), "source", 128, None),
 ("x01_coverage_ledger", ("shards", 0, "checkpoint"), "checkpoint", 128, None),
 ("x02_corpus_analyzer", ("posts", 0, "id"), "id", 64, None),
 ("x02_corpus_analyzer", ("posts", 0, "author"), "author", 128, None),
 ("x02_corpus_analyzer", ("posts", 0, "text"), "text", 2000, None),
 ("x03_drafts_only_content", ("theme",), "theme", 256, None),
 ("x03_drafts_only_content", ("sources", 0), "source", 2000, None),
 ("x04_paper_backtester", ("trades", 0, "side"), "side", 8, "XREG_REFUSED_BAD_TYPE:side"),
 ("x05_approval_queue", ("approvals", 0, "draft_id"), "draft_id", 64, None),
 ("x05_approval_queue", ("approvals", 0, "recipient"), "recipient", 256, None),
 ("x05_approval_queue", ("approvals", 0, "exact_text"), "exact_text", 4000, None),
 ("x05_approval_queue", ("drafts", 0, "id"), "id", 64, None),
 ("x05_approval_queue", ("drafts", 0, "recipient"), "recipient", 256, None),
 ("x05_approval_queue", ("drafts", 0, "text"), "text", 4000, None),
 ("x06_prefill_tracker", ("profile", "k"), "profile_value", 256, None),
 ("x06_prefill_tracker", ("opportunities", 0, "id"), "id", 64, None),
 ("x06_prefill_tracker", ("opportunities", 0, "deadline"), "deadline", 32, None),
 ("x06_prefill_tracker", ("opportunities", 0, "eligibility", 0), "eligibility", 128, None),
 ("x07_public_record_watcher", ("items", 0, "id"), "id", 64, None),
 ("x07_public_record_watcher", ("items", 0, "source"), "source", 64, None),
 ("x07_public_record_watcher", ("items", 0, "title"), "title", 256, None),
 ("x07_public_record_watcher", ("items", 0, "url"), "url", 512, None),
 ("x08_capability_ceiling", ("scores", 0, "task"), "task", 128, None),
 ("x09_niche_scorer", ("niches", 0, "id"), "id", 64, None),
 ("x10_preproduction", ("kind",), "kind", 16, "XREG_REFUSED_BAD_TYPE:kind"),
 ("x10_preproduction", ("title",), "title", 128, None),
 ("x10_preproduction", ("themes", 0), "theme", 64, None),
 ("x11_ev_ranker", ("opportunities", 0, "id"), "id", 64, None),
 ("x12_world_sim", ("agents", 0), "agent", 64, None),
 ("x13_style_lenses", ("idea",), "idea", 2000, None),
 ("x14_claim_packet", ("unit_id",), "unit_id", 64, None),
 ("x14_claim_packet", ("excerpt",), "excerpt", 2000, None),
 ("x14_claim_packet", ("code_summary",), "code_summary", 2000, None),
 ("x14_claim_packet", ("tests",), "tests", 2000, None),
 ("x14_claim_packet", ("responses", 0, "validator"), "validator", 32, "XREG_REFUSED_BAD_TYPE:validator"),
 ("x14_claim_packet", ("responses", 0, "text"), "text", 8000, None),
 ("x16_export_analyzer", ("export_kind",), "export_kind", 16, "XREG_REFUSED_BAD_TYPE:export_kind"),
 ("x16_export_analyzer", ("records", 0, "id"), "id", 64, None),
 ("x16_export_analyzer", ("records", 0, "kind"), "kind", 16, "XREG_REFUSED_BAD_TYPE:record_kind"),
 ("x16_export_analyzer", ("records", 0, "text"), "text", 1000, None),
 ("x17_masterplan_assembler", ("sections", 0, "id"), "id", 64, None),
 ("x17_masterplan_assembler", ("sections", 0, "source_ref"), "source_ref", 256, None),
 ("x17_masterplan_assembler", ("sections", 0, "content"), "content", 20000, None),
 ("x18_scan_to_approval", ("items", 0, "id"), "id", 64, None),
 ("x18_scan_to_approval", ("items", 0, "text"), "text", 1000, None),
 ("x21_concept_registry", ("concepts", 0, "name"), "name", 128, None),
 ("x22_prefill_complete", ("application_id",), "application_id", 64, None),
 ("x23_source_legality", ("sites", 0, "url"), "url", 512, None),
 ("x23_source_legality", ("sites", 0, "license"), "license", 128, None),
 ("x24_open_book_collections", ("add", 0, "name"), "name", 128, None),
 ("x24_open_book_collections", ("add", 0, "url"), "url", 512, None),
 ("x25_patent_claim_drafter", ("title",), "title", 256, None),
 ("x25_patent_claim_drafter", ("features", 0), "feature", 256, None),
 ("x25_patent_claim_drafter", ("prior_art_refs", 0), "prior_art_ref", 256, None),
 ("x26_hustle_templates", ("paths", 0), "path", 64, None),
 ("x27_science_criteria_checker", ("projects", 0, "id"), "id", 64, None),
 ("x28_release_gate", ("rows", 0, "id"), "id", 64, None),
 ("x28_release_gate", ("rows", 0, "status"), "status", 32, "XREG_REFUSED_BAD_TYPE:status"),
 ("x29_benchmark_board", ("benchmarks", 0, "name"), "name", 128, None),
 ("x30_install_gate", ("installs", 0, "tool"), "tool", 128, None),
] + [(fn, ("as_of",), "as_of", 32, None) for fn in BASES]

# (fn, path, name, lo, hi)
INTS = [
 ("x01_coverage_ledger", ("shards", 0, "records"), "records", 0, 10**15),
 ("x04_paper_backtester", ("predictions", 0, "outcome"), "outcome", 0, 1),
 ("x06_prefill_tracker", ("opportunities", 0, "fee"), "fee", 0, 10**9),
 ("x12_world_sim", ("seed",), "seed", 0, 2**63 - 1),
 ("x12_world_sim", ("steps",), "steps", 0, 10000),
 ("x15_shard_planner", ("items",), "items", 0, 10**12),
 ("x15_shard_planner", ("shard_size",), "shard_size", 1, 1000000),
 ("x19_builder_scheduler", ("concurrency_cap",), "concurrency_cap", 1, 256),
 ("x27_science_criteria_checker", ("projects", 0, "datasets"), "datasets", 0, 10**9),
 ("x27_science_criteria_checker", ("projects", 0, "tools"), "tools", 0, 10**9),
]

# (fn, path, name, cap, kind) kind: list or dict
CAPS = [
 ("x01_coverage_ledger", ("shards",), "shards", 4096, "list"),
 ("x02_corpus_analyzer", ("posts",), "posts", 65536, "list"),
 ("x03_drafts_only_content", ("sources",), "sources", 256, "list"),
 ("x04_paper_backtester", ("trades",), "trades", 10000, "list"),
 ("x04_paper_backtester", ("predictions",), "predictions", 100000, "list"),
 ("x05_approval_queue", ("drafts",), "drafts", 256, "list"),
 ("x05_approval_queue", ("approvals",), "approvals", 256, "list"),
 ("x06_prefill_tracker", ("opportunities",), "opportunities", 512, "list"),
 ("x06_prefill_tracker", ("opportunities", 0, "eligibility"), "eligibility", 32, "list"),
 ("x06_prefill_tracker", ("profile",), "profile", 64, "dict"),
 ("x07_public_record_watcher", ("items",), "items", 4096, "list"),
 ("x08_capability_ceiling", ("scores",), "scores", 1024, "list"),
 ("x09_niche_scorer", ("niches",), "niches", 1024, "list"),
 ("x10_preproduction", ("themes",), "themes", 16, "list"),
 ("x11_ev_ranker", ("opportunities",), "opportunities", 1024, "list"),
 ("x12_world_sim", ("agents",), "agents", 64, "list"),
 ("x14_claim_packet", ("responses",), "responses", 8, "list"),
 ("x16_export_analyzer", ("records",), "records", 65536, "list"),
 ("x17_masterplan_assembler", ("sections",), "sections", 1024, "list"),
 ("x18_scan_to_approval", ("items",), "items", 4096, "list"),
 ("x20_measured_deltas", ("axes",), "axes", 64, "dict"),
 ("x21_concept_registry", ("concepts",), "concepts", 2048, "list"),
 ("x22_prefill_complete", ("fields",), "fields", 128, "dict"),
 ("x22_prefill_complete", ("profile",), "profile", 128, "dict"),
 ("x23_source_legality", ("sites",), "sites", 512, "list"),
 ("x24_open_book_collections", ("add",), "add", 256, "list"),
 ("x25_patent_claim_drafter", ("features",), "features", 16, "list"),
 ("x25_patent_claim_drafter", ("prior_art_refs",), "prior_art_refs", 64, "list"),
 ("x26_hustle_templates", ("paths",), "paths", 64, "list"),
 ("x27_science_criteria_checker", ("projects",), "projects", 256, "list"),
 ("x27_science_criteria_checker", ("projects", 0, "outcome_claims"), "outcome_claims", 16, "list"),
 ("x28_release_gate", ("rows",), "rows", 4096, "list"),
 ("x29_benchmark_board", ("benchmarks",), "benchmarks", 256, "list"),
 ("x30_install_gate", ("installs",), "installs", 256, "list"),
]

# (fn, path to the record, where)
RECS = [
 ("x01_coverage_ledger", ("shards", 0), "shard"), ("x02_corpus_analyzer", ("posts", 0), "post"),
 ("x04_paper_backtester", ("trades", 0), "trade"), ("x04_paper_backtester", ("predictions", 0), "prediction"),
 ("x05_approval_queue", ("approvals", 0), "approval"), ("x05_approval_queue", ("drafts", 0), "draft"),
 ("x06_prefill_tracker", ("opportunities", 0), "opportunity"), ("x07_public_record_watcher", ("items", 0), "item"),
 ("x08_capability_ceiling", ("scores", 0), "score"), ("x09_niche_scorer", ("niches", 0), "niche"),
 ("x11_ev_ranker", ("opportunities", 0), "opportunity"), ("x14_claim_packet", ("responses", 0), "response"),
 ("x16_export_analyzer", ("records", 0), "record"), ("x17_masterplan_assembler", ("sections", 0), "section"),
 ("x18_scan_to_approval", ("items", 0), "item"), ("x21_concept_registry", ("concepts", 0), "concept"),
 ("x23_source_legality", ("sites", 0), "site"), ("x24_open_book_collections", ("add", 0), "add"),
 ("x27_science_criteria_checker", ("projects", 0), "project"), ("x28_release_gate", ("rows", 0), "row"),
 ("x29_benchmark_board", ("benchmarks", 0), "benchmark"), ("x30_install_gate", ("installs", 0), "install"),
] + [(fn, (), "payload") for fn in BASES]


def at(payload, path):
    cur = payload
    for k in path:
        cur = cur[k]
    return cur


SCOPES = {'x01_coverage_ledger': {'as_of': '2026-10-11',
                         'data_source': 'supplied',
                         'implemented': ['measured coverage ledger over supplied shard records'],
                         'not_implemented': ['live crawling', 'fetching', 'corpus completeness']},
 'x02_corpus_analyzer': {'as_of': '2026-10-11',
                         'data_source': 'supplied',
                         'implemented': ['analysis of the supplied corpus only'],
                         'not_implemented': ['access to all posts ever', 'live platform reads']},
 'x03_drafts_only_content': {'as_of': '2026-10-11',
                             'data_source': 'supplied',
                             'implemented': ['one original draft for manual posting'],
                             'not_implemented': ['multi-account posting', 'autoposting', "repurposing others' posts"]},
 'x04_paper_backtester': {'as_of': '2026-10-11',
                          'data_source': 'supplied',
                          'implemented': ['backtest over supplied prices', 'calibration of supplied predictions'],
                          'not_implemented': ['broker connection', 'live trading', 'market prediction']},
 'x05_approval_queue': {'as_of': '2026-10-11',
                        'data_source': 'supplied',
                        'implemented': ['draft queue with exact-text approval matching'],
                        'not_implemented': ['sending', 'any release without an exact recipient+text match']},
 'x06_prefill_tracker': {'as_of': '2026-10-11',
                         'data_source': 'supplied',
                         'implemented': ['prefill packets', 'deadline ordering', 'fee-waiver flags'],
                         'not_implemented': ['submission', 'eligibility guarantees', 'winning']},
 'x07_public_record_watcher': {'as_of': '2026-10-11',
                               'data_source': 'supplied',
                               'implemented': ['filtering of supplied public-feed items'],
                               'not_implemented': ['classified or restricted material', 'live feed fetching']},
 'x08_capability_ceiling': {'as_of': '2026-10-11',
                            'data_source': 'supplied',
                            'implemented': ['arithmetic over supplied scores'],
                            'not_implemented': ['AGI', 'superintelligence', 'human mimicry']},
 'x09_niche_scorer': {'as_of': '2026-10-11',
                      'data_source': 'supplied',
                      'implemented': ['scoring of supplied niche numbers', 'a blueprint skeleton'],
                      'not_implemented': ['company registration', 'payments', 'coverage of all industries']},
 'x10_preproduction': {'as_of': '2026-10-11',
                       'data_source': 'supplied',
                       'implemented': ['pre-production structure for a supplied concept'],
                       'not_implemented': ['publishing', 'monetization', 'account creation']},
 'x11_ev_ranker': {'as_of': '2026-10-11',
                   'data_source': 'supplied',
                   'implemented': ['expected-value arithmetic on supplied numbers'],
                   'not_implemented': ['income guarantees', 'ruthless competitiveness claims']},
 'x12_world_sim': {'as_of': '2026-10-11',
                   'data_source': 'supplied',
                   'implemented': ['a seeded deterministic simulation with labeled agents'],
                   'not_implemented': ['real people', 'unlabeled synthetic humans']},
 'x13_style_lenses': {'as_of': '2026-10-11',
                      'data_source': 'supplied',
                      'implemented': ['divergent-thinking prompts per named lens'],
                      'not_implemented': ['diagnosis', 'replication of any condition', 'clinical claims']},
 'x14_claim_packet': {'as_of': '2026-10-11',
                      'data_source': 'supplied',
                      'implemented': ['packet assembly', 'verbatim response recording'],
                      'not_implemented': ['running validators', 'treating verdicts as approval']},
 'x15_shard_planner': {'as_of': '2026-10-11',
                       'data_source': 'supplied',
                       'implemented': ['shard arithmetic and resume tokens'],
                       'not_implemented': ['compute purchase', 'execution']},
 'x16_export_analyzer': {'as_of': '2026-10-11',
                         'data_source': 'supplied',
                         'implemented': ['analysis of her supplied export records'],
                         'not_implemented': ['live account access', 'third-party private data']},
 'x17_masterplan_assembler': {'as_of': '2026-10-11',
                              'data_source': 'supplied',
                              'implemented': ['assembly of supplied sections', 'a measured page estimate'],
                              'not_implemented': ['padding to a page target',
                                                  'unsourced content presented as sourced']},
 'x18_scan_to_approval': {'as_of': '2026-10-11',
                          'data_source': 'supplied',
                          'implemented': ['scan-to-draft pipeline over supplied items'],
                          'not_implemented': ['acting', 'outreach', 'applying']},
 'x19_builder_scheduler': {'as_of': '2026-10-11',
                           'data_source': 'supplied',
                           'implemented': ['queue scheduling arithmetic for up to 1000 jobs'],
                           'not_implemented': ['real concurrent builders', 'spend on compute']},
 'x20_measured_deltas': {'as_of': '2026-10-11',
                         'data_source': 'supplied',
                         'implemented': ['before/after arithmetic per supplied axis'],
                         'not_implemented': ['unitless multiplier claims']},
 'x21_concept_registry': {'as_of': '2026-10-11',
                          'data_source': 'supplied',
                          'implemented': ['a test-gated count of supplied concepts'],
                          'not_implemented': ['AGI', 'general intelligence claims']},
 'x22_prefill_complete': {'as_of': '2026-10-11',
                          'data_source': 'supplied',
                          'implemented': ['a complete prefilled packet'],
                          'not_implemented': ['submission', 'auto-filing']},
 'x23_source_legality': {'as_of': '2026-10-11',
                         'data_source': 'supplied',
                         'implemented': ['legality filtering of supplied site records'],
                         'not_implemented': ['fetching', 'paywalled or terms-restricted ingestion']},
 'x24_open_book_collections': {'as_of': '2026-10-11',
                               'data_source': 'supplied',
                               'implemented': ['registry of open/public-domain collections'],
                               'not_implemented': ['pirate sources', 'fetching']},
 'x25_patent_claim_drafter': {'as_of': '2026-10-11',
                              'data_source': 'supplied',
                              'implemented': ['claim skeleton drafting for her invention'],
                              'not_implemented': ['filing', 'legal advice', "patenting others' ideas"]},
 'x26_hustle_templates': {'as_of': '2026-10-11',
                          'data_source': 'supplied',
                          'implemented': ['template generation per supplied career path'],
                          'not_implemented': ['income guarantees', 'employment impersonation', 'unsupervised tests']},
 'x27_science_criteria_checker': {'as_of': '2026-10-11',
                                  'data_source': 'supplied',
                                  'implemented': ['numeric criteria checks on supplied manifests'],
                                  'not_implemented': ['guaranteeing discoveries', 'awards', 'benchmark wins']},
 'x28_release_gate': {'as_of': '2026-10-11',
                      'data_source': 'supplied',
                      'implemented': ['gate evaluation over supplied ledger rows'],
                      'not_implemented': ['sending the line', 'marking substitutes as done']},
 'x29_benchmark_board': {'as_of': '2026-10-11',
                         'data_source': 'supplied',
                         'implemented': ['deltas over supplied scores'],
                         'not_implemented': ['world-class adjectives', 'unmeasured claims']},
 'x30_install_gate': {'as_of': '2026-10-11',
                      'data_source': 'supplied',
                      'implemented': ['an approval-gated install plan'],
                      'not_implemented': ['installing', 'desktop changes without approval']}}

GOLD = [('x01_coverage_ledger',
  {'as_of': '2026-10-11',
   'shards': [{'checkpoint': 'c1', 'records': 5, 'shard_id': 's1', 'source': 'b'},
              {'checkpoint': 'c2', 'records': 0, 'shard_id': 's2', 'source': 'a'},
              {'checkpoint': 'c3', 'records': 7, 'shard_id': 's3', 'source': 'b'}]},
  {'claim': 'throughput_only', 'per_source': {'a': 0, 'b': 12}, 'resumable': True, 'shards': 3, 'total_records': 12}),
 ('x01_coverage_ledger',
  {'as_of': '2026-10-11', 'shards': []},
  {'claim': 'throughput_only', 'per_source': {}, 'resumable': True, 'shards': 0, 'total_records': 0}),
 ('x02_corpus_analyzer',
  {'as_of': '2026-10-11',
   'posts': [{'author': 'a',
              'id': 'p1',
              'text': 'zzz zzz w01 w02 w03 w04 w05 w06 w07 w08 w09 w10 w11 w12 w13 w14 w15 w16 w17 w18 w19 w20 w21 w22 '
                      'w23 w24 w25 ab #Tag #tag'},
             {'author': 'b', 'id': 'p2', 'text': 'abc #Other'},
             {'author': 'a', 'id': 'p3', 'text': 'Zzz!'}]},
  {'corpus_size': 3,
   'distinct_authors': 2,
   'hashtags': ['other', 'tag'],
   'token_counts': {'abc': 1,
                    'other': 1,
                    'tag': 2,
                    'w01': 1,
                    'w02': 1,
                    'w03': 1,
                    'w04': 1,
                    'w05': 1,
                    'w06': 1,
                    'w07': 1,
                    'w08': 1,
                    'w09': 1,
                    'w10': 1,
                    'w11': 1,
                    'w12': 1,
                    'w13': 1,
                    'w14': 1,
                    'w15': 1,
                    'w16': 1,
                    'zzz': 3},
   'top_tokens': ['zzz',
                  'tag',
                  'abc',
                  'other',
                  'w01',
                  'w02',
                  'w03',
                  'w04',
                  'w05',
                  'w06',
                  'w07',
                  'w08',
                  'w09',
                  'w10',
                  'w11',
                  'w12',
                  'w13',
                  'w14',
                  'w15',
                  'w16']}),
 ('x02_corpus_analyzer',
  {'as_of': '2026-10-11', 'posts': []},
  {'corpus_size': 0, 'distinct_authors': 0, 'hashtags': [], 'token_counts': {}, 'top_tokens': []}),
 ('x03_drafts_only_content',
  {'as_of': '2026-10-11', 'sources': ['beta gamma', 'delta beta'], 'theme': 'alpha'},
  {'draft': 'Draft (alpha): beta, delta, gamma - an original take built from 2 supplied sources.',
   'originality_overlap': 0.5,
   'status': 'draft_only'}),
 ('x03_drafts_only_content',
  {'as_of': '2026-10-11', 'sources': ['aaa bbb ccc', 'ddd'], 'theme': 'ttt'},
  {'draft': 'Draft (ttt): aaa, bbb, ccc, ddd - an original take built from 2 supplied sources.',
   'originality_overlap': 0.6,
   'status': 'draft_only'}),
 ('x03_drafts_only_content',
  {'as_of': '2026-10-11', 'sources': ['cd'], 'theme': 'ab'},
  {'draft': 'Draft (ab): fresh angle - an original take built from 1 supplied sources.',
   'originality_overlap': 0.0,
   'status': 'draft_only'}),
 ('x04_paper_backtester',
  {'as_of': '2026-10-11',
   'closes': [10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
   'predictions': [{'outcome': 1, 'p': 0.5}, {'outcome': 0, 'p': 1}],
   'trades': [{'index': 0, 'qty': 2, 'side': 'buy'}, {'index': 2, 'qty': 1, 'side': 'sell'}]},
  {'brier': 0.625,
   'final_equity': 70.0,
   'not_financial_advice': True,
   'paper': True,
   'trades': 2,
   'walk_forward_checkpoints': [30.0, 50.0, 60.0]}),
 ('x04_paper_backtester',
  {'as_of': '2026-10-11', 'closes': [5.0], 'predictions': [], 'trades': []},
  {'brier': None,
   'final_equity': 0.0,
   'not_financial_advice': True,
   'paper': True,
   'trades': 0,
   'walk_forward_checkpoints': [5.0]}),
 ('x04_paper_backtester',
  {'as_of': '2026-10-11',
   'closes': [5.0, 6.0],
   'predictions': [{'outcome': 0, 'p': 0}, {'outcome': 1, 'p': 1}],
   'trades': [{'index': 1, 'qty': 1.5, 'side': 'buy'}]},
  {'brier': 0.0,
   'final_equity': 0.0,
   'not_financial_advice': True,
   'paper': True,
   'trades': 1,
   'walk_forward_checkpoints': [6.0]}),
 ('x05_approval_queue',
  {'approvals': [{'draft_id': 'd1', 'exact_text': 't1', 'recipient': 'r1'},
                 {'draft_id': 'd2', 'exact_text': 't2', 'recipient': 'OTHER'},
                 {'draft_id': 'd4', 'exact_text': 't4x', 'recipient': 'r4'},
                 {'draft_id': 'd9', 'exact_text': 't', 'recipient': 'r'}],
   'as_of': '2026-10-11',
   'drafts': [{'id': 'd1', 'recipient': 'r1', 'text': 't1'},
              {'id': 'd2', 'recipient': 'r2', 'text': 't2'},
              {'id': 'd3', 'recipient': 'r3', 'text': 't3'},
              {'id': 'd4', 'recipient': 'r4', 'text': 't4'}]},
  {'queue': [{'id': 'd1', 'recipient': 'r1', 'status': 'released'},
             {'id': 'd2', 'recipient': 'r2', 'status': 'pending'},
             {'id': 'd3', 'recipient': 'r3', 'status': 'pending'},
             {'id': 'd4', 'recipient': 'r4', 'status': 'pending'}],
   'rejected_approvals': ['d2', 'd4']}),
 ('x06_prefill_tracker',
  {'as_of': '2026-10-11',
   'opportunities': [{'deadline': '2026-02-01', 'eligibility': ['e1', 'e2'], 'fee': 5, 'id': 'o2'},
                     {'deadline': '2026-02-01', 'eligibility': [], 'fee': 0, 'id': 'o1'},
                     {'deadline': '2026-03-01', 'eligibility': ['x'], 'fee': 1, 'id': 'o0'}],
   'profile': {'a': '1', 'b': '2'}},
  {'count': 3,
   'packets': [{'deadline': '2026-02-01',
                'eligibility': [],
                'fee': 0,
                'opportunity_id': 'o1',
                'prefilled': {'a': '1', 'b': '2'},
                'submit': 'user_only',
                'waiver_draft_needed': False},
               {'deadline': '2026-02-01',
                'eligibility': ['e1', 'e2'],
                'fee': 5,
                'opportunity_id': 'o2',
                'prefilled': {'a': '1', 'b': '2'},
                'submit': 'user_only',
                'waiver_draft_needed': True},
               {'deadline': '2026-03-01',
                'eligibility': ['x'],
                'fee': 1,
                'opportunity_id': 'o0',
                'prefilled': {'a': '1', 'b': '2'},
                'submit': 'user_only',
                'waiver_draft_needed': True}]}),
 ('x07_public_record_watcher',
  {'as_of': '2026-10-11',
   'items': [{'id': 'z', 'source': 'grants', 'title': 't', 'url': 'u'},
             {'id': 'a', 'source': 'foia', 'title': 't', 'url': 'u'},
             {'id': 'm', 'source': 'other', 'title': 't', 'url': 'u'},
             {'id': 'b', 'source': 'sec', 'title': 't', 'url': 'u'},
             {'id': 'c', 'source': 'patents', 'title': 't', 'url': 'u'},
             {'id': 'd', 'source': 'procurement', 'title': 't', 'url': 'u'},
             {'id': 'e', 'source': 'federal_register', 'title': 't', 'url': 'u'},
             {'id': 'f', 'source': 'secx', 'title': 't', 'url': 'u'}],
   'seek_restricted': False},
  {'digest': [{'id': 'a', 'source': 'foia', 'title': 't', 'url': 'u'},
              {'id': 'b', 'source': 'sec', 'title': 't', 'url': 'u'},
              {'id': 'c', 'source': 'patents', 'title': 't', 'url': 'u'},
              {'id': 'd', 'source': 'procurement', 'title': 't', 'url': 'u'},
              {'id': 'e', 'source': 'federal_register', 'title': 't', 'url': 'u'},
              {'id': 'z', 'source': 'grants', 'title': 't', 'url': 'u'}],
   'excluded_non_allowlisted': ['f', 'm']}),
 ('x08_capability_ceiling',
  {'as_of': '2026-10-11',
   'scores': [{'max_score': 4, 'score': 1, 'task': 't2'},
              {'max_score': 4, 'score': 3, 'task': 't1'},
              {'max_score': 5, 'score': 0, 'task': 't0'}]},
  {'ceiling_ratio': 0.75,
   'claims': 'measured_only',
   'mean_ratio': 0.333333,
   'measured': [{'ratio': 0.0, 'task': 't0'}, {'ratio': 0.75, 'task': 't1'}, {'ratio': 0.25, 'task': 't2'}]}),
 ('x08_capability_ceiling',
  {'as_of': '2026-10-11', 'scores': []},
  {'ceiling_ratio': 0.0, 'claims': 'measured_only', 'mean_ratio': 0.0, 'measured': []}),
 ('x09_niche_scorer',
  {'as_of': '2026-10-11',
   'niches': [{'competition': 1, 'demand': 3, 'id': 'n1', 'setup_cost': 0},
              {'competition': 0, 'demand': 3, 'id': 'n2', 'setup_cost': 0},
              {'competition': 0, 'demand': 3, 'id': 'n0', 'setup_cost': 1},
              {'competition': 0.5, 'demand': 1.5, 'id': 'n3', 'setup_cost': 0.5}]},
  {'blueprint_skeleton': {'funnel': ['draft'],
                          'kpis': [],
                          'offer': 'TBD',
                          'pricing': 'TBD',
                          'worker_roles': ['researcher', 'builder', 'auditor']},
   'ranking': [{'id': 'n2', 'score': 3.0},
               {'id': 'n0', 'score': 1.5},
               {'id': 'n1', 'score': 1.5},
               {'id': 'n3', 'score': 0.75}]}),
 ('x10_preproduction',
  {'as_of': '2026-10-11', 'kind': 'game', 'monetize': False, 'publish': False, 'themes': ['a', 'b'], 'title': 'T'},
  {'artifacts': {'design_doc': ['premise', 'mechanics', 'levels', 'art_direction'],
                 'lua_scripts': [],
                 'project_files': ['default.project.json']},
   'status': 'preproduction_only',
   'themes': ['a', 'b'],
   'title': 'T'}),
 ('x10_preproduction',
  {'as_of': '2026-10-11', 'kind': 'anime', 'themes': [], 'title': 'T'},
  {'artifacts': {'bible': ['premise', 'characters', 'world'], 'scripts': [], 'shot_lists': [], 'storyboards': []},
   'status': 'preproduction_only',
   'themes': [],
   'title': 'T'}),
 ('x11_ev_ranker',
  {'as_of': '2026-10-11',
   'opportunities': [{'cost': 10, 'expected_return': 100, 'id': 'o1', 'probability': 0.5},
                     {'cost': 0, 'expected_return': 20, 'id': 'o2', 'probability': 1},
                     {'cost': 0, 'expected_return': 20, 'id': 'o0', 'probability': 1},
                     {'cost': 9, 'expected_return': 5, 'id': 'o3', 'probability': 0}]},
  {'guarantee_language': False,
   'ranking': [{'expected_value': 40.0, 'id': 'o1'},
               {'expected_value': 20, 'id': 'o0'},
               {'expected_value': 20, 'id': 'o2'},
               {'expected_value': -9, 'id': 'o3'}]}),
 ('x12_world_sim',
  {'agents': ['a', 'b', 'c'], 'as_of': '2026-10-11', 'seed': 7, 'steps': 6},
  {'agents': [{'name': 'a', 'synthetic': True}, {'name': 'b', 'synthetic': True}, {'name': 'c', 'synthetic': True}],
   'events': ['step 0: b builds',
              'step 1: b explores',
              'step 2: a observes',
              'step 3: c observes',
              'step 4: b socializes',
              'step 5: a socializes'],
   'seed': 7}),
 ('x12_world_sim',
  {'agents': [], 'as_of': '2026-10-11', 'seed': 0, 'steps': 3},
  {'agents': [], 'events': [], 'seed': 0}),
 ('x12_world_sim',
  {'agents': ['a'], 'as_of': '2026-10-11', 'seed': 9223372036854775807, 'steps': 0},
  {'agents': [{'name': 'a', 'synthetic': True}], 'events': [], 'seed': 9223372036854775807}),
 ('x13_style_lenses',
  {'as_of': '2026-10-11', 'idea': 'alpha beta alpha gamma delta'},
  {'disclaimer': 'Cognitive-style lenses are divergent-thinking strategies. They are not diagnosis, not a replication '
                 'of any condition, and make no clinical claim.',
   'lenses': {'analogical-transfer': 'analogical-transfer lens on alpha, beta, delta: angle 5 reframes alpha, beta, '
                                     'delta as analogical transfer.',
              'combinatorial': 'combinatorial lens on alpha, beta, delta: angle 6 reframes alpha, beta, delta as '
                               'combinatorial.',
              'hyperfocus': 'hyperfocus lens on alpha, beta, delta: angle 1 reframes alpha, beta, delta as hyperfocus.',
              'melancholic-depth': 'melancholic-depth lens on alpha, beta, delta: angle 4 reframes alpha, beta, delta '
                                   'as melancholic depth.',
              'pattern-first': 'pattern-first lens on alpha, beta, delta: angle 2 reframes alpha, beta, delta as '
                               'pattern first.',
              'systemizing': 'systemizing lens on alpha, beta, delta: angle 3 reframes alpha, beta, delta as '
                             'systemizing.'}}),
 ('x13_style_lenses',
  {'as_of': '2026-10-11', 'idea': 'ab'},
  {'disclaimer': 'Cognitive-style lenses are divergent-thinking strategies. They are not diagnosis, not a replication '
                 'of any condition, and make no clinical claim.',
   'lenses': {'analogical-transfer': 'analogical-transfer lens on the idea: angle 5 reframes the idea as analogical '
                                     'transfer.',
              'combinatorial': 'combinatorial lens on the idea: angle 6 reframes the idea as combinatorial.',
              'hyperfocus': 'hyperfocus lens on the idea: angle 1 reframes the idea as hyperfocus.',
              'melancholic-depth': 'melancholic-depth lens on the idea: angle 4 reframes the idea as melancholic '
                                   'depth.',
              'pattern-first': 'pattern-first lens on the idea: angle 2 reframes the idea as pattern first.',
              'systemizing': 'systemizing lens on the idea: angle 3 reframes the idea as systemizing.'}}),
 ('x14_claim_packet',
  {'as_of': '2026-10-11',
   'code_summary': 'cs',
   'excerpt': 'ex',
   'responses': [{'text': 'r1', 'validator': 'chatgpt'},
                 {'text': 'r2', 'validator': 'deepseek'},
                 {'text': 'r3', 'validator': 'claude'},
                 {'text': 'r4', 'validator': 'perplexity'}],
   'tests': 'tt',
   'unit_id': 'u1'},
  {'packet': {'code_summary': 'cs',
              'excerpt': 'ex',
              'question': 'does this code implement the excerpt; list gaps',
              'tests': 'tt',
              'unit': 'u1'},
   'responses': [{'text': 'r1', 'validator': 'chatgpt'},
                 {'text': 'r2', 'validator': 'deepseek'},
                 {'text': 'r3', 'validator': 'claude'},
                 {'text': 'r4', 'validator': 'perplexity'}],
   'verdict_semantics': 'evidence_not_approval'}),
 ('x15_shard_planner',
  {'as_of': '2026-10-11', 'items': 10, 'shard_size': 3},
  {'compute_agnostic': True,
   'plan_truncated': True,
   'resume_tokens_preview': ['shard-0-of-4', 'shard-1-of-4', 'shard-2-of-4'],
   'shard_count': 4,
   'shard_size': 3}),
 ('x15_shard_planner',
  {'as_of': '2026-10-11', 'items': 9, 'shard_size': 3},
  {'compute_agnostic': True,
   'plan_truncated': False,
   'resume_tokens_preview': ['shard-0-of-3', 'shard-1-of-3', 'shard-2-of-3'],
   'shard_count': 3,
   'shard_size': 3}),
 ('x15_shard_planner',
  {'as_of': '2026-10-11', 'items': 0, 'shard_size': 5},
  {'compute_agnostic': True, 'plan_truncated': False, 'resume_tokens_preview': [], 'shard_count': 0, 'shard_size': 5}),
 ('x15_shard_planner',
  {'as_of': '2026-10-11', 'items': 2, 'shard_size': 1000000},
  {'compute_agnostic': True,
   'plan_truncated': False,
   'resume_tokens_preview': ['shard-0-of-1'],
   'shard_count': 1,
   'shard_size': 1000000}),
 ('x16_export_analyzer',
  {'as_of': '2026-10-11',
   'export_kind': 'instagram',
   'records': [{'id': '1', 'kind': 'like', 'text': 'river stone river'},
               {'id': '2', 'kind': 'follow', 'text': 'stone'},
               {'id': '3', 'kind': 'like', 'text': 'garden w01 w02 w03 w04 w05 w06'}],
   'third_party_private': False},
  {'export_kind': 'instagram',
   'inspiration_briefs': ['inspiration brief: similar-but-better take on river',
                          'inspiration brief: similar-but-better take on stone',
                          'inspiration brief: similar-but-better take on garden',
                          'inspiration brief: similar-but-better take on w01',
                          'inspiration brief: similar-but-better take on w02'],
   'per_kind': {'follow': 1, 'like': 2},
   'records': 3,
   'themes': ['river', 'stone', 'garden', 'w01', 'w02']}),
 ('x17_masterplan_assembler',
  {'as_of': '2026-10-11',
   'sections': [{'content': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                 'id': 's1',
                 'source_ref': 'ref'},
                {'content': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
                 'id': 's2',
                 'source_ref': None}]},
  {'page_estimate': 3,
   'page_estimate_basis': 'chars_divided_by_3000',
   'sections': [{'chars': 6000, 'id': 's1', 'mark': 'sourced'}, {'chars': 3000, 'id': 's2', 'mark': 'UNSOURCED'}],
   'unsourced': ['s2']}),
 ('x17_masterplan_assembler',
  {'as_of': '2026-10-11',
   'sections': [{'content': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                 'id': 's1',
                 'source_ref': 'ref'},
                {'content': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
                 'id': 's2',
                 'source_ref': None}]},
  {'page_estimate': 2,
   'page_estimate_basis': 'chars_divided_by_3000',
   'sections': [{'chars': 5999, 'id': 's1', 'mark': 'sourced'}, {'chars': 3000, 'id': 's2', 'mark': 'UNSOURCED'}],
   'unsourced': ['s2']}),
 ('x17_masterplan_assembler',
  {'as_of': '2026-10-11', 'sections': []},
  {'page_estimate': 0, 'page_estimate_basis': 'chars_divided_by_3000', 'sections': [], 'unsourced': []}),
 ('x18_scan_to_approval',
  {'as_of': '2026-10-11', 'items': [{'id': 'i1', 'text': 'alpha alpha w01 w02 w03 w04 w05 w06 w07 w08 w09 w10 w11'}]},
  {'drafts': [{'id': 'draft-1', 'idea': 'idea: alpha', 'status': 'pending_approval'},
              {'id': 'draft-2', 'idea': 'idea: w01', 'status': 'pending_approval'},
              {'id': 'draft-3', 'idea': 'idea: w02', 'status': 'pending_approval'},
              {'id': 'draft-4', 'idea': 'idea: w03', 'status': 'pending_approval'},
              {'id': 'draft-5', 'idea': 'idea: w04', 'status': 'pending_approval'},
              {'id': 'draft-6', 'idea': 'idea: w05', 'status': 'pending_approval'},
              {'id': 'draft-7', 'idea': 'idea: w06', 'status': 'pending_approval'},
              {'id': 'draft-8', 'idea': 'idea: w07', 'status': 'pending_approval'},
              {'id': 'draft-9', 'idea': 'idea: w08', 'status': 'pending_approval'},
              {'id': 'draft-10', 'idea': 'idea: w09', 'status': 'pending_approval'}],
   'ideas': ['idea: alpha',
             'idea: w01',
             'idea: w02',
             'idea: w03',
             'idea: w04',
             'idea: w05',
             'idea: w06',
             'idea: w07',
             'idea: w08',
             'idea: w09'],
   'scanned': 1}),
 ('x19_builder_scheduler',
  {'as_of': '2026-10-11', 'concurrency_cap': 256, 'jobs': 1000},
  {'actual_concurrency': 256, 'concurrency_basis': 'configured_cap_not_measured_hardware', 'queued': 1000, 'waves': 4}),
 ('x19_builder_scheduler',
  {'as_of': '2026-10-11', 'concurrency_cap': 4, 'jobs': 10},
  {'actual_concurrency': 4, 'concurrency_basis': 'configured_cap_not_measured_hardware', 'queued': 10, 'waves': 3}),
 ('x19_builder_scheduler',
  {'as_of': '2026-10-11', 'concurrency_cap': 4, 'jobs': 3},
  {'actual_concurrency': 3, 'concurrency_basis': 'configured_cap_not_measured_hardware', 'queued': 3, 'waves': 1}),
 ('x19_builder_scheduler',
  {'as_of': '2026-10-11', 'concurrency_cap': 1, 'jobs': 0},
  {'actual_concurrency': 0, 'concurrency_basis': 'configured_cap_not_measured_hardware', 'queued': 0, 'waves': 0}),
 ('x20_measured_deltas',
  {'as_of': '2026-10-11',
   'axes': {'a': {'after': 2, 'before': -2}, 'b': {'after': 5, 'before': 0}, 'c': {'after': 1, 'before': 3}},
   'multiplier': 0},
  {'axes': {'a': {'delta': 4, 'pct': 2.0}, 'b': {'delta': 5, 'pct': None}, 'c': {'delta': -2, 'pct': -0.666667}}}),
 ('x21_concept_registry',
  {'as_of': '2026-10-11',
   'concepts': [{'name': 'z', 'test_passed': True},
                {'name': 'a', 'test_passed': True},
                {'name': 'm', 'test_passed': False}]},
  {'count_basis': 'test_gated', 'counted_concepts': ['a', 'z'], 'passing': 2, 'registered': 3}),
 ('x22_prefill_complete',
  {'application_id': 'app',
   'as_of': '2026-10-11',
   'fields': {'a': '1', 'b': '2', 'c': '5'},
   'profile': {'a': 'P', 'zz': 'unused'}},
  {'application_id': 'app', 'complete': True, 'prefilled': {'a': 'P', 'b': '2', 'c': '5'}, 'submit': 'user_only'}),
 ('x23_source_legality',
  {'as_of': '2026-10-11',
   'sites': [{'free_public': True, 'license': 'l3', 'tos_checked': True, 'url': 'u3'},
             {'free_public': True, 'license': 'l1', 'tos_checked': True, 'url': 'u1'},
             {'free_public': False, 'license': 'l', 'tos_checked': True, 'url': 'u4'},
             {'free_public': True, 'license': 'l', 'tos_checked': False, 'url': 'u5'},
             {'free_public': False, 'license': 'l', 'tos_checked': False, 'url': 'u6'}]},
  {'excluded': [{'reasons': ['not_free_public'], 'url': 'u4'},
                {'reasons': ['tos_unchecked'], 'url': 'u5'},
                {'reasons': ['not_free_public', 'tos_unchecked'], 'url': 'u6'}],
   'ingestible': [{'license': 'l1', 'url': 'u1'}, {'license': 'l3', 'url': 'u3'}],
   'ingestible_count': 2}),
 ('x24_open_book_collections',
  {'add': [{'name': 'Zed', 'public_domain': True, 'url': 'uz'}, {'name': 'Abe', 'public_domain': True, 'url': 'ua'}],
   'as_of': '2026-10-11',
   'pirate': False},
  {'added': [{'name': 'Abe', 'url': 'ua'}, {'name': 'Zed', 'url': 'uz'}],
   'collections': ['Project Gutenberg',
                   'Standard Ebooks',
                   'Open Library',
                   'Internet Archive public domain',
                   'HathiTrust public domain',
                   'Wikisource',
                   'Abe',
                   'Zed'],
   'seed_count': 6}),
 ('x25_patent_claim_drafter',
  {'as_of': '2026-10-11', 'features': ['f1', 'f2'], 'file': False, 'prior_art_refs': ['r1', 'r2'], 'title': 'T'},
  {'claims': ['1. A method for T, comprising: f1; f2.',
              '2. The method of claim 1, wherein f1.',
              '3. The method of claim 1, wherein f2.'],
   'prior_art_refs': ['r1', 'r2'],
   'status': 'draft_only',
   'title': 'T'}),
 ('x25_patent_claim_drafter',
  {'as_of': '2026-10-11', 'features': [], 'prior_art_refs': ['r1'], 'title': 'T'},
  {'claims': ['1. A method for T, comprising: TBD.'], 'prior_art_refs': ['r1'], 'status': 'draft_only', 'title': 'T'}),
 ('x26_hustle_templates',
  {'as_of': '2026-10-11', 'guarantee': False, 'impersonate': False, 'paths': ['b', 'a']},
  {'count': 2,
   'templates': [{'deliverable': 'draft deliverable for her review',
                  'path': 'a',
                  'result_log': [],
                  'test_plan': 'one small no-spend supervised test in her name'},
                 {'deliverable': 'draft deliverable for her review',
                  'path': 'b',
                  'result_log': [],
                  'test_plan': 'one small no-spend supervised test in her name'}]}),
 ('x27_science_criteria_checker',
  {'as_of': '2026-10-11',
   'projects': [{'datasets': 119, 'id': 'b', 'outcome_claims': ['x'], 'tools': 40},
                {'datasets': 120, 'id': 'a', 'outcome_claims': [], 'tools': 39},
                {'datasets': 120, 'id': 'c', 'outcome_claims': [], 'tools': 40},
                {'datasets': 0, 'id': 'd', 'outcome_claims': [], 'tools': 0}]},
  {'results': [{'datasets_ok': True, 'id': 'a', 'outcome_claims': 'none', 'tools_ok': False},
               {'datasets_ok': False, 'id': 'b', 'outcome_claims': 'not_checkable', 'tools_ok': True},
               {'datasets_ok': True, 'id': 'c', 'outcome_claims': 'none', 'tools_ok': True},
               {'datasets_ok': False, 'id': 'd', 'outcome_claims': 'none', 'tools_ok': False}],
   'thresholds': {'datasets': 120, 'tools': 40}}),
 ('x28_release_gate',
  {'as_of': '2026-10-11',
   'auto_send': False,
   'rows': [{'id': 'r1', 'status': 'IMPLEMENTED-BOUNDED'},
            {'id': 'r2', 'status': 'PARKED_BY_USER'},
            {'id': 'r3', 'status': 'STOPPED_BY_USER'},
            {'id': 'r4', 'status': 'SUPERSEDED'}],
   'user_acknowledged_substitutes': False},
  {'blockers': [], 'candy_line': 'withheld', 'release': 'ready', 'substitutes': []}),
 ('x28_release_gate',
  {'as_of': '2026-10-11',
   'rows': [{'id': 'r2', 'status': 'SUBSTITUTE'}, {'id': 'r1', 'status': 'SUBSTITUTE'}],
   'user_acknowledged_substitutes': False},
  {'blockers': [], 'candy_line': 'withheld', 'release': 'awaiting_user_acknowledgment', 'substitutes': ['r1', 'r2']}),
 ('x28_release_gate',
  {'as_of': '2026-10-11', 'rows': [{'id': 'r1', 'status': 'SUBSTITUTE'}], 'user_acknowledged_substitutes': True},
  {'blockers': [], 'candy_line': 'withheld', 'release': 'ready', 'substitutes': ['r1']}),
 ('x28_release_gate',
  {'as_of': '2026-10-11',
   'rows': [{'id': 'r2', 'status': 'OPEN'}, {'id': 'r1', 'status': 'OPEN'}, {'id': 'r3', 'status': 'SUBSTITUTE'}],
   'user_acknowledged_substitutes': True},
  {'blockers': ['r1', 'r2'], 'candy_line': 'withheld', 'release': 'blocked', 'substitutes': ['r3']}),
 ('x28_release_gate',
  {'as_of': '2026-10-11', 'rows': [], 'user_acknowledged_substitutes': False},
  {'blockers': [], 'candy_line': 'withheld', 'release': 'ready', 'substitutes': []}),
 ('x29_benchmark_board',
  {'as_of': '2026-10-11',
   'benchmarks': [{'baseline': 1.5, 'name': 'b', 'ours': 2},
                  {'baseline': 1, 'name': 'a', 'ours': 1},
                  {'baseline': 1, 'name': 'c', 'ours': 0.5}],
   'claim_unmeasured': False},
  {'board': [{'claimed': 'measured', 'delta': 0, 'name': 'a', 'win': False},
             {'claimed': 'measured', 'delta': 0.5, 'name': 'b', 'win': True},
             {'claimed': 'measured', 'delta': -0.5, 'name': 'c', 'win': False}],
   'wins': 1}),
 ('x30_install_gate',
  {'as_of': '2026-10-11', 'installs': [{'approved': True, 'tool': 'b'}, {'approved': True, 'tool': 'a'}]},
  {'executed': False, 'plan': [{'planned': True, 'tool': 'a'}, {'planned': True, 'tool': 'b'}]}),
 ('x02_corpus_analyzer',
  {'as_of': '2026-10-11',
   'posts': [{'author': 'a', 'id': 'p1', 'text': 'foo #t01 #t02 #t03 #t04 #t05 #t06 #t07 #t08 #t09 #t10'},
             {'author': 'b', 'id': 'p2', 'text': '#t11 #t12 #t13 #t14 #t15 #t16 #t17 #t18 #t19 #t20 #t21'}]},
  {'corpus_size': 2,
   'distinct_authors': 2,
   'hashtags': ['t01',
                't02',
                't03',
                't04',
                't05',
                't06',
                't07',
                't08',
                't09',
                't10',
                't11',
                't12',
                't13',
                't14',
                't15',
                't16',
                't17',
                't18',
                't19',
                't20'],
   'token_counts': {'foo': 1,
                    't01': 1,
                    't02': 1,
                    't03': 1,
                    't04': 1,
                    't05': 1,
                    't06': 1,
                    't07': 1,
                    't08': 1,
                    't09': 1,
                    't10': 1,
                    't11': 1,
                    't12': 1,
                    't13': 1,
                    't14': 1,
                    't15': 1,
                    't16': 1,
                    't17': 1,
                    't18': 1,
                    't19': 1},
   'top_tokens': ['foo',
                  't01',
                  't02',
                  't03',
                  't04',
                  't05',
                  't06',
                  't07',
                  't08',
                  't09',
                  't10',
                  't11',
                  't12',
                  't13',
                  't14',
                  't15',
                  't16',
                  't17',
                  't18',
                  't19']}),
 ('x03_drafts_only_content',
  {'as_of': '2026-10-11', 'sources': ['bbb', 'ccc'], 'theme': 'aaa'},
  {'draft': 'Draft (aaa): bbb, ccc - an original take built from 2 supplied sources.',
   'originality_overlap': 0.333333,
   'status': 'draft_only'}),
 ('x03_drafts_only_content',
  {'as_of': '2026-10-11', 'sources': ['bbb ccc ddd eee fff ggg hhh iii jjj'], 'theme': 'alpha'},
  {'draft': 'Draft (alpha): bbb, ccc, ddd, eee, fff - an original take built from 1 supplied sources.',
   'originality_overlap': 0.5,
   'status': 'draft_only'}),
 ('x04_paper_backtester',
  {'as_of': '2026-10-11',
   'closes': [1.0, 1.1234567],
   'predictions': [{'outcome': 0, 'p': 0.3333333}],
   'trades': [{'index': 0, 'qty': 1, 'side': 'buy'}]},
  {'brier': 0.111111,
   'final_equity': 0.123457,
   'not_financial_advice': True,
   'paper': True,
   'trades': 1,
   'walk_forward_checkpoints': [1.123457]}),
 ('x08_capability_ceiling',
  {'as_of': '2026-10-11', 'scores': [{'max_score': 3, 'score': 1, 'task': 't'}]},
  {'ceiling_ratio': 0.333333,
   'claims': 'measured_only',
   'mean_ratio': 0.333333,
   'measured': [{'ratio': 0.333333, 'task': 't'}]}),
 ('x08_capability_ceiling',
  {'as_of': '2026-10-11', 'scores': [{'max_score': 1, 'score': 1, 'task': 'u'}]},
  {'ceiling_ratio': 1.0, 'claims': 'measured_only', 'mean_ratio': 1.0, 'measured': [{'ratio': 1.0, 'task': 'u'}]}),
 ('x09_niche_scorer',
  {'as_of': '2026-10-11',
   'niches': [{'competition': 0, 'demand': 0, 'id': 'nz', 'setup_cost': 0},
              {'competition': 2, 'demand': 1, 'id': 'nt', 'setup_cost': 0}]},
  {'blueprint_skeleton': {'funnel': ['draft'],
                          'kpis': [],
                          'offer': 'TBD',
                          'pricing': 'TBD',
                          'worker_roles': ['researcher', 'builder', 'auditor']},
   'ranking': [{'id': 'nt', 'score': 0.333333}, {'id': 'nz', 'score': 0.0}]}),
 ('x11_ev_ranker',
  {'as_of': '2026-10-11', 'opportunities': [{'cost': 0, 'expected_return': 1, 'id': 'o', 'probability': 0.3333333}]},
  {'guarantee_language': False, 'ranking': [{'expected_value': 0.333333, 'id': 'o'}]}),
 ('x19_builder_scheduler',
  {'as_of': '2026-10-11', 'concurrency_cap': 4, 'jobs': 5},
  {'actual_concurrency': 4, 'concurrency_basis': 'configured_cap_not_measured_hardware', 'queued': 5, 'waves': 2}),
 ('x19_builder_scheduler',
  {'as_of': '2026-10-11', 'concurrency_cap': 4, 'jobs': 1},
  {'actual_concurrency': 1, 'concurrency_basis': 'configured_cap_not_measured_hardware', 'queued': 1, 'waves': 1}),
 ('x20_measured_deltas',
  {'as_of': '2026-10-11', 'axes': {'d': {'after': 1.1234567, 'before': 1}}},
  {'axes': {'d': {'delta': 0.123457, 'pct': 0.123457}}}),
 ('x29_benchmark_board',
  {'as_of': '2026-10-11', 'benchmarks': [{'baseline': 1, 'name': 'n', 'ours': 1.1234567}]},
  {'board': [{'claimed': 'measured', 'delta': 0.123457, 'name': 'n', 'win': True}], 'wins': 1})]


def _R(code):
    return "XREG_REFUSED_" + code


def _with(fn, **kw):
    d = copy.deepcopy(BASES[fn])
    d.update(kw)
    return d


FNS = sorted(BASES)


@pytest.mark.parametrize("fn", FNS)
def test_guard_runs_first_in_every_function(fn):
    assert msg(fn, dict(BASES[fn], spend=True)) == _R("SPEND")
    assert msg(fn, dict(BASES[fn], broker=1)) == _R("TRADE")


@pytest.mark.parametrize("fn", FNS)
def test_non_dict_payload_refused(fn):
    assert msg(fn, "nope") == _R("BAD_TYPE:payload")
    assert msg(fn, None) == _R("BAD_TYPE:payload")


@pytest.mark.parametrize("fn", FNS)
def test_base_payload_is_valid_and_scope_exact(fn):
    r = call(fn, BASES[fn])
    assert set(r["scope"]) == {"implemented", "not_implemented", "data_source", "as_of"}
    assert r["scope"]["data_source"] == "supplied" and r["scope"]["as_of"] == A
    assert r["scope"] == SCOPES[fn]


@pytest.mark.parametrize("fn,path,name,limit,at_limit_error", TEXTS)
def test_text_field_type_blank_and_length(fn, path, name, limit, at_limit_error):
    base = BASES[fn]
    assert msg(fn, setp(base, path, 5)) == _R("BAD_TYPE:" + name)
    assert msg(fn, setp(base, path, "")) == _R("EMPTY:" + name)
    assert msg(fn, setp(base, path, "x" * (limit + 1))) == _R("TEXT_TOO_LONG:" + name)
    at = setp(base, path, "x" * limit)
    if at_limit_error is None:
        call(fn, at)
    else:
        assert msg(fn, at) == at_limit_error


@pytest.mark.parametrize("fn,path,name,lo,hi", INTS)
def test_int_bounds_exact(fn, path, name, lo, hi):
    base = BASES[fn]
    for ok in (lo, hi):
        call(fn, setp(base, path, ok))
    for bad in (lo - 1, hi + 1, True, 1.0, "1"):
        assert msg(fn, setp(base, path, bad)) == _R("OUT_OF_RANGE:" + name)


PASS_ERR = {("x25_patent_claim_drafter", "prior_art_refs"): _R("PRIORART_MISSING:prior_art_search_record_required")}


def _filler(base, path, kind):
    """Real elements for a container at path: copies of its first element (or 0 / 1 when empty)."""
    cur = at(base, path)
    if kind == "list":
        return copy.deepcopy(cur[0]) if cur else 0
    return copy.deepcopy(next(iter(cur.values()))) if cur else 1


def _real(base, path, kind, n):
    """A real built-in list or dict of exactly n entries (no subclass, no faked __len__)."""
    one = _filler(base, path, kind)
    if kind == "list":
        return [copy.deepcopy(one) for _ in range(n)]
    return {"k%d" % i: copy.deepcopy(one) for i in range(n)}


def _oversize(fn, payload, name):
    try:
        call(fn, payload)
    except ValueError as e:
        return str(e) == _R("OVERSIZE:" + name)
    return False


@pytest.mark.parametrize("fn,path,name,cap,kind", CAPS)
def test_cap_n_passes_and_n_plus_1_refused(fn, path, name, cap, kind):
    base = BASES[fn]
    at_cap = setp(base, path, _real(base, path, kind, cap))
    assert type(at(at_cap, path)) is (list if kind == "list" else dict) and len(at(at_cap, path)) == cap
    # N: the cap itself never fires (the content may still be refused for other reasons, e.g. duplicates)
    assert not _oversize(fn, at_cap, name)
    over = setp(base, path, _real(base, path, kind, cap + 1))
    assert msg(fn, over) == _R("OVERSIZE:" + name)
    assert msg(fn, setp(base, path, "x")) == _R("OVERSIZE:" + name)


@pytest.mark.parametrize("fn,path,name,cap,kind", CAPS)
def test_container_subclass_refused_even_under_the_cap(fn, path, name, cap, kind):
    base = BASES[fn]
    sub = ListSub if kind == "list" else DictSub
    inner = copy.deepcopy(at(base, path))
    assert msg(fn, setp(base, path, sub(inner))) == _R("OVERSIZE:" + name)
    assert msg(fn, setp(base, path, sub())) == _R("OVERSIZE:" + name)


@pytest.mark.parametrize("fn", FNS)
def test_payload_subclass_refused(fn):
    assert msg(fn, DictSub(copy.deepcopy(BASES[fn]))) == _R("BAD_TYPE:payload")


@pytest.mark.parametrize("fn,path,where", RECS)
def test_nested_record_subclass_refused(fn, path, where):
    base = BASES[fn]
    if not path:  # the payload itself: pinned by test_payload_subclass_refused
        assert msg(fn, DictSub(copy.deepcopy(base))) == _R("BAD_TYPE:" + where)
        return
    assert msg(fn, setp(base, path, DictSub(copy.deepcopy(at(base, path))))) == _R("BAD_TYPE:" + where)


def test_x20_axis_pair_subclass_refused():
    f = "x20_measured_deltas"
    assert msg(f, P(axes={"a": DictSub(before=1, after=2)})) == _R("BAD_TYPE:axis_pair")


@pytest.mark.parametrize("fn", FNS)
def test_record_key_must_be_exact_str(fn):
    base = copy.deepcopy(BASES[fn])
    key = next(k for k in base if k != "as_of")
    forged = {(StrSub(k) if k == key else k): v for k, v in base.items()}
    assert any(type(k) is StrSub for k in forged)
    assert msg(fn, forged) == _R("BAD_TYPE:key")


@pytest.mark.parametrize("fn", FNS)
def test_record_key_count_capped_before_iteration(fn):
    class Boom(dict):
        def __iter__(self):
            raise AssertionError("iterated before the key-count cap")
    big = Boom({"k%d" % i: 1 for i in range(65)})
    big_plain = {"k%d" % i: 1 for i in range(65)}
    assert msg(fn, big_plain) == _R("OVERSIZE:payload")
    # exact-dict check comes first, so a dict subclass is refused as BAD_TYPE without being iterated
    assert msg(fn, big) == _R("BAD_TYPE:payload")


def test_x04_closes_cap_and_content():
    fn = "x04_paper_backtester"
    base = _with(fn, trades=[], predictions=[])
    call(fn, setp(base, ("closes",), [1.0] * 100000))
    assert msg(fn, setp(base, ("closes",), [1.0] * 100001)) == _R("OVERSIZE:closes")
    assert msg(fn, setp(base, ("closes",), "x")) == _R("OVERSIZE:closes")
    for bad in ([], [0.0], [-1.0, 2.0], [1.0, 0]):
        assert msg(fn, setp(base, ("closes",), bad)) == _R("OUT_OF_RANGE:closes")
    for bad in ([True], ["x"], [float("nan")], [float("inf")], [float("-inf")], [None]):
        assert msg(fn, setp(base, ("closes",), bad)) == _R("BAD_TYPE:closes")
    call(fn, setp(base, ("closes",), [0.5, 7]))


@pytest.mark.parametrize("fn,path,where", RECS)
def test_record_shape_strict(fn, path, where):
    base = BASES[fn]
    rec = at(base, path)
    for key in rec:
        assert msg(fn, delp(base, path + (key,))) == _R("EMPTY_FIELD:" + key)
    assert msg(fn, setp(base, path + ("zz",), 1)) == _R("UNKNOWN_FIELDS:" + where)
    if path:
        assert msg(fn, setp(base, path, "x")) == _R("BAD_TYPE:" + where)


# (fn, payload, refusal) -- each a distinct raise site or boundary of the register
def _sp():
    b = BASES
    out = []
    add = lambda fn, p, code: out.append((fn, p, _R(code)))
    add("x03_drafts_only_content", _with("x03_drafts_only_content", theme="ttt", sources=["aaa bbb ccc eee", "ddd"]), "COPY:near_duplicate_of_source")
    f = "x04_paper_backtester"
    add(f, _with(f, trades=[{"index": 3, "side": "buy", "qty": 1}]), "OUT_OF_RANGE:index")
    add(f, _with(f, trades=[{"index": -1, "side": "buy", "qty": 1}]), "OUT_OF_RANGE:index")
    add(f, _with(f, trades=[{"index": True, "side": "buy", "qty": 1}]), "OUT_OF_RANGE:index")
    add(f, _with(f, trades=[{"index": 1, "side": "buy", "qty": 1}, {"index": 1, "side": "sell", "qty": 1}]), "OUT_OF_RANGE:trade_order")
    add(f, _with(f, trades=[{"index": 1, "side": "buy", "qty": 1}, {"index": 0, "side": "sell", "qty": 1}]), "OUT_OF_RANGE:trade_order")
    add(f, _with(f, trades=[{"index": 0, "side": "hold", "qty": 1}]), "BAD_TYPE:side")
    for q in (0, -1, 0.0):
        add(f, _with(f, trades=[{"index": 0, "side": "buy", "qty": q}]), "OUT_OF_RANGE:qty")
    for q in (True, "1", float("nan")):
        add(f, _with(f, trades=[{"index": 0, "side": "buy", "qty": q}]), "BAD_TYPE:qty")
    for p in (-0.1, 1.1):
        add(f, _with(f, predictions=[{"p": p, "outcome": 0}]), "OUT_OF_RANGE:p")
    add(f, _with(f, predictions=[{"p": float("nan"), "outcome": 0}]), "BAD_TYPE:p")
    add(f, _with(f, predictions=[{"p": True, "outcome": 0}]), "BAD_TYPE:p")
    add("x05_approval_queue", _with("x05_approval_queue", drafts=[{"id": "d", "recipient": "r", "text": "t"}, {"id": "d", "recipient": "r2", "text": "t2"}]), "DUPLICATE:id")
    add("x07_public_record_watcher", _with("x07_public_record_watcher", seek_restricted=True), "CLASSIFIED:restricted_material_refused")
    add("x06_prefill_tracker", _with("x06_prefill_tracker", profile="x"), "OVERSIZE:profile")
    f = "x08_capability_ceiling"
    for s, m in ((3, 2), (-1, 2), (1, 0), (1, -1)):
        add(f, _with(f, scores=[{"task": "t", "score": s, "max_score": m}]), "OUT_OF_RANGE:score")
    add(f, _with(f, scores=[{"task": "t", "score": True, "max_score": 2}]), "BAD_TYPE:score")
    add(f, _with(f, scores=[{"task": "t", "score": 1, "max_score": "2"}]), "BAD_TYPE:max_score")
    f = "x08_capability_ceiling"
    add(f, _with(f, scores=[{"task": "t", "score": 0, "max_score": 0}]), "OUT_OF_RANGE:score")
    f = "x09_niche_scorer"
    for k in ("demand", "competition", "setup_cost"):
        n = {"id": "n", "demand": 1, "competition": 0, "setup_cost": 0}
        n[k] = -1
        add(f, _with(f, niches=[dict(n)]), "OUT_OF_RANGE:niche_numbers")
        n[k] = True
        add(f, _with(f, niches=[dict(n)]), "BAD_TYPE:" + k)
    f = "x10_preproduction"
    add(f, _with(f, publish=True), "PUBLISH:publishing_and_monetization_stay_hers")
    add(f, _with(f, monetize=True), "PUBLISH:publishing_and_monetization_stay_hers")
    add(f, _with(f, publish=True, kind="novel"), "PUBLISH:publishing_and_monetization_stay_hers")
    add(f, _with(f, kind="novel"), "BAD_TYPE:kind")
    f = "x11_ev_ranker"
    base_o = {"id": "o", "expected_return": 10, "cost": 1, "probability": 0.5}
    add(f, _with(f, opportunities=[dict(base_o, guaranteed=True)]), "GUARANTEE:income_cannot_be_guaranteed")
    for k, v in (("cost", -1), ("probability", 1.1), ("probability", -0.1)):
        add(f, _with(f, opportunities=[dict(base_o, **{k: v})]), "OUT_OF_RANGE:ev_numbers")
    add(f, _with(f, opportunities=[dict(base_o, expected_return="x")]), "BAD_TYPE:expected_return")
    add(f, _with(f, opportunities=[dict(base_o, cost="x")]), "BAD_TYPE:cost")
    add(f, _with(f, opportunities=[dict(base_o, probability="x")]), "BAD_TYPE:probability")
    f = "x12_world_sim"
    add(f, _with(f, deceptive_use=True), "DECEPTIVE:synthetic_people_must_stay_labeled")
    add(f, _with(f, deceptive_use=True, seed=-1), "DECEPTIVE:synthetic_people_must_stay_labeled")
    f = "x13_style_lenses"
    add(f, _with(f, clinical=True), "CLINICAL:no_diagnosis_or_condition_imitation")
    add(f, _with(f, diagnose=True), "CLINICAL:no_diagnosis_or_condition_imitation")
    add("x14_claim_packet", _with("x14_claim_packet", responses=[{"validator": "gemini", "text": "t"}]), "BAD_TYPE:validator")
    f = "x16_export_analyzer"
    add(f, _with(f, third_party_private=True), "THIRDPARTYPRIVATE:private_data_of_others_refused")
    add(f, _with(f, export_kind="tiktok"), "BAD_TYPE:export_kind")
    add(f, _with(f, records=[{"id": "i", "kind": "share", "text": "hello"}]), "BAD_TYPE:record_kind")
    f = "x17_masterplan_assembler"
    add(f, _with(f, sections=[{"id": "s", "source_ref": None, "content": "c"}, {"id": "s", "source_ref": None, "content": "d"}]), "DUPLICATE:id")
    add(f, _with(f, sections=[{"id": "s", "source_ref": "", "content": "c"}]), "EMPTY:source_ref")
    f = "x19_builder_scheduler"
    add(f, _with(f, jobs=1001), "OVERCAP:queue_capacity_is_1000")
    add(f, _with(f, jobs=10**6), "OVERCAP:queue_capacity_is_1000")
    add(f, _with(f, jobs=10**6 + 1), "OUT_OF_RANGE:jobs")
    add(f, _with(f, jobs=-1), "OUT_OF_RANGE:jobs")
    f = "x20_measured_deltas"
    add(f, _with(f, multiplier=True), "NOUNIT:multiplier_claims_have_no_unit")
    add(f, _with(f, multiplier=1000000, axes="x"), "NOUNIT:multiplier_claims_have_no_unit")
    add(f, _with(f, axes="x"), "OVERSIZE:axes")
    add(f, _with(f, axes={"a": "x"}), "BAD_TYPE:axis_pair")
    add(f, _with(f, axes={"a": {"before": 1}}), "BAD_TYPE:axis_pair")
    add(f, _with(f, axes={"a": {"before": 1, "after": 2, "zz": 3}}), "BAD_TYPE:axis_pair")
    add(f, _with(f, axes={"a": {"before": True, "after": 2}}), "BAD_TYPE:before")
    add(f, _with(f, axes={"a": {"before": 1, "after": "x"}}), "BAD_TYPE:after")
    add(f, _with(f, axes={"x" * 65: {"before": 1, "after": 2}}), "TEXT_TOO_LONG:axis")
    add(f, _with(f, axes={"": {"before": 1, "after": 2}}), "EMPTY:axis")
    f = "x21_concept_registry"
    add(f, _with(f, concepts=[{"name": "n", "test_passed": True}, {"name": "n", "test_passed": False}]), "DUPLICATE:name")
    add(f, _with(f, concepts=[{"name": "n", "test_passed": 1}]), "BAD_TYPE:test_passed")
    f = "x22_prefill_complete"
    add(f, _with(f, fields="x"), "OVERSIZE:fields")
    add(f, _with(f, profile="x"), "OVERSIZE:profile")
    add(f, _with(f, fields={"x" * 129: "v"}), "TEXT_TOO_LONG:field")
    add(f, _with(f, fields={"": "v"}), "EMPTY:field")
    add(f, _with(f, fields={"k": "x" * 257}), "TEXT_TOO_LONG:value")
    add(f, _with(f, fields={"k": ""}), "EMPTY:value")
    add(f, _with(f, fields={"k": "v"}, profile={"k": "y" * 257}), "TEXT_TOO_LONG:value")
    f = "x23_source_legality"
    s1 = {"url": "u", "free_public": True, "tos_checked": True, "license": "l"}
    add(f, _with(f, sites=[s1, dict(s1)]), "DUPLICATE:url")
    add(f, _with(f, sites=[dict(s1, free_public=1)]), "BAD_TYPE:free_public")
    add(f, _with(f, sites=[dict(s1, tos_checked="yes", license=5)]), "BAD_TYPE:tos_checked")
    f = "x24_open_book_collections"
    add(f, _with(f, pirate=True), "PIRACY:copyrighted_pirate_sources_refused")
    add(f, _with(f, add=[{"name": "n", "url": "u", "public_domain": False}]), "PIRACY:public_domain_only")
    add(f, _with(f, add=[{"name": "n", "url": "u", "public_domain": 1}]), "BAD_TYPE:public_domain")
    f = "x25_patent_claim_drafter"
    add(f, _with(f, file=True), "FILE:filing_is_hers")
    add(f, _with(f, prior_art_refs=[]), "PRIORART_MISSING:prior_art_search_record_required")
    f = "x26_hustle_templates"
    add(f, _with(f, guarantee=True), "GUARANTEE:income_cannot_be_guaranteed")
    add(f, _with(f, impersonate=True), "IMPERSONATE:no_employment_impersonation")
    add(f, _with(f, guarantee=True, impersonate=True), "GUARANTEE:income_cannot_be_guaranteed")
    f = "x28_release_gate"
    add(f, _with(f, auto_send=True), "CANDY_EARLY:line_is_never_auto_sent")
    add(f, _with(f, auto_send=True, rows="x"), "CANDY_EARLY:line_is_never_auto_sent")
    add(f, _with(f, rows=[{"id": "i", "status": "DONE"}]), "BAD_TYPE:status")
    add(f, _with(f, user_acknowledged_substitutes=1), "BAD_TYPE:user_acknowledged_substitutes")
    f = "x29_benchmark_board"
    add(f, _with(f, claim_unmeasured=True), "UNMEASURED:claims_require_measurement")
    add(f, _with(f, benchmarks=[{"name": "n", "ours": True, "baseline": 1}]), "BAD_TYPE:ours")
    add(f, _with(f, benchmarks=[{"name": "n", "ours": 1, "baseline": "x"}]), "BAD_TYPE:baseline")
    f = "x30_install_gate"
    add(f, _with(f, installs=[{"tool": "t", "approved": False}]), "UNAPPROVED_INSTALL:her_approval_required_per_install")
    add(f, _with(f, installs=[{"tool": "t", "approved": 1}]), "BAD_TYPE:approved")
    return out


SPECIAL = _sp()


@pytest.mark.parametrize("fn,payload,code", SPECIAL)
def test_register_level_refusals_exact(fn, payload, code):
    assert msg(fn, payload) == code


OK_FLAGS = [
    ("x07_public_record_watcher", {"seek_restricted": False}), ("x10_preproduction", {"publish": False, "monetize": False}),
    ("x12_world_sim", {"deceptive_use": False}), ("x13_style_lenses", {"clinical": False, "diagnose": False}),
    ("x16_export_analyzer", {"third_party_private": False}), ("x20_measured_deltas", {"multiplier": 0}),
    ("x24_open_book_collections", {"pirate": False}), ("x25_patent_claim_drafter", {"file": False}),
    ("x26_hustle_templates", {"guarantee": False, "impersonate": False}), ("x28_release_gate", {"auto_send": False}),
    ("x29_benchmark_board", {"claim_unmeasured": False}),
]


@pytest.mark.parametrize("fn,extra", OK_FLAGS)
def test_falsy_optional_flags_accepted(fn, extra):
    call(fn, _with(fn, **extra))


def test_x11_guaranteed_false_accepted_and_x04_boundaries_ok():
    f = "x11_ev_ranker"
    o = {"id": "o", "expected_return": 10, "cost": 0, "probability": 0}
    call(f, _with(f, opportunities=[dict(o, guaranteed=False)]))
    call(f, _with(f, opportunities=[dict(o, probability=1)]))
    g = "x04_paper_backtester"
    call(g, _with(g, predictions=[{"p": 0, "outcome": 0}, {"p": 1, "outcome": 1}]))


@pytest.mark.parametrize("fn,payload,expected", GOLD)
def test_golden_output(fn, payload, expected):
    r = dict(call(fn, copy.deepcopy(payload)))
    r.pop("scope")
    assert r == expected


def test_x08_full_score_ratio_one():
    f = "x08_capability_ceiling"
    r = call(f, _with(f, scores=[{"task": "t", "score": 2, "max_score": 2}]))
    assert r["measured"] == [{"task": "t", "ratio": 1.0}] and r["mean_ratio"] == 1.0 and r["ceiling_ratio"] == 1.0


def test_policy_pins_against_canonical():
    assert len(x.FORBIDDEN_KEYS) == 13 and x.PREFIX == "XREG"
    assert set(x.FORBIDDEN_KEYS.values()) == set(policy.RULES)
    for key, rule in x.FORBIDDEN_KEYS.items():
        assert msg("x01_coverage_ledger", P(shards=[], **{key: True})) == "XREG_REFUSED_" + policy.RULES[rule]
        assert msg("x01_coverage_ledger", P(shards=[], **{key: 0})) == _R("UNKNOWN_FIELDS:payload")


def test_registry_and_constants():
    assert sorted(x.REGISTER) == sorted("X%d" % i for i in range(1, 31))
    assert [x.REGISTER["X%d" % i].__name__[:3] for i in range(1, 31)] == ["x%02d" % i for i in range(1, 31)]
    assert x.ALLOWED_FEEDS == ("foia", "procurement", "grants", "sec", "patents", "federal_register")
    assert x.LENSES == ("hyperfocus", "pattern-first", "systemizing", "melancholic-depth", "analogical-transfer", "combinatorial")
    assert x.VALIDATORS == ("chatgpt", "deepseek", "claude", "perplexity")
    assert x.EXPORT_KINDS == ("instagram", "linkedin", "pasted") and x.RECORD_KINDS == ("like", "comment", "follow")
    assert x.GATE_STATUSES == ("IMPLEMENTED-BOUNDED", "SUBSTITUTE", "PARKED_BY_USER", "STOPPED_BY_USER", "SUPERSEDED", "OPEN")
    assert x.SEED_COLLECTIONS[0] == "Project Gutenberg" and len(x.SEED_COLLECTIONS) == 6
    assert x.LENS_DISCLAIMER.startswith("Cognitive-style lenses") and x.LENS_DISCLAIMER.endswith("no clinical claim.")


@pytest.mark.parametrize("value", ["linkedin", "pasted", "instagram"])
def test_x16_all_export_kinds_accepted(value):
    call("x16_export_analyzer", _with("x16_export_analyzer", export_kind=value))


def test_x16_record_kinds_and_x28_statuses_all_accepted():
    f = "x16_export_analyzer"
    for k in ("like", "comment", "follow"):
        call(f, _with(f, records=[{"id": "i", "kind": k, "text": "hello"}]))
    g = "x28_release_gate"
    for s in x.GATE_STATUSES:
        call(g, _with(g, rows=[{"id": "i", "status": s}]))


def test_x12_all_six_actions_reachable_and_table_pinned():
    assert x._ACTIONS == ("observes", "builds", "trades", "rests", "socializes", "explores")
    r = call("x12_world_sim", _with("x12_world_sim", seed=1, agents=["a", "b", "c"], steps=300))
    assert len(r["events"]) == 300
    assert {e.split(" ", 3)[3] for e in r["events"]} == set(x._ACTIONS)


def test_x27_outcome_claim_text_rules():
    f = "x27_science_criteria_checker"
    base = _with(f, projects=[{"id": "i", "datasets": 1, "tools": 1, "outcome_claims": ["c"]}])
    path = ("projects", 0, "outcome_claims", 0)
    assert msg(f, setp(base, path, 5)) == _R("BAD_TYPE:outcome_claim")
    assert msg(f, setp(base, path, "")) == _R("EMPTY:outcome_claim")
    assert msg(f, setp(base, path, "x" * 257)) == _R("TEXT_TOO_LONG:outcome_claim")
    assert call(f, setp(base, path, "x" * 256))["results"][0]["outcome_claims"] == "not_checkable"


# --- exact-boundary pins closing the four survivors of the independent mutant run ---
def test_x19_waves_exact_when_jobs_is_a_multiple_of_cap():
    f = "x19_builder_scheduler"
    for jobs, cap, waves in ((10, 5, 2), (11, 5, 3), (5, 5, 1), (6, 5, 2), (0, 5, 0), (4, 4, 1), (8, 4, 2)):
        out = call(f, P(jobs=jobs, concurrency_cap=cap))
        assert out["waves"] == waves, (jobs, cap)
        assert out["queued"] == jobs and out["actual_concurrency"] == min(jobs, cap)


def test_x20_axis_name_64_accepted_65_refused():
    f = "x20_measured_deltas"
    pair = {"before": 1, "after": 2}
    out = call(f, P(axes={"a" * 64: pair}))
    assert list(out["axes"]) == ["a" * 64]
    assert msg(f, P(axes={"a" * 65: pair})) == "XREG_REFUSED_TEXT_TOO_LONG:axis"


def test_x22_field_key_128_accepted_129_refused():
    f = "x22_prefill_complete"
    base = dict(application_id="a", profile={})
    out = call(f, P(fields={"k" * 128: "v"}, **base))
    assert list(out["prefilled"]) == ["k" * 128]
    assert msg(f, P(fields={"k" * 129: "v"}, **base)) == "XREG_REFUSED_TEXT_TOO_LONG:field"


def test_x22_value_256_accepted_257_refused():
    f = "x22_prefill_complete"
    base = dict(application_id="a", profile={})
    out = call(f, P(fields={"k": "v" * 256}, **base))
    assert out["prefilled"] == {"k": "v" * 256}
    assert msg(f, P(fields={"k": "v" * 257}, **base)) == "XREG_REFUSED_TEXT_TOO_LONG:value"
    # the profile value overrides the field value and is capped the same way
    assert call(f, P(fields={"k": "v"}, application_id="a", profile={"k": "p" * 256}))["prefilled"] == {"k": "p" * 256}
    assert msg(f, P(fields={"k": "v"}, application_id="a", profile={"k": "p" * 257})) == "XREG_REFUSED_TEXT_TOO_LONG:value"


@pytest.mark.parametrize("fn", FNS)
def test_record_key_count_boundary_64_not_oversize(fn):
    sixty_four = {"k%d" % i: 1 for i in range(64)}
    assert msg(fn, sixty_four) != _R("OVERSIZE:payload")
    assert msg(fn, sixty_four).startswith("XREG_REFUSED_")


@pytest.mark.parametrize("fn", FNS)
def test_payload_subclass_is_refused_as_shape_even_when_it_names_a_forbidden_action(fn):
    # guard() reads exact dicts only; a subclass is refused as BAD_TYPE:payload and never reaches policy.check
    sub = DictSub(copy.deepcopy(BASES[fn]))
    sub["send"] = True
    assert msg(fn, sub) == _R("BAD_TYPE:payload")


# --- round 3: mapping keys must be exact str, refused before any str()/sorted() ---
def test_x20_axes_keys_must_be_exact_str():
    f = "x20_measured_deltas"
    ok = {"before": 1, "after": 2}
    assert msg(f, P(axes={1: ok})) == _R("BAD_TYPE:axis_key")
    # int key colliding with the str key of another axis used to be accepted and silently collapsed
    assert msg(f, P(axes={1: {"before": 1, "after": 2}, "1": {"before": 1, "after": 5}})) == _R("BAD_TYPE:axis_key")
    assert msg(f, P(axes={"1": {"before": 1, "after": 5}, 1: ok})) == _R("BAD_TYPE:axis_key")
    assert msg(f, P(axes={StrSub("a"): ok})) == _R("BAD_TYPE:axis_key")
    assert msg(f, P(axes={b"a": ok})) == _R("BAD_TYPE:axis_key")
    assert call(f, P(axes={"1": {"before": 1, "after": 5}}))["axes"] == {"1": {"delta": 4, "pct": 4.0}}


def test_x20_axis_pair_keys_must_be_exact_str():
    f = "x20_measured_deltas"
    assert msg(f, P(axes={"a": {StrSub("before"): 1, "after": 2}})) == _R("BAD_TYPE:axis_pair")
    assert msg(f, P(axes={"a": {"before": 1, StrSub("after"): 2}})) == _R("BAD_TYPE:axis_pair")
    assert call(f, P(axes={"a": {"before": 1, "after": 2}}))["axes"]["a"]["delta"] == 1


def test_x22_fields_keys_must_be_exact_str_and_never_raise_typeerror():
    f = "x22_prefill_complete"
    base = dict(application_id="a", profile={})
    for fields in ({1: "v"}, {1: "v", "1": "w"}, {"1": "w", 1: "v"}, {StrSub("k"): "v"}, {None: "v"}, {1: "v", "a": "w"}):
        assert msg(f, P(fields=fields, **base)) == _R("BAD_TYPE:field_key"), fields


def test_x22_profile_keys_must_be_exact_str():
    f = "x22_prefill_complete"
    for profile in ({1: "v"}, {StrSub("k"): "v"}, {"k": "v", 2: "w"}):
        assert msg(f, P(application_id="a", fields={"k": "v"}, profile=profile)) == _R("BAD_TYPE:profile_key"), profile


def test_x22_values_are_strict_str_not_coerced():
    f = "x22_prefill_complete"
    for bad in (5, 1.5, None, True, b"x", ["a"]):
        assert msg(f, P(application_id="a", fields={"k": bad}, profile={})) == _R("BAD_TYPE:value"), bad
        assert msg(f, P(application_id="a", fields={"k": "v"}, profile={"k": bad})) == _R("BAD_TYPE:value"), bad
    # str-subclass VALUES are screened by c30.policy.clean_text (strict type once the shared helper repair lands)
    # a profile value overrides the field value; a non-overridden field keeps its own
    out = call(f, P(application_id="a", fields={"a": "1", "b": "2"}, profile={"a": "9"}))
    assert out["prefilled"] == {"a": "9", "b": "2"}


def test_x06_profile_keys_must_be_exact_str():
    f = "x06_prefill_tracker"
    base = copy.deepcopy(BASES[f])
    for profile in ({1: "v"}, {1: "v", "1": "w"}, {StrSub("k"): "v"}):
        assert msg(f, setp(base, ("profile",), profile)) == _R("BAD_TYPE:profile_key"), profile


def test_x22_key_checks_run_in_declared_order_fields_then_profile():
    f = "x22_prefill_complete"
    assert msg(f, P(application_id="a", fields={1: "v"}, profile={2: "w"})) == _R("BAD_TYPE:field_key")
    assert msg(f, P(application_id="a", fields={"k": "v"}, profile={2: "w"})) == _R("BAD_TYPE:profile_key")
