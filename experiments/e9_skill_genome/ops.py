"""Base operations (the agent's primitive vocabulary). All pure, tuple -> tuple."""
from __future__ import annotations

def _mk():
    o = {}
    o["sort"] = lambda x: tuple(sorted(x))
    o["sort_desc"] = lambda x: tuple(sorted(x, reverse=True))
    o["reverse"] = lambda x: tuple(reversed(x))
    def dedupe(x):
        seen, out = set(), []
        for v in x:
            if v not in seen:
                seen.add(v); out.append(v)
        return tuple(out)
    o["dedupe"] = dedupe
    def cumsum(x):
        s, out = 0, []
        for v in x:
            s += v; out.append(s)
        return tuple(out)
    o["cumsum"] = cumsum
    def running_max(x):
        m, out = None, []
        for v in x:
            m = v if m is None or v > m else m
            out.append(m)
        return tuple(out)
    o["running_max"] = running_max
    o["pair_sum"] = lambda x: tuple(x[i] + x[i + 1] for i in range(len(x) - 1))
    o["abs"] = lambda x: tuple(abs(v) for v in x)
    o["filter_pos"] = lambda x: tuple(v for v in x if v > 0)
    o["filter_even"] = lambda x: tuple(v for v in x if v % 2 == 0)
    o["filter_odd"] = lambda x: tuple(v for v in x if v % 2 == 1)
    o["filter_gt2"] = lambda x: tuple(v for v in x if v > 2)
    o["filter_gt5"] = lambda x: tuple(v for v in x if v > 5)
    o["add1"] = lambda x: tuple(v + 1 for v in x)
    o["sub1"] = lambda x: tuple(v - 1 for v in x)
    o["add3"] = lambda x: tuple(v + 3 for v in x)
    o["mul2"] = lambda x: tuple(v * 2 for v in x)
    o["neg"] = lambda x: tuple(-v for v in x)
    o["sq"] = lambda x: tuple(v * v for v in x)
    o["halve"] = lambda x: tuple(v // 2 for v in x)
    o["mod5"] = lambda x: tuple(v % 5 for v in x)
    o["mod3"] = lambda x: tuple(v % 3 for v in x)
    o["take3"] = lambda x: tuple(x[:3])
    o["take5"] = lambda x: tuple(x[:5])
    o["drop1"] = lambda x: tuple(x[1:])
    o["drop2"] = lambda x: tuple(x[2:])
    o["rotate1"] = lambda x: tuple(x[1:] + x[:1])
    o["every2"] = lambda x: tuple(x[::2])
    o["clip9"] = lambda x: tuple(min(max(v, 0), 9) for v in x)
    return o

OPS = _mk()
NAMES = tuple(OPS)          # deterministic order
