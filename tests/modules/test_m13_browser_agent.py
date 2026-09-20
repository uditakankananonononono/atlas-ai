import pytest

from app.core.models import ApprovalStatus
from app.modules.m13_browser_agent.forms import FieldDescriptor, match_fields
from app.modules.m13_browser_agent.service import Service
from app.modules.m13_browser_agent.vlm_loop import NavigationLoop


class Locator:
    def __init__(self, page, selector):
        self.page, self.selector = page, selector

    async def click(self):
        self.page.clicked.append(self.selector)

    async def fill(self, value):
        self.page.filled[self.selector] = value


class Response:
    status = 200


class Page:
    def __init__(self):
        self.clicked, self.filled, self.url = [], {}, "https://example.com/form"
        self.mouse = self

    def locator(self, selector):
        return Locator(self, selector)

    async def screenshot(self, **kwargs):
        open(kwargs["path"], "wb").write(b"png")

    async def content(self):
        return "<html/>"

    async def goto(self, url, **kwargs):
        self.url = url
        return Response()

    async def wheel(self, x, y):
        self.scrolled = y


class Sessions:
    def __init__(self):
        self.p = Page()

    async def page(self, *args):
        return self.p


class Store:
    def __init__(self):
        self.used, self.events = set(), []

    async def append_audit(self, event):
        self.events.append(event)

    async def was_consumed(self, approval_id):
        return approval_id in self.used

    async def consume(self, approval_id, tenant_id):
        if approval_id in self.used:
            raise PermissionError("approval was already consumed")
        self.used.add(approval_id)


class Approvals:
    def __init__(self):
        self.rows = {}

    def submit(self, **kwargs):
        self.rows["a"] = {"id": "a", "payload": kwargs["payload"], "status": ApprovalStatus.PENDING}
        return self.rows["a"]

    def get(self, approval_id):
        return self.rows[approval_id]


def test_field_matching_is_typed_and_one_to_one():
    fields = [FieldDescriptor("#e", label="Email address", input_type="email"), FieldDescriptor("#p", label="Mobile", input_type="tel")]
    assert match_fields(fields, {"email": "a@b.com", "phone": "123"}) == {"#e": "a@b.com", "#p": "123"}


@pytest.mark.asyncio
async def test_exact_single_use_approval_is_bound_to_url_and_content(tmp_path):
    approvals, sessions, store = Approvals(), Sessions(), Store()
    service = Service(sessions, approvals, store, str(tmp_path), {"example.com"})
    request = await service.request_submit("t", "u", "r", "#go", {"name": "Ada"})
    with pytest.raises(PermissionError):
        await service.submit("t", "r", "#go", {"name": "Ada"}, request["approval_id"])
    approvals.rows["a"]["status"] = ApprovalStatus.APPROVED
    with pytest.raises(PermissionError):
        await service.submit("t", "r", "#go", {"name": "Changed"}, "a")
    sessions.p.url = "https://example.com/other"
    with pytest.raises(PermissionError):
        await service.submit("t", "r", "#go", {"name": "Ada"}, "a")
    sessions.p.url = "https://example.com/form"
    await service.submit("t", "r", "#go", {"name": "Ada"}, "a")
    assert sessions.p.clicked == ["#go"]
    with pytest.raises(PermissionError):
        await service.submit("t", "r", "#go", {"name": "Ada"}, "a")


@pytest.mark.asyncio
async def test_fill_does_not_put_values_in_audit(tmp_path):
    service = Service(Sessions(), Approvals(), Store(), str(tmp_path))
    await service.fill("t", "r", [FieldDescriptor("#e", label="Email", input_type="email")], {"email": "secret@example.com"})
    event = service.store.events[-1]
    assert event.payload == {"selectors": ["#e"], "count": 1}


class Planner:
    async def next_action(self, instruction, screenshot_path, history):
        return {"type": "click", "selector": "#pay", "is_submit": True, "form_values": {"amount": "10"}}


@pytest.mark.asyncio
async def test_visual_loop_stages_submit_without_clicking(tmp_path):
    approvals, sessions, store = Approvals(), Sessions(), Store()
    service = Service(sessions, approvals, store, str(tmp_path), {"example.com"})
    result = await NavigationLoop(service, Planner()).run("t", "r", "pay", actor_id="u")
    assert result["status"] == "awaiting_approval"
    assert sessions.p.clicked == []
