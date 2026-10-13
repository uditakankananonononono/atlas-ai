"""E6: counterfactual world-model selection with information-value experiment choice (directions 2 and 5).

Hidden world: y = g(x_i, x_j) over 5 binary inputs, observed with flip noise. A candidate causal model is
(g, i, j); 120 candidates (5*4 ordered pairs * 6 gates), collapsed into behavioral equivalence classes.
Agent holds a posterior over classes, may run an intervention do(x) (one of 32 input settings, each with a cost),
sees a noisy y, updates, and stops when the top class has posterior >= STOP. Policies:
  random: uniform intervention;  eig: max expected entropy reduction;  eig_cost: max EIG / cost.
Everything is synthetic and authored here; costs and noise are my choices."""
import itertools
import numpy as np

GATES = {"and": lambda a, b: a & b, "or": lambda a, b: a | b, "xor": lambda a, b: a ^ b,
         "a_not_b": lambda a, b: a & (1 - b), "nand": lambda a, b: 1 - (a & b), "nor": lambda a, b: 1 - (a | b)}
N_IN = 5
SETTINGS = np.array(list(itertools.product([0, 1], repeat=N_IN)), dtype=int)  # 32 x 5


def candidates():
    out = []
    for i in range(N_IN):
        for j in range(N_IN):
            if i != j:
                for g in GATES:
                    out.append((g, i, j, GATES[g](SETTINGS[:, i], SETTINGS[:, j])))
    return out


def classes():
    """Behavioral equivalence classes: candidates with identical outputs on all 32 settings."""
    seen = {}
    for g, i, j, tab in candidates():
        seen.setdefault(tab.tobytes(), (tab, []))[1].append((g, i, j))
    return [v for v in seen.values()]


def eig(post, tabs, noise):
    """Expected entropy reduction for each of the 32 interventions."""
    H = lambda p: -(p[p > 0] * np.log(p[p > 0])).sum()
    h0 = H(post)
    gains = np.zeros(len(SETTINGS))
    for s in range(len(SETTINGS)):
        out = np.zeros(2)
        newh = 0.0
        for y in (0, 1):
            lik = np.where(tabs[:, s] == y, 1 - noise, noise)
            joint = post * lik
            py = joint.sum()
            if py > 0:
                newh += py * H(joint / py)
        gains[s] = h0 - newh
    return gains


def run(world, policy, costs, noise, rng, stop=0.9, max_steps=60):
    cl = classes()
    tabs = np.array([c[0] for c in cl])
    post = np.ones(len(cl)) / len(cl)
    spent = 0.0
    for step in range(max_steps):
        if post.max() >= stop:
            break
        if policy == "random":
            s = int(rng.integers(len(SETTINGS)))
        else:
            g = eig(post, tabs, noise)
            s = int(np.argmax(g if policy == "eig" else g / costs))
        y = int(tabs[world, s]) ^ int(rng.random() < noise)
        lik = np.where(tabs[:, s] == y, 1 - noise, noise)
        post = post * lik
        post /= post.sum()
        spent += costs[s]
    return dict(correct=int(post.argmax()) == world, steps=step + (post.max() < stop), cost=spent, converged=bool(post.max() >= stop))
