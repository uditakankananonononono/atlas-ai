"""G116 / c35.bookmarks_exec - bookmarked-sites application executor.

Source request (instinct doc, verbatim): "I have included a bunch of
bookmarked websites. Completely fill up for applications and do whatever
necessary."

What c35.docs_ingest was missing (audit G116): the linked bookmarks doc was
never decomposed and no applications were acted on. This unit decomposes the
owner's bookmark corpus (supplied at runtime; the corpus is private and is
bound to the commitment in c35.bookmarks_data via load_corpus), classifies
every site into an executable kind, infers the concrete action plan per
site, builds prefill-ready task packets, and keeps an execution ledger with
plain statuses. Submission, account creation and any external effect stay
refused keys (owner-gated); packets mark exactly what waits on her.
Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from app.modules.c30 import policy

PREFIX = "APPLY"
KINDS = ("application_form", "scholarship", "competition", "fellowship",
         "incubator", "admissions_info", "template_doc", "platform_account",
         "community", "reference")
MAX_ROWS = 2000
_KEY_RULES = (
    ("SUBMIT", frozenset({"submit", "auto_apply", "send", "dispatch"})),
    ("SPEND", frozenset({"pay", "purchase", "spend", "buy", "checkout", "card_number"})),
    ("NOCREDS", frozenset({"login", "password", "credentials", "otp", "api_key",
                           "access_token", "bearer", "passwd"})),
)
_RULES = (
    ("template_doc", ("docs.google.", "sheets.google.")),
    ("platform_account", ("app.slack.com", "handshake", "linkedin.com", "discord")),
    ("incubator", ("ycombinator", "incubator", "accelerator", "zfellows", "fellowship")),
    ("competition", ("competition", "olympiad", "isef", "challenge", "contest", "award",
                     "hackathon", "devpost")),
    ("scholarship", ("scholarship", "financial aid", "grant", "stipend")),
    ("application_form", ("jotform", "form.", "forms.", "typeform", "registration",
                          "entry", "signup", "sign-up")),
    ("admissions_info", ("admission", "college", "university", "ivy", "harvard",
                         "commonapp", "essay", "supplement")),
)
_ACTIONS = {
    "application_form": ["extract_form_fields", "map_profile_to_fields", "draft_answers",
                         "owner_review_then_owner_submits"],
    "scholarship": ["read_eligibility", "prepare_documents", "draft_essay_outline",
                    "owner_review_then_owner_submits"],
    "competition": ["read_rules_and_deadline", "check_team_and_eligibility",
                    "prepare_entry_materials", "owner_review_then_owner_submits"],
    "fellowship": ["read_criteria", "prepare_cv_and_proposal", "draft_statement_outline",
                   "owner_review_then_owner_submits"],
    "incubator": ["read_program_fit", "prepare_pitch_deck_outline", "draft_application_answers",
                  "owner_review_then_owner_submits"],
    "admissions_info": ["read_guidance", "extract_requirements_into_plan", "no_submission_here"],
    "template_doc": ["copy_template_structure", "fill_owner_fields_from_profile",
                     "owner_review_before_use"],
    "platform_account": ["owner_signs_in_herself", "then_atlas_can_read_with_session",
                         "account_creation_owner_gated"],
    "community": ["read_rules", "draft_intro_message", "owner_review_before_posting"],
    "reference": ["read_and_extract_into_plan"],
}
DEADLINE_YEAR_RE = re.compile(r"\b(2025|2026|2027)\b")


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def _scan_keys(node, depth=0):
    if depth > 16:
        _refuse("OVERSIZE", "request")
    if type(node) is dict:
        for key, value in node.items():
            if type(key) is not str:
                _refuse("BAD_TYPE", "key")
            norm = key.casefold().replace("-", "_")
            for reason, table in _KEY_RULES:
                if norm in table:
                    _refuse(reason, norm)
            if type(value) in (dict, list, tuple):
                _scan_keys(value, depth + 1)
    elif type(node) in (list, tuple):
        for value in node:
            if type(value) in (dict, list, tuple):
                _scan_keys(value, depth + 1)


def classify(title, url):
    """Executable kind from the site's title + host + path."""
    probe = (title + " " + urlsplit(url).netloc + urlsplit(url).path).casefold()
    for kind, needles in _RULES:
        if any(n in probe for n in needles):
            return kind
    return "reference"


def _packet(idx, title, url, as_of):
    kind = classify(title, url)
    years = DEADLINE_YEAR_RE.findall(title)
    stale_hint = "2025" in years and "2026" not in years
    status = {"application_form": "ready_for_field_mapping",
              "template_doc": "ready_for_fill",
              "platform_account": "needs_owner_signin"}.get(kind, "ready_for_reading")
    return {"seq": idx, "title": title[:120], "url": url, "kind": kind,
            "actions": list(_ACTIONS[kind]), "status": status,
            "urgency": ("stale_season_check" if stale_hint else
                        "current_season" if "2026" in years else "undated"),
            "as_of": as_of}


def run(request):
    """Decompose supplied bookmarks into an executable ledger; plain dict out."""
    if type(request) is not dict:
        _refuse("BAD_TYPE", "request")
    _scan_keys(request)
    if set(request) - {"as_of", "bookmarks", "kinds"}:
        _refuse("UNKNOWN", "request")
    as_of = policy.clean_text(request.get("as_of"), PREFIX, "as_of", 10)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
        _refuse("BAD_TYPE", "as_of")
    rows = request.get("bookmarks")
    if type(rows) is not list or not rows or len(rows) > MAX_ROWS:
        _refuse("BAD_TYPE", "bookmarks")
    source = "runtime_supplied"
    want = request.get("kinds")
    if want is not None:
        if type(want) is not list or any(k not in KINDS for k in want):
            _refuse("BAD_TYPE", "kinds")
    ledger, seen = [], set()
    for i, row in enumerate(rows):
        if type(row) not in (list, tuple) or len(row) != 2:
            _refuse("BAD_TYPE", "bookmarks[%d]" % i)
        title = policy.clean_text(row[0], PREFIX, "title", 500)
        url = policy.clean_text(row[1], PREFIX, "url", 2048)
        if not url.startswith(("https://", "http://")):
            _refuse("BAD_TYPE", "url")
        if url in seen:
            continue
        seen.add(url)
        packet = _packet(len(ledger) + 1, title, url, as_of)
        if want and packet["kind"] not in want:
            continue
        ledger.append(packet)
    by_kind = {k: 0 for k in KINDS}
    for p in ledger:
        by_kind[p["kind"]] += 1
    stale = sum(1 for p in ledger if p["urgency"] == "stale_season_check")
    order = {"application_form": 0, "competition": 1, "scholarship": 2, "fellowship": 3,
             "incubator": 4, "template_doc": 5, "admissions_info": 6,
             "platform_account": 7, "community": 8, "reference": 9}
    plan = sorted(ledger, key=lambda p: (order[p["kind"]], p["seq"]))
    return {
        "as_of": as_of, "source": source,
        "ledger": ledger, "execution_plan": [p["seq"] for p in plan],
        "coverage": {"bookmarks": len(rows), "unique_urls": len(ledger),
                     "duplicates_dropped": len(rows) - len(ledger),
                     "by_kind": by_kind, "stale_season_check": stale,
                     "needs_owner_signin": by_kind["platform_account"]},
        "scope": policy.scope(
            ["decomposition of a runtime-supplied bookmark corpus",
             "per-site executable kind and concrete action plan",
             "prefill-ready packets with plain statuses and season checks"],
            ["submission, account creation, sign-in - refused keys, owner-gated",
             "live fetching - packets prepare work; fetching is the browser lane's job",
             "deadline truth - season hints come from title years, flagged as hints",
             "corpus storage - the corpus is private, runtime-supplied, and bound "
             "to the commitment in c35.bookmarks_data"],
            source, as_of),
    }
