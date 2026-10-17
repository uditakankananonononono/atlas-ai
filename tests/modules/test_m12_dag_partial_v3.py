import asyncio, pytest
from app.modules.m12_ai_research_lab.workflow import DagEngine, Workflow, Node

def WF(*nodes): return Workflow("w", tuple(Node(i,"t",tuple(d),{}) for i,d in nodes))
def run(c): return asyncio.run(c)

def test_failure_error_carries_completed_sibling_outputs():
    async def runner(task, cfg, ctx): return {"usage": {"n": 1}}
    calls=[]
    async def r(task,cfg,ctx):
        calls.append(1)
        if len(calls)==2: raise ValueError("boom")
        return {"usage":{"n":1}}
    eng=DagEngine(r)
    try: run(eng.run(WF(("a",[]),("b",[])),{}))
    except RuntimeError as e:
        assert e.partial_results and len(e.partial_results)==1
    else: raise AssertionError("no error")

def test_failure_error_carries_prior_layer_outputs():
    async def r(task,cfg,ctx):
        if ctx["parents"]: raise ValueError("boom")
        return {"x":1}
    try: run(DagEngine(r).run(WF(("a",[]),("b",["a"])),{}))
    except RuntimeError as e: assert e.partial_results=={"a":{"x":1}}
    else: raise AssertionError

def test_cancelled_node_is_not_recorded_as_success():
    async def r(task,cfg,ctx): raise asyncio.CancelledError()
    try: out=run(DagEngine(r).run(WF(("a",[])),{}))
    except (RuntimeError, asyncio.CancelledError): return
    raise AssertionError("cancelled node recorded as success: %r" % (out,))

def test_success_path_unchanged():
    async def r(task,cfg,ctx): return {"p":sorted(ctx["parents"])}
    out=run(DagEngine(r).run(WF(("a",[]),("b",["a"])),{}))
    assert out=={"a":{"p":[]},"b":{"p":["a"]}}

def test_review_required_still_propagates_with_partial():
    from app.modules.m12_ai_research_lab.wiring import WorkflowReviewRequired
    async def r(task,cfg,ctx):
        if ctx["parents"]: raise WorkflowReviewRequired("res")
        return {"x":1}
    try: run(DagEngine(r).run(WF(("a",[]),("b",["a"])),{}))
    except WorkflowReviewRequired as e: assert e.partial_results=={"a":{"x":1}}
    else: raise AssertionError

def test_outer_cancellation_propagates_and_children_are_cancelled():
    state={"cancelled":0,"started":0}
    async def r(task,cfg,ctx):
        state["started"]+=1
        try: await asyncio.sleep(10)
        except asyncio.CancelledError:
            state["cancelled"]+=1; raise
    async def main():
        t=asyncio.ensure_future(DagEngine(r).run(WF(("a",[]),("b",[])),{}))
        await asyncio.sleep(0.05); t.cancel()
        try: await t
        except asyncio.CancelledError: return "cancelled"
        return "swallowed"
    assert asyncio.run(main())=="cancelled"
    assert state=={"cancelled":2,"started":2}

def test_non_exception_baseexception_is_not_converted():
    async def r(task,cfg,ctx): raise KeyboardInterrupt()
    # a KeyboardInterrupt in a task escapes the loop itself; it must never become a RuntimeError or a result
    try: asyncio.run(DagEngine(r).run(WF(("a",[])),{}))
    except KeyboardInterrupt: return
    except RuntimeError: raise AssertionError("converted to RuntimeError")
    raise AssertionError("returned a result")
