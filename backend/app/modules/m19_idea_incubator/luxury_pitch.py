"""Pitch assets for one generated idea: brief, one-pager, evidence appendix, scorecard CSV.

Every statement in the assets traces to supplied evidence, the prior-art result
or the prototype receipt. The assets are review-only drafts: they carry no
brand-affiliation claim and are never sent. Sending goes through
luxury_outreach.LuxuryOutreachQueue and human approval.
"""
from __future__ import annotations
import csv, io
from html import escape
from .luxury_venture import VentureBrief

def build_pitch_assets(brief: VentureBrief, idea: dict, priorart: dict | None = None, prototype: dict | None = None) -> dict:
    src = {s.source_id: s for s in brief.sources}
    cited = sorted({sid for e in idea["evidence"] for sid in e["source_ids"]})
    missing = [sid for sid in cited if sid not in src]
    if missing: raise ValueError("idea cites unknown sources: " + ", ".join(missing))
    if not idea["evidence"]: raise ValueError("an idea without evidence cannot be pitched")
    pa = priorart or {"label": "unchecked"}
    proto_line = ("Reference prototype: components " + ", ".join(prototype["built"]) + " built; own tests " +
                  ("passed" if prototype["all_tests_passed"] else "did NOT all pass") + " (synthetic fixtures).") if prototype else "No prototype built yet."
    pa_line = f"Prior-art check: {pa['label']}." + (" " + pa["caveat"] if pa.get("caveat") else "")
    ev_lines = [f"- \"{e['quote']}\" (signals {e['signal_id']}; sources {', '.join(e['source_ids'])}; terms {', '.join(e['matched_terms'])})" for e in idea["evidence"]]
    src_lines = [f"- {sid}: {src[sid].title} - {src[sid].url} (observed {src[sid].observed_at}): {src[sid].finding}" for sid in cited]
    sc = idea["scores"]
    md = "\n".join([f"# {idea['idea_id'].replace('_', ' ').replace('+', ' + ').title()} for {brief.brand_or_segment}", "",
        "> Review-only draft. No affiliation with, or endorsement by, the named brand. Not sent to anyone.", "",
        "## The problem", brief.customer_job, "", "## The idea", idea["mechanism"] + ".", "",
        "## Evidence", *ev_lines, "", "## What we checked", pa_line, proto_line, "",
        f"## Scorecard (heuristic, not market fact)", f"- Evidence strength: {sc['evidence_strength']}", f"- Capability readiness: {sc['readiness']}", f"- Total: {sc['total']}", "",
        "## Sources", *src_lines, "", "## Claim limits", "- No validated demand or revenue is claimed.", "- Scores rank candidates; they do not predict outcomes.", "- Prior-art search covered public indexes only."])
    html = ("<!doctype html><meta charset=utf-8><title>" + escape(idea["idea_id"]) + "</title><body style='font-family:Georgia,serif;max-width:42em;margin:2em auto'>"
        f"<h1>{escape(brief.brand_or_segment)}: {escape(idea['idea_id'])}</h1><p><em>Review-only draft. No brand affiliation or endorsement.</em></p>"
        f"<h2>Problem</h2><p>{escape(brief.customer_job)}</p><h2>Idea</h2><p>{escape(idea['mechanism'])}.</p><h2>Evidence</h2><ul>"
        + "".join(f"<li>{escape(e['quote'])}</li>" for e in idea["evidence"]) + f"</ul><p>{escape(pa_line)}</p><p>{escape(proto_line)}</p>")
    buf = io.StringIO(); w = csv.writer(buf); w.writerow(["metric", "value"])
    for k, v in sc.items(): w.writerow([k, v])
    return {"idea_id": idea["idea_id"], "review_status": "pending", "external_action_started": False,
            "files": {"brief.md": md, "one-pager.html": html, "scorecard.csv": buf.getvalue()},
            "evidence_refs": cited}
