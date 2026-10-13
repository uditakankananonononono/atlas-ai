"""Skill genome: precondition, executable procedure, expected outputs, known failure cases,
verification tests. The procedure is real source text that is exec'd (restricted builtins)."""
from __future__ import annotations
from dataclasses import dataclass, field
from ops import OPS

PRE_FLAGS = ("nonneg", "distinct", "nonempty")
CON_FLAGS = ("len_le", "subset", "sorted")

def pre_props(x):
    return {"nonneg": all(v >= 0 for v in x), "distinct": len(set(x)) == len(x), "nonempty": len(x) > 0}

def con_props(x, y):
    return {"len_le": len(y) <= len(x), "subset": set(y) <= set(x), "sorted": list(y) == sorted(y)}

def source_for(program):
    lines = ["def run(xs):"] + [f"    xs = OPS[{n!r}](xs)" for n in program] + ["    return xs"]
    return "\n".join(lines)

def compile_procedure(src):
    ns = {"__builtins__": {}, "OPS": OPS}
    exec(src, ns)
    return ns["run"]

@dataclass
class Skill:
    sid: str
    program: tuple                 # flattened base-op names (the genome's genotype)
    origin: str                    # induced | rewritten | combined | manual
    precondition: frozenset        # PRE_FLAGS that must hold for the input it receives
    expected: frozenset            # CON_FLAGS that the output must satisfy vs its input
    tests: list                    # [(input_tuple, output_tuple)] verification tests
    failure_cases: list = field(default_factory=list)   # [{"task","input","expected","got"}]
    parent: str | None = None
    procedure: str = ""
    fn: object = None
    def __post_init__(self):
        self.procedure = source_for(self.program)
        self.fn = compile_procedure(self.procedure)

    def applicable(self, x):
        p = pre_props(x)
        return all(p[f] for f in self.precondition)

    def contract_ok(self, x, y):
        c = con_props(x, y)
        return all(c[f] for f in self.expected)

    def run_tests(self):
        for i, o in self.tests:
            try:
                if tuple(self.fn(i)) != tuple(o):
                    return False
            except Exception:
                return False
        return True

def make_skill(sid, program, origin, tests, parent=None, failure_cases=None):
    """Infer precondition/expected-output contract from the tests' inputs/outputs (flags that held on all)."""
    pre = {f for f in PRE_FLAGS if all(pre_props(i)[f] for i, _ in tests)}
    con = {f for f in CON_FLAGS if all(con_props(i, o)[f] for i, o in tests)}
    return Skill(sid, tuple(program), origin, frozenset(pre), frozenset(con), list(tests),
                 list(failure_cases or []), parent)
