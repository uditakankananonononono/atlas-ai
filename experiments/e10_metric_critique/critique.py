"""Atlas Solve/Critique/Redefine with externally anchored metric admission.

Critic only proposes from an authored catalogue of proven semantic invariants.
It cannot invent a reward or evaluate its own deployment success.
"""
from __future__ import annotations
import heapq
import math
from collections import deque
from dataclasses import dataclass
from random import Random

Graph = dict[int, list[tuple[int, int]]]


@dataclass(frozen=True)
class Policy:
    name: str
    kind: str
    parameter: int = 0

    def solve(self, graph, source, target):
        if self.kind == 'bfs':
            # shortest number of edges, then report that path's real cost
            queue = deque([(source, 0)])
            seen = {source}
            while queue:
                node, cost = queue.popleft()
                if node == target:
                    return cost
                edges = sorted(graph[node], reverse=bool(self.parameter % 2))
                for nxt, weight in edges:
                    if nxt not in seen:
                        seen.add(nxt)
                        queue.append((nxt, cost+weight))
            return math.inf
        distances = {source:0}
        queue = [(0, source)]
        closed = set()
        while queue:
            _, node = heapq.heappop(queue)
            if node in closed:
                continue
            closed.add(node)
            if node == target:
                return distances[node]
            for nxt, weight in graph[node]:
                candidate = distances[node]+weight
                if nxt in closed or candidate >= distances.get(nxt,math.inf):
                    continue
                distances[nxt] = candidate
                if self.kind == 'dijkstra':
                    priority = candidate
                elif self.kind == 'heuristic':
                    priority = candidate+self.parameter*abs(target-nxt)
                elif self.kind == 'quantized':
                    priority = candidate//self.parameter
                else:
                    raise ValueError(self.kind)
                heapq.heappush(queue,(priority,nxt))
        return math.inf


def reference(graph, source, target):
    """Independent Bellman-Ford oracle; no heap or policy implementation."""
    distances = {node:math.inf for node in graph}
    distances[source] = 0
    for _ in range(len(graph)-1):
        changed = False
        for node in graph:
            for nxt, weight in graph[node]:
                candidate = distances[node]+weight
                if candidate < distances[nxt]:
                    distances[nxt] = candidate
                    changed = True
        if not changed:
            break
    return distances[target]


def make_graph(seed, mode):
    r = Random(seed)
    size = r.randrange(7,13)
    graph = {i:[] for i in range(size)}
    for i in range(size-1):
        graph[i].append((i+1,1 if mode=='nominal' else r.randrange(2,31)))
    if mode != 'nominal':
        # General sparse directed graphs, not a fixed counterexample template.
        for i in graph:
            for j in graph:
                if i != j and r.random() < .18 and all(v != j for v,_ in graph[i]):
                    graph[i].append((j,2*r.randrange(1,16)))
    return graph, 0, size-1


def transform(graph, source, target, kind, seed):
    r = Random(seed)
    out = {node:edges[:] for node,edges in graph.items()}
    if kind == 'relabel':
        ids = list(out)
        shuffled = ids[:]
        r.shuffle(shuffled)
        mapping = dict(zip(ids,shuffled))
        return {mapping[k]:[(mapping[v],w) for v,w in edges] for k,edges in out.items()},mapping[source],mapping[target]
    if kind == 'subdivide':
        # Every weight >=2 splits into two positive integer weights. Every
        # original path has an equal-cost subdivided path and vice versa.
        counter = max(out)+1
        for node in list(graph):
            out[node] = []
            for nxt, weight in graph[node]:
                if weight >= 2:
                    left = r.randrange(1,weight)
                    out[node].append((counter,left))
                    out[counter] = [(nxt,weight-left)]
                    counter += 1
                else:
                    out[node].append((nxt,weight))
    elif kind == 'scale':
        factor = r.randrange(2,8)
        out = {node:[(nxt,weight*factor) for nxt,weight in edges] for node,edges in out.items()}
        return out, source, target
    elif kind == 'irrelevant_component':
        n = max(out)+1
        out[n] = [(n+1,3)]
        out[n+1] = [(n,2)]
    else:
        raise ValueError(kind)
    return out,source,target


def metric(policy, cases, kind):
    failed = 0
    for index,(g,s,t) in enumerate(cases):
        ng,ns,nt = transform(g,s,t,kind,900000+index)
        baseline = policy.solve(g,s,t)
        observed = policy.solve(ng,ns,nt)
        # Ratio obtained from independent specification oracle, never policy.
        factor = reference(ng,ns,nt)/reference(g,s,t) if kind=='scale' else 1
        assert reference(ng,ns,nt) == reference(g,s,t)*factor
        failed += observed != baseline*factor
    return failed/len(cases)


def external_error(policy, cases):
    return sum(policy.solve(g,s,t) != reference(g,s,t) for g,s,t in cases)/len(cases)


def auc(scores, labels):
    # Binary risky-label criterion predeclared as >10% independent error.
    bad = [s for s,l in zip(scores,labels) if l]
    good = [s for s,l in zip(scores,labels) if not l]
    if not bad or not good:
        return .5
    return sum((a>b)+.5*(a==b) for a in bad for b in good)/(len(bad)*len(good))


def admit(scores, labels, seed=912, permutations=4999):
    """Independent validator controls admission, including familywise correction."""
    observed = {kind:auc(values,labels) for kind,values in scores.items()}
    winner = max(observed, key=lambda k:(observed[k],k))
    r = Random(seed)
    exceed = 0
    for _ in range(permutations):
        shuffled = labels[:]
        r.shuffle(shuffled)
        exceed += max(auc(values,shuffled) for values in scores.values()) >= observed[winner]
    p = (1+exceed)/(1+permutations)
    return {'proposed':winner,'auc':observed,'corrected_permutation_p':p,
            'admitted':observed[winner]>=.75 and p<=.05,
            'rules':{'min_auc':.75,'familywise_max_statistic_p':.05,'permutations':permutations}}
