"""Execute a blueprint's offline worker graph using registered handlers.

A actual workflow runner, not company formation or autonomous external effects.
Handlers must be trusted, side-effect-free callables. This is not a sandbox.
"""
from app.troop.roles import ActionWorker, Plan, Step, RuleReviewer
from app.troop.runner import TroopRunner, PlanError


def _execute_blueprint(blueprint: dict, handlers: dict, *, max_workers: int = 4, isolated_worker=None):
    if type(blueprint) is not dict or type(handlers) is not dict:
        raise ValueError('blueprint and registered handlers required')
    graph = blueprint.get('worker_graph')
    if type(graph) is not dict or set(graph) != {'nodes', 'edges', 'isolated'}:
        raise ValueError('blueprint worker graph required')
    nodes, edges = graph['nodes'], graph['edges']
    if type(nodes) is not list or not 1 <= len(nodes) <= 16 or any(type(n) is not str or not n for n in nodes):
        raise ValueError('bounded named roles required')
    if len(set(nodes)) != len(nodes) or type(edges) is not list or len(edges) > 256:
        raise ValueError('invalid worker graph')
    deps = {n: [] for n in nodes}
    for edge in edges:
        if type(edge) is not dict or set(edge) != {'from', 'to'} or edge['from'] not in deps or edge['to'] not in deps:
            raise ValueError('unknown edge role')
        deps[edge['to']].append(edge['from'])
    if any(n not in handlers or (isolated_worker is None and not callable(handlers[n])) for n in nodes):
        raise ValueError('all worker roles require actual handlers')
    worker = isolated_worker or ActionWorker()
    for name in nodes:
        worker.register(name, handlers[name])
    steps = tuple(Step(n, n, {'offer': blueprint.get('offer')}, tuple(deps[n]), {'type': 'non_empty'}) for n in nodes)
    tid = blueprint.get('id')
    class Planner:
        def plan(self, task):
            return Plan(tid, steps)
    return TroopRunner(Planner(), worker, RuleReviewer(), max_workers=max_workers).run({'id': tid})


def execute_blueprint(blueprint: dict, handlers: dict, *, max_workers: int = 4):
    """Trusted in-process callables; existing behavior and no sandbox guarantee."""
    return _execute_blueprint(blueprint, handlers, max_workers=max_workers)


def execute_isolated_blueprint(blueprint: dict, sources: dict, *, max_workers: int = 4,
                               timeout_seconds: int = 15, memory_mb: int = 256):
    """Registered Python source only, existing M04 namespaces, no account effects.

    Return runner result and bounded attempt receipts; not durable company ops.
    """
    from app.troop.isolated_worker import IsolatedPythonWorker
    worker=IsolatedPythonWorker(timeout_seconds=timeout_seconds,memory_mb=memory_mb)
    result=_execute_blueprint(blueprint,sources,max_workers=max_workers,isolated_worker=worker)
    return result,worker.receipts
