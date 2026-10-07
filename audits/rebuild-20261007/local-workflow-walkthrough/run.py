"""Run with PYTHONPATH=backend .venv/bin/python <this file>. No external effects."""
import json
from tempfile import TemporaryDirectory
from pathlib import Path
from sqlalchemy import create_engine
from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository

with TemporaryDirectory() as directory:
    engine = create_engine('sqlite:///' + str(Path(directory) / 'workflow.sqlite'))
    repo = GCWRepository(engine, tenant_id='walkthrough'); repo.create_schema()
    runtime = GCWRuntime(repo)
    task = runtime.submit_goal('Sum supplied open invoices', run_immediately=False)
    runtime.prepare_supplied_plan(task.id, steps=[
        {'id': 'filter', 'title': 'Select open rows', 'tool': 'csv_filter',
         'arguments': {'csv_text': 'id,status,amount\nA,open,10\nB,paid,20\nC,open,5\n', 'where': {'status': 'open'}}},
        {'id': 'sum', 'title': 'Sum selected amounts', 'tool': 'csv_summary', 'depends_on': ['filter'],
         'arguments': {'csv_text': {'$step': 'filter', 'path': ['csv_text']}, 'value_column': 'amount'}}])
    runtime.run_task(task.id, max_ticks=1, yield_on_boundary=True)
    engine.dispose()
    reopened = create_engine('sqlite:///' + str(Path(directory) / 'workflow.sqlite'))
    runtime = GCWRuntime(GCWRepository(reopened, tenant_id='walkthrough'))
    completed = runtime.run_task(task.id, max_ticks=2)
    evidence = runtime.task_evidence(task.id)
    closed = runtime.close(task.id)
    assert completed.state.value == 'succeeded'
    assert completed.plan[1].output['groups'][0]['sum'] == 15
    assert evidence['action_count'] == 2
    print(json.dumps({'task_state': completed.state.value, 'output': completed.plan[1].output,
        'evidence': evidence, 'retrospective': closed['retrospective']}, indent=2))
    reopened.dispose()
