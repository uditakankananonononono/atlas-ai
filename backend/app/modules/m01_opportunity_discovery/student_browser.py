"""Owner-session adapters for the 17 student platforms, composed with M13.

Read real DOM links, never invent authenticated endpoints or selectors. Browser
sessions and application records are durable in M13. Navigation is confined to
exact platform origins and to links observed in the current page. Applications
are staged individually and submitted only through M02's exact approval flow.
Extension-only capabilities and editorial feeds are not relabelled as APIs.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import urljoin, urlsplit, urlunsplit
import re

from bs4 import BeautifulSoup
from sqlalchemy import JSON, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, SessionLocal, engine
from app.modules.m13_browser_agent.application_flow import (
    ApplicationFlow, BlockedError, WorkflowStateError, probe_auth, probe_captcha,
)
from .student_platforms import BY_ID, PlatformUnavailable


@dataclass(frozen=True)
class BrowserAdapter:
    platform: str
    hosts: tuple[str, ...]
    listing_pattern: str
    account_workflow: str
    caveat: str = ""


# Patterns constrain link classification, not fabricated site endpoints.
ADAPTERS = {
    'ripplematch': BrowserAdapter('ripplematch', ('ripplematch.com', 'www.ripplematch.com', 'app.ripplematch.com'), r'/(?:jobs?|opportunities|matches)(?:/|\?|$)', 'profile_and_matches', 'Vendor documents recommendations, not unconditional auto-apply.'),
    'simplify': BrowserAdapter('simplify', ('simplify.jobs',), r'/p/[\w-]+', 'profile_and_jobs', 'Copilot requires a user-installed extension; Autopilot requires Simplify+. Atlas does not install or impersonate the extension.'),
    'raiseme': BrowserAdapter('raiseme', ('raiseme.com', 'www.raiseme.com', 'raise.me', 'www.raise.me'), r'/(?:colleges|universities|schools)/[^/]+', 'portfolio_and_colleges', 'Micro-scholarships are conditional institutional aid, not cash earned or admission applications.'),
    'bold': BrowserAdapter('bold', ('bold.org',), r'/scholarships/[^/]+/?$', 'profile_and_scholarships'),
    'fastweb': BrowserAdapter('fastweb', ('www.fastweb.com', 'fastweb.com'), r'/college-scholarships/scholarships/\d+', 'profile_and_scholarships'),
    'devpost': BrowserAdapter('devpost', ('devpost.com', 'www.devpost.com'), r'/(?:hackathons/\d+|software/[^/]+)', 'hackathons_and_notifications', 'Email alert settings require owner review; no subscription is silently enabled.'),
    'challengerocket': BrowserAdapter('challengerocket', ('challengerocket.com', 'www.challengerocket.com'), r'/[^/]+/?$', 'challenges_and_application'),
    'mlh': BrowserAdapter('mlh', ('www.mlh.com', 'mlh.com', 'events.mlh.io'), r'/events/\d+', 'events'),
    'internshala': BrowserAdapter('internshala', ('internshala.com',), r'/internship/detail/[^/]+', 'profile_and_internships'),
    'unigo': BrowserAdapter('unigo', ('www.unigo.com', 'unigo.com'), r'/scholarships/[^/]+', 'scholarships'),
    'kaggle': BrowserAdapter('kaggle', ('www.kaggle.com', 'kaggle.com'), r'/competitions/[^/]+', 'competition_rules_and_entry', 'Competition rules and eligibility must be reviewed before joining.'),
}
for _id in ('scholarships360', 'scholarshiproar', 'scholarshipregion', 'opportunitiesforafricans', 'scholarshipunion', 'opportunitiesforyouth'):
    ADAPTERS[_id] = BrowserAdapter(_id, (urlsplit(BY_ID[_id].url).hostname,), r'/[^/]+', 'editorial_discovery', 'Editorial source, not an authenticated scholarship application provider.')
assert ADAPTERS.keys() == BY_ID.keys()

_CONTROL = re.compile(r'\b(profile|portfolio|education|experience|matches|notifications|settings|colleges|scholarships|hackathons|internships|competitions)\b', re.I)
_UNSAFE_LINK = re.compile(r'(?:logout|log-out|signout|sign-out|delete|unsubscribe|checkout|payment|autopilot)', re.I)
_BLOCK_TEXT = ('too many requests', 'rate limit exceeded', 'access denied', 'temporarily blocked', 'unusual traffic')


def platform_url(adapter: BrowserAdapter, url: str) -> str:
    """Exact hosts only. M13 separately enforces public DNS/navigation policy."""
    p = urlsplit(url)
    host_ok = p.hostname in adapter.hosts
    if adapter.platform == 'devpost' and p.hostname:
        host_ok = host_ok or bool(re.fullmatch(r'[a-z0-9-]+\.devpost\.com', p.hostname))
    if p.scheme != 'https' or not host_ok or p.username or p.password or p.port not in (None, 443):
        raise PermissionError('destination is outside this platform')
    return urlunsplit((p.scheme, p.netloc, p.path or '/', p.query, ''))


def page_links(adapter: BrowserAdapter, page_url: str, html: str) -> list[dict]:
    """Extract real navigable links, with card text as provenance."""
    platform_url(adapter, page_url)
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup(['script', 'style', 'noscript']):
        node.decompose()
    rows, seen = [], set()
    for a in soup.select('a[href]'):
        href = a['href']
        if _UNSAFE_LINK.search(href):
            continue
        try:
            url = platform_url(adapter, urljoin(page_url, href))
        except (PermissionError, ValueError):
            continue
        title = re.sub(r'\s+', ' ', a.get_text(' ', strip=True)).strip()
        if not title or len(title) > 500 or url in seen:
            continue
        path = urlsplit(url).path
        # CR listing pages identify actual cards, avoiding its broad slug shape.
        if adapter.platform == 'challengerocket':
            listing = bool(a.find_parent(class_='challenge-card__title'))
        else:
            listing = bool(re.search(adapter.listing_pattern, path))
            if adapter.platform == 'devpost' and urlsplit(url).hostname not in adapter.hosts:
                listing = path == '/' and urlsplit(url).hostname not in {'help.devpost.com'}
        account = bool(_CONTROL.search(title))
        # A Devpost event has its own subdomain and is discovered from the DOM.
        if not listing and not account:
            continue
        seen.add(url)
        rows.append({'id': sha256(url.encode()).hexdigest()[:24], 'title': title,
                     'url': url, 'kind': 'opportunity' if listing else 'account_navigation',
                     'source_url': page_url})
        if len(rows) >= 100:
            break
    return rows


class StudentBrowserCheckpoint(Base):
    __tablename__ = 'm01_student_browser_checkpoints'
    tenant_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    platform: Mapped[str] = mapped_column(String(80))
    actor_id: Mapped[str] = mapped_column(String(120))
    next_read: Mapped[float] = mapped_column(Float, default=0)
    data: Mapped[dict] = mapped_column(JSON)


class SQLCheckpoints:
    """Durable rate/block state and observed-link provenance, scoped by owner."""
    def __init__(self, sessions=None):
        if sessions is None:
            StudentBrowserCheckpoint.__table__.create(engine, checkfirst=True)
        self.sessions = sessions or SessionLocal

    def create(self, tenant, session, actor, platform):
        with self.sessions.begin() as db:
            db.add(StudentBrowserCheckpoint(tenant_id=tenant, session_id=session,
                   actor_id=actor, platform=platform, next_read=0,
                   data={'links': [], 'seen_ids': [], 'blocked': ''}))

    def get(self, tenant, session, actor):
        with self.sessions() as db:
            row = db.get(StudentBrowserCheckpoint, (tenant, session))
            if row is None:
                raise KeyError(session)
            if row.actor_id != actor:
                raise PermissionError('platform session belongs to a different actor')
            return {'platform': row.platform, 'next_read': row.next_read, **row.data}

    def reserve(self, tenant, session, actor, now, interval):
        """Conditional update prevents concurrent reads across worker processes."""
        from sqlalchemy import update
        with self.sessions.begin() as db:
            row = db.get(StudentBrowserCheckpoint, (tenant, session))
            if row is None:
                raise KeyError(session)
            if row.actor_id != actor:
                raise PermissionError('platform session belongs to a different actor')
            if row.data.get('blocked'):
                raise BlockedError(row.data['blocked'])
            changed = db.execute(update(StudentBrowserCheckpoint).where(
                StudentBrowserCheckpoint.tenant_id == tenant,
                StudentBrowserCheckpoint.session_id == session,
                StudentBrowserCheckpoint.next_read <= now,
            ).values(next_read=now + interval))
            if changed.rowcount != 1:
                raise PlatformUnavailable('read pacing active; do not poll faster')

    def save(self, tenant, session, actor, data):
        with self.sessions.begin() as db:
            row = db.get(StudentBrowserCheckpoint, (tenant, session))
            if row is None:
                raise KeyError(session)
            if row.actor_id != actor:
                raise PermissionError('platform session belongs to a different actor')
            row.data = {key: value for key, value in data.items() if key not in {'platform', 'next_read'}}


class StudentBrowser:
    """Real browser reads and individual form staging; never blanket auto-submit."""
    def __init__(self, flow: ApplicationFlow, checkpoints, clock=None):
        self.flow, self.checkpoints = flow, checkpoints
        self.clock = clock or (lambda: datetime.now(timezone.utc).timestamp())
        self._locks = {}  # Serialize read/open within one process; SQL handles other workers.

    async def start(self, tenant, actor, platform, owner_account_confirmed, terms_permit):
        if not owner_account_confirmed or not terms_permit:
            raise PermissionError('own account and site-permitted workflow must be confirmed')
        if platform not in ADAPTERS:
            raise KeyError(platform)
        record = await self.flow.start(tenant, actor, BY_ID[platform].url,
                                      opportunity_kind='student_platform', opportunity_id=platform,
                                      label=BY_ID[platform].name, allowed_hosts=ADAPTERS[platform].hosts)
        self.checkpoints.create(tenant, record.session_id, actor, platform)
        view = record.public_view()
        view.update({'account_workflow': ADAPTERS[platform].account_workflow,
                     'caveat': ADAPTERS[platform].caveat, 'live_workflow_verified': False})
        return view

    async def _snapshot(self, tenant, actor, session):
        state = self.checkpoints.get(tenant, session, actor)
        adapter = ADAPTERS[state['platform']]
        if state.get('blocked'):
            raise BlockedError(state['blocked'])
        record = self.flow._record(tenant, session)
        self.flow._require_actor(record, actor)
        page = await self.flow._page(record)
        url = platform_url(adapter, page.url)
        html = await self.flow.browser.extract(tenant, session)
        issues = probe_captcha(html)
        visible = BeautifulSoup(html, 'html.parser').get_text(' ', strip=True).lower()
        issues += [text for text in _BLOCK_TEXT if text in visible]
        if issues:
            state['blocked'] = 'site challenge or rate limit; stop, no automatic retries'
            self.checkpoints.save(tenant, session, actor, state)
            self.flow._blocked(record, state['blocked'], issues)
            raise BlockedError(state['blocked'])
        if probe_auth(url, html).required:
            raise WorkflowStateError('log in personally in the paired browser, then resume via M02')
        return state, adapter, record, url, html

    async def read(self, tenant, actor, session):
        lock = self._locks.setdefault((tenant, session), asyncio.Lock())
        async with lock:
            self.checkpoints.reserve(tenant, session, actor, self.clock(), 60)
            state, adapter, record, url, html = await self._snapshot(tenant, actor, session)
            links = page_links(adapter, url, html)
            if not links:
                raise PlatformUnavailable('no supported platform links found; layout or account needs owner navigation')
            prior = set(state.get('seen_ids', []))
            new_items = [x for x in links if x['kind'] == 'opportunity' and x['id'] not in prior]
            state.update({'links': links, 'page_url': url,
                          'seen_ids': sorted(prior | {x['id'] for x in links})[-1000:],
                          'observed_at': datetime.fromtimestamp(self.clock(), timezone.utc).isoformat()})
            self.checkpoints.save(tenant, session, actor, state)
            return {'session_id': session, 'platform': adapter.platform, 'source_url': url,
                    'links': links, 'new_opportunities': new_items,
                    'observed_at': state['observed_at'], 'matching_basis': 'site_visible_links_not_eligibility',
                    'submitted': False, 'alerts_sent': False, 'caveat': adapter.caveat}

    async def open(self, tenant, actor, session, link_id):
        lock = self._locks.setdefault((tenant, session), asyncio.Lock())
        async with lock:
            self.checkpoints.reserve(tenant, session, actor, self.clock(), 5)
            state, adapter, record, url, html = await self._snapshot(tenant, actor, session)
            stored = next((x for x in state.get('links', []) if x['id'] == link_id), None)
            live = page_links(adapter, url, html)
            if state.get('page_url') != url or not stored or stored not in live:
                raise WorkflowStateError('selected link is stale or not observed on the current platform page')
            # Create a separate approval-bound application record. Never reuse a
            # staged application's values/approval for another opportunity.
            child = await self.flow.start(tenant, actor, stored['url'],
                       opportunity_kind='student_platform', opportunity_id=adapter.platform,
                       label=stored['title'], allowed_hosts=tuple(set(adapter.hosts) | {urlsplit(stored['url']).hostname}))
            try:
                platform_url(adapter, child.url)
            except PermissionError:
                self.flow._blocked(child, 'platform redirected to an external sponsor; review in M02 separately', [])
                raise
            self.checkpoints.create(tenant, child.session_id, actor, adapter.platform)
            return child.public_view()

    async def stage(self, tenant, actor, session, fields, selector):
        lock = self._locks.setdefault((tenant, session), asyncio.Lock())
        async with lock:
            # Origin and block checks precede any write, even if the user navigated manually.
            _, _, _, _, html = await self._snapshot(tenant, actor, session)
            soup = BeautifulSoup(html, 'html.parser')
            try:
                buttons = soup.select(selector)
            except Exception as exc:
                raise ValueError('invalid submit selector') from exc
            if len(buttons) != 1 or buttons[0].name not in {'button', 'input'}:
                raise WorkflowStateError('choose exactly one submit control observed on the live page')
            if buttons[0].name == 'input' and buttons[0].get('type', '').lower() not in {'submit', 'button'}:
                raise WorkflowStateError('selector is not a submit control')
            inspection = await self.flow.inspect(tenant, actor, session)
            unsupported = [d['selector'] for d in inspection['fields'] if d['input_type'] in {'checkbox', 'radio', 'select', 'file'}]
            if soup.find('select') or soup.find('input', attrs={'type': 'file'}):
                unsupported.append('select/file input')
            if unsupported:
                raise WorkflowStateError('this form needs owner handling for non-text controls: ' + ', '.join(unsupported))
            result = await self.flow.stage(tenant, actor, session, fields, selector)
            result['next_step'] = 'Review exact preview, then request individual M02 final-submit approval. No batch approval.'
            return result
