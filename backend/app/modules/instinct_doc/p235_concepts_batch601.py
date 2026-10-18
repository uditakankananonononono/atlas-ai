"""b601 exact deterministic cache replacement simulation with recount certificates.

Reference strings are tuples of length 0..REF_MAX of exact int keys 0..KEY_MAX
(booleans and int subclasses refused); capacities are exact ints 1..CAP_MAX.
Policies: LRU (hit moves to front), FIFO (no reorder on hit), LFU (evict the
least frequent, ties to the least recently used), and Belady MIN (offline:
evict the key whose next use is furthest ahead, never-used-again counts as
infinity, ties broken to the larger key). Check order is pinned: container arguments in global phases across
ALL container arguments (tuple types, then length caps and shapes, then
element types, then element ranges; within a phase, arguments are visited
in positional order), then scalar/tag arguments in positional order (type
before value), then cross-argument constraints (state length versus
capacity, certificate key uniqueness and order). Structural violations raise ValueError P235:<name>:<code>;
a well-formed but wrong certificate returns False. Deterministic only.
States: LRU tuple most-recent-first, FIFO tuple oldest-first, LFU tuple of
(key, frequency) pairs sorted by key, MIN certificate is (hits, evictions).
"""
from importlib.util import find_spec
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry' or find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:
        raise
    def make_fail(name):
        def fail(code):
            raise ValueError('P235:%s:%s' % (name, code))
        return fail

SCOPE = 'PARTIAL exact deterministic cache replacement simulation over supplied bounded reference strings with recount certificates'
NOT_CLAIMED = ('AGI-like intelligence', 'hardware cache fidelity', 'optimality beyond exact Belady recomputation', 'production readiness')

REF_MAX = 256
KEY_MAX = 63
CAP_MAX = 8
POLICIES = ('lru', 'fifo', 'lfu')


def _refs(f, label, refs):
    if type(refs) is not tuple:
        f('bad_type:' + label)
    if len(refs) > REF_MAX:
        f('bad_value:' + label)
    for x in refs:
        if type(x) is not int:
            f('bad_type:' + label + ' element')
    for x in refs:
        if not 0 <= x <= KEY_MAX:
            f('bad_value:' + label + ' element')
    return refs


def _cap(f, cap):
    if type(cap) is not int:
        f('bad_type:cap')
    if not 1 <= cap <= CAP_MAX:
        f('bad_value:cap')
    return cap


def _policy(f, policy):
    if type(policy) is not str:
        f('bad_type:policy')
    if policy not in POLICIES:
        f('bad_value:policy')
    return policy


def _lru(refs, cap):
    state = []
    hits = 0
    for x in refs:
        if x in state:
            hits += 1
            state.remove(x)
            state.insert(0, x)
        else:
            state.insert(0, x)
            if len(state) > cap:
                state.pop()
    return hits, tuple(state)


def _fifo(refs, cap):
    state = []
    hits = 0
    for x in refs:
        if x in state:
            hits += 1
        else:
            state.append(x)
            if len(state) > cap:
                state.pop(0)
    return hits, tuple(state)


def _lfu(refs, cap):
    freq = {}
    used = {}
    hits = 0
    for t, x in enumerate(refs):
        if x in freq:
            hits += 1
            freq[x] += 1
            used[x] = t
        else:
            if len(freq) == cap:
                victim = min(freq, key=lambda k: (freq[k], used[k]))
                del freq[victim]
                del used[victim]
            freq[x] = 1
            used[x] = t
    return hits, tuple(sorted(freq.items()))


def _min(refs, cap):
    cache = set()
    hits = 0
    evicted = []
    for t, x in enumerate(refs):
        if x in cache:
            hits += 1
            continue
        if len(cache) == cap:
            def nxt(k):
                try:
                    return refs.index(k, t + 1)
                except ValueError:
                    return len(refs) + 1
            victim = max(cache, key=lambda k: (nxt(k), k)) # furthest next use, ties to the larger key
            cache.discard(victim)
            evicted.append(victim)
        cache.add(x)
    return hits, tuple(evicted)


def lru_simulate(refs, cap):
    """(hits, final LRU state most-recent-first) for the reference string."""
    f = make_fail('lru_simulate')
    return _lru(_refs(f, 'refs', refs), _cap(f, cap))


def _cert_head(f, refs, cert):
    if type(refs) is not tuple:
        f('bad_type:refs')
    if type(cert) is not tuple:
        f('bad_type:cert')
    if len(refs) > REF_MAX:
        f('bad_value:refs')
    if len(cert) != 2:
        f('bad_shape:cert')
    h, st = cert
    for x in refs:
        if type(x) is not int:
            f('bad_type:refs element')
    if type(h) is not int:
        f('bad_type:cert hits')
    if type(st) is not tuple:
        f('bad_type:cert state')
    return h, st


def _refs_ranges(f, refs):
    for x in refs:
        if not 0 <= x <= KEY_MAX:
            f('bad_value:refs element')


def _state_int_types(f, st):
    for x in st:
        if type(x) is not int:
            f('bad_type:cert state element')


def _state_int_ranges(f, st):
    for x in st:
        if not 0 <= x <= KEY_MAX:
            f('bad_value:cert state element')


def lru_check(refs, cap, cert):
    """cert is exactly the deterministic lru_simulate output."""
    f = make_fail('lru_check')
    h, st = _cert_head(f, refs, cert)
    _state_int_types(f, st)
    _refs_ranges(f, refs)
    if h < 0:
        f('bad_value:cert hits')
    _state_int_ranges(f, st)
    c = _cap(f, cap)
    if len(st) > c:
        f('bad_value:cert state')
    return (h, st) == _lru(refs, c)


def fifo_simulate(refs, cap):
    """(hits, final FIFO state oldest-first) for the reference string."""
    f = make_fail('fifo_simulate')
    return _fifo(_refs(f, 'refs', refs), _cap(f, cap))


def fifo_check(refs, cap, cert):
    """cert is exactly the deterministic fifo_simulate output."""
    f = make_fail('fifo_check')
    h, st = _cert_head(f, refs, cert)
    _state_int_types(f, st)
    _refs_ranges(f, refs)
    if h < 0:
        f('bad_value:cert hits')
    _state_int_ranges(f, st)
    c = _cap(f, cap)
    if len(st) > c:
        f('bad_value:cert state')
    return (h, st) == _fifo(refs, c)


def lfu_simulate(refs, cap):
    """(hits, final LFU state as (key, frequency) pairs sorted by key);
    eviction picks the least frequent, ties to the least recently used."""
    f = make_fail('lfu_simulate')
    return _lfu(_refs(f, 'refs', refs), _cap(f, cap))


def lfu_check(refs, cap, cert):
    """cert is exactly the deterministic lfu_simulate output."""
    f = make_fail('lfu_check')
    h, st = _cert_head(f, refs, cert)
    for p in st:
        if type(p) is not tuple or len(p) != 2:
            f('bad_shape:cert state entry')
    for p in st:
        if type(p[0]) is not int or type(p[1]) is not int:
            f('bad_type:cert state entry')
    _refs_ranges(f, refs)
    if h < 0:
        f('bad_value:cert hits')
    for p in st:
        if not 0 <= p[0] <= KEY_MAX or p[1] < 1:
            f('bad_value:cert state entry')
    c = _cap(f, cap)
    if len(st) > c:
        f('bad_value:cert state')
    vs = [p[0] for p in st]
    if len(set(vs)) != len(vs):
        f('bad_value:cert state duplicate')
    if any(vs[i] >= vs[i + 1] for i in range(len(vs) - 1)):
        f('bad_value:cert state order')
    return (h, st) == _lfu(refs, c)


def belady_min(refs, cap):
    """(hits, evicted keys in order) under Belady's offline MIN rule."""
    f = make_fail('belady_min')
    return _min(_refs(f, 'refs', refs), _cap(f, cap))


def belady_check(refs, cap, cert):
    """cert is exactly the deterministic belady_min output, and its hit count
    dominates the lru/fifo/lfu hit counts on the same inputs (optimality
    witness inequality)."""
    f = make_fail('belady_check')
    h, ev = _cert_head(f, refs, cert)
    _state_int_types(f, ev)
    _refs_ranges(f, refs)
    if h < 0:
        f('bad_value:cert hits')
    _state_int_ranges(f, ev)
    c = _cap(f, cap)
    if len(ev) > len(refs):
        f('bad_value:cert state')
    if (h, ev) != _min(refs, c):
        return False
    return h >= _lru(refs, c)[0] and h >= _fifo(refs, c)[0] and h >= _lfu(refs, c)[0]


def eviction_log(refs, cap, policy):
    """Evicted keys in order under the named online policy."""
    f = make_fail('eviction_log')
    _refs(f, 'refs', refs)
    c = _cap(f, cap)
    p = _policy(f, policy)
    state = []
    freq = {}
    used = {}
    out = []
    for t, x in enumerate(refs):
        if p == 'lru':
            if x in state:
                state.remove(x)
                state.insert(0, x)
            else:
                state.insert(0, x)
                if len(state) > c:
                    out.append(state.pop())
        elif p == 'fifo':
            if x not in state:
                state.append(x)
                if len(state) > c:
                    out.append(state.pop(0))
        else:
            if x in freq:
                freq[x] += 1
                used[x] = t
            else:
                if len(freq) == c:
                    victim = min(freq, key=lambda k: (freq[k], used[k]))
                    out.append(victim)
                    del freq[victim]
                    del used[victim]
                freq[x] = 1
                used[x] = t
    return tuple(out)


def log_check(refs, cap, policy, log):
    """log is exactly the deterministic eviction_log output."""
    f = make_fail('log_check')
    if type(refs) is not tuple:
        f('bad_type:refs')
    if type(log) is not tuple:
        f('bad_type:log')
    if len(refs) > REF_MAX:
        f('bad_value:refs')
    if len(log) > len(refs):
        f('bad_value:log')
    for x in refs:
        if type(x) is not int:
            f('bad_type:refs element')
    for x in log:
        if type(x) is not int:
            f('bad_type:log element')
    _refs_ranges(f, refs)
    for x in log:
        if not 0 <= x <= KEY_MAX:
            f('bad_value:log element')
    c = _cap(f, cap)
    p = _policy(f, policy)
    return log == eviction_log(refs, c, p)
