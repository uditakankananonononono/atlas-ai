from app.modules.c36.workforce import execute_isolated_blueprint

def test_actual_registered_sources_execute_blueprint_in_namespace():
    graph={'id':'test-company','offer':'Offline arithmetic only','worker_graph':{
        'nodes':['researcher','analyst'],'edges':[{'from':'researcher','to':'analyst'}],'isolated':[]}}
    result,receipts=execute_isolated_blueprint(graph,{
        'researcher':'def action(args,inputs,attempt,feedback):\n    return [2,3]',
        'analyst':'def action(args,inputs,attempt,feedback):\n    return sum(inputs["researcher"])'})
    assert result.outputs['analyst']==5
    assert len(receipts)==2
    assert all(r['exit_code']==0 and r['output_sha256'] for r in receipts)

def test_hanging_source_fails_and_blocks_downstream():
    graph={'id':'test-company','offer':'Offline arithmetic only','worker_graph':{
        'nodes':['researcher','analyst'],'edges':[{'from':'researcher','to':'analyst'}],'isolated':[]}}
    result,receipts=execute_isolated_blueprint(graph,{
        'researcher':'def action(args,inputs,attempt,feedback):\n    import time\n    time.sleep(30)',
        'analyst':'def action(args,inputs,attempt,feedback):\n    return 1'},timeout_seconds=1)
    assert 'analyst' not in result.outputs
    assert receipts and all(r['timed_out'] for r in receipts)
