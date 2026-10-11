"""c30.x_register - v2 X1-X30 cannot-as-stated register: bounded substitutes.

Each X row names an aspiration that cannot become code as stated; this module
implements the documented legal substitute for each, in bounded form. Pure
stdlib, deterministic, fully offline: every function validates a supplied
payload, computes over supplied data only, and returns a result carrying the
program honesty block (scope: implemented / not_implemented / data_source /
as_of). No coverage ("all", "every") is claimed that the input did not have;
counts are computed, never asserted. A payload that truthy-names a forbidden
action is refused by this module's guard(): it maps the 13 FORBIDDEN_KEYS to a
canonical rule name and calls app.modules.c30.policy.check(rule, "XREG"), which
raises a plain ValueError "XREG_REFUSED_<RULE>" (SPEND, OUTREACH, FAKEACCT,
AUTOPOST, SCRAPE, TRADE). Text fields go through the canonical
app.modules.c30.policy.clean_text with the same prefix (BAD_TYPE, EMPTY,
CONTROL_CHARS, TEXT_TOO_LONG). Register-level refusals use _err and are also
plain ValueError "XREG_REFUSED_<REASON>". There is no local policy module.
"""
from __future__ import annotations

import random

from app.modules.c30 import policy as _policy

PREFIX = "XREG"

# Supplied request fields that name a forbidden action -> canonical rule name (a key of
# app.modules.c30.policy.RULES). A test pins this table against the canonical RULES.
FORBIDDEN_KEYS = {
    "spend": "spend", "purchase": "spend", "buy_compute": "spend",
    "send": "outreach", "submit": "outreach", "outreach": "outreach",
    "multi_account": "fakeacct", "fake_accounts": "fakeacct",
    "post_now": "autopost", "autopost": "autopost",
    "scrape": "scrape",
    "broker": "trade", "live_trade": "trade",
}


MAX_RECORD_KEYS = 64  # no register record has more than a handful of fields; a larger dict is refused unread


def guard(payload) -> None:
    """Refuse (through the canonical check) when a payload truthy-names a forbidden action."""
    if type(payload) is not dict:
        return
    for key, rule in FORBIDDEN_KEYS.items():
        if payload.get(key):
            _policy.check(rule, PREFIX)


def _err(reason: str) -> ValueError:
    return ValueError("XREG_REFUSED_" + reason)


def _text(value, name, limit):
    return _policy.clean_text(value, PREFIX, name, limit)


def _opt_text(value, name, limit):
    if value is None:
        return None
    return _text(value, name, limit)


def _int(value, name, lo, hi):
    if type(value) is not int or value < lo or value > hi:
        raise _err("OUT_OF_RANGE:" + name)
    return value


def _num(value, name):
    if type(value) not in (int, float) or value != value or value in (float("inf"), float("-inf")):
        raise _err("BAD_TYPE:" + name)
    return value


def _bool(value, name):
    if type(value) is not bool:
        raise _err("BAD_TYPE:" + name)
    return value


def _record(payload, fields, where, optional=()):
    if type(payload) is not dict:
        raise _err("BAD_TYPE:" + where)
    if len(payload) > MAX_RECORD_KEYS:  # cap before any iteration
        raise _err("OVERSIZE:" + where)
    allowed = set(fields) | set(optional)
    for key in payload:
        if type(key) is not str:
            raise _err("BAD_TYPE:key")
        if key not in allowed:
            raise _err("UNKNOWN_FIELDS:" + where)
    for name in fields:
        if name not in payload:
            raise _err("EMPTY_FIELD:" + name)


def _str_keys(mapping, code):
    """Refuse the first key (in declared order) that is not an exact str, before any str() or sorted()."""
    for key in mapping:
        if type(key) is not str:
            raise _err("BAD_TYPE:" + code)


def _items(payload, name, cap):
    items = payload[name]
    if type(items) is not list or len(items) > cap:
        raise _err("OVERSIZE:" + name)
    return items


def _scope(as_of, implemented, not_implemented):
    return {"implemented": implemented, "not_implemented": not_implemented,
            "data_source": "supplied", "as_of": as_of}


def _as_of(payload):
    return _text(payload["as_of"], "as_of", 32)


def _tokens(text):
    out = {}
    for raw in text.lower().split():
        tok = "".join(ch for ch in raw if ch.isalnum())
        if len(tok) >= 3:
            out[tok] = out.get(tok, 0) + 1
    return out


def _top_tokens(texts, n):
    hist = {}
    for t in texts:
        for tok, c in _tokens(t).items():
            hist[tok] = hist.get(tok, 0) + c
    return sorted(hist.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


# X1: open-corpora ingestion -> measured coverage ledger over supplied shards.
def x01_coverage_ledger(payload):
    guard(payload)
    _record(payload, ("as_of", "shards"), "payload")
    as_of = _as_of(payload)
    shards = _items(payload, "shards", 4096)
    seen, per_source, total = set(), {}, 0
    for shard in shards:
        _record(shard, ("shard_id", "source", "records", "checkpoint"), "shard")
        sid = _text(shard["shard_id"], "shard_id", 64)
        if sid in seen:
            raise _err("DUPLICATE:shard_id")
        seen.add(sid)
        source = _text(shard["source"], "source", 128)
        records = _int(shard["records"], "records", 0, 10**15)
        _text(shard["checkpoint"], "checkpoint", 128)
        per_source[source] = per_source.get(source, 0) + records
        total += records
    return {"shards": len(shards), "total_records": total,
            "per_source": dict(sorted(per_source.items())), "resumable": True,
            "claim": "throughput_only",
            "scope": _scope(as_of, ["measured coverage ledger over supplied shard records"],
                            ["live crawling", "fetching", "corpus completeness"])}


# X2: all-posts-ever -> analyzer over a supplied public corpus.
def x02_corpus_analyzer(payload):
    guard(payload)
    _record(payload, ("as_of", "posts"), "payload")
    as_of = _as_of(payload)
    posts = _items(payload, "posts", 65536)
    authors, texts = set(), []
    for post in posts:
        _record(post, ("id", "author", "text"), "post")
        _text(post["id"], "id", 64)
        authors.add(_text(post["author"], "author", 128))
        texts.append(_text(post["text"], "text", 2000))
    top = _top_tokens(texts, 20)
    hashtags = sorted((t for t, _c in _top_tokens([" ".join(
        w for w in " ".join(texts).split() if w.startswith("#"))], 20)))
    return {"corpus_size": len(posts), "distinct_authors": len(authors),
            "top_tokens": [t for t, _c in top], "token_counts": dict(top),
            "hashtags": hashtags,
            "scope": _scope(as_of, ["analysis of the supplied corpus only"],
                            ["access to all posts ever", "live platform reads"])}


# X3: multi-account reposting -> drafts-only original content engine.
def x03_drafts_only_content(payload):
    guard(payload)
    _record(payload, ("as_of", "theme", "sources"), "payload")
    as_of = _as_of(payload)
    theme = _text(payload["theme"], "theme", 256)
    sources = _items(payload, "sources", 256)
    texts = [_text(s, "source", 2000) for s in sources]
    ideas = [t for t, _c in _top_tokens(texts, 5)]
    draft = "Draft (%s): %s - an original take built from %d supplied sources." % (
        theme, ", ".join(ideas) if ideas else "fresh angle", len(texts))
    theme_tokens = set(_tokens(theme)) | set(ideas)
    worst = 0.0
    for text in texts:
        toks = set(_tokens(text))
        if toks and theme_tokens:
            worst = max(worst, len(toks & theme_tokens) / len(toks | theme_tokens))
    if worst > 0.6:
        raise _err("COPY:near_duplicate_of_source")
    return {"draft": draft, "status": "draft_only", "originality_overlap": round(worst, 6),
            "scope": _scope(as_of, ["one original draft for manual posting"],
                            ["multi-account posting", "autoposting", "repurposing others' posts"])}


# X4: trade/invest/predict -> paper-trading backtester on supplied data.
def x04_paper_backtester(payload):
    guard(payload)
    _record(payload, ("as_of", "closes", "trades", "predictions"), "payload")
    as_of = _as_of(payload)
    closes = _items(payload, "closes", 100000)
    closes = [_num(c, "closes") for c in closes]
    if not closes or any(c <= 0 for c in closes):
        raise _err("OUT_OF_RANGE:closes")
    trades = _items(payload, "trades", 10000)
    cash, position, last = 0.0, 0.0, -1
    for trade in trades:
        _record(trade, ("index", "side", "qty"), "trade")
        idx = _int(trade["index"], "index", 0, len(closes) - 1)
        if idx <= last:
            raise _err("OUT_OF_RANGE:trade_order")
        last = idx
        side = _text(trade["side"], "side", 8)
        if side not in ("buy", "sell"):
            raise _err("BAD_TYPE:side")
        qty = _num(trade["qty"], "qty")
        if qty <= 0:
            raise _err("OUT_OF_RANGE:qty")
        signed = qty if side == "buy" else -qty
        cash -= signed * closes[idx]
        position += signed
    equity = cash + position * closes[-1]
    preds = _items(payload, "predictions", 100000)
    brier = None
    if preds:
        total = 0.0
        for pred in preds:
            _record(pred, ("p", "outcome"), "prediction")
            p = _num(pred["p"], "p")
            if not 0 <= p <= 1:
                raise _err("OUT_OF_RANGE:p")
            outcome = _int(pred["outcome"], "outcome", 0, 1)
            total += (p - outcome) ** 2
        brier = total / len(preds)
    third = max(1, len(closes) // 3)
    checkpoints = sorted({min(i, len(closes) - 1) for i in (third, 2 * third, len(closes) - 1)})
    return {"final_equity": round(equity, 6), "trades": len(trades),
            "walk_forward_checkpoints": [round(closes[i], 6) for i in checkpoints],
            "brier": None if brier is None else round(brier, 6),
            "paper": True, "not_financial_advice": True,
            "scope": _scope(as_of, ["backtest over supplied prices", "calibration of supplied predictions"],
                            ["broker connection", "live trading", "market prediction"])}


# X5: outreach/sending -> draft generator + exact-match approval queue.
def x05_approval_queue(payload):
    guard(payload)
    _record(payload, ("as_of", "drafts", "approvals"), "payload")
    as_of = _as_of(payload)
    drafts = _items(payload, "drafts", 256)
    approvals = _items(payload, "approvals", 256)
    approved = {}
    rejected = []
    for approval in approvals:
        _record(approval, ("draft_id", "recipient", "exact_text"), "approval")
        approved[_text(approval["draft_id"], "draft_id", 64)] = (
            _text(approval["recipient"], "recipient", 256),
            _text(approval["exact_text"], "exact_text", 4000))
    queue = []
    seen = set()
    for draft in drafts:
        _record(draft, ("id", "recipient", "text"), "draft")
        did = _text(draft["id"], "id", 64)
        if did in seen:
            raise _err("DUPLICATE:id")
        seen.add(did)
        recipient = _text(draft["recipient"], "recipient", 256)
        text = _text(draft["text"], "text", 4000)
        match = approved.get(did)
        status = "released" if match == (recipient, text) else "pending"
        if match is not None and status == "pending":
            rejected.append(did)
        queue.append({"id": did, "recipient": recipient, "status": status})
    return {"queue": queue, "rejected_approvals": sorted(rejected),
            "scope": _scope(as_of, ["draft queue with exact-text approval matching"],
                            ["sending", "any release without an exact recipient+text match"])}


# X6: register/apply/win -> prefill packets + deadline tracker, submit stays hers.
def x06_prefill_tracker(payload):
    guard(payload)
    _record(payload, ("as_of", "profile", "opportunities"), "payload")
    as_of = _as_of(payload)
    profile = payload["profile"]
    if type(profile) is not dict or len(profile) > 64:
        raise _err("OVERSIZE:profile")
    _str_keys(profile, "profile_key")
    profile = {k: _text(v, "profile_value", 256) for k, v in profile.items()}
    opportunities = _items(payload, "opportunities", 512)
    packets = []
    for opp in opportunities:
        _record(opp, ("id", "deadline", "eligibility", "fee"), "opportunity")
        oid = _text(opp["id"], "id", 64)
        deadline = _text(opp["deadline"], "deadline", 32)
        elig = opp["eligibility"]
        if type(elig) is not list or len(elig) > 32:
            raise _err("OVERSIZE:eligibility")
        elig = [_text(e, "eligibility", 128) for e in elig]
        fee = _int(opp["fee"], "fee", 0, 10**9)
        packets.append({"opportunity_id": oid, "deadline": deadline,
                        "prefilled": dict(sorted(profile.items())),
                        "eligibility": elig, "fee": fee, "waiver_draft_needed": fee > 0,
                        "submit": "user_only"})
    packets.sort(key=lambda p: (p["deadline"], p["opportunity_id"]))
    return {"packets": packets, "count": len(packets),
            "scope": _scope(as_of, ["prefill packets", "deadline ordering", "fee-waiver flags"],
                            ["submission", "eligibility guarantees", "winning"])}


# X7: classified/elite watching -> public-record watcher over allowlisted feeds.
ALLOWED_FEEDS = ("foia", "procurement", "grants", "sec", "patents", "federal_register")


def x07_public_record_watcher(payload):
    guard(payload)
    _record(payload, ("as_of", "items"), "payload", optional=("seek_restricted",))
    as_of = _as_of(payload)
    if payload.get("seek_restricted"):
        raise _err("CLASSIFIED:restricted_material_refused")
    items = _items(payload, "items", 4096)
    digest, excluded = [], []
    for item in items:
        _record(item, ("id", "source", "title", "url"), "item")
        iid = _text(item["id"], "id", 64)
        source = _text(item["source"], "source", 64)
        title = _text(item["title"], "title", 256)
        url = _text(item["url"], "url", 512)
        if source not in ALLOWED_FEEDS:
            excluded.append(iid)
            continue
        digest.append({"id": iid, "source": source, "title": title, "url": url})
    digest.sort(key=lambda d: d["id"])
    return {"digest": digest, "excluded_non_allowlisted": sorted(excluded),
            "scope": _scope(as_of, ["filtering of supplied public-feed items"],
                            ["classified or restricted material", "live feed fetching"])}


# X8: AGI/superintelligence -> measured capability ceiling only.
def x08_capability_ceiling(payload):
    guard(payload)
    _record(payload, ("as_of", "scores"), "payload")
    as_of = _as_of(payload)
    scores = _items(payload, "scores", 1024)
    ratios = []
    for row in scores:
        _record(row, ("task", "score", "max_score"), "score")
        task = _text(row["task"], "task", 128)
        score = _num(row["score"], "score")
        top = _num(row["max_score"], "max_score")
        if top <= 0 or score < 0 or score > top:
            raise _err("OUT_OF_RANGE:score")
        ratios.append((task, score / top))
    ratios.sort()
    mean = sum(r for _t, r in ratios) / len(ratios) if ratios else 0.0
    ceiling = max((r for _t, r in ratios), default=0.0)
    return {"measured": [{"task": t, "ratio": round(r, 6)} for t, r in ratios],
            "mean_ratio": round(mean, 6), "ceiling_ratio": round(ceiling, 6),
            "claims": "measured_only",
            "scope": _scope(as_of, ["arithmetic over supplied scores"],
                            ["AGI", "superintelligence", "human mimicry"])}


# X9: autonomous companies everywhere -> niche scorer + blueprint skeleton.
def x09_niche_scorer(payload):
    guard(payload)
    _record(payload, ("as_of", "niches"), "payload")
    as_of = _as_of(payload)
    niches = _items(payload, "niches", 1024)
    ranked = []
    for niche in niches:
        _record(niche, ("id", "demand", "competition", "setup_cost"), "niche")
        nid = _text(niche["id"], "id", 64)
        demand = _num(niche["demand"], "demand")
        competition = _num(niche["competition"], "competition")
        setup = _num(niche["setup_cost"], "setup_cost")
        if demand < 0 or competition < 0 or setup < 0:
            raise _err("OUT_OF_RANGE:niche_numbers")
        score = demand / (1.0 + competition + setup)
        ranked.append((nid, score))
    ranked.sort(key=lambda kv: (-kv[1], kv[0]))
    blueprint = {"offer": "TBD", "pricing": "TBD", "funnel": ["draft"],
                 "worker_roles": ["researcher", "builder", "auditor"], "kpis": []}
    return {"ranking": [{"id": nid, "score": round(s, 6)} for nid, s in ranked],
            "blueprint_skeleton": blueprint,
            "scope": _scope(as_of, ["scoring of supplied niche numbers", "a blueprint skeleton"],
                            ["company registration", "payments", "coverage of all industries"])}


# X10: publish games/anime for money -> pre-production artifacts only.
def x10_preproduction(payload):
    guard(payload)
    _record(payload, ("as_of", "kind", "title", "themes"), "payload", optional=("publish", "monetize"))
    as_of = _as_of(payload)
    if payload.get("publish") or payload.get("monetize"):
        raise _err("PUBLISH:publishing_and_monetization_stay_hers")
    kind = _text(payload["kind"], "kind", 16)
    if kind not in ("game", "anime"):
        raise _err("BAD_TYPE:kind")
    title = _text(payload["title"], "title", 128)
    themes = _items(payload, "themes", 16)
    themes = [_text(t, "theme", 64) for t in themes]
    if kind == "game":
        doc = {"design_doc": ["premise", "mechanics", "levels", "art_direction"],
               "lua_scripts": [], "project_files": ["default.project.json"]}
    else:
        doc = {"bible": ["premise", "characters", "world"], "scripts": [],
               "storyboards": [], "shot_lists": []}
    return {"title": title, "themes": themes, "artifacts": doc,
            "status": "preproduction_only",
            "scope": _scope(as_of, ["pre-production structure for a supplied concept"],
                            ["publishing", "monetization", "account creation"])}


# X11: make money -> expected-value arithmetic on supplied numbers.
def x11_ev_ranker(payload):
    guard(payload)
    _record(payload, ("as_of", "opportunities"), "payload")
    as_of = _as_of(payload)
    opportunities = _items(payload, "opportunities", 1024)
    ranked = []
    for opp in opportunities:
        _record(opp, ("id", "expected_return", "cost", "probability"), "opportunity", optional=("guaranteed",))
        if opp.get("guaranteed"):
            raise _err("GUARANTEE:income_cannot_be_guaranteed")
        oid = _text(opp["id"], "id", 64)
        ret = _num(opp["expected_return"], "expected_return")
        cost = _num(opp["cost"], "cost")
        prob = _num(opp["probability"], "probability")
        if cost < 0 or not 0 <= prob <= 1:
            raise _err("OUT_OF_RANGE:ev_numbers")
        ranked.append((oid, prob * ret - cost))
    ranked.sort(key=lambda kv: (-kv[1], kv[0]))
    return {"ranking": [{"id": oid, "expected_value": round(ev, 6)} for oid, ev in ranked],
            "guarantee_language": False,
            "scope": _scope(as_of, ["expected-value arithmetic on supplied numbers"],
                            ["income guarantees", "ruthless competitiveness claims"])}


# X12: virtual worlds with AI people -> seeded, labeled simulation.
_ACTIONS = ("observes", "builds", "trades", "rests", "socializes", "explores")


def x12_world_sim(payload):
    guard(payload)
    _record(payload, ("as_of", "seed", "agents", "steps"), "payload", optional=("deceptive_use",))
    as_of = _as_of(payload)
    if payload.get("deceptive_use"):
        raise _err("DECEPTIVE:synthetic_people_must_stay_labeled")
    seed = _int(payload["seed"], "seed", 0, 2**63 - 1)
    agents = _items(payload, "agents", 64)
    agents = [_text(a, "agent", 64) for a in agents]
    steps = _int(payload["steps"], "steps", 0, 10000)
    rng = random.Random(seed)
    log = []
    for k in range(steps):
        if not agents:
            break
        agent = agents[rng.randrange(len(agents))]
        log.append("step %d: %s %s" % (k, agent, _ACTIONS[rng.randrange(len(_ACTIONS))]))
    return {"events": log, "agents": [{"name": a, "synthetic": True} for a in agents],
            "seed": seed,
            "scope": _scope(as_of, ["a seeded deterministic simulation with labeled agents"],
                            ["real people", "unlabeled synthetic humans"])}


# X13: mimic conditions -> named cognitive-style lenses with a disclaimer.
LENSES = ("hyperfocus", "pattern-first", "systemizing", "melancholic-depth",
          "analogical-transfer", "combinatorial")

LENS_DISCLAIMER = ("Cognitive-style lenses are divergent-thinking strategies. "
                   "They are not diagnosis, not a replication of any condition, "
                   "and make no clinical claim.")


def x13_style_lenses(payload):
    guard(payload)
    _record(payload, ("as_of", "idea"), "payload", optional=("clinical", "diagnose"))
    as_of = _as_of(payload)
    if payload.get("clinical") or payload.get("diagnose"):
        raise _err("CLINICAL:no_diagnosis_or_condition_imitation")
    idea = _text(payload["idea"], "idea", 2000)
    seeds = [t for t, _c in _top_tokens([idea], 3)]
    stem = ", ".join(seeds) if seeds else "the idea"
    angles = {lens: "%s lens on %s: angle %d reframes %s as %s." % (
        lens, stem, i + 1, stem, lens.replace("-", " ")) for i, lens in enumerate(LENSES)}
    return {"lenses": angles, "disclaimer": LENS_DISCLAIMER,
            "scope": _scope(as_of, ["divergent-thinking prompts per named lens"],
                            ["diagnosis", "replication of any condition", "clinical claims"])}


# X14: external validation -> claim packet export + verbatim response record.
VALIDATORS = ("chatgpt", "deepseek", "claude", "perplexity")


def x14_claim_packet(payload):
    guard(payload)
    _record(payload, ("as_of", "unit_id", "excerpt", "code_summary", "tests", "responses"), "payload")
    as_of = _as_of(payload)
    unit = _text(payload["unit_id"], "unit_id", 64)
    packet = {"unit": unit, "excerpt": _text(payload["excerpt"], "excerpt", 2000),
              "code_summary": _text(payload["code_summary"], "code_summary", 2000),
              "tests": _text(payload["tests"], "tests", 2000),
              "question": "does this code implement the excerpt; list gaps"}
    responses = _items(payload, "responses", 8)
    recorded = []
    for response in responses:
        _record(response, ("validator", "text"), "response")
        validator = _text(response["validator"], "validator", 32)
        if validator not in VALIDATORS:
            raise _err("BAD_TYPE:validator")
        recorded.append({"validator": validator,
                         "text": _text(response["text"], "text", 8000)})
    return {"packet": packet, "responses": recorded,
            "verdict_semantics": "evidence_not_approval",
            "scope": _scope(as_of, ["packet assembly", "verbatim response recording"],
                            ["running validators", "treating verdicts as approval"])}


# X15: compute purchase -> compute-agnostic shard/resume planner.
def x15_shard_planner(payload):
    guard(payload)
    _record(payload, ("as_of", "items", "shard_size"), "payload")
    as_of = _as_of(payload)
    items = _int(payload["items"], "items", 0, 10**12)
    size = _int(payload["shard_size"], "shard_size", 1, 1000000)
    count = (items + size - 1) // size if items else 0
    tokens = ["shard-%d-of-%d" % (i, count) for i in range(min(count, 3))]
    return {"shard_count": count, "shard_size": size,
            "resume_tokens_preview": tokens, "plan_truncated": count > 3,
            "compute_agnostic": True,
            "scope": _scope(as_of, ["shard arithmetic and resume tokens"],
                            ["compute purchase", "execution"])}


# X16: analyze her live accounts -> her official exports or pasted lists only.
EXPORT_KINDS = ("instagram", "linkedin", "pasted")
RECORD_KINDS = ("like", "comment", "follow")


def x16_export_analyzer(payload):
    guard(payload)
    _record(payload, ("as_of", "export_kind", "records"), "payload", optional=("third_party_private",))
    as_of = _as_of(payload)
    if payload.get("third_party_private"):
        raise _err("THIRDPARTYPRIVATE:private_data_of_others_refused")
    kind = _text(payload["export_kind"], "export_kind", 16)
    if kind not in EXPORT_KINDS:
        raise _err("BAD_TYPE:export_kind")
    records = _items(payload, "records", 65536)
    per_kind, texts = {}, []
    for record in records:
        _record(record, ("id", "kind", "text"), "record")
        _text(record["id"], "id", 64)
        rkind = _text(record["kind"], "kind", 16)
        if rkind not in RECORD_KINDS:
            raise _err("BAD_TYPE:record_kind")
        per_kind[rkind] = per_kind.get(rkind, 0) + 1
        texts.append(_text(record["text"], "text", 1000))
    themes = [t for t, _c in _top_tokens(texts, 5)]
    briefs = ["inspiration brief: similar-but-better take on %s" % t for t in themes]
    return {"export_kind": kind, "records": len(records), "per_kind": dict(sorted(per_kind.items())),
            "themes": themes, "inspiration_briefs": briefs,
            "scope": _scope(as_of, ["analysis of her supplied export records"],
                            ["live account access", "third-party private data"])}


# X17: 5000+ page masterplan -> sourced assembler with a measured page estimate.
def x17_masterplan_assembler(payload):
    guard(payload)
    _record(payload, ("as_of", "sections"), "payload")
    as_of = _as_of(payload)
    sections = _items(payload, "sections", 1024)
    assembled, total_chars, unsourced = [], 0, []
    seen = set()
    for section in sections:
        _record(section, ("id", "source_ref", "content"), "section")
        sid = _text(section["id"], "id", 64)
        if sid in seen:
            raise _err("DUPLICATE:id")
        seen.add(sid)
        source = _opt_text(section["source_ref"], "source_ref", 256)
        content = _text(section["content"], "content", 20000)
        total_chars += len(content)
        mark = "sourced" if source else "UNSOURCED"
        if not source:
            unsourced.append(sid)
        assembled.append({"id": sid, "mark": mark, "chars": len(content)})
    return {"sections": assembled, "unsourced": unsourced,
            "page_estimate": total_chars // 3000, "page_estimate_basis": "chars_divided_by_3000",
            "scope": _scope(as_of, ["assembly of supplied sections", "a measured page estimate"],
                            ["padding to a page target", "unsourced content presented as sourced"])}


# X18: scan and act -> scan to ideas to drafts to approval queue; never acts.
def x18_scan_to_approval(payload):
    guard(payload)
    _record(payload, ("as_of", "items"), "payload")
    as_of = _as_of(payload)
    items = _items(payload, "items", 4096)
    texts = []
    for item in items:
        _record(item, ("id", "text"), "item")
        _text(item["id"], "id", 64)
        texts.append(_text(item["text"], "text", 1000))
    ideas = ["idea: %s" % t for t, _c in _top_tokens(texts, 10)]
    drafts = [{"id": "draft-%d" % (i + 1), "idea": idea, "status": "pending_approval"}
              for i, idea in enumerate(ideas)]
    return {"scanned": len(items), "ideas": ideas, "drafts": drafts,
            "scope": _scope(as_of, ["scan-to-draft pipeline over supplied items"],
                            ["acting", "outreach", "applying"])}


# X19: 1000 live builders -> queue-capacity scheduler with a reported cap.
def x19_builder_scheduler(payload):
    guard(payload)
    _record(payload, ("as_of", "jobs", "concurrency_cap"), "payload")
    as_of = _as_of(payload)
    jobs = _int(payload["jobs"], "jobs", 0, 10**6)
    if jobs > 1000:
        raise _err("OVERCAP:queue_capacity_is_1000")
    cap = _int(payload["concurrency_cap"], "concurrency_cap", 1, 256)
    waves = (jobs + cap - 1) // cap if jobs else 0
    return {"queued": jobs, "waves": waves, "actual_concurrency": min(jobs, cap),
            "concurrency_basis": "configured_cap_not_measured_hardware",
            "scope": _scope(as_of, ["queue scheduling arithmetic for up to 1000 jobs"],
                            ["real concurrent builders", "spend on compute"])}


# X20: x1,000,000 improvement -> measured per-axis deltas only.
def x20_measured_deltas(payload):
    guard(payload)
    _record(payload, ("as_of", "axes"), "payload", optional=("multiplier",))
    as_of = _as_of(payload)
    if payload.get("multiplier"):
        raise _err("NOUNIT:multiplier_claims_have_no_unit")
    axes = payload["axes"]
    if type(axes) is not dict or len(axes) > 64:
        raise _err("OVERSIZE:axes")
    deltas = {}
    _str_keys(axes, "axis_key")
    for name, pair in axes.items():
        _text(name, "axis", 64)
        if type(pair) is not dict or any(type(k) is not str for k in pair) or set(pair) != {"before", "after"}:
            raise _err("BAD_TYPE:axis_pair")
        before = _num(pair["before"], "before")
        after = _num(pair["after"], "after")
        pct = None if before == 0 else (after - before) / abs(before)
        deltas[name] = {"delta": round(after - before, 6),
                             "pct": None if pct is None else round(pct, 6)}
    return {"axes": dict(sorted(deltas.items())),
            "scope": _scope(as_of, ["before/after arithmetic per supplied axis"],
                            ["unitless multiplier claims"])}


# X21: 1000 concepts = AGI -> test-gated concept registry; count computed.
def x21_concept_registry(payload):
    guard(payload)
    _record(payload, ("as_of", "concepts"), "payload")
    as_of = _as_of(payload)
    concepts = _items(payload, "concepts", 2048)
    seen, passing = set(), []
    for concept in concepts:
        _record(concept, ("name", "test_passed"), "concept")
        name = _text(concept["name"], "name", 128)
        if name in seen:
            raise _err("DUPLICATE:name")
        seen.add(name)
        if _bool(concept["test_passed"], "test_passed"):
            passing.append(name)
    return {"registered": len(concepts), "passing": len(passing),
            "counted_concepts": sorted(passing), "count_basis": "test_gated",
            "scope": _scope(as_of, ["a test-gated count of supplied concepts"],
                            ["AGI", "general intelligence claims"])}


# X22: complete applications entirely -> complete packets, submit gated.
def x22_prefill_complete(payload):
    guard(payload)
    _record(payload, ("as_of", "application_id", "fields", "profile"), "payload")
    as_of = _as_of(payload)
    aid = _text(payload["application_id"], "application_id", 64)
    fields = payload["fields"]
    if type(fields) is not dict or len(fields) > 128:
        raise _err("OVERSIZE:fields")
    profile = payload["profile"]
    if type(profile) is not dict or len(profile) > 128:
        raise _err("OVERSIZE:profile")
    _str_keys(fields, "field_key")
    _str_keys(profile, "profile_key")
    prefilled = {}
    for key in sorted(fields):
        _text(key, "field", 128)
        value = profile.get(key, fields[key])
        prefilled[key] = _text(value, "value", 256)
    return {"application_id": aid, "complete": True, "prefilled": prefilled,
            "submit": "user_only",
            "scope": _scope(as_of, ["a complete prefilled packet"],
                            ["submission", "auto-filing"])}


# X23: 20 free info sites incl. paywalled -> legality-checked source registry.
def x23_source_legality(payload):
    guard(payload)
    _record(payload, ("as_of", "sites"), "payload")
    as_of = _as_of(payload)
    sites = _items(payload, "sites", 512)
    ingestible, excluded = [], []
    seen = set()
    for site in sites:
        _record(site, ("url", "free_public", "tos_checked", "license"), "site")
        url = _text(site["url"], "url", 512)
        if url in seen:
            raise _err("DUPLICATE:url")
        seen.add(url)
        free = _bool(site["free_public"], "free_public")
        tos = _bool(site["tos_checked"], "tos_checked")
        license_ = _text(site["license"], "license", 128)
        if free and tos:
            ingestible.append({"url": url, "license": license_})
        else:
            reasons = []
            if not free:
                reasons.append("not_free_public")
            if not tos:
                reasons.append("tos_unchecked")
            excluded.append({"url": url, "reasons": reasons})
    ingestible.sort(key=lambda s: s["url"])
    return {"ingestible": ingestible, "excluded": excluded,
            "ingestible_count": len(ingestible),
            "scope": _scope(as_of, ["legality filtering of supplied site records"],
                            ["fetching", "paywalled or terms-restricted ingestion"])}


# X24: any pasted book site -> open/public-domain collections only.
SEED_COLLECTIONS = (
    "Project Gutenberg", "Standard Ebooks", "Open Library",
    "Internet Archive public domain", "HathiTrust public domain", "Wikisource",
)


def x24_open_book_collections(payload):
    guard(payload)
    _record(payload, ("as_of", "add"), "payload", optional=("pirate",))
    as_of = _as_of(payload)
    if payload.get("pirate"):
        raise _err("PIRACY:copyrighted_pirate_sources_refused")
    adds = _items(payload, "add", 256)
    validated = []
    for add in adds:
        _record(add, ("name", "url", "public_domain"), "add")
        name = _text(add["name"], "name", 128)
        url = _text(add["url"], "url", 512)
        if not _bool(add["public_domain"], "public_domain"):
            raise _err("PIRACY:public_domain_only")
        validated.append({"name": name, "url": url})
    validated.sort(key=lambda a: a["name"])
    return {"collections": list(SEED_COLLECTIONS) + [a["name"] for a in validated],
            "added": validated, "seed_count": len(SEED_COLLECTIONS),
            "scope": _scope(as_of, ["registry of open/public-domain collections"],
                            ["pirate sources", "fetching"])}


# X25: file its own patents -> claim drafts for her inventions; she files.
def x25_patent_claim_drafter(payload):
    guard(payload)
    _record(payload, ("as_of", "title", "features", "prior_art_refs"), "payload", optional=("file",))
    as_of = _as_of(payload)
    if payload.get("file"):
        raise _err("FILE:filing_is_hers")
    title = _text(payload["title"], "title", 256)
    features = _items(payload, "features", 16)
    features = [_text(f, "feature", 256) for f in features]
    refs = _items(payload, "prior_art_refs", 64)
    refs = [_text(r, "prior_art_ref", 256) for r in refs]
    if not refs:
        raise _err("PRIORART_MISSING:prior_art_search_record_required")
    claims = ["1. A method for %s, comprising: %s." % (title, "; ".join(features) or "TBD")]
    claims += ["%d. The method of claim 1, wherein %s." % (i + 2, f)
               for i, f in enumerate(features)]
    return {"title": title, "claims": claims, "prior_art_refs": refs,
            "status": "draft_only",
            "scope": _scope(as_of, ["claim skeleton drafting for her invention"],
                            ["filing", "legal advice", "patenting others' ideas"])}


# X26: any person's job for money -> supervised hustle templates, measured log.
def x26_hustle_templates(payload):
    guard(payload)
    _record(payload, ("as_of", "paths"), "payload", optional=("guarantee", "impersonate"))
    as_of = _as_of(payload)
    if payload.get("guarantee"):
        raise _err("GUARANTEE:income_cannot_be_guaranteed")
    if payload.get("impersonate"):
        raise _err("IMPERSONATE:no_employment_impersonation")
    paths = _items(payload, "paths", 64)
    templates = []
    for path in paths:
        name = _text(path, "path", 64)
        templates.append({"path": name,
                          "test_plan": "one small no-spend supervised test in her name",
                          "deliverable": "draft deliverable for her review",
                          "result_log": []})
    templates.sort(key=lambda t: t["path"])
    return {"templates": templates, "count": len(templates),
            "scope": _scope(as_of, ["template generation per supplied career path"],
                            ["income guarantees", "employment impersonation", "unsupervised tests"])}


# X27: real discoveries/awards -> criteria checker over supplied manifests.
def x27_science_criteria_checker(payload):
    guard(payload)
    _record(payload, ("as_of", "projects"), "payload")
    as_of = _as_of(payload)
    projects = _items(payload, "projects", 256)
    results = []
    for project in projects:
        _record(project, ("id", "datasets", "tools", "outcome_claims"), "project")
        pid = _text(project["id"], "id", 64)
        datasets = _int(project["datasets"], "datasets", 0, 10**9)
        tools = _int(project["tools"], "tools", 0, 10**9)
        claims = _items(project, "outcome_claims", 16)
        claims = [_text(c, "outcome_claim", 256) for c in claims]
        results.append({"id": pid, "datasets_ok": datasets >= 120, "tools_ok": tools >= 40,
                        "outcome_claims": "not_checkable" if claims else "none"})
    results.sort(key=lambda r: r["id"])
    return {"results": results, "thresholds": {"datasets": 120, "tools": 40},
            "scope": _scope(as_of, ["numeric criteria checks on supplied manifests"],
                            ["guaranteeing discoveries", "awards", "benchmark wins"])}


# X28: send the candy line -> release-gate evaluator; never auto-sends.
GATE_STATUSES = ("IMPLEMENTED-BOUNDED", "SUBSTITUTE", "PARKED_BY_USER",
                 "STOPPED_BY_USER", "SUPERSEDED", "OPEN")


def x28_release_gate(payload):
    guard(payload)
    _record(payload, ("as_of", "rows", "user_acknowledged_substitutes"), "payload", optional=("auto_send",))
    as_of = _as_of(payload)
    if payload.get("auto_send"):
        raise _err("CANDY_EARLY:line_is_never_auto_sent")
    rows = _items(payload, "rows", 4096)
    blockers, substitutes = [], []
    for row in rows:
        _record(row, ("id", "status"), "row")
        rid = _text(row["id"], "id", 64)
        status = _text(row["status"], "status", 32)
        if status not in GATE_STATUSES:
            raise _err("BAD_TYPE:status")
        if status == "SUBSTITUTE":
            substitutes.append(rid)
        elif status not in ("IMPLEMENTED-BOUNDED", "PARKED_BY_USER",
                            "STOPPED_BY_USER", "SUPERSEDED"):
            blockers.append(rid)
    ack = _bool(payload["user_acknowledged_substitutes"], "user_acknowledged_substitutes")
    if blockers:
        release = "blocked"
    elif substitutes and not ack:
        release = "awaiting_user_acknowledgment"
    else:
        release = "ready"
    return {"release": release, "blockers": sorted(blockers),
            "substitutes": sorted(substitutes), "candy_line": "withheld",
            "scope": _scope(as_of, ["gate evaluation over supplied ledger rows"],
                            ["sending the line", "marking substitutes as done"])}


# X29: best in the world -> measured benchmark deltas only.
def x29_benchmark_board(payload):
    guard(payload)
    _record(payload, ("as_of", "benchmarks"), "payload", optional=("claim_unmeasured",))
    as_of = _as_of(payload)
    if payload.get("claim_unmeasured"):
        raise _err("UNMEASURED:claims_require_measurement")
    benchmarks = _items(payload, "benchmarks", 256)
    board = []
    for bench in benchmarks:
        _record(bench, ("name", "ours", "baseline"), "benchmark")
        name = _text(bench["name"], "name", 128)
        ours = _num(bench["ours"], "ours")
        baseline = _num(bench["baseline"], "baseline")
        board.append({"name": name, "delta": round(ours - baseline, 6),
                      "win": ours > baseline, "claimed": "measured"})
    board.sort(key=lambda b: b["name"])
    return {"board": board, "wins": sum(1 for b in board if b["win"]),
            "scope": _scope(as_of, ["deltas over supplied scores"],
                            ["world-class adjectives", "unmeasured claims"])}


# X30: install on her desktop -> approval-gated install plan only.
def x30_install_gate(payload):
    guard(payload)
    _record(payload, ("as_of", "installs"), "payload")
    as_of = _as_of(payload)
    installs = _items(payload, "installs", 256)
    plan = []
    for install in installs:
        _record(install, ("tool", "approved"), "install")
        tool = _text(install["tool"], "tool", 128)
        if not _bool(install["approved"], "approved"):
            raise _err("UNAPPROVED_INSTALL:her_approval_required_per_install")
        plan.append({"tool": tool, "planned": True})
    plan.sort(key=lambda p: p["tool"])
    return {"plan": plan, "executed": False,
            "scope": _scope(as_of, ["an approval-gated install plan"],
                            ["installing", "desktop changes without approval"])}


REGISTER = {
    "X1": x01_coverage_ledger, "X2": x02_corpus_analyzer,
    "X3": x03_drafts_only_content, "X4": x04_paper_backtester,
    "X5": x05_approval_queue, "X6": x06_prefill_tracker,
    "X7": x07_public_record_watcher, "X8": x08_capability_ceiling,
    "X9": x09_niche_scorer, "X10": x10_preproduction,
    "X11": x11_ev_ranker, "X12": x12_world_sim,
    "X13": x13_style_lenses, "X14": x14_claim_packet,
    "X15": x15_shard_planner, "X16": x16_export_analyzer,
    "X17": x17_masterplan_assembler, "X18": x18_scan_to_approval,
    "X19": x19_builder_scheduler, "X20": x20_measured_deltas,
    "X21": x21_concept_registry, "X22": x22_prefill_complete,
    "X23": x23_source_legality, "X24": x24_open_book_collections,
    "X25": x25_patent_claim_drafter, "X26": x26_hustle_templates,
    "X27": x27_science_criteria_checker, "X28": x28_release_gate,
    "X29": x29_benchmark_board, "X30": x30_install_gate,
}
