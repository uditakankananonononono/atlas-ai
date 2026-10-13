"""Author-only hidden worlds. This file must never be imported by the proposer."""
import hashlib
import numpy as np
from engine import MASK, SETTINGS


def generate(seed, count, outside=False):
    if not 1 <= count <= (80 if outside else 400):
        raise ValueError("requested worlds exceed safe finite-support bound")
    rng = np.random.default_rng(seed)
    seen = set()
    worlds = []
    while len(worlds) < count:
        i, j, k = map(int, rng.choice(5, 3, replace=False))
        a, b, c = (SETTINGS[:, q].copy() for q in (i, j, k))
        a ^= int(rng.integers(2)); b ^= int(rng.integers(2)); c ^= int(rng.integers(2))
        op1, op2 = rng.choice(["and", "or", "xor"], 2)
        fn = {"and": np.bitwise_and, "or": np.bitwise_or, "xor": np.bitwise_xor}
        values = ((a + b + c) >= 2).astype(int) if outside else fn[op2](fn[op1](a, b), c)
        table = sum(int(y) << s for s, y in enumerate(values))
        if table in seen:
            continue
        seen.add(table)
        digest = hashlib.sha256(str(table).encode()).hexdigest()
        # Behavioral hash split, never same table on development and holdout.
        split = "development" if int(digest[:8], 16) % 4 == 0 else "heldout"
        worlds.append(dict(table=table, world_id=digest[:12], split=split,
                           outside=outside))
    return worlds
