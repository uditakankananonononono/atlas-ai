"""Group 71: turn owner-exported interest signals into ranked topics.

Sources actually parsed: (a) Gmail messages already fetched by the owner's
connected account, filtered to labelIds containing STARRED; (b) LinkedIn
data-export Reactions.csv / Comments.csv rows; (c) Instagram data-export
liked_posts JSON (owner-downloaded; live login is not used). Output is topic
weights, never an action.
"""
from __future__ import annotations
import csv, io, json, re
from collections import Counter

STOP = set("the a an and or of to in for on with at by from is are was be this that it as your you our we new re fwd".split())


def _terms(text):
    return [w for w in re.findall(r"[a-z]{3,}", (text or "").lower()) if w not in STOP]


def from_starred_gmail(messages):
    out = []
    for m in messages:
        if "STARRED" in (m.get("labelIds") or m.get("labels") or []):
            out.append({"source": "gmail_starred", "weight": 3, "text": "%s %s" % (m.get("subject", ""), m.get("snippet", ""))})
    return out


def from_linkedin_csv(csv_text, kind="reaction"):
    rows = csv.DictReader(io.StringIO(csv_text))
    w = 2 if kind == "reaction" else 3
    return [{"source": "linkedin_" + kind, "weight": w, "text": r.get("Link", "") + " " + (r.get("Message") or r.get("Comment") or r.get("Type") or "")} for r in rows]


def from_instagram_likes(json_text):
    data = json.loads(json_text)
    items = data if isinstance(data, list) else (data.get("likes_media_likes", []) if isinstance(data, dict) else [])
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        texts = [it.get("title", "")] + [sd.get("value", "") for sd in it.get("string_list_data", [])]
        out.append({"source": "instagram_like", "weight": 1, "text": " ".join(texts)})
    return out


def rank(signals, top=20):
    c = Counter()
    for s in signals:
        for t in set(_terms(s["text"])):
            c[t] += s["weight"]
    return [{"topic": t, "score": n} for t, n in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:top]]
