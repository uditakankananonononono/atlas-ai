"""M01 auto-apply tool registry (v2 unit A1): descriptors only.

No accounts, logins, submissions, autofill or network calls live here. Each
entry says what a tool is for and what Atlas may do with it. "Free" claims are
quoted from the spec and stay UNVERIFIED until re-checked on the tool's public
page. Unknown terms are clearly marked stubs and are never guessed.
"""
from __future__ import annotations

from dataclasses import dataclass

from .student_platforms import BY_ID as _PLATFORM_BY_ID

APPLY_REFUSED_AUTOSUBMIT = 'APPLY_REFUSED_AUTOSUBMIT'
APPLY_REFUSED_SPEND = 'APPLY_REFUSED_SPEND'
APPLY_REFUSED_TOS = 'APPLY_REFUSED_TOS'

# Statuses
SPEC_NAMED = 'spec_named'                # named in her M01 tool list (WhatsApp, 2026-10-11 15:03:34 IST)
UNKNOWN_STUB = 'unknown_pending_user'    # term not identified; do not build
CANDIDATE_PENDING = 'candidate_pending_approval'  # not hers; she must approve

# Capabilities Atlas may *prepare*; none of them submits or autofills.
PROFILE_EXPORT = 'profile_export'
MATCHES_IMPORT = 'matches_import'
DEADLINE_SYNC = 'deadline_sync'
OPEN_FORM = 'open_form_for_user'


@dataclass(frozen=True)
class ToolDescriptor:
    id: str
    name: str
    status: str
    kind: str
    url: str = ''
    spec_free_claim: str = ''     # her stated claim (WhatsApp 2026-10-11 15:03:34 IST); not verified against live vendor pages
    free_verified: bool = False
    capabilities: tuple[str, ...] = ()
    account_mode: str = 'none'    # none | user_own_logged_in_account
    notes: str = ''
    submission_gate: str = 'user_exact_draft_approval'

    @property
    def buildable(self) -> bool:
        return self.status != UNKNOWN_STUB


def _named(id_, name, kind, claim, caps, account='none', notes=''):
    p = _PLATFORM_BY_ID.get(id_)
    return ToolDescriptor(id_, name, SPEC_NAMED, kind, p.url if p else '', claim, False, caps, account, notes)


_STD = (PROFILE_EXPORT, MATCHES_IMPORT, DEADLINE_SYNC, OPEN_FORM)
NAMED = (
    _named('ripplematch', 'RippleMatch', 'job', 'Completely Free for Students', _STD, 'user_own_logged_in_account'),
    _named('simplify', 'Simplify', 'job', '(Simplify.jobs) Chrome Extension (Completely Free)', (PROFILE_EXPORT, OPEN_FORM), 'user_own_logged_in_account',
           'User-installed Chrome extension; Atlas never runs it or fills forms.'),
    _named('raiseme', 'RaiseMe', 'scholarship', '100% Free', (MATCHES_IMPORT, DEADLINE_SYNC)),
    _named('bold', 'Bold.org', 'scholarship', '100% Free', (MATCHES_IMPORT, DEADLINE_SYNC, OPEN_FORM)),
    _named('fastweb', 'Fastweb', 'scholarship', '100% Free', (MATCHES_IMPORT, DEADLINE_SYNC, OPEN_FORM)),
    _named('devpost', 'Devpost', 'hackathon', '100% Free', (MATCHES_IMPORT, DEADLINE_SYNC, OPEN_FORM)),
    _named('challengerocket', 'ChallengeRocket', 'competition', '100% Free for students', (MATCHES_IMPORT, DEADLINE_SYNC, OPEN_FORM)),
)

# Terms from her notes that are not identified. Stubs only.
STUBS = (
    ToolDescriptor('paperbleach', 'paperbleach', UNKNOWN_STUB, 'unknown',
                   notes='UNKNOWN TERM. Her note: "completed applications entirely and uses paperbleach". '
                         'Not identified (may be a name variation). Pending her answer; no connector, no URL, no guess.'),
    ToolDescriptor('clicky', 'clicky', UNKNOWN_STUB, 'unknown',
                   notes='UNKNOWN TERM. Her note: "integrate clicky, okara ai tool". Exact product/link unconfirmed. Pending her answer.'),
    ToolDescriptor('okara', 'okara', UNKNOWN_STUB, 'unknown',
                   notes='UNKNOWN TERM ("okara ai tool"). Exact product/link unconfirmed. Pending her answer.'),
)

# "+ 10 more": the spec says discovery finds them with evidence and she approves.
# The other platforms already in student_platforms are surfaced as candidates only.
PLUS_MORE_TARGET = 10
CANDIDATES = tuple(
    ToolDescriptor(p.id, p.name, CANDIDATE_PENDING, p.kind, p.url, '', False, (MATCHES_IMPORT, DEADLINE_SYNC),
                   notes='Existing read-only platform; not named by her. Needs evidence and her approval before counting as one of the "+10 more".')
    for p in _PLATFORM_BY_ID.values() if p.id not in {t.id for t in NAMED}
)

REGISTRY = NAMED + STUBS + CANDIDATES
BY_ID = {t.id: t for t in REGISTRY}
assert len(BY_ID) == len(REGISTRY)


def get(tool_id: str) -> ToolDescriptor:
    try:
        return BY_ID[tool_id]
    except KeyError:
        raise KeyError(f'unknown tool {tool_id!r}') from None


def describe(tool_id: str) -> dict:
    t = get(tool_id)
    return {**t.__dict__, 'capabilities': list(t.capabilities), 'buildable': t.buildable,
            'autosubmit': False, 'autofill': False, 'live_accounts_used': False}


def registry_payload() -> dict:
    """Payload for GET /c35/m01-tools (route wiring left to the integrator)."""
    return {
        'tools': [describe(t.id) for t in REGISTRY],
        'counts': {'spec_named': len(NAMED), 'unknown_stubs': len(STUBS), 'candidates_pending': len(CANDIDATES),
                   'plus_more_target': PLUS_MORE_TARGET},
        'free_claims_verified': False,
    }


def request_action(tool_id: str, action: str) -> dict:
    """Capability gate. Prepare-only actions pass; everything else raises a refusal code."""
    t = get(tool_id)
    if not t.buildable:
        raise LookupError(f'{tool_id} is an unidentified term; pending the user')
    if action in {'submit', 'autosubmit', 'apply', 'autofill'}:
        raise PermissionError(APPLY_REFUSED_AUTOSUBMIT)
    if action in {'pay', 'subscribe', 'upgrade', 'purchase'}:
        raise PermissionError(APPLY_REFUSED_SPEND)
    if action in {'login', 'signup', 'create_account', 'bypass_challenge', 'scrape'}:
        raise PermissionError(APPLY_REFUSED_TOS)
    if action not in t.capabilities:
        raise PermissionError(APPLY_REFUSED_TOS)
    return {'tool': tool_id, 'action': action, 'prepare_only': True}
