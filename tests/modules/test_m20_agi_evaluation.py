import pytest
from app.modules.m20_general_cognitive_worker.agi_evaluation import (
    AGIProvenanceRecorder, CrossDomainTransferBenchmark, TransferCase,
)
from app.modules.m25_knowledge_copilot.artifact_events import ArtifactEventStore


def test_transfer_benchmark_measures_held_out_domains_and_worst_domain():
    cases=[TransferCase('math','math',{'items':[1,2,3]},6),
           TransferCase('ops','operations',{'items':[4,5]},9,source_domain='math')]
    bench=CrossDomainTransferBenchmark(cases)
    report=bench.run(lambda problem: sum(problem['items']))
    assert report['accuracy']==report['transfer_accuracy']==report['worst_domain_accuracy']==1
    assert report['domain_count']==2 and len(report['benchmark_hash'])==64


def test_transfer_benchmark_cannot_hide_domain_failure_in_global_score():
    cases=[TransferCase('a','a',{'value':1},1),TransferCase('b','b',{'value':2},2,source_domain='a')]
    report=CrossDomainTransferBenchmark(cases).run(lambda problem: 1)
    assert report['accuracy']==.5 and report['transfer_accuracy']==0 and report['worst_domain_accuracy']==0


def test_transfer_benchmark_rejects_single_domain_theater():
    with pytest.raises(ValueError,match='two domains'):
        CrossDomainTransferBenchmark([TransferCase('x','same',{},None)])


def test_agi_artifacts_use_shared_provenance_contract_and_tenant_store(tmp_path):
    store=ArtifactEventStore(tmp_path/'events.sqlite')
    recorder=AGIProvenanceRecorder(store,'tenant-a','98a45ff')
    stored=recorder.record(artifact_kind='cross_domain_evaluation',artifact={'accuracy':.75},
                           source_refs=[{'uri':'atlas://benchmark/transfer-v1'}])
    assert stored['created'] and stored['bytes_verified']
    event=stored['event']
    assert event['module_id']==20 and event['tenant_id']=='tenant-a'
    assert event['execution_state']=='simulated' and len(event['event_sha256'])==64
    assert store.list('tenant-b')==[]
    with pytest.raises(ValueError,match='requires receipt_ids'):
        recorder.record(artifact_kind='evaluation',artifact={},source_refs=[],
                        execution_state='independently_verified')


def test_transfer_case_snapshot_and_run_hash_do_not_change_from_mutating_strategy():
 cases=[TransferCase('a','a',{'value':[1]},[1]),TransferCase('b','b',{'value':[2]},[2],source_domain='a')]
 bench=CrossDomainTransferBenchmark(cases)
 baseline=bench.run(lambda problem:problem['value'])['benchmark_hash']
 cases[0].problem['value'].append(9);cases[0].expected.append(9)
 view=bench.cases;view[1].problem['value'].append(8)
 def strategy(problem):problem['value'].append(7);return problem['value']
 def scorer(actual,expected):expected.append(7);return .25
 report=bench.run(strategy,scorer)
 assert report['benchmark_hash']==baseline
 clean=bench.run(lambda problem:problem['value'])
 assert clean['accuracy']==1 and clean['benchmark_hash']==baseline


@pytest.mark.parametrize('score',[True,'1',float('nan'),float('inf'),-1,2])
def test_transfer_scorer_invalid_numeric_score_records_failure(score):
 bench=CrossDomainTransferBenchmark([TransferCase('a','a',{},1),TransferCase('b','b',{},1,source_domain='a')])
 report=bench.run(lambda problem:1,lambda actual,expected:score)
 assert report['accuracy']==0 and all(r['error'] for r in report['results'])
