"""Group 80 math engine: exact, bounded problem solvers with independent verification.

Instinct doc request (group 80): "Crack maths problems and dilemmas in any field."

Scope honestly stated: this engine solves NAMED problem families exactly -
linear systems, quadratics, polynomial calculus, linear Diophantine equations,
factorization/primality, Chinese remainder systems, combinatorics, sequences
and descriptive statistics - plus safe arithmetic expression evaluation. It
does NOT solve unrestricted "any field" mathematics: no geometry, no proof
generation, no non-polynomial calculus, no differential equations. Every
result carries a verification receipt computed by a SEPARATE code path
(verify()); a result whose verification fails is never reported as solved.
Stdlib only. All inputs are bounds-checked with explicit refusals.
"""
from __future__ import annotations

import ast
import math
import random
from fractions import Fraction

RATIONAL_BOUND = 10**12
MAX_INT_BITS = 200  # ~10**60; intermediate cap inside the expression evaluators
RHO_ITERATION_BUDGET = 500000
MAX_UNKNOWNS = 8
MAX_DEGREE = 64
MAX_FACTOR = 10**18
MAX_CRT = 8
MAX_COMB_N = 10**5
COMB_RESULT_BOUND = 10**60
MAX_EXPR_LEN = 256
MAX_EXPR_POW = 64
MAX_TERMS = 65
MAX_SEQ_N = 10**6
MAX_STATS_ROWS = 10000


def _rational(value, label):
    if type(value) is int:
        result = Fraction(value)
    elif type(value) is Fraction:
        result = value
    elif isinstance(value, str) and len(value) <= 64 and \
            __import__('re').fullmatch(r'[+-]?[0-9]{1,64}(/[0-9]{1,64})?', value):
        try:
            result = Fraction(value)
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError(label + ' requires rational string/integer') from exc
    else:
        raise ValueError(label + ' requires rational string/integer')
    if abs(result.numerator) > RATIONAL_BOUND or result.denominator > RATIONAL_BOUND:
        raise ValueError(label + ' rational components exceed 10**12')
    return result


def _bigint(value, label, bound=MAX_FACTOR):
    if type(value) is int:
        out = value
    elif type(value) is Fraction and value.denominator == 1:
        out = value.numerator
    elif isinstance(value, str) and __import__('re').fullmatch(r'[+-]?[0-9]{1,50}', value):
        out = int(value)
    else:
        raise ValueError(label + ' requires an integer <= 10**18')
    if abs(out) > bound:
        raise ValueError(label + ' exceeds bound')
    return out


def _cap(value, label):
    if value.numerator.bit_length() > MAX_INT_BITS or \
            value.denominator.bit_length() > MAX_INT_BITS:
        raise ValueError(label + ' intermediate exceeds size bound')
    return value


def _rational_list(values, label, lo, hi):
    if not isinstance(values, list) or not lo <= len(values) <= hi:
        raise ValueError(label + ' requires a list of %d..%d entries' % (lo, hi))
    return [_rational(v, label + ' entry') for v in values]


# ----------------------------------------------------------------Surd exact form
class Surd:
    """Exact quadratic surd a + b*sqrt(r), r squarefree positive integer."""

    def __init__(self, a, b=Fraction(0), r=1):
        self.a, self.b, self.r = a, b, r

    @staticmethod
    def _pair(x, o):
        o = o if isinstance(o, Surd) else Surd(o)
        if x.r != o.r:
            if x.b == 0:
                x = Surd(x.a, Fraction(0), o.r)
            elif o.b == 0:
                o = Surd(o.a, Fraction(0), x.r)
            else:
                raise ValueError('surd radical mismatch')
        return x, o

    def __add__(self, o):
        x, o = Surd._pair(self, o)
        return Surd(x.a + o.a, x.b + o.b, x.r)

    def __neg__(self):
        return Surd(-self.a, -self.b, self.r)

    def __sub__(self, o):
        return self + (-o if isinstance(o, Surd) else Surd(-o))

    def __mul__(self, o):
        x, o = Surd._pair(self, o)
        return Surd(x.a * o.a + x.b * o.b * x.r, x.a * o.b + x.b * o.a, x.r)

    def __eq__(self, o):
        o = o if isinstance(o, Surd) else Surd(o)
        sa = (self.a, self.b, self.r if self.b != 0 else 1)
        oa = (o.a, o.b, o.r if o.b != 0 else 1)
        return sa == oa

    def __str__(self):
        if self.b == 0:
            return str(self.a)
        return '(%s)+(%s)*sqrt(%d)' % (self.a, self.b, self.r)


def _squarefree(n):
    """Exact squarefree kernel via bounded full factorization (n <= 10**18)."""
    if not 1 <= n <= MAX_FACTOR:
        raise ValueError('squarefree input outside 1..10**18')
    out = 1
    f = 2
    rest = n
    while f * f <= rest and f <= 10**6:
        e = 0
        while rest % f == 0:
            rest //= f
            e += 1
        if e % 2 == 1:
            out *= f
        f += 1
    if rest > 1:
        # rest has no factor <= 10**6; it is prime, p*q, or p**2/q**2-free parts
        if is_prime(rest):
            out *= rest
        else:
            root = math.isqrt(rest)
            if root * root == rest:
                if not is_prime(root):
                    raise ValueError('squarefree factorization inconclusive')
                # p**2 contributes nothing to the kernel
            else:
                f1 = _pollard_rho(rest, [RHO_ITERATION_BUDGET])
                f2 = rest // f1
                if not (is_prime(f1) and is_prime(f2)):
                    raise ValueError('squarefree factorization inconclusive')
                out *= f1 if f1 != f2 else 1
                if f1 != f2:
                    out *= f2
    return out


# ----------------------------------------------------------------linear systems
def solve_linear_system(matrix, vector):
    """Gaussian elimination over Fraction on matrix x = vector."""
    a = [_rational_list(row, 'matrix row', 1, MAX_UNKNOWNS) for row in
         (matrix if isinstance(matrix, list) else (_ for _ in ()).throw(ValueError('matrix list required')))]
    b = _rational_list(vector, 'vector', 1, MAX_UNKNOWNS)
    n = len(a)
    if len(b) != n or any(len(row) != n for row in a):
        raise ValueError('square matrix with matching vector required (<= %d unknowns)' % MAX_UNKNOWNS)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    pivots, row = [], 0
    for col in range(n):
        pivot = next((r for r in range(row, n) if m[r][col] != 0), None)
        if pivot is None:
            continue
        m[row], m[pivot] = m[pivot], m[row]
        pv = m[row][col]
        m[row] = [v / pv for v in m[row]]
        for r in range(n):
            if r != row and m[r][col] != 0:
                factor = m[r][col]
                m[r] = [v - factor * w for v, w in zip(m[r], m[row])]
        pivots.append(col)
        row += 1
    rank_a = len(pivots)
    rank_aug = _rank([row[:] + [b[i]] for i, row in enumerate(a)])
    if any(all(m[r][c] == 0 for c in range(n)) and m[r][n] != 0 for r in range(n)):
        return {'kind': 'linear_system', 'status': 'no_solution', 'rank_coefficients': rank_a,
                'rank_augmented': rank_aug, 'solution': None}
    if rank_a < n:
        return {'kind': 'linear_system', 'status': 'infinite_solutions',
                'rank_coefficients': rank_a, 'rank_augmented': rank_a, 'solution': None,
                'free_variables': n - rank_a}
    sol = [Fraction(0)] * n
    for i, col in enumerate(pivots):
        sol[col] = m[i][n]
    return {'kind': 'linear_system', 'status': 'unique', 'rank_coefficients': n,
            'rank_augmented': n, 'solution': [str(v) for v in sol]}


def _rank(rows):
    m = [row[:] for row in rows if any(v != 0 for v in row)]
    if not m:
        return 0
    nr, nc, rank = len(m), len(m[0]), 0
    for col in range(nc - 1, -1, -1):
        pivot = next((r for r in range(rank, nr) if m[r][col] != 0), None)
        if pivot is None:
            continue
        m[rank], m[pivot] = m[pivot], m[rank]
        pv = m[rank][col]
        for r in range(nr):
            if r != rank and m[r][col] != 0:
                f = m[r][col] / pv
                m[r] = [v - f * w for v, w in zip(m[r], m[rank])]
        rank += 1
    return rank


# ----------------------------------------------------------------quadratics
def _quadratic_exact(a, b, c):
    """Exact quadratic solution shared by the solver and the verifier."""
    a, b, c = _rational(a, 'a'), _rational(b, 'b'), _rational(c, 'c')
    if a == 0:
        raise ValueError('a must be nonzero for a quadratic')
    disc = b * b - 4 * a * c
    if disc < 0:
        return 'no_real_roots', disc, []
    p, q, r = -b / (2 * a), Fraction(0), 1
    if disc > 0:
        num, den = abs(disc.numerator), disc.denominator
        n2 = num * den  # sqrt(disc) == sqrt(n2) / den
        r = _squarefree(n2)
        d = math.isqrt(n2 // r)
        if d * d * r != n2:
            raise ValueError('discriminant not representable as a quadratic surd')
        q = Fraction(d, 2 * abs(a) * den)
    if disc > 0 and r == 1:
        roots = [Surd(p + q), Surd(p - q)]
    else:
        roots = [Surd(p, q, r), Surd(p, -q, r)] if disc > 0 else [Surd(p, Fraction(0), 1)]
    return ('two_real_roots' if disc > 0 else 'repeated_root'), disc, roots


def solve_quadratic(a, b, c):
    a, b, c = _rational(a, 'a'), _rational(b, 'b'), _rational(c, 'c')
    status, disc, roots = _quadratic_exact(a, b, c)
    if status == 'no_real_roots':
        return {'kind': 'quadratic', 'status': 'no_real_roots',
                'discriminant': str(disc), 'roots': [],
                'coefficients': [str(a), str(b), str(c)]}
    return {'kind': 'quadratic', 'status': status,
            'discriminant': str(disc),
            'roots': [str(x) for x in roots], '_roots_exact': roots,
            'coefficients': [str(a), str(b), str(c)]}


# ----------------------------------------------------------------polynomials
def _poly(coeffs, label):
    p = _rational_list(coeffs, label, 1, MAX_TERMS)
    if len(p) - 1 > MAX_DEGREE:
        raise ValueError(label + ' degree exceeds %d' % MAX_DEGREE)
    while len(p) > 1 and p[-1] == 0:
        p.pop()
    return p


def poly_derivative(coeffs):
    p = _poly(coeffs, 'polynomial')
    return [p[i] * i for i in range(1, len(p))] or [Fraction(0)]


def poly_integral(coeffs):
    p = _poly(coeffs, 'polynomial')
    return [Fraction(0)] + [p[i] / (i + 1) for i in range(len(p))]


def poly_eval(coeffs, x):
    x = _rational(x, 'x')
    out = Fraction(0)
    for c in reversed(_poly(coeffs, 'polynomial')):
        out = out * x + c
    return out


def _poly_eq(p, q):
    return _poly(list(p), 'p') == _poly(list(q), 'q')


# ----------------------------------------------------------------number theory
EGCD_BOUND = 10**160


def egcd(a, b):
    a, b = _bigint(a, 'a', EGCD_BOUND), _bigint(b, 'b', EGCD_BOUND)
    if a == 0 and b == 0:
        raise ValueError('egcd requires a nonzero input')
    old, new, so, sn = abs(a), abs(b), (1 if a >= 0 else -1), 0
    to, tn = 0, (1 if b >= 0 else -1)
    while new:
        q = old // new
        old, new = new, old - q * new
        so, sn = sn, so - q * sn
        to, tn = tn, to - q * tn
    return old, so, to


def solve_diophantine(a, b, c):
    a_i, b_i, c_i = _bigint(a, 'a'), _bigint(b, 'b'), _bigint(c, 'c')
    g, x0, y0 = egcd(a_i, b_i)
    if c_i % g != 0:
        return {'kind': 'diophantine', 'status': 'no_solution', 'gcd': g}
    k = c_i // g
    x, y = x0 * k, y0 * k
    return {'kind': 'diophantine', 'status': 'solved', 'gcd': g,
            'particular': [x, y],
            'general': ['x = %d + %d*t' % (x, b_i // g), 'y = %d - %d*t' % (y, a_i // g)]}


_MR_BASES_64 = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)


def _mr_witness(n, d, s, a):
    x = pow(a, d, n)
    if x in (1, n - 1):
        return False
    for _ in range(s - 1):
        x = x * x % n
        if x == n - 1:
            return False
    return True


def is_prime(n):
    n = _bigint(n, 'n')
    if not 0 < n <= MAX_FACTOR:
        raise ValueError('n within 1..10**18 required')
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n == p:
            return True
        if n % p == 0:
            return False
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    return not any(_mr_witness(n, d, s, a) for a in _MR_BASES_64)


def _pollard_rho(n, budget):
    if n % 2 == 0:
        return 2
    rng = random.Random(n)
    while True:
        x = rng.randrange(2, n - 1)
        y, c, d = x, rng.randrange(1, n - 1), 1
        while d == 1:
            budget[0] -= 1
            if budget[0] < 0:
                raise ValueError('factorization budget exhausted')
            x = (x * x + c) % n
            y = (y * y + c) % n
            y = (y * y + c) % n
            d = math.gcd(abs(x - y), n)
        if d != n:
            return d


def factor(n):
    n = _bigint(n, 'n')
    if not 1 < n <= MAX_FACTOR:
        raise ValueError('n within 2..10**18 required')
    out = []
    budget = [RHO_ITERATION_BUDGET]

    def split(m):
        if m == 1:
            return
        if is_prime(m):
            out.append(m)
            return
        d = _pollard_rho(m, budget)
        split(d)
        split(m // d)
    small = n
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        while small % p == 0:
            out.append(p)
            small //= p
    if small > 1:
        split(small)
    out.sort()
    return {'kind': 'factor', 'status': 'factored', 'n': n,
            'factors': out, 'distinct': sorted(set(out))}


def solve_crt(remainders, moduli):
    r = [_bigint(v, 'remainder') for v in remainders] if isinstance(remainders, list) else None
    m = [_bigint(v, 'modulus') for v in moduli] if isinstance(moduli, list) else None
    if r is None or m is None or not 1 <= len(r) <= MAX_CRT or len(r) != len(m):
        raise ValueError('1..%d congruence pairs required' % MAX_CRT)
    if any(v <= 0 or v > MAX_FACTOR for v in m):
        raise ValueError('positive moduli <= 10**18 required')
    for i in range(len(m)):
        for j in range(i + 1, len(m)):
            if math.gcd(m[i], m[j]) != 1:
                raise ValueError('pairwise coprime moduli required')
        r[i] %= m[i]
    x, big = 0, 1
    for mi in m:
        big *= mi
    if big > EGCD_BOUND:
        raise ValueError('combined modulus exceeds bound')
    for ri, mi in zip(r, m):
        partial = big // mi
        _, inv, _ = egcd(partial, mi)
        x = (x + ri * partial * inv) % big
    return {'kind': 'crt', 'status': 'solved', 'solution': x, 'modulus': big,
            'congruences': [[ri, mi] for ri, mi in zip(r, m)]}


# ----------------------------------------------------------------combinatorics
def combinatorics(op, n, k=None):
    n = _bigint(n, 'n')
    if not 0 <= n <= MAX_COMB_N:
        raise ValueError('n within 0..%d required' % MAX_COMB_N)
    if op in ('choose', 'permute'):
        k = _bigint(k, 'k') if k is not None else None
        if k is None or not 0 <= k <= n:
            raise ValueError('k within 0..n required')
    if op == 'choose':
        kk = min(k, n - k)
        result = 1
        for i in range(1, kk + 1):
            result = result * (n - kk + i) // i
            if result > COMB_RESULT_BOUND:
                raise ValueError('result exceeds 10**60')
    elif op == 'permute':
        result = 1
        for i in range(n - k + 1, n + 1):
            result *= i
            if result > COMB_RESULT_BOUND:
                raise ValueError('result exceeds 10**60')
    elif op == 'derangements':
        result, sign = 1, -1
        d = [1, 0]
        for i in range(2, n + 1):
            d.append((i - 1) * (d[i - 1] + d[i - 2]))
            if d[-1] > COMB_RESULT_BOUND:
                raise ValueError('result exceeds 10**60')
        result = d[n]
    elif op == 'catalan':
        if n > 500:
            raise ValueError('catalan n <= 500')
        result = 1
        for i in range(1, n + 1):
            result = result * (n + i) // i
            if result > COMB_RESULT_BOUND:
                raise ValueError('result exceeds 10**60')
        result //= (n + 1)
    elif op == 'fibonacci':
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
            if b > COMB_RESULT_BOUND:
                raise ValueError('result exceeds 10**60')
        result = a
    else:
        raise ValueError('op must be choose/permute/derangements/catalan/fibonacci')
    return {'kind': 'combinatorics', 'op': op, 'n': n,
            'k': k, 'status': 'computed', 'result': result}


# ----------------------------------------------------------------sequences
def sequence(kind, a1, step, n):
    a1, step = _rational(a1, 'a1'), _rational(step, 'step')
    n = _bigint(n, 'n')
    if not 1 <= n <= MAX_SEQ_N:
        raise ValueError('n within 1..10**6 required')
    if kind == 'arithmetic':
        nth = a1 + (n - 1) * step
        total = Fraction(n) * (a1 + nth) / 2
    elif kind == 'geometric':
        if step == 1:
            nth, total = a1, a1 * n
        else:
            bits = max(abs(step.numerator), 1).bit_length() + step.denominator.bit_length()
            if n * bits > 64 * MAX_INT_BITS:
                raise ValueError('sequence value exceeds bounds')
            powv = step ** (n - 1)
            if abs(powv.numerator) > 10**60 or powv.denominator > 10**60:
                raise ValueError('sequence value exceeds bounds')
            nth = a1 * powv
            total = a1 * (step ** n - 1) / (step - 1)
    else:
        raise ValueError('kind must be arithmetic/geometric')
    return {'kind': 'sequence', 'sequence_kind': kind, 'status': 'computed',
            'nth': str(nth), 'sum_first_n': str(total), 'n': n}


# ----------------------------------------------------------------statistics
def statistics(values):
    data = _rational_list(values, 'data', 1, MAX_STATS_ROWS)
    n = len(data)
    mean = sum(data, Fraction(0)) / n
    ordered = sorted(data)
    median = ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2
    var = sum((v - mean) ** 2 for v in data) / n
    return {'kind': 'statistics', 'status': 'computed', 'count': n,
            'mean': str(mean), 'median': str(median),
            'population_variance': str(var),
            'min': str(ordered[0]), 'max': str(ordered[-1])}


# ----------------------------------------------------------------expressions
_ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult,
            ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Constant, ast.Mod, ast.FloorDiv,
            ast.Modulo if hasattr(ast, 'Modulo') else ast.Mod)


def _eval_node(node):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if type(node.value) is int:
            return Fraction(node.value)
        raise ValueError('integer constants only (use a/b for fractions)')
    if isinstance(node, ast.UnaryOp):
        v = _eval_node(node.operand)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp):
        l, r = _eval_node(node.left), _eval_node(node.right)
        if isinstance(node.op, ast.Add):
            return _cap(l + r, 'add')
        if isinstance(node.op, ast.Sub):
            return _cap(l - r, 'subtract')
        if isinstance(node.op, ast.Mult):
            return _cap(l * r, 'multiply')
        if isinstance(node.op, ast.Div):
            if r == 0:
                raise ValueError('division by zero')
            return _cap(l / r, 'divide')
        if isinstance(node.op, ast.FloorDiv):
            if r == 0:
                raise ValueError('division by zero')
            return _cap(Fraction(l // r), 'floor_divide')
        if isinstance(node.op, ast.Mod):
            if r == 0:
                raise ValueError('modulo by zero')
            return _cap(Fraction(l % r), 'modulo')
        if isinstance(node.op, ast.Pow):
            if r.denominator != 1 or not 0 <= r <= MAX_EXPR_POW:
                raise ValueError('exponent must be an integer 0..%d' % MAX_EXPR_POW)
            if l != 0 and (abs(l).numerator.bit_length() - 1) * int(r) > MAX_INT_BITS:
                raise ValueError('power result exceeds size bound')
            return _cap(l ** int(r), 'power')
    raise ValueError('unsupported expression element')


def evaluate_expression(source):
    if not isinstance(source, str) or not 1 <= len(source) <= MAX_EXPR_LEN:
        raise ValueError('expression string of 1..%d chars required' % MAX_EXPR_LEN)
    if any(c.isalpha() for c in source):
        raise ValueError('numbers and operators only; names and calls refused')
    tree = ast.parse(source, mode='eval')
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ValueError('unsupported expression element: ' + type(node).__name__)
    value = _eval_node(tree)
    if abs(value.numerator) > 10**60 or value.denominator > 10**60:
        raise ValueError('expression value exceeds bounds')
    return {'kind': 'expression', 'status': 'computed', 'source': source, 'value': str(value)}


def _eval_rpn(source):
    """Independent evaluator: shunting-yard to RPN, stack evaluation."""
    import re as _re
    flat = source.replace(' ', '').replace('**', '\x01').replace('//', '\x02')
    tokens = [t.replace('\x01', '^').replace('\x02', '//')
              for t in _re.findall(r'\d+|[+\-*/%()]|\x01|\x02', flat)]
    if not tokens or ''.join(tokens) != flat.replace('\x01', '^').replace('\x02', '//'):
        raise ValueError('tokenizer mismatch')
    prec = {'+': 1, '-': 1, '*': 2, '/': 2, '%': 2, '//': 2, '^': 3, 'u-': 2.5}
    right_assoc = {'^', 'u-'}
    out, ops = [], []
    prev_op = True
    for t in tokens:
        if t.isdigit():
            out.append(Fraction(int(t)))
            prev_op = False
        elif t == '(':
            ops.append(t)
            prev_op = True
        elif t == ')':
            while ops and ops[-1] != '(':
                out.append(ops.pop())
            if not ops:
                raise ValueError('unbalanced parentheses')
            ops.pop()
            prev_op = False
        else:
            if t == '+' and prev_op:
                continue  # unary plus: no-op
            if t == '-' and prev_op:
                t = 'u-'  # Python precedence: below **, above *
            while ops and ops[-1] != '(' and (
                    prec[ops[-1]] > prec[t] or (prec[ops[-1]] == prec[t] and t not in right_assoc)):
                out.append(ops.pop())
            ops.append(t)
            prev_op = True
    while ops:
        if ops[-1] == '(':
            raise ValueError('unbalanced parentheses')
        out.append(ops.pop())
    stack = []
    for t in out:
        if isinstance(t, Fraction):
            stack.append(t)
        elif t == 'u-':
            stack.append(_cap(-stack.pop(), 'rpn'))
        else:
            b, a = stack.pop(), stack.pop()
            if t == '+':
                stack.append(_cap(a + b, 'rpn'))
            elif t == '-':
                stack.append(_cap(a - b, 'rpn'))
            elif t == '*':
                stack.append(_cap(a * b, 'rpn'))
            elif t == '/':
                if b == 0:
                    raise ValueError('division by zero')
                stack.append(_cap(a / b, 'rpn'))
            elif t == '//':
                if b == 0:
                    raise ValueError('division by zero')
                stack.append(_cap(Fraction(a // b), 'rpn'))
            elif t == '%':
                if b == 0:
                    raise ValueError('modulo by zero')
                stack.append(_cap(Fraction(a % b), 'rpn'))
            else:
                if b.denominator != 1 or not 0 <= b <= MAX_EXPR_POW:
                    raise ValueError('exponent must be an integer 0..%d' % MAX_EXPR_POW)
                if a != 0 and (abs(a).numerator.bit_length() - 1) * int(b) > MAX_INT_BITS:
                    raise ValueError('power result exceeds size bound')
                stack.append(_cap(a ** int(b), 'rpn'))
    if len(stack) != 1:
        raise ValueError('invalid expression')
    return stack[0]


def _fib(n):
    """F(n) by fast doubling; independent of the solver's iteration."""
    def pair(k):
        if k == 0:
            return 0, 1
        a, b = pair(k >> 1)
        c = a * (2 * b - a)
        d = a * a + b * b
        return (d, c + d) if k & 1 else (c, d)
    return pair(n)[0]


# ----------------------------------------------------------------verification
def verify(task, result):
    """Independent re-check bound to the ORIGINAL task inputs.

    Nothing in the result is trusted: every reported field is recomputed
    from the task and compared; solver-internal values are only used after
    being re-validated against the task.
    """
    checks = []
    if not isinstance(task, dict) or not isinstance(result, dict):
        return {'verified': False, 'reason': 'bad types', 'checks': []}
    if result.get('kind') != task.get('kind'):
        return {'verified': False, 'reason': 'kind mismatch', 'checks': []}
    kind = task.get('kind')
    status = result.get('status')
    fixed_keys = {
        'quadratic': ({'kind', 'status', 'discriminant', 'roots', 'coefficients'},
                      {'_roots_exact'}),
        'polynomial_derivative': ({'kind', 'status', 'coefficients_out'}, set()),
        'polynomial_integral': ({'kind', 'status', 'coefficients_out'}, set()),
        'is_prime': ({'kind', 'status', 'n', 'prime'}, set()),
        'factor': ({'kind', 'status', 'n', 'factors', 'distinct'}, set()),
        'crt': ({'kind', 'status', 'solution', 'modulus', 'congruences'}, set()),
        'combinatorics': ({'kind', 'op', 'n', 'k', 'status', 'result'}, set()),
        'sequence': ({'kind', 'sequence_kind', 'status', 'nth', 'sum_first_n', 'n'}, set()),
        'statistics': ({'kind', 'status', 'count', 'mean', 'median',
                        'population_variance', 'min', 'max'}, set()),
        'expression': ({'kind', 'status', 'source', 'value'}, set()),
    }
    if kind in fixed_keys:
        required, optional = fixed_keys[kind]
        # 'verification' is allowed so a delivered result (receipt attached)
        # re-verifies standalone; the old receipt's content is never trusted
        if not required <= set(result) or \
                set(result) - required - optional - {'verification'}:
            return {'verified': False, 'failed': ['exact_keys'], 'checks': ['exact_keys']}
    try:
        if kind == 'linear_system':
            matrix, vector = task['matrix'], task.get('vector')
            if not isinstance(matrix, list) \
                    or not 1 <= len(matrix) <= MAX_UNKNOWNS:
                raise ValueError('matrix outside solve bounds')
            # shape caps before any element iteration: square rows, matching
            # vector - the same admissible-input boundary solve() enforces
            if any(not isinstance(row, list) or len(row) != len(matrix) for row in matrix):
                raise ValueError('matrix outside solve bounds')
            if not isinstance(vector, list) or len(vector) != len(matrix):
                raise ValueError('vector outside solve bounds')
            a = [[_rational(v, 'm') for v in row] for row in matrix]
            b = [_rational(v, 'v') for v in vector]
            n = len(a)
            rank_a = _rank([row[:] for row in a])
            rank_aug = _rank([row[:] + [b[i]] for i, row in enumerate(a)])
            expected = ('no_solution' if rank_a < rank_aug
                        else 'unique' if rank_a == n else 'infinite_solutions')
            expected_keys = {'kind', 'status', 'rank_coefficients', 'rank_augmented',
                             'solution'}
            if expected == 'infinite_solutions':
                expected_keys.add('free_variables')
            checks.append(('exact_keys', set(result) - {'verification'} == expected_keys))
            checks.append(('rank_coefficients', rank_a == result['rank_coefficients']))
            checks.append(('rank_augmented', rank_aug == result['rank_augmented']))
            checks.append(('status', expected == status))
            if expected == 'unique':
                sol = [_rational(v, 's') for v in result['solution']]
                checks.append(('solution_shape', len(sol) == n))
                ok = all(sum(c * x for c, x in zip(row, sol)) == b[i] for i, row in enumerate(a))
                checks.append(('substitution', ok))
            elif expected == 'infinite_solutions':
                checks.append(('free_variables', result.get('free_variables') == n - rank_a))
        elif kind == 'quadratic':
            a, b, c = _rational(task['a'], 'a'), _rational(task['b'], 'b'), _rational(task['c'], 'c')
            disc = b * b - 4 * a * c
            expected = ('no_real_roots' if disc < 0
                        else 'repeated_root' if disc == 0 else 'two_real_roots')
            checks.append(('discriminant', str(disc) == result['discriminant']))
            checks.append(('status', expected == status))
            checks.append(('coefficients', [str(a), str(b), str(c)] == result['coefficients']))
            if expected == 'no_real_roots':
                checks.append(('roots_empty', result.get('roots') == []))
            else:
                _, _, roots = _quadratic_exact(a, b, c)
                checks.append(('displayed_roots',
                               [str(x) for x in roots] == result['roots']))
                checks.append(('root_count', len(roots) == (1 if disc == 0 else 2)))
                if '_roots_exact' in result:
                    checks.append(('roots_exact', result['_roots_exact'] == roots))
                s = roots[0] + (roots[1] if len(roots) > 1 else roots[0])
                pr = roots[0] * (roots[1] if len(roots) > 1 else roots[0])
                checks.append(('vieta_sum', s == Surd(-b / a)))
                checks.append(('vieta_product', pr == Surd(c / a)))
                for root in roots:
                    checks.append(('root_evaluation',
                                   Surd(a) * root * root + Surd(b) * root + Surd(c) == Surd(0)))
        elif kind == 'diophantine':
            a, b, c = (_bigint(task[k], k) for k in ('a', 'b', 'c'))
            g = math.gcd(abs(a), abs(b))
            expected = 'solved' if c % g == 0 else 'no_solution'
            expected_keys = {'kind', 'status', 'gcd'}
            if expected == 'solved':
                expected_keys |= {'particular', 'general'}
            checks.append(('exact_keys', set(result) - {'verification'} == expected_keys))
            checks.append(('gcd', g == result['gcd']))
            checks.append(('status', expected == status))
            if expected == 'solved':
                x, y = result['particular']
                checks.append(('equation', a * x + b * y == c))
                expected_general = ['x = %d + %d*t' % (x, b // g),
                                    'y = %d - %d*t' % (y, a // g)]
                checks.append(('general_solution', result['general'] == expected_general))
        elif kind == 'is_prime':
            n = _bigint(task['n'], 'n')
            recheck = _mr_prime_recheck(n) if n >= 2 else False
            checks.append(('n', result['n'] == n))
            checks.append(('status', result.get('status') == 'computed'))
            checks.append(('independent_primality',
                           type(result['prime']) is bool and result['prime'] == recheck))
        elif kind == 'factor':
            n = _bigint(task['n'], 'n')
            factors = result['factors']
            if not isinstance(factors, list) or len(factors) > 64 or \
                    any(type(f) is not int or not 2 <= f <= n for f in factors):
                raise ValueError('factors outside solve bounds')
            prod = 1
            for f in factors:
                prod *= f
            checks.append(('n', result['n'] == n))
            checks.append(('status', result.get('status') == 'factored'))
            checks.append(('product', prod == n))
            checks.append(('factors_prime', all(_mr_prime_recheck(f) for f in factors)))
            checks.append(('distinct', result['distinct'] == sorted(set(factors))))
        elif kind == 'crt':
            if not isinstance(task['remainders'], list) or not isinstance(task['moduli'], list) \
                    or not 1 <= len(task['remainders']) <= MAX_CRT \
                    or len(task['remainders']) != len(task['moduli']):
                raise ValueError('congruences outside solve bounds')
            r = [_bigint(v, 'r') for v in task['remainders']]
            mods = [_bigint(v, 'm') for v in task['moduli']]
            big = 1
            for mi in mods:
                big *= mi
            x = result['solution']
            checks.append(('status', result.get('status') == 'solved'))
            checks.append(('modulus', result['modulus'] == big))
            checks.append(('residues', all(x % mi == ri % mi for ri, mi in zip(r, mods))))
            checks.append(('range', 0 <= x < big))
            normalized = [[ri % mi, mi] for ri, mi in zip(r, mods)]
            checks.append(('congruences', result['congruences'] == normalized))
        elif kind == 'combinatorics':
            op, n, k = task['op'], _bigint(task['n'], 'n'), task.get('k')
            k = _bigint(k, 'k') if k is not None else None
            if op not in ('choose', 'permute', 'derangements', 'catalan', 'fibonacci'):
                raise ValueError('op outside solve bounds')
            if not 0 <= n <= MAX_COMB_N:
                raise ValueError('n outside solve bounds')
            if op in ('choose', 'permute') and (k is None or not 0 <= k <= n):
                raise ValueError('k outside solve bounds')
            if op == 'catalan' and n > 500:
                raise ValueError('catalan outside solve bounds')
            checks.append(('op', result['op'] == op))
            checks.append(('n', result['n'] == n))
            checks.append(('k', result.get('k') == k))
            checks.append(('status', result.get('status') == 'computed'))
            if op == 'choose':
                expected = math.comb(n, k)
            elif op == 'permute':
                expected = math.perm(n, k)
            elif op == 'derangements':
                # feasibility first: the capped recurrence trips past the
                # result bound near n=47, so the inclusion-exclusion recompute
                # below only ever runs where it is cheap
                d = [1, 0]
                for i in range(2, n + 1):
                    d.append((i - 1) * (d[i - 1] + d[i - 2]))
                    if d[-1] > COMB_RESULT_BOUND:
                        raise ValueError('result exceeds 10**60')
                expected = sum((-1) ** i * math.factorial(n) // math.factorial(i)
                               for i in range(n + 1))
            elif op == 'catalan':
                expected = math.comb(2 * n, n) // (n + 1)
            else:
                expected = _fib(n)
            if expected > COMB_RESULT_BOUND:
                raise ValueError('result exceeds 10**60')
            checks.append(('recompute', result['result'] == expected))
        elif kind == 'sequence':
            skind = task['sequence_kind']
            if skind not in ('arithmetic', 'geometric'):
                raise ValueError('sequence_kind outside solve bounds')
            n = _bigint(task['n'], 'n')
            if not 1 <= n <= MAX_SEQ_N:
                raise ValueError('n outside solve bounds')
            a1, step = _rational(task['a1'], 'a1'), _rational(task['step'], 'step')
            checks.append(('n', result['n'] == n))
            checks.append(('sequence_kind', result.get('sequence_kind') == skind))
            checks.append(('status', result.get('status') == 'computed'))
            if skind == 'arithmetic':
                nth = a1 + (n - 1) * step
                total = n * a1 + step * n * (n - 1) / 2  # distinct arrangement
            elif step == 1:
                nth, total = a1, a1 * n
            else:
                bits = max(abs(step.numerator), 1).bit_length() + step.denominator.bit_length()
                if n * bits > 64 * MAX_INT_BITS:
                    raise ValueError('sequence value exceeds bounds')
                powv = step ** (n - 1)
                if abs(powv.numerator) > 10**60 or powv.denominator > 10**60:
                    raise ValueError('sequence value exceeds bounds')
                nth = a1 * powv
                if n <= 10000:
                    acc, term = Fraction(0), a1
                    for _ in range(n):
                        acc += term
                        term *= step
                    total = acc
                else:
                    total = a1 * (step ** n - 1) / (step - 1)
            checks.append(('nth', str(nth) == result['nth']))
            checks.append(('sum', str(total) == result['sum_first_n']))
        elif kind == 'statistics':
            if not isinstance(task['values'], list) \
                    or not 1 <= len(task['values']) <= MAX_STATS_ROWS:
                raise ValueError('values outside solve bounds')
            data = [_rational(v, 'd') for v in task['values']]
            cnt = len(data)
            mean = sum(data, Fraction(0)) / cnt
            ordered = sorted(data)
            median = ordered[cnt // 2] if cnt % 2 else (ordered[cnt // 2 - 1] + ordered[cnt // 2]) / 2
            var = sum((v - mean) ** 2 for v in data) / cnt
            checks.append(('count', result['count'] == cnt))
            checks.append(('status', result.get('status') == 'computed'))
            checks.append(('mean', str(mean) == result['mean']))
            checks.append(('median', str(median) == result['median']))
            checks.append(('variance', str(var) == result['population_variance']))
            checks.append(('min', str(ordered[0]) == result['min']))
            checks.append(('max', str(ordered[-1]) == result['max']))
        elif kind == 'expression':
            source = task['source']
            if not isinstance(source, str) or not 1 <= len(source) <= MAX_EXPR_LEN:
                raise ValueError('expression source outside solve bounds')
            checks.append(('source', result['source'] == source))
            checks.append(('status', result.get('status') == 'computed'))
            checks.append(('independent_evaluator', str(_eval_rpn(source)) == result['value']))
        elif kind == 'polynomial_derivative':
            checks.append(('status', result.get('status') == 'computed'))
            integral = poly_integral(result['coefficients_out'])
            original = _poly(task['coefficients'], 'p')
            restored = _poly(integral, 'i')
            restored[0] = original[0]
            checks.append(('integral_of_derivative', _poly_eq(restored, original)))
        elif kind == 'polynomial_integral':
            checks.append(('status', result.get('status') == 'computed'))
            integrated = _poly(result['coefficients_out'], 'i')
            # the solver fixes the integration constant at zero; an altered
            # constant shares the derivative and must not verify
            checks.append(('constant_term', integrated[0] == 0))
            checks.append(('derivative_of_integral',
                           _poly_eq(poly_derivative(result['coefficients_out']),
                                    _poly(task['coefficients'], 'p'))))
        else:
            return {'verified': False, 'reason': 'unknown kind', 'checks': []}
    except (KeyError, ValueError, TypeError, ZeroDivisionError) as exc:
        return {'verified': False, 'reason': 'verification error: ' + str(exc)[:120], 'checks': checks}
    failed = [name for name, ok in checks if not ok]
    return {'verified': not failed, 'failed': failed,
            'checks': [name for name, _ in checks]}


def _mr_prime_recheck(n):
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n == p:
            return True
        if n % p == 0:
            return False
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    return not any(_mr_witness(n, d, s, a) for a in (41, 43, 47, 53, 59, 61, 67, 71))


# ----------------------------------------------------------------dispatcher
def solve(task):
    if not isinstance(task, dict):
        raise ValueError('math task requires an object')
    kind = task.get('kind')
    if kind == 'linear_system':
        core = solve_linear_system(task.get('matrix'), task.get('vector'))
    elif kind == 'quadratic':
        core = solve_quadratic(task.get('a'), task.get('b'), task.get('c'))
    elif kind == 'polynomial_derivative':
        core = {'kind': kind, 'status': 'computed',
                'coefficients_out': poly_derivative(task.get('coefficients'))}
    elif kind == 'polynomial_integral':
        core = {'kind': kind, 'status': 'computed',
                'coefficients_out': poly_integral(task.get('coefficients'))}
    elif kind == 'diophantine':
        core = solve_diophantine(task.get('a'), task.get('b'), task.get('c'))
    elif kind == 'is_prime':
        n = _bigint(task.get('n'), 'n')
        core = {'kind': kind, 'status': 'computed', 'n': n, 'prime': is_prime(n)}
    elif kind == 'factor':
        core = factor(task.get('n'))
    elif kind == 'crt':
        core = solve_crt(task.get('remainders'), task.get('moduli'))
    elif kind == 'combinatorics':
        core = combinatorics(task.get('op'), task.get('n'), task.get('k'))
    elif kind == 'sequence':
        core = sequence(task.get('sequence_kind'), task.get('a1'), task.get('step'), task.get('n'))
    elif kind == 'statistics':
        core = statistics(task.get('values'))
    elif kind == 'expression':
        core = evaluate_expression(task.get('source'))
    else:
        raise ValueError('kind must be one of: linear_system, quadratic, '
                         'polynomial_derivative, polynomial_integral, diophantine, '
                         'is_prime, factor, crt, combinatorics, sequence, statistics, expression')
    receipt = verify(task, core)
    core = {k: v for k, v in core.items() if not k.startswith('_')}
    core['verification'] = receipt
    if not receipt['verified']:
        core['status'] = 'verification_failed'
    return core
