"""E9 task generator: authored multi-file Python repair tasks. 6 modules x 3 functions (2 primitives + 1 cross-module
composite). Later modules call functions defined in earlier modules. Bugs are k single AST mutations injected in k
different functions. Visible tests drive the agent; hidden tests (never shown to any agent) score the final program.
Data statement: the projects, tests and bugs are authored synthetic data (templates + seeded random constants)."""
import ast, copy, random, signal, sys

L2L = {
"prefix": "def {N}(xs):\n    out = []\n    s = 0\n    for x in xs:\n        s = s + x\n        out.append(s)\n    return out\n",
"clip": "def {N}(xs):\n    out = []\n    for x in xs:\n        y = x\n        if y < {LO}:\n            y = {LO}\n        if y > {HI}:\n            y = {HI}\n        out.append(y)\n    return out\n",
"diff": "def {N}(xs):\n    out = []\n    for i in range(1, len(xs)):\n        out.append(xs[i] - xs[i - 1])\n    return out\n",
"dedupe": "def {N}(xs):\n    out = []\n    for x in xs:\n        if len(out) == 0 or out[-1] != x:\n            out.append(x)\n    return out\n",
"affine": "def {N}(xs):\n    out = []\n    for x in xs:\n        out.append((x * {A} + {B}) % {M})\n    return out\n",
"keepgt": "def {N}(xs):\n    out = []\n    for x in xs:\n        if x > {T}:\n            out.append(x)\n    return out\n",
"winmax": "def {N}(xs):\n    out = []\n    for i in range(len(xs) - {W} + 1):\n        m = xs[i]\n        for j in range(1, {W}):\n            if xs[i + j] > m:\n                m = xs[i + j]\n        out.append(m)\n    return out\n",
"runmax": "def {N}(xs):\n    out = []\n    m = {LO}\n    for x in xs:\n        if x > m:\n            m = x\n        out.append(m)\n    return out\n",
}
L2I = {
"countgt": "def {N}(xs):\n    c = 0\n    for x in xs:\n        if x > {T}:\n            c = c + 1\n    return c\n",
"sumabs": "def {N}(xs):\n    t = 0\n    for x in xs:\n        if x < 0:\n            t = t - x\n        else:\n            t = t + x\n    return t\n",
"maxgap": "def {N}(xs):\n    best = 0\n    for i in range(1, len(xs)):\n        g = xs[i] - xs[i - 1]\n        if g < 0:\n            g = 0 - g\n        if g > best:\n            best = g\n    return best\n",
"inversions": "def {N}(xs):\n    c = 0\n    for i in range(len(xs)):\n        for j in range(i + 1, len(xs)):\n            if xs[i] > xs[j]:\n                c = c + 1\n    return c\n",
"longrun": "def {N}(xs):\n    if len(xs) == 0:\n        return 0\n    best = 1\n    cur = 1\n    for i in range(1, len(xs)):\n        if xs[i] == xs[i - 1]:\n            cur = cur + 1\n        else:\n            cur = 1\n        if cur > best:\n            best = cur\n    return best\n",
"weighted": "def {N}(xs):\n    t = 0\n    for i in range(len(xs)):\n        t = t + i * xs[i]\n    return t\n",
"argmax": "def {N}(xs):\n    if len(xs) == 0:\n        return -1\n    k = 0\n    for i in range(1, len(xs)):\n        if xs[i] > xs[k]:\n            k = i\n    return k\n",
"altsum": "def {N}(xs):\n    t = 0\n    s = 1\n    for x in xs:\n        t = t + s * x\n        s = 0 - s\n        s = s\n    return t\n",
}
NMOD, NPRIM, NVIS = 6, 2, 8
CMP = ["Lt", "LtE", "Gt", "GtE", "Eq", "NotEq"]
ARI = [["Add", "Sub", "Mult"], ["Mod", "FloorDiv"]]
LISTNAMES = {"xs", "out"}


def params(r):
    lo = r.randint(-3, 0)
    return dict(LO=lo, HI=lo + r.randint(2, 6), A=r.randint(2, 4), B=r.randint(0, 3), M=r.randint(5, 9),
                T=r.randint(-2, 3), W=r.randint(2, 3))


def sites_of(tree):
    """Deterministic list of (node_index, kind, lineno, variants) for structure-preserving mutations."""
    out = []
    fn_names = {}
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        names = {a.arg for a in fn.args.args} | {t.id for n in ast.walk(fn) if isinstance(n, ast.Assign)
                 for t in n.targets if isinstance(t, ast.Name)} | {n.target.id for n in ast.walk(fn) if isinstance(n, ast.For)}
        for n in ast.walk(fn): fn_names[id(n)] = sorted(names - LISTNAMES)
    for i, n in enumerate(ast.walk(tree)):
        if isinstance(n, ast.Compare) and len(n.ops) == 1:
            cur = type(n.ops[0]).__name__
            if cur in CMP: out.append((i, "cmp", n.lineno, [c for c in CMP if c != cur]))
        elif isinstance(n, ast.BinOp):
            cur = type(n.op).__name__
            for g in ARI:
                if cur in g: out.append((i, "ari", n.lineno, [c for c in g if c != cur]))
        elif isinstance(n, ast.BoolOp):
            out.append((i, "bool", n.lineno, ["Or" if isinstance(n.op, ast.And) else "And"]))
        elif isinstance(n, ast.Constant) and type(n.value) is int:
            out.append((i, "const", n.lineno, [n.value + 1, n.value - 1]))
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in LISTNAMES and n.id in fn_names.get(id(n), []):
            out.append((i, "name", n.lineno, [v for v in fn_names[id(n)] if v != n.id]))
    return [o for o in out if o[3]]


def apply_edits(tree, edits):
    """edits: dict node_index -> variant. Returns mutated deep copy."""
    t = copy.deepcopy(tree)
    for i, n in enumerate(ast.walk(t)):
        if i in edits:
            v = edits[i]
            if isinstance(n, ast.Compare): n.ops = [getattr(ast, v)()]
            elif isinstance(n, ast.BinOp): n.op = getattr(ast, v)()
            elif isinstance(n, ast.BoolOp): n.op = getattr(ast, v)()
            elif isinstance(n, ast.Constant): n.value = v
            elif isinstance(n, ast.Name): n.id = v
    return t


class Timeout(Exception): pass
def _alarm(*a): raise Timeout()


class Project:
    def __init__(self, seed, k):
        r = random.Random(seed)
        self.seed, self.k = seed, k
        self.src, self.l2l, self.l2i, self.funcs = [], [], [], []
        for m in range(NMOD):
            s = ""
            for p in range(NPRIM):
                if p == 0 or r.random() < 0.5:
                    t = r.choice(sorted(L2L)); name = f"{t}_{m}_{p}"; self.l2l.append(name)
                    s += L2L[t].format(N=name, **params(r)) + "\n"
                else:
                    t = r.choice(sorted(L2I)); name = f"{t}_{m}_{p}"; self.l2i.append(name)
                    s += L2I[t].format(N=name, **params(r)) + "\n"
                self.funcs.append(name)
            if not self.l2i:
                t = r.choice(sorted(L2I)); name = f"{t}_{m}_x"; self.l2i.append(name)
                s += L2I[t].format(N=name, **params(r)) + "\n"; self.funcs.append(name)
            L = r.choice(self.l2l[:-1] if len(self.l2l) > 1 and m else self.l2l)
            R = r.choice(self.l2i)
            name = f"comp_{m}"
            s += f"def {name}(xs):\n    return {R}({L}(xs)) + {r.randint(0, 3)}\n"
            self.funcs.append(name)
            self.src.append(s)
        self.trees = [ast.parse(s, f"<m{i}>") for i, s in enumerate(self.src)]
        self.sites = [sites_of(t) for t in self.trees]
        self.ref = self.build({})
        self.vis, self.hid = [], []
        for f in self.funcs:
            for j in range(NVIS + 20):
                xs = [r.randint(-6, 9) for _ in range(r.choice([0, 1, 2, 3, 5, 6, 8]))]
                if j == 0: xs = [] if r.random() < 0.3 else xs
                (self.vis if j < NVIS else self.hid).append((f, tuple(xs), self.ref[f](list(xs))))
        self.bugs = self._inject(r, k)

    def build(self, edits):
        """edits: dict (module, node_index) -> variant. Returns namespace of functions (timeout-guarded callers)."""
        ns = {}
        for i, t in enumerate(self.trees):
            e = {n: v for (m, n), v in edits.items() if m == i}
            tt = apply_edits(t, e) if e else t
            exec(compile(tt, f"<m{i}>", "exec"), ns)
        return ns

    def run(self, ns, tests):
        """number of failing tests; infinite loops/exceptions count as failures."""
        bad = 0
        signal.setitimer(signal.ITIMER_REAL, 2.0)
        try:
            for f, xs, exp in tests:
                try:
                    if ns[f](list(xs)) != exp: bad += 1
                except Timeout: return len(tests)
                except Exception: bad += 1
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        return bad

    def _inject(self, r, k):
        signal.signal(signal.SIGALRM, _alarm)
        mods = r.sample(range(NMOD), k)
        bugs = {}
        for m in mods:
            for _ in range(200):
                i, kind, line, vs = r.choice(self.sites[m])
                v = r.choice(vs)
                if self.run(self.build({(m, i): v}), self.vis) > 0:
                    bugs[(m, i)] = v; break
            else: raise RuntimeError("no detectable bug")
        return bugs

    def edit_space(self):
        """All single-site values per site, including the original value (a 'revert'), so bug locations are not leaked."""
        return [((m, i), v, kind) for m in range(NMOD) for (i, kind, line, vs) in self.sites[m]
                for v in vs + [self.original_of((m, i))]]

    def original_of(self, key):
        m, i = key
        n = list(ast.walk(self.trees[m]))[i]
        if isinstance(n, ast.Compare): return type(n.ops[0]).__name__
        if isinstance(n, (ast.BinOp, ast.BoolOp)): return type(n.op).__name__
        return n.value if isinstance(n, ast.Constant) else n.id
