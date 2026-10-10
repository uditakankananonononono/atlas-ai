"""A13 optional RabbitMQ routing: hermetic acceptance tests (AUTHORED FIRST, NOT RUN by the builder).

No network, no broker, no docker. kombu is never called: the backend and queue builder take injected
fakes shaped after kombu 5.4.2 (API read from the public v5.4.2 source, see the package manifest).
These tests check Atlas's own logic and the shape of the committed files. They do NOT prove that a real
RabbitMQ container routes messages; that is the main side's separate broker acceptance.
"""
import io
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest
import yaml

from app.runtime import rabbitmq_backend as rb
from app.workers import celery_broker_config as cb

ROOT = Path(__file__).resolve().parents[2]
OVERRIDE = ROOT / 'deploy/local/docker-compose.rabbitmq.yml'
CONSTRAINTS = ROOT / 'deploy/local/constraints-rabbitmq.txt'
PINNED_DIGEST = 'sha256:d7af1c87c5f1eda13fcfca06db452bf3aeab6619fc3358b68535c0c02c4e52bc'
GAPS = [
    'Opt-in via the override only; the default deployment keeps Redis and is unchanged.',
    'Managed/cloud RabbitMQ features (clustering, managed upgrades, cloud SLAs) are not covered.',
    'Broker acceptance (real container routing) runs on the main side, not in this package.',
]
NASTY = 'p@ss:w/rd#?%&=+ ~"\'\\;'  # every URL-reserved character plus space, quotes, backslash


def kombu_style_parts(url):
    """Mirror of kombu 5.4.2 kombu/utils/url.py url_to_parts (lines 58-75), used to prove round-trips."""
    scheme = urlparse(url).scheme
    parts = urlparse('http://' + url[len(scheme) + 3:])
    path = parts.path or ''
    path = path[1:] if path and path[0] == '/' else path
    return (scheme, unquote(parts.hostname or '') or None, parts.port, unquote(parts.username or '') or None,
            unquote(parts.password or '') or None, unquote(path or '') or None)


# ---------------- fakes shaped after kombu 5.4.2 ----------------
class FakeExchange:
    def __init__(self, name, type, durable):
        self.name, self.type, self.durable = name, type, durable


class FakeMessage:
    def __init__(self, payload, log):
        self.payload, self._log = payload, log

    def ack(self):
        self._log.append('ack')


class FakeBoundQueue:
    def __init__(self, spec, channel):
        self.spec, self.channel = spec, channel

    def declare(self):
        self.channel.log.append(('declare', self.spec['name'], self.spec['routing_key']))

    def get(self, no_ack=False):
        self.channel.log.append(('get', self.spec['name'], no_ack))
        pending = self.channel.inbox.get(self.spec['name'], [])
        return FakeMessage(pending.pop(0), self.channel.log) if pending else None


class FakeChannel:
    def __init__(self, inbox, log):
        self.inbox, self.log = inbox, log

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.log.append('channel-closed')
        return False


class FakeQueue:
    def __init__(self, name, exchange, routing_key, durable):
        self.spec = {'name': name, 'exchange': exchange, 'routing_key': routing_key, 'durable': durable}

    def __call__(self, channel):
        return FakeBoundQueue(self.spec, channel)


class FakeProducer:
    def __init__(self, conn, serializer):
        self.conn, self.serializer = conn, serializer

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def publish(self, body, **kwargs):
        if self.conn.fail_publish:
            raise OSError('connect to amqp://atlas:PLACEHOLDER-NOT-A-SECRET@rabbitmq:5672// refused')
        self.conn.published.append({'body': body, 'serializer': self.serializer, **kwargs})


class FakeConnection:
    def __init__(self, fail_publish=False):
        self.published, self.log, self.inbox, self.fail_publish = [], [], {}, fail_publish

    def Producer(self, serializer):
        return FakeProducer(self, serializer)

    def channel(self):
        return FakeChannel(self.inbox, self.log)


def make_backend(conn=None):
    conn = conn or FakeConnection()
    return rb.RabbitRoutingBackend(conn, exchange_factory=FakeExchange, queue_factory=FakeQueue), conn


# ================= celery_broker_config: flag, URL building, reserved characters =================
@pytest.mark.parametrize('env', [{}, {'ATLAS_RABBITMQ_URL': ''}, {'ATLAS_RABBITMQ_URL': '  '},
                                 {'ATLAS_RABBITMQ_URL': 'http://rabbitmq:15672'}, {'ATLAS_RABBITMQ_URL': 'redis://x'},
                                 {'ATLAS_RABBITMQ_HOST': '   '}])
def test_backend_is_off_unless_amqp_url_or_host_is_set(env):
    assert cb.is_enabled(env) is False


@pytest.mark.parametrize('env', [{'ATLAS_RABBITMQ_URL': 'amqp://u:p@h:5672//'}, {'ATLAS_RABBITMQ_URL': 'amqps://u:p@h/v'},
                                 {'ATLAS_RABBITMQ_HOST': 'rabbitmq'},
                                 {'ATLAS_RABBITMQ_URL': 'junk', 'ATLAS_RABBITMQ_HOST': 'rabbitmq'}])
def test_backend_is_on_for_amqp_url_or_host(env):
    assert cb.is_enabled(env) is True


def test_explicit_url_wins_over_parts_and_is_returned_unchanged():
    env = {'ATLAS_RABBITMQ_URL': ' amqp://u:p@h:5672// ', 'ATLAS_RABBITMQ_HOST': 'other'}
    assert cb.broker_url_from_env(env) == 'amqp://u:p@h:5672//'


def test_url_from_parts_percent_encodes_every_reserved_character_and_round_trips():
    env = {'ATLAS_RABBITMQ_HOST': 'rabbitmq', 'ATLAS_RABBITMQ_USER': 'at@las:user', 'ATLAS_RABBITMQ_PASSWORD': NASTY}
    url = cb.broker_url_from_env(env)
    userinfo_and_host = url[len('amqp://'):].split('/', 1)[0]
    assert userinfo_and_host.count('@') == 1  # only the real separator survives unencoded
    assert url.count('#') == 0 and url.count('?') == 0 and ' ' not in url and '"' not in url
    assert kombu_style_parts(url) == ('amqp', 'rabbitmq', 5672, 'at@las:user', NASTY, '/')


@pytest.mark.parametrize('vhost,expected_path', [(None, '/%2F'), ('/', '/%2F'), ('atlas', '/atlas'), ('a/b c', '/a%2Fb%20c')])
def test_vhost_is_encoded_and_default_vhost_decodes_to_slash(vhost, expected_path):
    env = {'ATLAS_RABBITMQ_HOST': 'h', 'ATLAS_RABBITMQ_USER': 'u', 'ATLAS_RABBITMQ_PASSWORD': 'p'}
    if vhost is not None:
        env['ATLAS_RABBITMQ_VHOST'] = vhost
    url = cb.broker_url_from_env(env)
    assert urlparse(url).path == expected_path
    assert kombu_style_parts(url)[5] == (vhost or '/')


def test_port_default_and_override_and_validation():
    base = {'ATLAS_RABBITMQ_HOST': 'h', 'ATLAS_RABBITMQ_USER': 'u', 'ATLAS_RABBITMQ_PASSWORD': 'p'}
    assert kombu_style_parts(cb.broker_url_from_env(base))[2] == 5672
    assert kombu_style_parts(cb.broker_url_from_env({**base, 'ATLAS_RABBITMQ_PORT': '5673'}))[2] == 5673
    for bad in ['0', '65536', 'abc', '-1', '']:
        with pytest.raises(cb.ConfigError):
            cb.broker_url_from_env({**base, 'ATLAS_RABBITMQ_PORT': bad})


@pytest.mark.parametrize('missing', ['ATLAS_RABBITMQ_USER', 'ATLAS_RABBITMQ_PASSWORD'])
def test_missing_credentials_fail_loudly_without_echoing_values(missing):
    env = {'ATLAS_RABBITMQ_HOST': 'h', 'ATLAS_RABBITMQ_USER': 'u', 'ATLAS_RABBITMQ_PASSWORD': NASTY}
    del env[missing]
    with pytest.raises(cb.ConfigError) as info:
        cb.broker_url_from_env(env)
    assert missing in str(info.value) and NASTY not in str(info.value)


@pytest.mark.parametrize('host', ['rab bit', 'a/b', 'a@b', 'a:5672', 'rabbit\n', '-x', 'x-'])
def test_host_must_be_a_plain_hostname(host):
    env = {'ATLAS_RABBITMQ_HOST': host, 'ATLAS_RABBITMQ_USER': 'u', 'ATLAS_RABBITMQ_PASSWORD': 'p'}
    with pytest.raises(cb.ConfigError):
        cb.broker_url_from_env(env)


def test_broker_url_from_env_refuses_when_not_enabled():
    with pytest.raises(cb.ConfigError):
        cb.broker_url_from_env({})


def test_redacted_url_hides_password_and_keeps_user_and_host():
    url = cb.broker_url_from_env({'ATLAS_RABBITMQ_HOST': 'rabbitmq', 'ATLAS_RABBITMQ_USER': 'u', 'ATLAS_RABBITMQ_PASSWORD': NASTY})
    red = cb.redacted_url(url)
    assert 'u:***@rabbitmq' in red and 'ss' not in red.split('@')[0].split(':')[-1]
    assert NASTY not in red and 'p%40ss' not in red


# ================= celery_broker_config: queues and CLI =================
def test_task_queue_names_match_the_queues_celery_app_routes_to_plus_default_celery_queue():
    text = (ROOT / 'backend/app/workers/celery_app.py').read_text()
    routed = set(re.findall(r'"queue":\s*"(\w+)"', text))
    assert routed and set(cb.TASK_QUEUE_NAMES) == routed | {'celery'}


def test_build_task_queues_uses_one_durable_topic_exchange_with_exact_routing_keys():
    exchanges, queues = [], []
    def exch(name, type, durable):
        exchanges.append(FakeExchange(name, type, durable)); return exchanges[-1]
    def queue(name, exchange, routing_key, durable):
        queues.append((name, exchange, routing_key, durable)); return queues[-1]
    built = cb.build_task_queues(exchange_factory=exch, queue_factory=queue)
    assert len(exchanges) == 1 and (exchanges[0].name, exchanges[0].type, exchanges[0].durable) == ('atlas.tasks', 'topic', True)
    assert len(built) == len(cb.TASK_QUEUE_NAMES)
    assert [q[0] for q in queues] == list(cb.TASK_QUEUE_NAMES)
    assert all(q[1] is exchanges[0] and q[2] == q[0] and q[3] is True for q in queues)


def test_cli_print_url_prints_encoded_url_for_command_substitution():
    out, err = io.StringIO(), io.StringIO()
    env = {'ATLAS_RABBITMQ_HOST': 'rabbitmq', 'ATLAS_RABBITMQ_USER': 'u', 'ATLAS_RABBITMQ_PASSWORD': NASTY}
    assert cb.main(['--print-url'], env=env, stdout=out, stderr=err) == 0
    assert out.getvalue().strip() == cb.broker_url_from_env(env) and err.getvalue() == ''


def test_cli_print_url_prints_nothing_and_succeeds_when_disabled_so_redis_default_stays():
    out, err = io.StringIO(), io.StringIO()
    assert cb.main(['--print-url'], env={}, stdout=out, stderr=err) == 0
    assert out.getvalue().strip() == '' and err.getvalue() == ''


def test_cli_print_url_misconfiguration_exits_2_with_safe_message():
    out, err = io.StringIO(), io.StringIO()
    env = {'ATLAS_RABBITMQ_HOST': 'rabbitmq', 'ATLAS_RABBITMQ_PASSWORD': NASTY}
    assert cb.main(['--print-url'], env=env, stdout=out, stderr=err) == 2
    assert out.getvalue() == '' and 'ATLAS_RABBITMQ_USER' in err.getvalue() and NASTY not in err.getvalue()


def test_cli_unknown_argument_exits_2():
    assert cb.main(['--nope'], env={}, stdout=io.StringIO(), stderr=io.StringIO()) == 2


def test_kombu_pin_status_reports_match_difference_and_missing_package():
    assert cb.kombu_pin_status(cb.VERIFIED_KOMBU_VERSION) == 'matches-verified-version'
    assert cb.kombu_pin_status('5.3.4') == 'differs-from-verified-version'
    assert cb.kombu_pin_status(None) == 'kombu-not-installed'


def test_constraints_overlay_pins_exactly_the_verified_kombu_version_and_fits_celery_range():
    lines = [x.strip() for x in CONSTRAINTS.read_text().splitlines() if x.strip() and not x.strip().startswith('#')]
    assert lines == [f'kombu=={cb.VERIFIED_KOMBU_VERSION}', 'celery==5.4.0']
    major, minor, patch = (int(x) for x in cb.VERIFIED_KOMBU_VERSION.split('.'))
    assert (5, 3, 4) <= (major, minor, patch) < (6, 0, 0)  # celery 5.4.0 requires kombu>=5.3.4,<6.0


# ================= module honesty =================
@pytest.mark.parametrize('module', [rb, cb])
def test_module_docstrings_state_all_three_named_gaps_verbatim(module):
    for gap in GAPS:
        assert gap in module.__doc__


# ================= rabbitmq_backend: AMQP topic semantics =================
@pytest.mark.parametrize('pattern,key,expected', [
    ('module.*', 'module.created', True), ('module.*', 'module.created.v2', False), ('module.*', 'module', False),
    ('module.#', 'module', True), ('module.#', 'module.a.b.c', True), ('module.#', 'other.a', False),
    ('#', 'anything.at.all', True), ('#', 'x', True), ('*', 'x', True), ('*', 'x.y', False),
    ('*.created.#', 'm01.created', True), ('*.created.#', 'm01.created.x.y', True), ('*.created.#', 'm01.deleted', False),
    ('a.#.z', 'a.z', True), ('a.#.z', 'a.b.c.z', True), ('a.#.z', 'a.b.c', False),
    ('a.b', 'a.b', True), ('a.b', 'a.bc', False), ('a.*.#', 'a.b', True), ('a.*.#', 'a', False),
])
def test_topic_matches_follows_amqp_wildcard_rules(pattern, key, expected):
    assert rb.topic_matches(pattern, key) is expected


@pytest.mark.parametrize('bad', ['', None, 5, 'a..b', '.a', 'a.', 'a b', 'a.*', 'a.#', 'x' * 256, 'a/b'])
def test_routing_key_validation_rejects_malformed_or_wildcard_keys(bad):
    with pytest.raises(rb.RoutingError):
        rb.validate_routing_key(bad)


@pytest.mark.parametrize('bad', ['', None, 'a..b', 'a.**', 'a.*b', 'a.#x', 'a b', 'x' * 256])
def test_binding_pattern_validation_rejects_partial_wildcards(bad):
    with pytest.raises(rb.RoutingError):
        rb.validate_binding_pattern(bad)


@pytest.mark.parametrize('good', ['#', '*', 'a.*', 'a.#.z', 'module.*'])
def test_binding_pattern_validation_accepts_whole_word_wildcards(good):
    assert rb.validate_binding_pattern(good) == good


# ================= rabbitmq_backend: from_env uses the config module =================
def test_from_env_is_none_and_never_connects_when_disabled():
    calls = []
    assert rb.RabbitRoutingBackend.from_env({}, connection_factory=lambda url: calls.append(url)) is None
    assert calls == []


def test_from_env_connects_with_the_encoded_url_built_from_parts():
    env = {'ATLAS_RABBITMQ_HOST': 'rabbitmq', 'ATLAS_RABBITMQ_USER': 'u', 'ATLAS_RABBITMQ_PASSWORD': NASTY}
    seen = []
    backend = rb.RabbitRoutingBackend.from_env(env, connection_factory=lambda u: seen.append(u) or FakeConnection(),
                                               exchange_factory=FakeExchange, queue_factory=FakeQueue)
    assert backend is not None and seen == [cb.broker_url_from_env(env)]
    assert kombu_style_parts(seen[0])[4] == NASTY


def test_from_env_with_explicit_url_connects_with_that_exact_url():
    seen = []
    rb.RabbitRoutingBackend.from_env({'ATLAS_RABBITMQ_URL': 'amqp://u:p@h:5672//'},
                                     connection_factory=lambda u: seen.append(u) or FakeConnection(),
                                     exchange_factory=FakeExchange, queue_factory=FakeQueue)
    assert seen == ['amqp://u:p@h:5672//']


# ================= rabbitmq_backend: binding / publish / consume =================
def test_bind_declares_durable_queue_on_durable_topic_exchange_with_pattern():
    backend, conn = make_backend()
    binding = backend.bind('workers', 'module.*')
    assert binding == rb.Binding(queue='workers', pattern='module.*')
    assert (backend.exchange.name, backend.exchange.type, backend.exchange.durable) == ('atlas.events', 'topic', True)
    assert ('declare', 'workers', 'module.*') in conn.log and backend.bindings == [binding]


def test_bind_rejects_bad_pattern_and_queue_names_before_touching_broker():
    backend, conn = make_backend()
    for queue, pattern in [('workers', 'a.*b'), ('', 'a.*'), (None, 'a.*'), ('q q', 'a.*')]:
        with pytest.raises(rb.RoutingError):
            backend.bind(queue, pattern)
    assert conn.log == [] and backend.bindings == []


def test_same_queue_can_hold_several_patterns_and_duplicate_bind_is_not_repeated():
    backend, conn = make_backend()
    backend.bind('workers', 'a.*')
    backend.bind('workers', 'b.#')
    backend.bind('workers', 'a.*')
    assert [(b.queue, b.pattern) for b in backend.bindings] == [('workers', 'a.*'), ('workers', 'b.#')]
    assert [x for x in conn.log if isinstance(x, tuple)] == [('declare', 'workers', 'a.*'), ('declare', 'workers', 'b.#')]


def test_bind_failure_is_a_safe_error_and_does_not_record_the_binding():
    backend, conn = make_backend()
    conn.channel = lambda: (_ for _ in ()).throw(OSError('amqp://u:PLACEHOLDER-NOT-A-SECRET@h refused'))
    with pytest.raises(rb.BackendUnavailable) as info:
        backend.bind('workers', 'a.*')
    assert str(info.value) == 'rabbitmq bind failed' and backend.bindings == []


def test_expected_queues_predicts_routing_from_declared_bindings_only():
    backend, _ = make_backend()
    backend.bind('workers', 'module.*')
    backend.bind('audit', '#')
    backend.bind('billing', 'billing.#')
    assert backend.expected_queues('module.created') == ['audit', 'workers']
    assert backend.expected_queues('billing.invoice.paid') == ['audit', 'billing']
    assert backend.expected_queues('module.created.v2') == ['audit']


def test_publish_hands_json_event_to_topic_exchange_with_routing_key():
    backend, conn = make_backend()
    result = backend.publish('module.created', {'id': 1})
    sent = conn.published[0]
    assert sent['body'] == {'id': 1} and sent['serializer'] == 'json'
    assert sent['routing_key'] == 'module.created' and sent['exchange'] is backend.exchange
    assert sent['declare'] == [backend.exchange] and sent['retry'] is True
    assert result == {'routing_key': 'module.created', 'exchange': 'atlas.events',
                      'exchange_type': 'topic', 'handed_to_broker': True}


@pytest.mark.parametrize('key,event', [('', {}), ('a.*', {}), ('a..b', {}), ('ok', 'text'), ('ok', None),
                                       ('ok', {'bad': object()}), ('ok', {1: 'non-str-key'}), ('ok', {'n': float('nan')})])
def test_publish_rejects_bad_input_without_calling_broker(key, event):
    backend, conn = make_backend()
    with pytest.raises(rb.RoutingError):
        backend.publish(key, event)
    assert conn.published == []


def test_publish_failure_raises_safe_error_without_leaking_connection_text():
    backend, _ = make_backend(FakeConnection(fail_publish=True))
    with pytest.raises(rb.BackendUnavailable) as info:
        backend.publish('module.created', {'id': 1})
    assert str(info.value) == 'rabbitmq publish failed'
    assert 'PLACEHOLDER' not in repr(info.value) and 'amqp://' not in repr(info.value)


def test_consume_one_returns_payload_and_acks_after_reading_in_ack_mode():
    backend, conn = make_backend()
    backend.bind('workers', 'module.*')
    conn.inbox['workers'] = [{'id': 7}]
    assert backend.consume_one('workers') == {'id': 7}
    assert ('get', 'workers', False) in conn.log
    assert conn.log.index('ack') > conn.log.index(('get', 'workers', False))


def test_consume_one_returns_none_when_empty_and_does_not_ack():
    backend, conn = make_backend()
    backend.bind('workers', 'module.*')
    assert backend.consume_one('workers') is None and 'ack' not in conn.log


def test_consume_unbound_queue_is_an_error_not_a_silent_none():
    backend, _ = make_backend()
    with pytest.raises(rb.RoutingError):
        backend.consume_one('never-bound')


# ================= compose override =================
def _override():
    return yaml.safe_load(OVERRIDE.read_text())


def _base():
    return yaml.safe_load((ROOT / 'deploy/local/docker-compose.yml').read_text())


def test_override_is_additive_and_only_touches_rabbitmq_api_and_worker():
    data = _override()
    assert set(data['services']) == {'rabbitmq', 'api', 'worker'}
    for name in ('api', 'worker'):
        assert 'image' not in data['services'][name] and set(data['services'][name]['build']) == {'context', 'dockerfile'}


def test_rabbitmq_image_is_pinned_by_digest_and_healthcheck_matches_verified_command():
    svc = _override()['services']['rabbitmq']
    assert svc['image'] == f'rabbitmq:3.13-alpine@{PINNED_DIGEST}'
    assert re.fullmatch(r'rabbitmq:3\.13-alpine@sha256:[0-9a-f]{64}', svc['image'])
    assert svc['healthcheck']['test'] == ['CMD', 'rabbitmq-diagnostics', '-q', 'check_port_listener', '5672']
    assert 'ports' not in svc and svc['restart'] == 'unless-stopped'
    assert any(v.split(':')[0] == 'atlas-rabbitmq' for v in svc['volumes']) and 'atlas-rabbitmq' in _override()['volumes']


def test_credentials_are_env_placeholders_only_never_literals():
    text = OVERRIDE.read_text()
    data = _override()
    placeholder = '${RABBITMQ_PASSWORD:?set RABBITMQ_PASSWORD}'
    assert data['services']['rabbitmq']['environment']['RABBITMQ_DEFAULT_PASS'] == placeholder
    for name in ('api', 'worker'):
        env = data['services'][name]['environment']
        assert env['ATLAS_RABBITMQ_PASSWORD'] == placeholder and env['ATLAS_RABBITMQ_HOST'] == 'rabbitmq'
        assert env['ATLAS_RABBITMQ_USER'] == 'atlas' and 'ATLAS_RABBITMQ_URL' not in env
    assert 'guest' not in text.lower() and 'amqp://' not in text.replace('# ', '').split('services:')[1]


def test_api_and_worker_set_broker_url_via_module_and_keep_the_base_command_verbatim():
    data, base = _override(), _base()
    for name in ('api', 'worker'):
        svc = data['services'][name]
        assert svc['environment']['CELERY_CONFIG_MODULE'] == 'app.workers.celery_broker_config'
        cmd = svc['command']
        assert cmd[:2] == ['sh', '-c'] and len(cmd) == 3
        assert 'export CELERY_BROKER_URL="$$(python -m app.workers.celery_broker_config --print-url)"' in cmd[2]
        assert cmd[2].endswith('exec ' + ' '.join(base['services'][name]['command']))
    assert (ROOT / 'backend/app/workers/celery_broker_config.py').is_file()


def test_api_and_worker_wait_for_healthy_rabbitmq():
    for name in ('api', 'worker'):
        assert _override()['services'][name]['depends_on']['rabbitmq'] == {'condition': 'service_healthy'}


def test_base_local_compose_is_unchanged_reference_without_rabbitmq():
    assert 'rabbitmq' not in _base()['services'] and {'api', 'worker'} <= set(_base()['services'])


# ================= build-environment pin (sixth target: deploy/local/Dockerfile.rabbitmq) =================
RABBIT_DOCKERFILE = ROOT / 'deploy/local/Dockerfile.rabbitmq'
STOCK_DOCKERFILE = ROOT / 'Dockerfile'
ADDED_DOCKERFILE_LINES = [
    'COPY deploy/local/constraints-rabbitmq.txt /constraints.txt',
    'ENV PIP_CONSTRAINT=/constraints.txt',
    'COPY --from=builder /constraints.txt /constraints.txt',
    'ENV PIP_CONSTRAINT=/constraints.txt',
    'RUN python -m app.workers.celery_broker_config --kombu-status | grep -q ": matches-verified-version$"',
]


def _lines(path):
    return path.read_text().splitlines()


def test_rabbit_dockerfile_is_the_stock_dockerfile_plus_only_the_five_pin_lines():
    stock, rab = _lines(STOCK_DOCKERFILE), _lines(RABBIT_DOCKERFILE)
    assert len(rab) == len(stock) + len(ADDED_DOCKERFILE_LINES)
    it = iter(rab)
    for line in stock:  # every stock line, unchanged and in order (subsequence)
        assert any(line == r for r in it), f'stock line missing or reordered: {line!r}'
    leftovers = list(rab)
    for line in stock:
        leftovers.remove(line)
    assert sorted(leftovers) == sorted(ADDED_DOCKERFILE_LINES)


def _index(lines, text, start=0):
    return next(i for i in range(start, len(lines)) if lines[i] == text)


def test_constraint_is_active_before_pip_wheel_in_builder_and_before_pip_install_in_runtime():
    rab = _lines(RABBIT_DOCKERFILE)
    second_from = [i for i, x in enumerate(rab) if x.startswith('FROM ')][1]
    wheel = next(i for i, x in enumerate(rab) if x.startswith('RUN pip wheel'))
    assert wheel < second_from and 'constraints' not in rab[wheel]
    assert _index(rab, 'COPY deploy/local/constraints-rabbitmq.txt /constraints.txt') < _index(rab, 'ENV PIP_CONSTRAINT=/constraints.txt') < wheel
    install = next(i for i, x in enumerate(rab) if x.startswith('RUN pip install'))
    assert install > second_from
    assert _index(rab, 'COPY --from=builder /constraints.txt /constraints.txt', second_from) < _index(rab, 'ENV PIP_CONSTRAINT=/constraints.txt', second_from) < install


def test_build_time_kombu_check_runs_after_code_copy_and_would_fail_the_build_on_mismatch():
    rab = _lines(RABBIT_DOCKERFILE)
    check = _index(rab, ADDED_DOCKERFILE_LINES[-1])
    assert check > _index(rab, 'COPY --chown=atlas:atlas backend ./backend') and check < _index(rab, 'USER atlas')
    # grep -q exits 1 when the status text is not exactly matches-verified-version, which fails the RUN step
    out = io.StringIO()
    cb.main(['--kombu-status'], stdout=out)
    assert re.fullmatch(r'kombu (\S+|None): (matches-verified-version|differs-from-verified-version|kombu-not-installed)\n', out.getvalue())
    for installed, ok in (('5.4.2', True), ('5.5.2', False), (None, False)):
        line = f'kombu {installed}: {cb.kombu_pin_status(installed)}'
        assert bool(re.search(r': matches-verified-version$', line)) is ok


def test_constraints_file_stays_inside_the_docker_build_context():
    ignore = (ROOT / '.dockerignore').read_text().splitlines()
    assert not any(x.strip().rstrip('/') in ('deploy', 'deploy/local', 'deploy/local/constraints-rabbitmq.txt', '*.txt') for x in ignore)
    assert CONSTRAINTS.is_file()


def test_compose_builds_api_and_worker_from_the_rabbit_dockerfile_with_repo_root_context():
    for name in ('api', 'worker'):
        build = _override()['services'][name]['build']
        assert build == {'context': '../..', 'dockerfile': 'deploy/local/Dockerfile.rabbitmq'}
        assert (ROOT / 'deploy/local' / '../..' / build['dockerfile']).resolve() == RABBIT_DOCKERFILE.resolve()
    assert _base()['x-runtime']['build'] == {'context': '../..'}  # base context the override must agree with


def test_celery_pin_matches_pyproject_range_and_celery_540_requires_the_kombu_pin_range():
    text = (ROOT / 'pyproject.toml').read_text()
    assert '"celery[redis]>=5.4,<6"' in text  # celery==5.4.0 is inside this range
    assert (5, 4, 0) >= (5, 4) and (5, 3, 4) <= tuple(int(x) for x in cb.VERIFIED_KOMBU_VERSION.split('.')) < (6, 0, 0)


@pytest.mark.parametrize('path', [RABBIT_DOCKERFILE, STOCK_DOCKERFILE])
def test_dockerfiles_contain_no_credentials_or_urls_with_userinfo(path):
    assert not re.search(r'\w+://[^/\s:@]+:[^/\s@]*@', path.read_text())


def test_caller_contract_wording_is_in_both_module_docstrings_exactly():
    contract = ('new backend opt-in, unwired; legacy RabbitTopicBus on ATLAS_RABBITMQ_URL remains the active path; '
                'selection mechanism:')
    for mod in (rb, cb):
        doc = ' '.join((mod.__doc__ or '').split())
        assert contract in doc
        assert 'BOTH the legacy ATLAS_RABBITMQ_URL AND the ATLAS_RABBITMQ_HOST/USER/PASSWORD parts must point at the SAME broker' in doc
