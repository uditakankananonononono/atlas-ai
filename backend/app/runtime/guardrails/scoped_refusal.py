"""Fail-closed unavailable effect routes, never a boolean approval substitute.

Only explicitly named unmapped person-facing/account-effect paths use this
boundary. Read, model and local preparation paths do not call it. Enabling a
path later requires a separate exact authority/transport binding implementation.
"""

def refuse_unbound_effect(effect: str) -> None:
    raise PermissionError('EFFECT_UNBOUND_REFUSED: ' + effect)
