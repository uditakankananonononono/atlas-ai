"""End-to-end opportunity application browser workflow (modules 1/2/13 share this engine).

One owner-driven flow: start a tenant-isolated paired browser session at an
opportunity's official application URL, pause for the owner to log in
themselves, inspect the form, stage only owner-approved grounded fields, read
back exact values, capture a redacted screenshot, and bind a separate
final-submit approval to tenant, actor, session, URL, selector, exact values
hash, and screenshot hash. The submit click executes exactly once, only after
approval, and every outcome - including CAPTCHA, site redesign, and click
failure - is reported honestly.

Atlas never accepts, stores, or transmits passwords, MFA codes, cookies, or
tokens. The owner types credentials into their own paired browser; API
payloads containing credential-shaped keys are rejected.

No FastAPI imports live here; the HTTP surface is
``m02_competition_manager.application_routes``.
"""
from __future__ import annotations

import re
import secrets
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Protocol

from bs4 import BeautifulSoup

from .domain import ActionType, AuditEvent
from .forms import FieldDescriptor, match_fields_detailed
from .security import NavigationBlocked, file_digest, validate_public_url, values_digest


class WorkflowStatus(str, Enum):
    CREATED = "created"
    AWAITING_USER_LOGIN = "awaiting_user_login"
    READY = "ready"
    STAGED = "staged"
    AWAITING_SUBMIT_APPROVAL = "awaiting_submit_approval"
    SUBMITTED = "submitted"
    BLOCKED = "blocked"
    FAILED = "failed"


class ApplicationFlowError(RuntimeError):
    """Base error for workflow violations."""


class SessionNotFoundError(ApplicationFlowError, KeyError):
    """No such session inside this tenant."""


class ActorMismatchError(ApplicationFlowError, PermissionError):
    """The session belongs to a different owner actor."""


class CredentialRejectedError(ApplicationFlowError, ValueError):
    """A payload carried credential-shaped keys Atlas must never accept."""


class WorkflowStateError(ApplicationFlowError):
    """The requested step does not fit the session's current state."""


class BlockedError(ApplicationFlowError):
    """The site itself blocks honest automation (CAPTCHA, redesign)."""


# Keys are normalized (lowercase, alphanumerics only) before matching, so
# "Password", "pass-word", "mfa_code" and "OTP" all trip the same gate.
_CREDENTIAL_KEYS = {
    "password", "passcode", "passwd", "pwd", "otp", "mfacode", "mfa",
    "totp", "2fa", "onetimecode", "verificationcode", "securitycode",
    "cookie", "cookies", "setcookie", "sessiontoken", "sessionid",
    "authtoken", "accesstoken", "refreshtoken", "bearertoken", "csrftoken",
    "secret", "secretkey", "apikey", "privatekey",
}

_LOGIN_URL_HINT = re.compile(r"/(login|log-in|signin|sign-in|sign-in|auth|sso|account)(/|$|[?#])", re.I)
_LOGIN_TEXT_HINTS = ("sign in to continue", "log in to continue", "you must log in", "please sign in", "create an account")
_CAPTCHA_HINTS = ("recaptcha", "g-recaptcha", "hcaptcha", "h-captcha", "cf-challenge", "cf-turnstile", "verify you are human", "are you a robot")

PAIRED_LOGIN_INSTRUCTIONS = (
    "Open the paired Atlas browser pane for this exact session on your own device.",
    "Log in yourself with your own username, password, and MFA - type them only into the site.",
    "Never send your password, MFA codes, cookies, or tokens to Atlas; Atlas rejects them.",
    "When the site shows your logged-in application form, confirm login to resume this workflow.",
)


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def assert_no_credentials(payload: dict[str, Any], path: str = "") -> None:
    """Reject any payload containing credential-shaped keys, recursively."""
    for key, value in payload.items():
        location = f"{path}.{key}" if path else str(key)
        if _normalize_key(str(key)) in _CREDENTIAL_KEYS:
            raise CredentialRejectedError(
                f"credentials are never accepted here: rejected key '{location}'"
            )
        if isinstance(value, dict):
            assert_no_credentials(value, location)


@dataclass
class AuthProbe:
    required: bool
    evidence: list[str] = field(default_factory=list)


def probe_auth(page_url: str, html: str) -> AuthProbe:
    """Honest heuristic: report whether the page is a login wall, with evidence.

    A password input alone is not a login wall - plenty of application forms
    create an account. It only counts when the page offers few other fillable
    fields, which is what real login walls look like.
    """
    evidence: list[str] = []
    if _LOGIN_URL_HINT.search(page_url):
        evidence.append(f"url matches login pattern: {page_url}")
    lowered = html.lower()
    if 'type="password"' in lowered or "type='password'" in lowered:
        other_fields = [d for d in extract_field_descriptors(html) if d.input_type != "password"]
        if len(other_fields) <= 2:
            evidence.append("password input present on a minimal form (login wall)")
    for hint in _LOGIN_TEXT_HINTS:
        if hint in lowered:
            evidence.append(f"page text: '{hint}'")
    return AuthProbe(required=bool(evidence), evidence=evidence)


def probe_captcha(html: str) -> list[str]:
    lowered = html.lower()
    return [hint for hint in _CAPTCHA_HINTS if hint in lowered]


def extract_field_descriptors(html: str, max_fields: int = 200) -> list[FieldDescriptor]:
    """Ground form descriptors in the page's own HTML - never invented selectors."""
    soup = BeautifulSoup(html, "html.parser")
    labels = {
        tag["for"]: tag.get_text(" ", strip=True)
        for tag in soup.find_all("label") if tag.get("for")
    }
    descriptors: list[FieldDescriptor] = []
    for element in soup.find_all(["input", "textarea", "select"]):
        if len(descriptors) >= max_fields:
            break
        input_type = (element.get("type") or ("textarea" if element.name == "textarea" else "text")).lower()
        if input_type in {"hidden", "submit", "button", "file", "image", "reset"}:
            continue
        element_id = element.get("id") or ""
        name = element.get("name") or ""
        if element_id:
            selector = f"#{element_id}"
        elif name:
            selector = f'{element.name}[name="{name}"]'
        else:
            continue
        label = labels.get(element_id, "")
        if not label and element.parent and element.parent.name == "label":
            label = element.parent.get_text(" ", strip=True)
        descriptors.append(FieldDescriptor(
            selector=selector,
            label=label,
            name=name,
            placeholder=element.get("placeholder") or "",
            input_type=input_type,
            required=element.has_attr("required"),
        ))
    return descriptors


@dataclass
class ApplicationSession:
    tenant_id: str
    session_id: str
    actor_id: str
    url: str
    opportunity_kind: str = ""       # "competition" | "opportunity" | "direct"
    opportunity_id: str = ""
    label: str = ""
    status: str = WorkflowStatus.CREATED.value
    submit_selector: str = ""
    form_selectors: list[str] = field(default_factory=list)
    staged_values: dict[str, str] = field(default_factory=dict)   # selector -> exact readback value
    values_digest: str = ""
    screenshot_path: str = ""
    screenshot_digest: str = ""
    approval_id: str = ""
    confirmation: dict[str, Any] = field(default_factory=dict)
    instructions: list[str] = field(default_factory=list)
    error: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApplicationSession":
        return cls(**data)

    def public_view(self) -> dict[str, Any]:
        """Owner-facing record: every state, digests, evidence - never staged raw values."""
        view = self.to_dict()
        view["staged_fields"] = sorted(self.staged_values)
        view.pop("staged_values", None)
        return view


class ApplicationSessionStore(Protocol):
    def create(self, record: ApplicationSession) -> ApplicationSession: ...
    def get(self, tenant_id: str, session_id: str) -> ApplicationSession | None: ...
    def save(self, record: ApplicationSession) -> ApplicationSession: ...


class BrowserSurface(Protocol):
    """The slice of the Module 13 service this flow drives."""
    sessions: Any
    approvals: Any
    store: Any
    allowed_hosts: Any

    async def navigate(self, tenant_id: str, session_id: str, url: str, persistent: bool = False) -> dict[str, Any]: ...
    async def fill(self, tenant_id: str, session_id: str, fields: list[FieldDescriptor], data: dict[str, str]) -> dict[str, str]: ...
    async def read_values(self, tenant_id: str, session_id: str, selectors: list[str]) -> dict[str, str]: ...
    async def screenshot(self, tenant_id: str, session_id: str, mask_selectors: list[str] | None = None) -> str: ...
    async def extract(self, tenant_id: str, session_id: str) -> str: ...


class ApplicationFlow:
    """Orchestrate the owner-driven application workflow over Module 13 primitives."""

    SUBMIT_TTL_SECONDS = 3600

    def __init__(
        self,
        browser: BrowserSurface,
        session_store: ApplicationSessionStore,
        approvals: Any = None,
        clock: Callable[[], datetime] | None = None,
    ):
        self.browser = browser
        self.store = session_store
        self.approvals = approvals if approvals is not None else browser.approvals
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    # -- internal helpers -------------------------------------------------

    def _record(self, tenant_id: str, session_id: str) -> ApplicationSession:
        record = self.store.get(tenant_id, session_id)
        if record is None:
            raise SessionNotFoundError(session_id)
        return record

    @staticmethod
    def _require_actor(record: ApplicationSession, actor_id: str) -> None:
        if record.actor_id != actor_id:
            raise ActorMismatchError("session belongs to a different actor")

    def _save(self, record: ApplicationSession) -> ApplicationSession:
        record.updated_at = time.time()
        return self.store.save(record)

    async def _audit(self, record: ApplicationSession, action: ActionType, payload: dict[str, Any]) -> None:
        await self.browser.store.append_audit(
            AuditEvent(record.tenant_id, record.session_id, action, payload)
        )

    async def _page(self, record: ApplicationSession):
        return await self.browser.sessions.page(record.tenant_id, record.session_id, True)

    async def _probe_page(self, record: ApplicationSession) -> tuple[Any, str, AuthProbe, list[str]]:
        page = await self._page(record)
        final_url = validate_public_url(page.url, self.browser.allowed_hosts)
        html = await self.browser.extract(record.tenant_id, record.session_id)
        return page, final_url, probe_auth(final_url, html), probe_captcha(html)

    def _blocked(self, record: ApplicationSession, reason: str, evidence: list[str]) -> ApplicationSession:
        record.status = WorkflowStatus.BLOCKED.value
        record.error = f"{reason} | evidence: {evidence}" if evidence else reason
        return self._save(record)

    # -- workflow steps ---------------------------------------------------

    async def start(
        self,
        tenant_id: str,
        actor_id: str,
        url: str,
        opportunity_kind: str = "direct",
        opportunity_id: str = "",
        label: str = "",
    ) -> ApplicationSession:
        """Create the paired session and navigate to the official application URL."""
        safe_url = validate_public_url(url, self.browser.allowed_hosts)
        record = ApplicationSession(
            tenant_id=tenant_id,
            session_id=f"app-{secrets.token_hex(8)}",
            actor_id=actor_id,
            url=safe_url,
            opportunity_kind=opportunity_kind,
            opportunity_id=opportunity_id,
            label=label,
        )
        self.store.create(record)
        await self.browser.navigate(tenant_id, record.session_id, safe_url, persistent=True)
        _, final_url, auth, captcha = await self._probe_page(record)
        record.url = final_url
        if captcha:
            await self._audit(record, ActionType.EXTRACT, {"phase": "start", "blocked": "captcha", "evidence": captcha})
            return self._blocked(record, "site presents a CAPTCHA; Atlas does not solve or bypass CAPTCHAs", captcha)
        if auth.required:
            record.status = WorkflowStatus.AWAITING_USER_LOGIN.value
            record.instructions = list(PAIRED_LOGIN_INSTRUCTIONS)
            await self._audit(record, ActionType.LOGIN, {"phase": "required", "evidence": auth.evidence})
            return self._save(record)
        record.status = WorkflowStatus.READY.value
        await self._audit(record, ActionType.LOGIN, {"phase": "not_required"})
        return self._save(record)

    async def resume(self, tenant_id: str, actor_id: str, session_id: str, login_confirmed: bool) -> ApplicationSession:
        """Resume after the owner confirms they logged in inside the paired session."""
        if not login_confirmed:
            raise WorkflowStateError("login must be explicitly confirmed by the owner to resume")
        record = self._record(tenant_id, session_id)
        self._require_actor(record, actor_id)
        if record.status == WorkflowStatus.READY.value:
            return record
        if record.status != WorkflowStatus.AWAITING_USER_LOGIN.value:
            raise WorkflowStateError(f"cannot resume a session in state '{record.status}'")
        _, final_url, auth, captcha = await self._probe_page(record)
        record.url = final_url
        if captcha:
            await self._audit(record, ActionType.EXTRACT, {"phase": "resume", "blocked": "captcha", "evidence": captcha})
            return self._blocked(record, "site presents a CAPTCHA after login; Atlas stops here", captcha)
        if auth.required:
            await self._audit(record, ActionType.LOGIN, {"phase": "still_required", "evidence": auth.evidence})
            record.error = "login still required: the paired session does not look logged in yet"
            return self._save(record)
        record.error = ""
        record.status = WorkflowStatus.READY.value
        await self._audit(record, ActionType.LOGIN, {"phase": "completed"})
        return self._save(record)

    async def inspect(self, tenant_id: str, actor_id: str, session_id: str) -> dict[str, Any]:
        """Extract grounded form descriptors from the live page."""
        record = self._record(tenant_id, session_id)
        self._require_actor(record, actor_id)
        if record.status not in {WorkflowStatus.READY.value, WorkflowStatus.STAGED.value}:
            raise WorkflowStateError(f"cannot inspect a session in state '{record.status}'")
        html = await self.browser.extract(tenant_id, session_id)
        captcha = probe_captcha(html)
        if captcha:
            self._blocked(record, "site presents a CAPTCHA; Atlas stops here", captcha)
            raise BlockedError(record.error)
        descriptors = extract_field_descriptors(html)
        if not descriptors:
            self._blocked(record, "no fillable form fields found; the site may have changed", ["empty descriptor set"])
            raise BlockedError(record.error)
        record.form_selectors = [d.selector for d in descriptors]
        self._save(record)
        await self._audit(record, ActionType.EXTRACT, {
            "phase": "inspect", "field_count": len(descriptors), "selectors": record.form_selectors,
        })
        return {"session_id": session_id, "fields": [d.__dict__ for d in descriptors]}

    async def stage(
        self,
        tenant_id: str,
        actor_id: str,
        session_id: str,
        approved_fields: dict[str, str],
        submit_selector: str,
    ) -> dict[str, Any]:
        """Stage only owner-approved grounded fields; never submit.

        Returns the exact readback preview: requested vs on-page values per
        selector, plus the redacted screenshot and both digests.
        """
        assert_no_credentials(approved_fields)
        record = self._record(tenant_id, session_id)
        self._require_actor(record, actor_id)
        if record.status not in {
            WorkflowStatus.READY.value, WorkflowStatus.STAGED.value,
            WorkflowStatus.AWAITING_SUBMIT_APPROVAL.value, WorkflowStatus.FAILED.value,
        }:
            raise WorkflowStateError(f"cannot stage a session in state '{record.status}'")
        if not record.form_selectors:
            raise WorkflowStateError("inspect the form before staging values")
        html = await self.browser.extract(tenant_id, session_id)
        captcha = probe_captcha(html)
        if captcha:
            self._blocked(record, "site presents a CAPTCHA; Atlas stops here", captcha)
            raise BlockedError(record.error)
        descriptors = extract_field_descriptors(html)
        known = {d.selector for d in descriptors}
        if set(record.form_selectors) - known:
            self._blocked(record, "form structure changed since inspection", sorted(set(record.form_selectors) - known))
            raise BlockedError(record.error)

        fillable = [d for d in descriptors if d.input_type != "password"]
        skipped_password = [d.selector for d in descriptors if d.input_type == "password"]
        # Conservative grounding: only values that mapped one-to-one are staged.
        mapping, used_keys = match_fields_detailed(fillable, approved_fields)
        unmapped = sorted(set(approved_fields) - used_keys)
        missing = sorted(set(mapping) - known)
        if missing:
            raise WorkflowStateError(f"resolved selectors are not on the page: {missing}")
        await self.browser.fill(tenant_id, session_id, fillable, approved_fields)
        readback = await self.browser.read_values(tenant_id, session_id, sorted(mapping))
        screenshot = await self.browser.screenshot(tenant_id, session_id, mask_selectors=sorted(mapping) + skipped_password)
        record.submit_selector = submit_selector
        record.staged_values = dict(readback)
        record.values_digest = values_digest(readback)
        record.screenshot_path = screenshot
        record.screenshot_digest = file_digest(screenshot)
        record.status = WorkflowStatus.STAGED.value
        record.error = ""
        self._save(record)
        preview = {
            selector: {
                "requested": mapping[selector],
                "on_page": readback[selector],
                "matches": mapping[selector] == readback[selector],
            }
            for selector in sorted(mapping)
        }
        await self._audit(record, ActionType.FILL, {
            "phase": "staged",
            "selectors": sorted(mapping),
            "unmapped_approved_fields": unmapped,
            "skipped_password_selectors": skipped_password,
            "values_digest": record.values_digest,
            "screenshot_digest": record.screenshot_digest,
            "readback_mismatches": sorted(s for s, p in preview.items() if not p["matches"]),
        })
        return {
            "session_id": session_id,
            "status": record.status,
            "preview": preview,
            "unmapped_approved_fields": unmapped,
            "skipped_password_selectors": skipped_password,
            "screenshot_path": screenshot,
            "screenshot_digest": record.screenshot_digest,
            "values_digest": record.values_digest,
            "submitted": False,
        }

    async def _verify_staged_snapshot(self, record: ApplicationSession) -> dict[str, Any]:
        """Re-read the live page and return the current binding facts."""
        page = await self._page(record)
        current_url = validate_public_url(page.url, self.browser.allowed_hosts)
        readback = await self.browser.read_values(record.tenant_id, record.session_id, sorted(record.staged_values))
        screenshot = await self.browser.screenshot(
            record.tenant_id, record.session_id, mask_selectors=sorted(record.staged_values)
        )
        return {
            "page_url": current_url,
            "form_values": readback,
            "values_digest": values_digest(readback),
            "screenshot_path": screenshot,
            "screenshot_digest": file_digest(screenshot),
        }

    async def request_final_submit(self, tenant_id: str, actor_id: str, session_id: str) -> dict[str, Any]:
        """Create the separate final-submit approval bound to exact current facts."""
        record = self._record(tenant_id, session_id)
        self._require_actor(record, actor_id)
        if record.status not in {
            WorkflowStatus.STAGED.value, WorkflowStatus.AWAITING_SUBMIT_APPROVAL.value,
        }:
            raise WorkflowStateError(f"cannot request final submit from state '{record.status}'")
        current = await self._verify_staged_snapshot(record)
        if current["form_values"] != record.staged_values:
            await self._audit(record, ActionType.SUBMIT, {"phase": "restage_required", "reason": "values changed since staging"})
            raise WorkflowStateError("page values changed since staging; stage again before requesting approval")
        payload = {
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "session_id": session_id,
            "selector": record.submit_selector,
            "form_values": current["form_values"],
            "values_digest": current["values_digest"],
            "page_url": current["page_url"],
            "screenshot_path": current["screenshot_path"],
            "screenshot_digest": current["screenshot_digest"],
        }
        view = self.approvals.submit(
            module_id=2,
            action_type="application_final_submit",
            user_id=tenant_id,
            payload=payload,
            ttl_seconds=self.SUBMIT_TTL_SECONDS,
        )
        record.approval_id = view["id"]
        record.screenshot_path = current["screenshot_path"]
        record.screenshot_digest = current["screenshot_digest"]
        record.status = WorkflowStatus.AWAITING_SUBMIT_APPROVAL.value
        self._save(record)
        await self._audit(record, ActionType.SUBMIT, {
            "phase": "approval_requested",
            "approval_id": view["id"],
            "selector": record.submit_selector,
            "values_digest": current["values_digest"],
            "screenshot_digest": current["screenshot_digest"],
            "page_url": current["page_url"],
        })
        return {
            "session_id": session_id,
            "status": record.status,
            "approval_id": view["id"],
            "bound": {k: payload[k] for k in ("tenant_id", "actor_id", "session_id", "selector", "values_digest", "page_url", "screenshot_digest")},
            "submitted": False,
        }

    async def execute_submit(self, tenant_id: str, actor_id: str, session_id: str, approval_id: str) -> dict[str, Any]:
        """Click the submit selector exactly once, only against an exact approval."""
        record = self._record(tenant_id, session_id)
        self._require_actor(record, actor_id)
        try:
            view = self.approvals.get(approval_id)
        except Exception as error:
            raise PermissionError("approval not found") from error
        payload = view.get("payload", {})
        status = view.get("status")
        status = status.value if hasattr(status, "value") else status
        expected_identity = {
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "session_id": session_id,
            "selector": record.submit_selector,
        }
        if status != "approved":
            raise PermissionError(f"approval is {status}, not approved")
        # The approval center keeps decided rows final; the execution TTL is
        # enforced here, at the moment of the irreversible effect.
        expires_at = view.get("expires_at")
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if self._clock() > expires_at:
                await self._audit(record, ActionType.SUBMIT, {"phase": "refused", "reason": "approval expired", "approval_id": approval_id})
                raise PermissionError("approval has expired; request a fresh one")
        mismatched = sorted(k for k, v in expected_identity.items() if payload.get(k) != v)
        if mismatched:
            raise PermissionError(f"approval is bound to different {', '.join(mismatched)}")

        page = await self._page(record)
        try:
            current_url = validate_public_url(page.url, self.browser.allowed_hosts)
            readback = await self.browser.read_values(tenant_id, session_id, sorted(payload.get("form_values", {})))
            screenshot = await self.browser.screenshot(tenant_id, session_id, mask_selectors=sorted(readback))
        except Exception as error:
            await self._audit(record, ActionType.SUBMIT, {"phase": "refused", "reason": f"page no longer matches approval: {error}", "approval_id": approval_id})
            raise PermissionError(f"page no longer matches the approval ({error}); a fresh approval is required") from error
        current = {
            "page_url": current_url,
            "values_digest": values_digest(readback),
            "screenshot_digest": file_digest(screenshot),
        }
        drift = sorted(k for k, v in current.items() if payload.get(k) != v)
        if drift:
            await self._audit(record, ActionType.SUBMIT, {"phase": "refused", "reason": f"changed since approval: {drift}", "approval_id": approval_id})
            raise PermissionError(f"page changed since approval ({', '.join(drift)}); a fresh approval is required")
        if readback != payload.get("form_values"):
            raise PermissionError("approved form values no longer match the page")
        if await self.browser.store.was_consumed(approval_id):
            await self._audit(record, ActionType.SUBMIT, {"phase": "refused", "reason": "approval replay", "approval_id": approval_id})
            raise PermissionError("approval was already consumed")

        # Consume before the external effect: a failed click cannot replay.
        await self.browser.store.consume(approval_id, tenant_id)
        try:
            await page.locator(payload["selector"]).click()
        except Exception as error:
            record.status = WorkflowStatus.FAILED.value
            record.error = f"submit click failed: {error}"
            self._save(record)
            await self._audit(record, ActionType.SUBMIT, {
                "phase": "failed", "approval_id": approval_id, "selector": payload["selector"], "error": str(error),
            })
            raise BlockedError(f"submit click failed; the approval is consumed and the application was not submitted: {error}") from error

        # Source readback: only what the site itself shows afterwards counts.
        final_url = validate_public_url(page.url, self.browser.allowed_hosts)
        html = await self.browser.extract(tenant_id, session_id)
        captcha = probe_captcha(html)
        if captcha:
            await self._audit(record, ActionType.SUBMIT, {"phase": "blocked_after_click", "evidence": captcha, "approval_id": approval_id})
            self._blocked(record, "site presented a CAPTCHA after the submit click; confirm the outcome manually", captcha)
            raise BlockedError(record.error)
        record.confirmation = {
            "final_url": final_url,
            "page_excerpt": re.sub(r"\s+", " ", html)[:500],
            "observed_at": time.time(),
            "approval_id": approval_id,
        }
        record.status = WorkflowStatus.SUBMITTED.value
        record.error = ""
        self._save(record)
        await self._audit(record, ActionType.SUBMIT, {
            "phase": "executed",
            "approval_id": approval_id,
            "selector": payload["selector"],
            "values_digest": current["values_digest"],
            "final_url": final_url,
        })
        return {"session_id": session_id, "status": record.status, "submitted": True, "confirmation": dict(record.confirmation)}

    def status(self, tenant_id: str, actor_id: str, session_id: str) -> dict[str, Any]:
        record = self._record(tenant_id, session_id)
        self._require_actor(record, actor_id)
        return record.public_view()
