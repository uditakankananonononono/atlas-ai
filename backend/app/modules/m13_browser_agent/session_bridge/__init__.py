"""Paired-PC session bridge: drive the owner's own logged-in browser sessions.

The bridge connects the M13 browser agent to a daemon running on the owner's
own PC. Pages live on her machine, in her browser, inside sessions she logged
into herself. Atlas never receives her cookies or passwords; it sends commands
and receives results, each one receipted on a hash chain the server verifies.

Boundaries (settled with the owner):
- read-only first; writes (anything that posts, follows, messages, or pays)
  stay behind the existing capture-bound, single-use approval flow;
- human-speed pacing on both sides of the wire;
- a login wall, challenge, or rate limit is reported as a limit, never
  worked around with retries, rotation, or evasion.
"""
