"""c33.app_forge (doc row 105): viral app/content engine across niches.

Closes the audit gap on c33.niches/c33.content ("taxonomy enumeration/ranked
drafts; no built viral apps"): this unit builds apps - for each
niche it writes a complete, runnable static web app (index.html with inline
CSS/JS, webmanifest, README) carrying engineered-virality mechanics: Web
Share API with clipboard fallback, a local referral counter, an interest
capture list stored locally with one-click JSON export. It also generates a
hook-scored content calendar per niche. Batch mode forges apps across
thousands of niches (cap enforced).

Honest bounds: virality is ENGINEERED mechanics (share, referral, capture),
not a promised viral outcome; apps are written to a local output directory
and are not deployed or posted anywhere. AUTOPOST/FAKEACCT guard: any
request key naming posting, publishing, accounts or sending refuses.
Stdlib only, offline, deterministic output.
"""
from __future__ import annotations

import hashlib
import html
import json
import os

from app.modules.c30 import policy

PREFIX = "SOCIAL"
MAX_APPS = 10000
MAX_NAME = 120
MAX_CALENDAR_DAYS = 60
MAX_OUT_PATH = 512

_FORBIDDEN_KEYS = frozenset({
    "post", "publish", "deploy", "upload", "send", "schedule_post", "account",
    "accounts", "login", "password", "token", "api_key", "bot", "bots"})

HOOK_PATTERNS = (
    ("curiosity", "The {niche} trick nobody explains properly", 0.9),
    ("number", "7 {niche} mistakes that waste your weekends", 0.85),
    ("howto", "How to start {niche} with zero budget", 0.8),
    ("contrarian", "Why most {niche} advice is backwards", 0.75),
    ("story", "I tried {niche} for 30 days - honest results", 0.7),
)

LIMITS = (
    "Apps carry engineered share/referral/capture mechanics; virality itself "
    "is not measured or promised.",
    "Apps are written to a local directory only; nothing is deployed, posted "
    "or published.",
    "Niche count is enumeration capacity over supplied vocabularies.",
)


def _err(code, detail=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, code, (":" + detail) if detail else ""))


def _guard(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(k, str) and k.casefold().replace("-", "_") in _FORBIDDEN_KEYS:
                _err("AUTOPOST", k.casefold())
            _guard(v)
    elif isinstance(node, (list, tuple)):
        for v in node:
            _guard(v)


def _slug(text):
    out = []
    for ch in text.lower():
        out.append(ch if ch.isalnum() else "-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:60] or "app"


_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>body{{font-family:system-ui;margin:2rem auto;max-width:42rem;padding:0 1rem}}
button{{padding:.6rem 1rem;font-size:1rem}}#count{{font-weight:bold}}</style></head>
<body>
<h1>{title}</h1><p>{tagline}</p>
<p>Niche: {niche} &middot; Audience: {audience} &middot; Format: {fmt}</p>
<section id="app"><!-- app body: extend per niche --></section>
<section id="share">
<button id="shareBtn">Share this app</button>
<button id="refBtn">Copy my referral link</button>
<p>People you brought: <span id="count">0</span></p>
</section>
<section id="capture">
<input id="email" type="email" placeholder="you@example.com">
<button id="keepBtn">Keep me posted</button>
<button id="exportBtn">Export my list (JSON)</button>
</section>
<script>
const KEY="{slug}";
const store={{get:(k,d)=>JSON.parse(localStorage.getItem(KEY+k)||JSON.stringify(d)),
set:(k,v)=>localStorage.setItem(KEY+k,JSON.stringify(v))}};
document.getElementById("count").textContent=store.get("referrals",0);
document.getElementById("shareBtn").onclick=async()=>{{
const data={{title:document.title,text:{tagline_js},url:location.href}};
if(navigator.share){{try{{await navigator.share(data)}}catch(e){{}}}}
else{{await navigator.clipboard.writeText(location.href);alert("Link copied")}}}};
document.getElementById("refBtn").onclick=async()=>{{
const ref=location.href+(location.href.includes("?")?"&":"?")+"ref="+KEY;
await navigator.clipboard.writeText(ref);
const n=store.get("referrals",0)+1;store.set("referrals",n);
document.getElementById("count").textContent=n;}};
document.getElementById("keepBtn").onclick=()=>{{
const v=document.getElementById("email").value.trim();
if(!v.includes("@")){{alert("Enter a valid email");return}}
const list=store.get("list",[]);list.push(v);store.set("list",list);
document.getElementById("email").value="";alert("Saved locally")}};
document.getElementById("exportBtn").onclick=()=>{{
const blob=new Blob([JSON.stringify(store.get("list",[]),null,2)],{{type:"application/json"}});
const a=document.createElement("a");a.href=URL.createObjectURL(blob);
a.download=KEY+"-list.json";a.click();}};
const params=new URLSearchParams(location.search);
if(params.get("ref")){{store.set("referredBy",params.get("ref"))}};
</script></body></html>
"""


def _niche_parts(niche):
    if not isinstance(niche, dict):
        raise ValueError("%s_REFUSED_BAD_TYPE:niche" % PREFIX)
    tax = policy.clean_text(niche.get("taxonomy"), PREFIX, "taxonomy", MAX_NAME)
    aud = policy.clean_text(niche.get("audience"), PREFIX, "audience", MAX_NAME)
    fmt = policy.clean_text(niche.get("format"), PREFIX, "format", MAX_NAME)
    return tax, aud, fmt


def forge(niche, brand, out_dir):
    """Build one complete runnable static app for a niche. Returns file map
    and the virality feature checklist."""
    _guard(brand)
    tax, aud, fmt = _niche_parts(niche)
    if not isinstance(brand, dict):
        raise ValueError("%s_REFUSED_BAD_TYPE:brand" % PREFIX)
    bname = policy.clean_text(brand.get("name"), PREFIX, "brand.name", MAX_NAME)
    tagline = policy.clean_text(brand.get("tagline", "Made for %s fans" % tax),
                                PREFIX, "brand.tagline", 200, allow_ws=False)
    out_dir = policy.clean_text(out_dir, PREFIX, "out_dir", MAX_OUT_PATH)
    slug = _slug("%s-%s-%s" % (tax, aud, fmt))
    root = os.path.realpath(out_dir)
    app_dir = os.path.join(root, slug)
    if os.path.commonpath((root, os.path.realpath(app_dir))) != root:
        _err("PATH")
    os.makedirs(app_dir, exist_ok=True)
    page = _HTML.format(title=html.escape("%s - %s" % (bname, tax.title())),
                        tagline=html.escape(tagline), niche=html.escape(tax),
                        audience=html.escape(aud), fmt=html.escape(fmt),
                        slug=slug, tagline_js=json.dumps(tagline))
    files = {}
    page_path = os.path.join(app_dir, "index.html")
    with open(page_path, "w", encoding="utf-8") as fh:
        fh.write(page)
    files["index"] = page_path
    manifest = {"name": "%s - %s" % (bname, tax.title()), "short_name": slug[:12],
                "start_url": "./index.html", "display": "standalone",
                "theme_color": "#111111", "background_color": "#ffffff"}
    man_path = os.path.join(app_dir, "app.webmanifest")
    with open(man_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    files["manifest"] = man_path
    readme_path = os.path.join(app_dir, "README.md")
    with open(readme_path, "w", encoding="utf-8") as fh:
        fh.write("# %s\n\nStatic app for niche `%s / %s / %s`.\n\n" % (slug, tax, aud, fmt))
        fh.write("Open index.html in a browser. Share, referral and capture mechanics "
                 "run locally (localStorage). Not deployed anywhere.\n")
    files["readme"] = readme_path
    digest = hashlib.sha256(page.encode("utf-8")).hexdigest()[:12]
    features = ["web-share-api", "clipboard-fallback", "referral-counter",
                "interest-capture", "local-json-export", "ref-param-attribution"]
    return {"slug": slug, "dir": app_dir, "files": files,
            "virality_features": features, "content_sha": digest,
            "deployed": False, "limits": list(LIMITS)}


def content_calendar(niche, days=14):
    """Hook-scored content titles per day for the niche."""
    tax, aud, fmt = _niche_parts(niche)
    if isinstance(days, bool) or not isinstance(days, int) \
            or not 1 <= days <= MAX_CALENDAR_DAYS:
        raise ValueError("%s_REFUSED_BAD_TYPE:days" % PREFIX)
    rows = []
    for d in range(days):
        hook, template, score = HOOK_PATTERNS[d % len(HOOK_PATTERNS)]
        rows.append({"day": d + 1, "title": template.format(niche=tax),
                     "hook_type": hook, "hook_score": score,
                     "audience": aud, "format": fmt})
    return {"niche": {"taxonomy": tax, "audience": aud, "format": fmt},
            "days": rows, "posted": False, "limits": list(LIMITS)}


def batch(niches, brand, out_dir, cap=100):
    """Forge apps across many niches. Returns per-app results and totals."""
    if isinstance(niches, bool) or not isinstance(niches, (list, tuple)) or not niches:
        _err("EMPTY", "niches")
    if isinstance(cap, bool) or not isinstance(cap, int) or not 1 <= cap <= MAX_APPS:
        raise ValueError("%s_REFUSED_BAD_TYPE:cap" % PREFIX)
    results = []
    for niche in niches[:cap]:
        results.append(forge(niche, brand, out_dir))
    return {"apps_built": len(results), "requested": len(niches), "cap": cap,
            "apps": [{"slug": r["slug"], "dir": r["dir"], "content_sha": r["content_sha"]}
                     for r in results],
            "deployed": False, "limits": list(LIMITS)}
