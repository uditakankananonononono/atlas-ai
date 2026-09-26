# Paired-PC session bridge (M13) + social reading layer (M06)

## What this is

Atlas's M13 browser agent runs headless Chromium on the server with fresh,
logged-out contexts. The session bridge closes that gap: a daemon on the
owner's own PC drives her real browser - attached over CDP to a Chrome she
already has running, or a dedicated persistent profile - so Atlas can read
pages inside sessions she logged into herself. Her cookies and passwords
never leave the machine; Atlas sends commands and receives results, each
receipted on a hash chain verified server-side
(`POST /api/v1/browser-agent/bridge/devices/{id}/verify-receipt`).

The social reading layer (M06 `social_reading/`) uses the bridge to read her
Instagram and LinkedIn follower lists and feeds, stores people and observed
work with provenance, and can harvest high-signal posts into M19 as captured
ideas for her review.

## Setup

1. In Atlas (tenant-authenticated): `POST /api/v1/browser-agent/bridge/pairing-challenge`
   returns a one-time code and nonce.
2. On her PC (Python 3.12+, `pip install playwright httpx websockets cryptography instaloader`,
   `playwright install chromium`):
   `python -m app.modules.m13_browser_agent.pc_daemon pair --server URL --nonce N --code 123456 --name "My laptop"`
3. Run it: `python -m app.modules.m13_browser_agent.pc_daemon run`
   or attach to her running Chrome: `... run --cdp-url http://127.0.0.1:9222`
   (start Chrome with `--remote-debugging-port=9222`).
4. Bridged sessions are named `pc.<device_id>.<name>` and work with every
   existing M13 endpoint, including the capture-bound submit flow.
5. Instagram follower/feed reads additionally need a local instaloader login
   on her PC: `instaloader --login <username>`. The session file stays on the
   machine and is never uploaded.

## Hard boundaries (enforced in code, daemon-side and server-side)

- **Approval-gated writes.** Any click that submits (post, comment, DM,
  follow, pay) only runs through the existing capture-bound, single-use
  approval flow. After the approval is consumed, the server arms exactly one
  click with an HMAC token over (approval_id, capture hash, selector, values
  digest); the daemon independently verifies the token before clicking. No
  token, no click. A failed click never replays - it needs a new capture and
  a new approval.
- **Capabilities are granted at pairing**, per device, and revocable at any
  time (`DELETE .../devices/{id}`). The daemon refuses anything outside its
  granted set.
- **Human-speed pacing** on both sides of the wire (default 5s between
  actions, clamped to 2-120s).
- **Blocks are surfaced, never evaded.** A login wall, challenge/CAPTCHA, or
  HTTP 429 stops the command and is reported as `blocked` with the reason.
  There is no retry loop, no account rotation, no header spoofing.
- **Read-only social layer.** `social_reading/` never posts, follows, likes,
  comments, or messages. Outreach stays in M06's approval-gated publishing
  path.

## Honest limits

- Platform terms of service may restrict automated access, including
  read-only access through a logged-in session. Instagram in particular has
  no official API for personal-account follower lists; that is why the read
  goes through her own session at human speed, and why any challenge stops
  the run instead of being worked around.
- LinkedIn parsing depends on the current page structure; parsers degrade
  gracefully (partial results, never invented data) but a LinkedIn layout
  change can reduce yield until the parser is updated.
- The daemon is not yet a signed installer with OS-keystore identity, native
  permission prompts, or a kill switch - those remain on the README gap list
  for the paired computer.
