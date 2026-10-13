"""Rows 65-76 evidence sheets: added sensitivity tests for sites the older selectors did not kill.
Offline fixtures only. No platform, account or network is contacted."""
import asyncio
import hashlib
import pathlib

import pytest

from app.modules.m22_tools_hub import (
    ApprovalStore, InstallError, ReviewDecision, ReviewRecord, ToolInstaller, _install_subject, _rollback_subject)
from tests.modules.test_m22_secure_installer import artifact, manifest_for, review_for


# ---- row 70: installer gates
def _setup(tmp_path, files):
    approvals = ApprovalStore(tmp_path / "ap.json")
    inst = ToolInstaller(tmp_path / "hub", approvals)
    blob = artifact(files)
    man = manifest_for(blob, files)
    grant = approvals.issue(action="tool.install", subject_digest=_install_subject(man), approved_by="reviewer", requested_by="builder")
    return approvals, inst, blob, man, grant


def test_install_refuses_failed_scan_even_with_pass_review_and_approval(tmp_path):
    _, inst, blob, man, grant = _setup(tmp_path, {"run.py": b"import os\nos.system('whoami')\n"})
    with pytest.raises(InstallError, match="scan did not pass"):
        inst.install(artifact=blob, manifest=man, review=review_for(man), approval_token=grant.token, actor="builder")
    assert not (tmp_path / "hub/tools/safe-tool").exists()


def test_install_refuses_non_pass_review(tmp_path):
    _, inst, blob, man, grant = _setup(tmp_path, {"run.py": b"print('ok')\n"})
    bad = ReviewRecord("reviewer", next(d for d in ReviewDecision if d is not ReviewDecision.PASS),
                       man.provenance.artifact_sha256, man.digest)
    with pytest.raises(InstallError, match="not pass"):
        inst.install(artifact=blob, manifest=man, review=bad, approval_token=grant.token, actor="builder")


def test_rollback_without_prior_version_and_with_missing_backup_refuses(tmp_path):
    approvals, inst, blob, man, grant = _setup(tmp_path, {"run.py": b"print('v1')\n"})
    first = inst.install(artifact=blob, manifest=man, review=review_for(man), approval_token=grant.token, actor="builder")
    g = approvals.issue(action="tool.rollback", subject_digest=_rollback_subject(first), approved_by="reviewer", requested_by="builder")
    with pytest.raises(InstallError, match="no prior version"):
        inst.rollback(operation_id=first.operation_id, approval_token=g.token, actor="builder")
    files2 = {"run.py": b"print('v2')\n"}
    blob2 = artifact(files2)
    man2 = manifest_for(blob2, files2, version="2.0.0")
    g2 = approvals.issue(action="tool.install", subject_digest=_install_subject(man2), approved_by="reviewer", requested_by="builder")
    second = inst.install(artifact=blob2, manifest=man2, review=review_for(man2), approval_token=g2.token, actor="builder")
    import shutil
    shutil.rmtree(inst.backups_dir / second.backup_id)
    g3 = approvals.issue(action="tool.rollback", subject_digest=_rollback_subject(second), approved_by="reviewer", requested_by="builder")
    with pytest.raises(InstallError, match="backup is missing"):
        inst.rollback(operation_id=second.operation_id, approval_token=g3.token, actor="builder")


# ---- row 71: Pinterest read guards (reader), fake pages
from app.modules.m06_social_media_manager.social_reading.knowledge import KnowledgeStore
from app.modules.m06_social_media_manager.social_reading.reader import SocialReader
from app.modules.m13_browser_agent.session_bridge.protocol import BlockKind, PlatformBlocked
from app.core.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class _Resp:
    def __init__(self, status):
        self.status = status


class _Page:
    def __init__(self, status=200, final="https://www.pinterest.com/", html="<html></html>"):
        self.status, self.final, self.html, self.url = status, final, html, "about:blank"
        self.goto_calls = []

    async def goto(self, url, wait_until="domcontentloaded"):
        self.goto_calls.append(url)
        self.url = self.final
        return _Resp(self.status)

    async def content(self):
        return self.html


class _Sessions:
    def __init__(self, page):
        self.p = page

    async def page(self, tenant_id, session_id, persistent=False):
        return self.p


def _reader(page):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return SocialReader(_Sessions(page), KnowledgeStore(sessionmaker(bind=engine)))


def _run(reader, **kw):
    args = dict(platform="pinterest", operation="feed", session_id="pc.dev.main")
    args.update(kw)
    return asyncio.run(reader.run("t", **args))


def test_pinterest_read_needs_paired_pc_session():
    page = _Page()
    with pytest.raises(ValueError, match="paired-PC"):
        _run(_reader(page), session_id="cloud-session")
    assert page.goto_calls == []


@pytest.mark.parametrize("limit", [0, 501, True, "5"])
def test_pinterest_limit_must_be_int_1_to_500(limit):
    page = _Page()
    with pytest.raises(ValueError, match="limit must be integer"):
        _run(_reader(page), limit=limit)
    assert page.goto_calls == []


def test_pinterest_429_is_rate_limit_block_and_4xx_is_policy_block():
    with pytest.raises(PlatformBlocked) as e:
        _run(_reader(_Page(status=429)))
    assert e.value.kind is BlockKind.RATE_LIMIT
    with pytest.raises(PlatformBlocked) as e:
        _run(_reader(_Page(status=403)))
    assert e.value.kind is BlockKind.POLICY


def test_pinterest_redirect_to_other_host_or_login_is_blocked():
    with pytest.raises(PlatformBlocked) as e:
        _run(_reader(_Page(final="https://evil.example/")))
    assert e.value.kind is BlockKind.POLICY
    with pytest.raises(PlatformBlocked) as e:
        _run(_reader(_Page(final="https://www.pinterest.com/login/")))
    assert e.value.kind is BlockKind.LOGIN_WALL


# ---- rows 67/72: integrated application flow
from app.core.models import ApprovalStatus
from app.modules.m02_competition_manager.grounded_drafting import GroundedApplicationDrafter
from app.modules.m02_competition_manager.humanize import HumanizedAnswer, NaturalVoiceService
from app.modules.m02_competition_manager.integrated_application import IntegratedApplicationFlow


class _FlowApprovals:
    """In-memory approvals fake: the flow tests own their fixture and never touch the shared approval database."""
    def __init__(self):
        self.items = []

    def put(self, item, *, user_id=None):
        item.status = ApprovalStatus.PENDING
        self.items.append(item)
        return item


class _Corpus:
    async def retrieve(self, q, limit):
        return [{'id': 1, 'title': 't', 'source_type': 'google_doc', 'source_id': 'doc1', 'locator': 'l',
                 'text': 'In 2025, I built Atlas and improved accuracy by 20%.', 'provenance': {'revision_id': 'r1'}}]


async def _gen(prompt, provider, model):
    return 'm', 'In 2025, I built Atlas and improved accuracy by 20%. [1]'


class _Voice:
    def __init__(self, ok, text="VOICED"):
        self.ok, self.text = ok, text

    async def humanize(self, field, draft, provider):
        return HumanizedAnswer(field, draft, self.text, 'm', self.ok)


FIELDS = [{'field': 'impact', 'question': 'What did you build?'}]


def test_flow_refuses_when_voice_pass_changed_facts():
    f = IntegratedApplicationFlow(_Corpus(), GroundedApplicationDrafter(_gen), _Voice(False), _FlowApprovals(), 'tenant-a')
    with pytest.raises(ValueError, match="changed factual anchors"):
        asyncio.run(f.prepare('c', 'https://official', FIELDS))


def test_flow_stages_the_humanized_text_not_the_raw_draft():
    f = IntegratedApplicationFlow(_Corpus(), GroundedApplicationDrafter(_gen), _Voice(True, "In 2025 I built Atlas, accuracy up 20%. [1]"), _FlowApprovals(), 'tenant-a')
    out = asyncio.run(f.prepare('c', 'https://official', FIELDS))
    assert out['exact_answers']['impact'] == "In 2025 I built Atlas, accuracy up 20%. [1]"


def test_flow_requires_a_tenant():
    for t in ("", "   "):
        with pytest.raises(ValueError, match="tenant_id"):
            IntegratedApplicationFlow(_Corpus(), None, None, None, t)


# ---- row 76: project builder guards
from app.modules.m14_project_builder.service import Service as Projects
from app.modules.m14_project_builder.schemas import CreateProjectRequest


class _Ap:
    def put(self, item, *, user_id=None):
        return item


def test_execution_cannot_be_proposed_before_planning():
    s = Projects(_Ap(), None)
    p = s.create("t", CreateProjectRequest(goal="Build a grounded report"))
    with pytest.raises(ValueError, match="planned first"):
        s.propose_execution(p)


def test_evaluate_plan_needs_a_plan():
    s = Projects(_Ap(), None)
    p = s.create("t", CreateProjectRequest(goal="Build a grounded report"))
    with pytest.raises(ValueError, match="planned before quality"):
        s.evaluate_plan(p)


def test_commit_refuses_paths_outside_the_workspace(tmp_path):
    with pytest.raises(ValueError, match="escapes project workspace"):
        Projects.commit(tmp_path, "m", ["../outside.txt"])


def test_advance_unknown_milestone_raises_keyerror_with_message():
    from app.modules.m14_project_builder.schemas import MilestoneAdvanceRequest
    s = Projects(_Ap(), None)
    p = s.create("t", CreateProjectRequest(goal="Build a grounded report"))
    with pytest.raises(KeyError, match="milestone not found"):
        s.advance_milestone(p, "nope", MilestoneAdvanceRequest(status="in_progress"))


class _EmptyCorpus:
    async def retrieve(self, q, limit):
        return []


def test_flow_refuses_to_draft_without_owner_evidence():
    f = IntegratedApplicationFlow(_EmptyCorpus(), GroundedApplicationDrafter(_gen), _Voice(True), _FlowApprovals(), 'tenant-a')
    with pytest.raises(ValueError, match="no owner corpus evidence"):
        asyncio.run(f.prepare('c', 'https://official', FIELDS))


def test_flow_keeps_final_submit_behind_separate_approval():
    f = IntegratedApplicationFlow(_Corpus(), GroundedApplicationDrafter(_gen), _Voice(True), _FlowApprovals(), 'tenant-a')
    out = asyncio.run(f.prepare('c', 'https://official', FIELDS))
    assert out['final_submit_requires_separate_approval'] is True and not out['submission_enabled']
    assert out['official_url'] == 'https://official'
