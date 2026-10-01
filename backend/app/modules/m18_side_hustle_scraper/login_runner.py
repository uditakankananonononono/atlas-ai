"""Finite, observed browser experiments. No arbitrary executor or client receipts.

Recipes are installed by the server operator after site-specific review. Login is
performed by the owner on the paired device; this module never reads login fields,
cookies, passwords, or session tokens. One run permits one zero-cost publication.
An ambiguous/crashed submit is reconciled by readback, never retried automatically.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

from bs4 import BeautifulSoup
from app.modules.m13_browser_agent.session_bridge.protocol import PlatformBlocked, is_pc_session, split_pc_session, validate_identifier


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class BrowserRecipe:
    platform: str
    origin: str
    discovery_url: str
    compose_url: str
    account_selector: str
    source_selector: str
    content_selector: str
    submit_selector: str
    terms_selector: str
    free_terms: str
    receipt_selector: str
    receipt_content_selector: str
    receipt_account_selector: str
    correlation_selector: str
    receipt_correlation_selector: str
    allowed_fields: tuple[str, ...]
    # Only explicitly installed test recipes may access a loopback fake site.
    local_test: bool = False

    def url(self, url):
        parsed = urlsplit(url)
        if parsed.username or parsed.password or parsed.fragment:
            raise ValueError("credentials and fragments are forbidden in URLs")
        if f"{parsed.scheme}://{parsed.netloc}" != self.origin:
            raise ValueError("URL left the installed adapter origin")
        if not self.local_test:
            from app.modules.m13_browser_agent.security import validate_public_url
            return validate_public_url(url, [urlsplit(self.origin).hostname])
        if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost'}:
            raise ValueError("test adapter requires a loopback HTTP origin")
        return url

    def __post_init__(self):
        fields = tuple(self.allowed_fields)
        if (not fields or len(set(fields)) != len(fields)
                or any(not isinstance(name, str) or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,127}", name) is None for name in fields)):
            raise ValueError("recipe requires an explicit unique form field allowlist")
        object.__setattr__(self, 'allowed_fields', fields)
        if self.platform not in {'pinterest', 'x', 'youtube', 'instagram', 'local_fixture'}:
            raise ValueError("platform is not allowlisted")
        if self.platform == 'local_fixture' and not self.local_test:
            raise ValueError("fixture recipe is test-only")
        for value in (self.account_selector, self.source_selector, self.content_selector,
                      self.submit_selector, self.terms_selector, self.free_terms,
                      self.receipt_selector, self.receipt_content_selector, self.receipt_account_selector,
                      self.correlation_selector, self.receipt_correlation_selector):
            if not value:
                raise ValueError("adapter selectors and exact no-fee terms are required")
        self.url(self.discovery_url)
        self.url(self.compose_url)


class LoginRunStore:
    def __init__(self, path):
        self.path = str(path)
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS m18_login_runs(tenant TEXT, id TEXT, revision INTEGER, body TEXT, PRIMARY KEY(tenant,id))')

    def db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA synchronous=FULL')
        return db

    def get(self, tenant, rid):
        with self.db() as db:
            row = db.execute('SELECT body FROM m18_login_runs WHERE tenant=? AND id=?', (tenant, rid)).fetchone()
        if not row:
            raise KeyError(rid)
        return json.loads(row[0])

    def create(self, tenant, run):
        with self.db() as db:
            db.execute('INSERT INTO m18_login_runs VALUES(?,?,?,?)', (tenant, run['id'], run['revision'], canonical(run)))
        return run

    def save(self, tenant, run, state):
        old = run['revision']
        run = dict(run, revision=old + 1, state=state)
        run['transitions'] = [*run['transitions'], {'state': state, 'at': datetime.now(timezone.utc).isoformat()}]
        with self.db() as db:
            changed = db.execute('UPDATE m18_login_runs SET revision=?,body=? WHERE tenant=? AND id=? AND revision=?',
                                 (run['revision'], canonical(run), tenant, run['id'], old)).rowcount
            if changed != 1:
                raise PermissionError('run changed concurrently; reload before continuing')
        return run


class LoginHustleRunner:
    def __init__(self, store, sessions, approvals, recipes, receipt_key: bytes):
        if len(receipt_key) < 32:
            raise ValueError('server receipt signing key must have at least 32 bytes')
        self.store, self.sessions, self.approvals = store, sessions, approvals
        self.recipes, self.receipt_key = dict(recipes), receipt_key

    def recipe(self, run):
        recipe = self.recipes.get(run['platform'])
        if recipe is None or digest(recipe.__dict__) != run['recipe_sha256']:
            raise PermissionError('adapter is unavailable or changed; start a new reviewed run')
        return recipe

    def create(self, tenant, actor, *, platform, account, session_id):
        validate_identifier(tenant)
        if not is_pc_session(session_id):
            raise ValueError('login experiments require an owner-paired PC session')
        split_pc_session(session_id)
        recipe = self.recipes.get(platform)
        if recipe is None:
            raise ValueError('platform adapter is not installed; no execution was attempted')
        if not account.strip() or len(account) > 200:
            raise ValueError('select an exact account identity')
        return self.store.create(tenant, {'id': str(uuid4()), 'revision': 0, 'state': 'login_handoff',
            'actor': actor, 'platform': platform, 'account': account, 'session_id': session_id,
            'recipe_sha256': digest(recipe.__dict__), 'transitions': [], 'sources': [],
            'login_instruction': 'Log in yourself on your paired browser. Atlas does not collect login secrets.',
            'limits': {'publications': 1, 'cost': 0, 'no_earnings_guarantee': True}})

    @staticmethod
    def text(soup, selector):
        nodes = soup.select(selector)
        if len(nodes) != 1:
            raise PermissionError('expected exactly one adapter readback element')
        return nodes[0].get_text(' ', strip=True)

    def identity(self, soup, selector, run):
        if self.text(soup, selector) != run['account']:
            raise PermissionError('logged-in account does not match owner selection')

    async def page(self, tenant, run):
        recipe = self.recipe(run)
        page = await self.sessions.page(tenant, run['session_id'], True)
        return recipe, page

    async def discover(self, tenant, rid):
        run = self.store.get(tenant, rid)
        if run['state'] not in {'login_handoff', 'paused'}:
            raise PermissionError('discovery is not available in this state')
        recipe, page = await self.page(tenant, run)
        try:
            await page.goto(recipe.discovery_url)
            recipe.url(page.url)
            soup = BeautifulSoup(await page.content(), 'html.parser')
            self.identity(soup, recipe.account_selector, run)
            sources = []
            for node in soup.select(recipe.source_selector)[:10]:
                url = recipe.url(urljoin(page.url, node.get('href', '')))
                quote = node.get_text(' ', strip=True)[:2000]
                if quote and node.get('href'):
                    sources.append({'url': url, 'quote': quote, 'sha256': digest({'url': url, 'quote': quote})})
            if not sources:
                raise PermissionError('no sourced discovery evidence was observed')
            run['sources'] = sources
            run['blueprint'] = {'evidence': sources, 'assumptions': ['Demand and earnings are unverified.'],
                                'next_step': 'Owner chooses hypothesis and exact bounded draft content.'}
            return self.store.save(tenant, run, 'blueprint_ready')
        except PlatformBlocked as error:
            run['pause_reason'] = error.kind.value
            return self.store.save(tenant, run, 'paused')

    @staticmethod
    def form_selectors(soup, button, recipe):
        form = button.find_parent('form')
        if form is None:
            raise PermissionError('publication must be a non-login form')
        # Refuse external form-associated controls too: they can be submitted
        # without belonging to this DOM subtree.
        if soup.select('[form]'):
            raise PermissionError('external form-associated controls are not supported')
        fields = form.select('input,textarea,select,button[name]')
        names = [node.get('name') for node in fields]
        if (any(node.get('type', '').lower() == 'password' for node in fields)
                or any(name not in recipe.allowed_fields for name in names)
                or len(set(names)) != len(names)):
            raise PermissionError('adapter form contains fields outside the reviewed allowlist')
        for selector in (recipe.content_selector, recipe.correlation_selector):
            nodes = form.select(selector)
            if len(nodes) != 1 or nodes[0] not in fields:
                raise PermissionError('draft and correlation must be allowlisted form fields')
        return [f'[name="{name}"]' for name in names]

    async def snapshot(self, tenant, run):
        recipe, page = await self.page(tenant, run)
        html = await page.content()
        recipe.url(page.url)
        soup = BeautifulSoup(html, 'html.parser')
        self.identity(soup, recipe.account_selector, run)
        if self.text(soup, recipe.terms_selector) != recipe.free_terms:
            raise PermissionError('final cost or terms changed; no effect allowed')
        nodes = soup.select(recipe.submit_selector)
        if len(nodes) != 1:
            raise PermissionError('submit target changed')
        form = nodes[0].find_parent('form')
        selectors = self.form_selectors(soup, nodes[0], recipe)
        values = await self.sessions.read_values(tenant, run['session_id'], selectors)
        if set(values) != set(selectors):
            raise PermissionError('adapter returned unexpected form fields')
        content = await self.sessions.read_values(tenant, run['session_id'], [recipe.content_selector])
        if content.get(recipe.content_selector) != run['draft']:
            raise PermissionError('draft content changed; review a new preview')
        action = recipe.url(urljoin(page.url, form.get('action') or page.url))
        return {'url': page.url, 'account': run['account'], 'form_action': action,
                'method': form.get('method', 'get'), 'form_text': form.get_text(' ', strip=True),
                'submit': str(nodes[0]), 'values': values, 'allowed_fields': list(recipe.allowed_fields),
                'terms': recipe.free_terms, 'draft': run['draft'], 'hypothesis': run['hypothesis'],
                'limits': run['limits'], 'source_hashes': [s['sha256'] for s in run['sources']]}

    async def preview(self, tenant, rid, actor, *, hypothesis, draft, max_minutes):
        run = self.store.get(tenant, rid)
        if run['actor'] != actor or run['state'] not in {'blueprint_ready', 'awaiting_approval'}:
            raise PermissionError('only the selecting owner can review a sourced blueprint')
        if not hypothesis.strip() or not draft.strip() or len(draft) > 5000 or not 1 <= max_minutes <= 120:
            raise ValueError('bounded hypothesis, draft (<=5000 chars), and 1-120 owner minutes required')
        run.update(hypothesis=hypothesis, draft=draft)
        run['limits']['owner_minutes'] = max_minutes
        run['expires_at'] = (datetime.now(timezone.utc) + timedelta(minutes=max_minutes)).isoformat()
        recipe, page = await self.page(tenant, run)
        try:
            await page.goto(recipe.compose_url)
            recipe.url(page.url)
            soup = BeautifulSoup(await page.content(), 'html.parser')
            self.identity(soup, recipe.account_selector, run)
            buttons = soup.select(recipe.submit_selector)
            if len(buttons) != 1:
                raise PermissionError('submit target changed')
            self.form_selectors(soup, buttons[0], recipe)
            await page.locator(recipe.content_selector).fill(draft)
            await page.locator(recipe.correlation_selector).fill(run['id'])
            snapshot = await self.snapshot(tenant, run)
            prior = BeautifulSoup(await page.content(), 'html.parser').select(recipe.receipt_selector)
            run['prior_provider_ids'] = [n.get_text(' ', strip=True) for n in prior]
            run['preview'] = snapshot
            run['preview_sha256'] = digest(snapshot)
            run['preview_image'] = await self.sessions.screenshot(tenant, run['session_id'])
            # Direct submit forces explicit human review, never a policy auto-allow.
            approval = self.approvals.submit(module_id=18, action_type='login_publish',
                payload=self.payload(run), user_id=tenant)
            run['approval_id'] = approval['id']
            return self.store.save(tenant, run, 'awaiting_approval')
        except PlatformBlocked as error:
            run['pause_reason'] = error.kind.value
            return self.store.save(tenant, run, 'paused')

    @staticmethod
    def payload(run):
        return {'run_id': run['id'], 'platform': run['platform'], 'session_id': run['session_id'],
                'recipe_sha256': run['recipe_sha256'], 'preview': run['preview'],
                'preview_sha256': run['preview_sha256'], 'expires_at': run['expires_at']}

    async def execute(self, tenant, rid, actor):
        run = self.store.get(tenant, rid)
        if run['actor'] != actor:
            raise PermissionError('only selecting owner may execute')
        if run['state'] == 'succeeded':
            self.verify_receipt(tenant, run)
        if run['state'] in {'succeeded', 'unknown', 'submitting'}:
            return run  # no duplicate submits, including after process crash
        if run['state'] != 'awaiting_approval':
            raise PermissionError('no reviewed preview awaiting approval')
        if datetime.now(timezone.utc) >= datetime.fromisoformat(run['expires_at']):
            run['outcome'] = 'Experiment time bound expired before submission.'
            return self.store.save(tenant, run, 'expired')
        try:
            snapshot = await self.snapshot(tenant, run)
            if digest(snapshot) != run['preview_sha256']:
                raise PermissionError('final browser state changed; approval cannot be used')
            approval = self.approvals.get(run['approval_id'])
            if approval['status'] != 'approved' or approval.get('approved_by') != actor:
                raise PermissionError('matching owner approval required')
            self.approvals.consume_effect(run['approval_id'], module_id=18, action_type='login_publish',
                payload=self.payload(run), user_id=tenant, effect_id=f"m18-login:{tenant}:{rid}", actor=actor)
            # Durable claim before network: a crash cannot repeat the click.
            run = self.store.save(tenant, run, 'submitting')
            recipe, page = await self.page(tenant, run)
            await self.sessions.authorize_submit(tenant, run['session_id'], approval_id=run['approval_id'],
                capture_sha256=run['preview_sha256'], selector=recipe.submit_selector, values=snapshot['values'],
                preview=snapshot, readback_selectors={'account': recipe.account_selector, 'terms': recipe.terms_selector})
            await page.locator(recipe.submit_selector).click()
            return await self.reconcile(tenant, rid)
        except PlatformBlocked as error:
            run['pause_reason'] = error.kind.value
            return self.store.save(tenant, run, 'unknown' if run['state'] == 'submitting' else 'paused')
        except Exception:
            if run['state'] == 'submitting':
                run['outcome'] = 'Submit may have occurred. Readback needed; no automatic retry.'
                self.store.save(tenant, run, 'unknown')
            raise

    def stop(self, tenant, rid, actor):
        run = self.store.get(tenant, rid)
        if run['actor'] != actor:
            raise PermissionError('only selecting owner may stop')
        if run['state'] in {'submitting', 'succeeded', 'unknown'}:
            raise PermissionError('effect may already have occurred; inspect readback instead')
        run['outcome'] = 'Owner stopped experiment before submit.'
        return self.store.save(tenant, run, 'stopped')

    async def reconcile(self, tenant, rid):
        run = self.store.get(tenant, rid)
        if run['state'] == 'succeeded':
            self.verify_receipt(tenant, run)
            return run
        if run['state'] not in {'submitting', 'unknown'}:
            raise PermissionError('nothing to reconcile')
        recipe, page = await self.page(tenant, run)
        try:
            html = await page.content()
            url = recipe.url(page.url)
            soup = BeautifulSoup(html, 'html.parser')
            self.identity(soup, recipe.receipt_account_selector, run)
            if self.text(soup, recipe.receipt_correlation_selector) != rid:
                raise PermissionError('readback belongs to another experiment')
            provider_id = self.text(soup, recipe.receipt_selector)
            content = self.text(soup, recipe.receipt_content_selector)
            if not provider_id or provider_id in run.get('prior_provider_ids', []) or content != run['draft']:
                raise PermissionError('authoritative readback does not match the reviewed publication')
            receipt = {'tenant': tenant, 'run_id': rid, 'approval_id': run['approval_id'],
                'provider_id': provider_id, 'correlation_id': rid, 'url': url, 'account': run['account'], 'content_sha256': digest(content),
                'preview_sha256': run['preview_sha256'], 'observed_at': datetime.now(timezone.utc).isoformat(),
                'basis': 'server-observed paired-browser readback', 'status': 'succeeded'}
            run['receipt'] = {'evidence': receipt, 'signature': hmac.new(self.receipt_key, canonical(receipt).encode(), hashlib.sha256).hexdigest()}
            run['outcome'] = 'One publication observed. Demand, conversions and profit remain unverified.'
            return self.store.save(tenant, run, 'succeeded')
        except (PermissionError, PlatformBlocked):
            run['outcome'] = 'Publication unverified. No automatic retry; owner must inspect the paired browser.'
            return self.store.save(tenant, run, 'unknown')

    def verify_receipt(self, tenant, run):
        receipt = run['receipt']
        evidence = receipt['evidence']
        signature = hmac.new(self.receipt_key, canonical(evidence).encode(), hashlib.sha256).hexdigest()
        if (not hmac.compare_digest(signature, receipt['signature']) or evidence['tenant'] != tenant
            or evidence['run_id'] != run['id'] or evidence['account'] != run['account']
            or evidence['preview_sha256'] != run['preview_sha256'] or evidence['content_sha256'] != digest(run['draft'])):
            raise PermissionError('adapter receipt integrity or binding failed')
        return evidence
