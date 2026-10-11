"""c30.policy - shared standing-rules guard for the v2 build program.

Every v2 unit imports this guard. It owns the six standing refusals; units
call check() with their own prefix so refusal codes carry the unit's family.
Stdlib only, offline.
"""
from __future__ import annotations

import hashlib
import json
import math
import unicodedata

RULES = {
    "spend": "SPEND",          # no spend without per-action approval
    "outreach": "OUTREACH",    # no email/DM/outreach without exact-draft approval
    "fakeacct": "FAKEACCT",    # no fake accounts, bots or multi-account posting
    "autopost": "AUTOPOST",    # no autonomous posting
    "scrape": "SCRAPE",        # no scraping that breaks terms or auth walls
    "trade": "TRADE",          # no real-money trading
}

FORBIDDEN_CATEGORIES = ("Cc", "Zl", "Zp")
MESSAGE_WS = frozenset({"\n", "\r", "\t"})  # ordinary message bytes, permitted with allow_ws


def check(action: str, prefix: str) -> None:
    """Raise ValueError('<prefix>_REFUSED_<RULE>') when action is a standing
    refusal. Unknown actions REFUSE too: the guard is fail-closed, so a typo
    or a new risky action can never slip through as pass-with-docs."""
    if action in RULES:
        raise ValueError("%s_REFUSED_%s" % (prefix, RULES[action]))
    raise ValueError("%s_REFUSED_UNKNOWN:%s" % (prefix, action))


def check_account(platform, existing, prefix: str) -> dict:
    """Enforced one-account-per-platform check for account-creation paths.

    existing is the supplied registry of accounts that already exist
    (dicts with a "platform" key; official or not, any existing account on
    the platform blocks another). Returns the descriptor for the single
    official account that may be proposed. Refuses <prefix>_REFUSED_FAKEACCT
    when the platform is taken."""
    platform = clean_text(platform, prefix, "platform", 64)
    if isinstance(existing, bool) or not isinstance(existing, (list, tuple)):
        raise ValueError("%s_REFUSED_BAD_TYPE:existing" % prefix)
    key = platform.strip().lower()
    for row in existing:
        if not isinstance(row, dict):
            raise ValueError("%s_REFUSED_BAD_TYPE:account" % prefix)
        other = clean_text(row.get("platform"), prefix, "platform", 64)
        if other.strip().lower() == key:
            raise ValueError("%s_REFUSED_FAKEACCT" % prefix)  # one account per platform
    return {"platform": platform, "official": True}


def clean_text(value, prefix: str, name: str, limit: int, allow_blank: bool = False,
               allow_ws: bool = False) -> str:
    """Shared text hygiene for caller-supplied fields: type, blank, control
    characters (Unicode Cc/Zl/Zp) and length. Raises ValueError with the
    unit's prefix. allow_ws permits the ordinary message bytes LF, CR and
    TAB (approved text is preserved byte-exact, never normalized); every
    other Cc/Zl/Zp character is still refused."""
    if isinstance(value, bool) or not isinstance(value, str):
        raise ValueError("%s_REFUSED_BAD_TYPE:%s" % (prefix, name))
    if not allow_blank and not value.strip():
        raise ValueError("%s_REFUSED_EMPTY:%s" % (prefix, name))
    if any(unicodedata.category(c) in FORBIDDEN_CATEGORIES
           and not (allow_ws and c in MESSAGE_WS) for c in value):
        raise ValueError("%s_REFUSED_CONTROL_CHARS:%s" % (prefix, name))
    if len(value) > limit:
        raise ValueError("%s_REFUSED_TEXT_TOO_LONG:%s" % (prefix, name))
    return value


def scope(implemented, not_implemented, data_source: str, as_of: str = "supplied-input") -> dict:
    """Mandatory honesty block on every v2 report. Coverage numbers are
    computed by the caller, never asserted."""
    return {"implemented": list(implemented), "not_implemented": list(not_implemented),
            "data_source": data_source, "as_of": as_of}


# --------------------------------------------------------------------------
# Canonical descriptor adapter (auditor-4 canonical surface)
#
# A typed, validated descriptor {class, module_id, tenant_id, action_type,
# payload} classifies side-effect-free into allow | refuse(code) |
# needs_approval(approval_id). Checking never creates m00 state: queue
# creation and permit consumption are separate calls. Hard-refuse classes
# cannot be overridden by any m00 allow. Payload hygiene lives in exactly
# ONE path (_validate_spend_payload / _validate_outreach_payload, reached
# through validate_descriptor): bind_* helpers only assemble, so a
# hand-constructed descriptor faces byte-identical validation.
# Legacy check() above stays as the deny-only compatibility wrapper with
# per-unit refusal mapping.
# --------------------------------------------------------------------------

CLASSES = ("offline", "spend", "outreach", "fakeacct", "autopost", "trade", "scrape")
HARD_REFUSE = frozenset({"fakeacct", "autopost", "trade", "scrape"})
GATED = frozenset({"spend", "outreach"})
OFFLINE_ALLOWLIST = frozenset({"analyze", "draft", "plan", "record", "read"})
_DESCRIPTOR_KEYS = frozenset({"class", "module_id", "tenant_id", "action_type", "payload"})

# class -> required action_type: class and action can never be relabeled apart
_CLASS_ACTION = {"spend": "spend", "outreach": "outreach"}

_SPEND_REQUIRED = ("merchant", "item", "amount", "currency", "quantity", "fees",
                   "undo_terms", "effect_id")
_SPEND_OPTIONAL = ("resource", "options")
_OUTREACH_KEYS = ("sender", "channel", "send_at", "to", "cc", "bcc", "subject",
                  "body", "body_sha256", "attachment_hashes")


def _bad(field):
    raise ValueError("POLICY_REFUSED_BAD_DESCRIPTOR:%s" % field)


def _validate_keys_str(value):
    """m00 _validate_payload_keys parity: no JSON key coercion anywhere."""
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            _bad("payload")
        for item in value.values():
            _validate_keys_str(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _validate_keys_str(item)


def _money(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(value):
        _bad(field)
    return value


def _validate_spend_payload(p):
    """The single spend hygiene path (bind_spend output and direct
    descriptors are indistinguishable here)."""
    if set(p) != frozenset(_SPEND_REQUIRED) | frozenset(_SPEND_OPTIONAL):
        _bad("payload")
    amount = _money(p["amount"], "amount")
    if amount <= 0:
        _bad("amount")
    currency = p["currency"]
    if not isinstance(currency, str) or len(currency) != 3 \
            or not currency.isalpha() or currency != currency.upper():
        _bad("currency")
    quantity = p["quantity"]
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        _bad("quantity")
    if _money(p["fees"], "fees") < 0:
        _bad("fees")
    clean_text(p["merchant"], "POLICY", "merchant", 256)
    clean_text(p["item"], "POLICY", "item", 256)
    clean_text(p["undo_terms"], "POLICY", "undo_terms", 512)
    clean_text(p["effect_id"], "POLICY", "effect_id", 200)
    if p["resource"] is not None:
        clean_text(p["resource"], "POLICY", "resource", 256)
    if p["options"] is not None and (isinstance(p["options"], bool)
                                     or not isinstance(p["options"], dict)):
        _bad("options")


def _validate_outreach_payload(p):
    """The single outreach hygiene path."""
    if set(p) != frozenset(_OUTREACH_KEYS):
        _bad("payload")
    clean_text(p["sender"], "POLICY", "sender", 320)
    clean_text(p["channel"], "POLICY", "channel", 64)
    clean_text(p["send_at"], "POLICY", "send_at", 64)
    for field in ("to", "cc", "bcc"):
        v = p[field]
        if isinstance(v, bool) or not isinstance(v, (list, tuple)):
            _bad(field)
        for a in v:
            clean_text(a, "POLICY", field, 320)
    if not p["to"]:
        raise ValueError("POLICY_REFUSED_EMPTY:to")
    # subjects are single-line (no allow_ws); blank subject is valid
    clean_text(p["subject"], "POLICY", "subject", 998, allow_blank=True)
    # bodies allow the ordinary message bytes LF/CR/TAB, preserved byte-exact
    clean_text(p["body"], "POLICY", "body", 200000, allow_ws=True)
    ah = p["attachment_hashes"]
    if isinstance(ah, bool) or not isinstance(ah, (list, tuple)):
        _bad("attachment_hashes")
    for h in ah:
        if not isinstance(h, str) or len(h) != 64 \
                or any(c not in "0123456789abcdef" for c in h):
            _bad("attachment_hashes")
    if p["body_sha256"] != hashlib.sha256(p["body"].encode("utf-8")).hexdigest():
        _bad("body_sha256")


def validate_descriptor(descriptor):
    """Raise POLICY_REFUSED_BAD_DESCRIPTOR:<field> / UNKNOWN:<class> unless
    the descriptor is exactly {class, module_id, tenant_id, action_type,
    payload} with valid types, class/action compatibility, a finite-JSON
    payload with string-only keys, and the class payload schema."""
    if isinstance(descriptor, bool) or not isinstance(descriptor, dict) \
            or set(descriptor) != _DESCRIPTOR_KEYS:
        _bad("keys")
    cls = descriptor["class"]
    if not isinstance(cls, str) or cls not in CLASSES:
        raise ValueError("POLICY_REFUSED_UNKNOWN:%s" % str(cls)[:64])
    module_id = descriptor["module_id"]
    if isinstance(module_id, bool) or not isinstance(module_id, int) or module_id < 1:
        _bad("module_id")
    from app.modules.catalog import BY_ID as _REGISTERED_MODULES
    if module_id not in _REGISTERED_MODULES:
        _bad("module_id")  # registered-source rule: no arbitrary module ids
    clean_text(descriptor["tenant_id"], "POLICY", "tenant_id", 120)
    action_type = descriptor["action_type"]
    if isinstance(action_type, bool) or not isinstance(action_type, str) \
            or not action_type.strip() or len(action_type) > 100:
        _bad("action_type")
    required_action = _CLASS_ACTION.get(cls)
    if required_action is not None and action_type != required_action:
        _bad("action_type")  # class/action relabeling is impossible by construction
    payload = descriptor["payload"]
    if isinstance(payload, bool) or not isinstance(payload, dict):
        _bad("payload")
    _validate_keys_str(payload)
    if cls == "spend":
        _validate_spend_payload(payload)
    elif cls == "outreach":
        _validate_outreach_payload(payload)
    try:
        json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        _bad("payload")


def classify(descriptor):
    """Side-effect-free gate: allow | refuse(code) | needs_approval.

    Never creates m00 state, never reads a service; same descriptor in, same
    decision out."""
    validate_descriptor(descriptor)
    cls = descriptor["class"]
    if cls in HARD_REFUSE:
        # cannot be overridden by any approval
        return {"decision": "refuse", "code": "POLICY_REFUSED_%s" % cls.upper(),
                "approval_id": None}
    if cls in GATED:
        # never allowed from supplied booleans or token-looking data
        return {"decision": "needs_approval", "code": None, "approval_id": None}
    action_type = descriptor["action_type"]
    if action_type in OFFLINE_ALLOWLIST:
        return {"decision": "allow", "code": None, "approval_id": None}
    return {"decision": "refuse", "code": "POLICY_REFUSED_UNKNOWN:%s" % action_type,
            "approval_id": None}


def payload_hash(payload) -> str:
    """SHA256 of the canonical JSON encoding of the exact payload (m00
    _canonical parity: sort_keys, tight separators, ensure_ascii=False, no
    NaN). String-key integrity is enforced first: {1: 'x'} never collides
    with {'1': 'x'} because the former refuses."""
    _validate_keys_str(payload)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def descriptor_hash(descriptor) -> str:
    """m00 _request_hash parity over the descriptor's binding tuple."""
    validate_descriptor(descriptor)
    body = {"module_id": descriptor["module_id"],
            "action_type": descriptor["action_type"],
            "payload": descriptor["payload"],
            "user_id": descriptor["tenant_id"]}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def bind_spend(*, tenant_id, module_id, merchant, item, amount, currency,
               quantity, fees, undo_terms, effect_id, resource=None, options=None):
    """Assemble a spend descriptor bound to merchant/resource/item/options,
    the final amount+currency+quantity+fees, undo terms and one effect id.
    All hygiene happens in validate_descriptor (single path); currency is
    normalized to upper before hashing so 'usd' and 'USD' are one review.
    Changed cost or item = a new descriptor = a new review."""
    payload = {"merchant": merchant, "resource": resource, "item": item,
               "options": options, "amount": amount,
               "currency": currency.upper() if isinstance(currency, str) else currency,
               "quantity": quantity, "fees": fees, "undo_terms": undo_terms,
               "effect_id": effect_id}
    descriptor = {"class": "spend", "module_id": module_id, "tenant_id": tenant_id,
                  "action_type": "spend", "payload": payload}
    validate_descriptor(descriptor)
    return descriptor


def bind_outreach(*, tenant_id, module_id, sender, channel, send_at, to, cc, bcc,
                  subject, body, attachment_hashes=()):
    """Assemble an outreach descriptor bound to the sender account, channel
    and time, every to/cc/bcc recipient, the exact subject and body,
    attachment hashes and the SHA256 of the exact UTF-8 body. All hygiene
    happens in validate_descriptor (single path)."""
    payload = {"sender": sender, "channel": channel, "send_at": send_at,
               "to": list(to) if isinstance(to, (list, tuple)) and not isinstance(to, bool) else to,
               "cc": list(cc) if isinstance(cc, (list, tuple)) and not isinstance(cc, bool) else cc,
               "bcc": list(bcc) if isinstance(bcc, (list, tuple)) and not isinstance(bcc, bool) else bcc,
               "subject": subject, "body": body,
               "body_sha256": (hashlib.sha256(body.encode("utf-8")).hexdigest()
                               if isinstance(body, str) else ""),
               "attachment_hashes": (list(attachment_hashes)
                                     if isinstance(attachment_hashes, (list, tuple))
                                     and not isinstance(attachment_hashes, bool)
                                     else attachment_hashes)}
    descriptor = {"class": "outreach", "module_id": module_id, "tenant_id": tenant_id,
                  "action_type": "outreach", "payload": payload}
    validate_descriptor(descriptor)
    return descriptor


def execute(descriptor, approval_id, *, actor, consume=None, effect_id=None,
            service=None, registry=None):
    """Execute an approved effect through m00 with the UNCHANGED descriptor.

    approval_id is a lookup reference, not bearer authorization. Hard-refuse
    classes refuse here too: an m00 allow can never override them. `consume`
    is the m00 consume_effect_checked callable (injected in unit tests); when
    omitted, the real m00 path is used: impact.consume_effect_checked over
    `service` (or the m00 default service)."""
    validate_descriptor(descriptor)
    cls = descriptor["class"]
    if cls in HARD_REFUSE:
        raise ValueError("POLICY_REFUSED_%s" % cls.upper())
    if cls not in GATED:
        raise ValueError("POLICY_REFUSED_NOT_EXECUTABLE:%s" % cls)
    approval_id = clean_text(approval_id, "POLICY", "approval_id", 200)
    actor = clean_text(actor, "POLICY", "actor", 120)
    if effect_id is None:
        effect_id = descriptor["payload"].get("effect_id")
    if isinstance(effect_id, bool) or not isinstance(effect_id, str) or not effect_id.strip():
        _bad("effect_id")
    if consume is None:
        from app.modules.m00_approval_center import impact
        if service is None:
            from app.modules.m00_approval_center.service import default_service
            service = default_service()
        extra = {"registry": registry} if registry is not None else {}
        consume = lambda **kw: impact.consume_effect_checked(service, **extra, **kw)
    return consume(approval_id=approval_id, module_id=descriptor["module_id"],
                   action_type=descriptor["action_type"], payload=descriptor["payload"],
                   user_id=descriptor["tenant_id"], effect_id=effect_id, actor=actor)
