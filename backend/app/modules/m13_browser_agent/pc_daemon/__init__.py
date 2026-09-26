"""The paired-PC daemon: runs on the owner's own machine.

It drives her real browser - either attached over CDP to a Chrome she already
has running, or a persistent local profile - so Atlas works inside sessions
she logged into herself. Credentials never leave the machine.

Hard rules enforced here, not just on the server:
- only capabilities granted at pairing are executed;
- human-speed pacing between actions;
- CLICK_SUBMIT runs only with a valid one-shot HMAC token minted by the
  server after it consumed the matching approval;
- a login wall, challenge, or rate limit stops the command and is reported
  as blocked; there is no retry, no rotation, no evasion.
"""
