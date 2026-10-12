"""Group 76: task router for the universal creator.

route(task) classifies a free-text task into a supported kind and returns the
module/capability to run, or an explicit UNSUPPORTED verdict listing the
nearest kinds. It does not pretend to do anything it cannot; support is the
KINDS table and growing it is the extension point.
"""
from __future__ import annotations
import importlib.util, re

KINDS = {
    "web_app": (r"\b(website|web app|landing page|dashboard|frontend)\b", "m14_project_builder"),
    "api_service": (r"\b(api|backend|service|endpoint)\b", "m14_project_builder"),
    "research_report": (r"\b(research|report|literature|survey|paper)\b", "m20_general_cognitive_worker"),
    "application_draft": (r"\b(application|scholarship|grant|essay|competition)\b", "m02_competition_manager"),
    "data_pipeline": (r"\b(scrape|ingest|pipeline|dataset|feed)\b", "c32.ingest"),
    "tool_integration": (r"\b(integrate|adapter|install tool|connect tool)\b", "instinct_doc.g67_76.adapters"),
}


def _importable(module):
    name = module if module.startswith("app.") else "app.modules." + module
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, AttributeError):
        return False


def route(task):
    """Route only to a target module that resolves at call time."""
    if not isinstance(task, str) or not task.strip():
        raise ValueError("CREATOR_REFUSED_TASK")
    t = task.lower()
    hits = [(k, m) for k, (rx, m) in KINDS.items() if re.search(rx, t)]
    ok = [(k, m) for k, m in hits if _importable(m)]
    if not ok:
        return {"supported": False, "verdict": "UNSUPPORTED", "nearest": sorted(KINDS), "task": task,
                "unavailable_targets": sorted({m for _, m in hits})}
    return {"supported": True, "kind": ok[0][0], "module": ok[0][1], "module_verified": True,
            "also": [h[0] for h in ok[1:]], "task": task,
            "caveat": "routing only; the target module is not run or checked for fitness"}
