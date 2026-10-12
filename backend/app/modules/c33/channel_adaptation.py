"""Source-bound, explicitly extractive channel drafts, not generic filler.

Uses owner's notes only. Never copies third-party posts or publishes. Covers
only the named platforms and supplied notes. No mass account creation.
"""
from app.modules.c30 import policy

LIMITS = {'linkedin': 3000, 'instagram': 2200, 'x': 280}


def adapt(notes: list, platforms: list) -> dict:
    if type(notes) is not list or not 1 <= len(notes) <= 100:
        raise ValueError('owner notes required')
    if type(platforms) is not list or not platforms or len(platforms) > len(LIMITS):
        raise ValueError('supported platforms required')
    if any(type(p) is not str or p not in LIMITS for p in platforms) or len(set(platforms)) != len(platforms):
        raise ValueError('unique supported platforms required')
    clean, ids = [], set()
    for note in notes:
        if type(note) is not dict or set(note) != {'id', 'title', 'text', 'owner_authored'} or note['owner_authored'] is not True:
            raise ValueError('explicit owner-authored notes required')
        rid = policy.clean_text(note['id'], 'SOCIAL', 'id', 128)
        if rid in ids:
            raise ValueError('duplicate note id')
        ids.add(rid)
        title = policy.clean_text(note['title'], 'SOCIAL', 'title', 128)
        text = policy.clean_text(note['text'], 'SOCIAL', 'text', 20000, allow_ws=True)
        clean.append((rid, title, text))
    drafts = []
    for platform in platforms:
        for rid, title, text in clean:
            prefix = title + '\n\n'
            capacity = LIMITS[platform] - len(prefix)
            chunks, rest = [], text
            while rest:
                if len(rest) <= capacity:
                    chunks.append(rest); break
                cut = rest.rfind(' ', 0, capacity + 1)
                if cut <= 0:
                    cut = capacity
                chunks.append(rest[:cut]); rest = rest[cut:].lstrip(' ')
            drafts.append({'platform': platform, 'source_id': rid,
                           'parts': [prefix + chunk for chunk in chunks],
                           'limit': LIMITS[platform], 'status': 'needs_owner_review',
                           'method': 'extractive adaptation of owner notes', 'sent': False})
    return {'drafts': drafts, 'scope': 'Only supplied owner notes and listed channels; no creation or posting.'}
