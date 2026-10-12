"""Group 76: task router for the universal creator.

route(task) classifies a free-text task into a supported kind and returns the
module/capability to run, or an explicit UNSUPPORTED verdict listing the
nearest kinds. It does not pretend to do anything it cannot; support is the
KINDS table and growing it is the extension point.
"""
from __future__ import annotations
import re

KINDS = {
    "web_app": (r"\b(website|web app|landing page|dashboard|frontend)\b", "m14_project_builder"),
    "api_service": (r"\b(api|backend|service|endpoint)\b", "m14_project_builder"),
    "research_report": (r"\b(research|report|literature|survey|paper)\b", "m20_general_cognitive_worker"),
    "application_draft": (r"\b(application|scholarship|grant|essay|competition)\b", "m02_competition_manager"),
    "data_pipeline": (r"\b(scrape|ingest|pipeline|dataset|feed)\b", "c32.ingest"),
    "tool_integration": (r"\b(integrate|adapter|install tool|connect tool)\b", "instinct_doc.g67_76.adapters"),
}


def route(task):
    t = task.lower()
    hits = [(k, m) for k, (rx, m) in KINDS.items() if re.search(rx, t)]
    if not hits:
        return {"supported": False, "verdict": "UNSUPPORTED", "nearest": sorted(KINDS), "task": task}
    return {"supported": True, "kind": hits[0][0], "module": hits[0][1], "also": [h[0] for h in hits[1:]], "task": task}
