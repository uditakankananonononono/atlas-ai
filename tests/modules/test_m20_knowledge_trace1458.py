"""Row1458 package gates. No learner-trait or real-world efficacy claims."""
from copy import deepcopy
from fractions import Fraction
import random
import pytest
from app.modules.m20_general_cognitive_worker.knowledge_trace1458 import (
    KnowledgeTraceError, trace, MAX_ATTEMPTS, MAX_SKILLS,
)


def request(scores=(True, False), *, tenant='a', skill='fractions', learner='p'):
    return {
        'source': {'title': 'Supplied fixture', 'url': 'https://example.org/scored'},
        'sources': {'scores': 'caller-scored exercise log', 'params': 'declared synthetic parameters'},
        'parameters': {skill: {'prior': .2, 'learn': .1, 'guess': .2, 'slip': .1, 'source_id': 'params'}},
        'attempts': [dict(attempt_id=f'{learner}-{skill}-{i}', tenant_id=tenant,
                          learner_id=learner, skill=skill, correct=c,
                          occurred_at=f'2026-10-01T00:00:{i:02d}+00:00', source_id='scores')
                     for i, c in enumerate(scores)]}


def run(p):
    return trace(p, tenant_id='a', actor_id='owner')


def test_analytical_observation_then_learning_and_provenance():
    p = request()
    before = deepcopy(p)
    o = run(p)
    assert p == before
    h = o['histories'][0]['steps']
    # Exact rational enumeration, independent of implementation formula floats.
    assert h[0]['likelihood'] == pytest.approx(float(Fraction(17, 50)))
    assert h[0]['posterior'] == pytest.approx(float(Fraction(9, 17)))
    assert h[0]['after_learning'] == pytest.approx(float(Fraction(49, 85)))
    assert h[0]['predicted_success_next'] == pytest.approx(float(Fraction(513, 850)))
    assert h[1]['posterior'] == pytest.approx(float(Fraction(49, 337)))
    assert h[1]['after_learning'] == pytest.approx(float(Fraction(389, 1685)))
    assert h[1]['prior'] == h[0]['after_learning']
    assert h[0]['attempt_id'] == p['attempts'][0]['attempt_id']
    assert h[0]['source_id'] == 'scores'
    assert h[0]['occurred_at'] == p['attempts'][0]['occurred_at']
    assert o['parameters'] == p['parameters'] and o['sources'] == p['sources']
    assert o['scope'] == {'tenant_id': 'a', 'actor_id': 'owner'}
    assert o['status'] == 'conditional_calculation'
    assert o['learner_mastery_verified'] is False and o['fitted_to_data'] is False
    assert 'confidence' not in o


@pytest.mark.parametrize('scores', [(True,), (False,), (True, True), (True, False), (False, True), (False, False)])
def test_latent_path_enumeration(scores):
    # Sum all latent state paths with exact probabilities (observation then transition).
    p = request(scores)
    mass = {False: Fraction(4, 5), True: Fraction(1, 5)}
    for i, score in enumerate(scores):
        weighted = {s: v * ((Fraction(9, 10) if s else Fraction(1, 5)) if score else
                            (Fraction(1, 10) if s else Fraction(4, 5))) for s, v in mass.items()}
        denominator = sum(weighted.values())
        posterior = weighted[True] / denominator
        step = run(p)['histories'][0]['steps'][i]
        assert step['posterior'] == pytest.approx(float(posterior))
        # Enumerate two transition edges out of the unknown state.
        mass = {True: posterior + weighted[False] / denominator * Fraction(1, 10),
                False: weighted[False] / denominator * Fraction(9, 10)}
        assert step['after_learning'] == pytest.approx(float(mass[True]))


@pytest.mark.parametrize('prior', [0, 1])
@pytest.mark.parametrize('learn', [0, 1])
@pytest.mark.parametrize('guess', [0, 1])
@pytest.mark.parametrize('slip', [0, 1])
@pytest.mark.parametrize('score', [True, False])
def test_zero_one_boundaries(prior, learn, guess, slip, score):
    p = request((score,)); p['parameters']['fractions'].update(prior=prior, learn=learn, guess=guess, slip=slip)
    o = run(p)
    likelihood = prior * ((1-slip) if score else slip) + (1-prior) * (guess if score else (1-guess))
    if likelihood == 0:
        assert o['status'] == 'abstained'
        assert o['histories'][0]['reason'] == 'zero_likelihood_observation'
        assert o['histories'][0]['predicted_success_next'] is None
    else:
        h = o['histories'][0]; assert h['status'] == 'conditional_calculation'
        assert 0 <= h['steps'][0]['posterior'] <= 1
        assert 0 <= h['predicted_success_next'] <= 1


@pytest.mark.parametrize('field', ['prior', 'learn', 'guess', 'slip'])
@pytest.mark.parametrize('value', [True, False, '0.2', None, [], {}, float('nan'), float('inf'), -float('inf'), -.01, 1.01, 10**1000])
def test_parameter_type_finite_range(field, value):
    p = request(); p['parameters']['fractions'][field] = value
    with pytest.raises(KnowledgeTraceError): run(p)


@pytest.mark.parametrize('field', ['prior','learn','guess','slip','source_id'])
def test_missing_declared_parameters_refuse(field):
    p = request(); del p['parameters']['fractions'][field]
    with pytest.raises(KnowledgeTraceError): run(p)


@pytest.mark.parametrize('value', [0, 1, 'true', None, [], {}])
def test_scores_are_exact_boolean(value):
    p = request(); p['attempts'][0]['correct'] = value
    with pytest.raises(KnowledgeTraceError): run(p)


@pytest.mark.parametrize('field', ['attempt_id', 'tenant_id', 'learner_id', 'skill', 'source_id', 'occurred_at', 'correct'])
def test_missing_attempt_fields(field):
    p = request(); del p['attempts'][0][field]
    with pytest.raises(KnowledgeTraceError): run(p)


@pytest.mark.parametrize('scores', [(True,True),(True,False)])
def test_duplicate_identity_refuses_even_contradictory_scores(scores):
    p = request(scores); p['attempts'][1]['attempt_id'] = p['attempts'][0]['attempt_id']
    with pytest.raises(KnowledgeTraceError, match='duplicate'): run(p)


@pytest.mark.parametrize('timestamp', ['2026-10-01T00:00:00+00:00', '2026-09-30T23:59:59+00:00', '2026-10-01T05:30:00+05:30', '2026-10-01T00:00:01', '2026-10-01', 'garbage', 1])
def test_exact_chronology_no_naive_or_tie(timestamp):
    p = request(); p['attempts'][1]['occurred_at'] = timestamp
    with pytest.raises(KnowledgeTraceError): run(p)


def test_input_order_is_not_silently_sorted_and_offsets_normalize():
    p=request(); p['attempts'].reverse()
    with pytest.raises(KnowledgeTraceError): run(p)
    p=request(); p['attempts'][1]['occurred_at']='2026-10-01T05:30:01+05:30'
    assert run(p)['histories'][0]['steps'][1]['occurred_at_utc']=='2026-10-01T00:00:01+00:00'


def test_separation_skill_learner_tenant_and_stateless_calls():
    p=request((True,)); q=request((False,), skill='geometry'); r=request((False,),learner='q')
    p['parameters'].update(q['parameters']); p['attempts'] += q['attempts'] + r['attempts']
    o=run(p); assert len(o['histories'])==3
    assert [h['skill'] for h in o['histories']]==['fractions','geometry','fractions']
    assert o['histories'][1]['steps'][0]['prior']==.2
    p['attempts'][0]['tenant_id']='b'
    with pytest.raises(KnowledgeTraceError,match='tenant'):run(p)
    assert run(request()) == run(request())


@pytest.mark.parametrize('where', ['attempt', 'parameters'])
def test_unknown_source_refuses(where):
    p=request()
    if where=='attempt': p['attempts'][0]['source_id']='missing'
    else: p['parameters']['fractions']['source_id']='missing'
    with pytest.raises(KnowledgeTraceError,match='source'):run(p)


def test_sparse_abstention_and_one_observation_scope():
    o=run(request(())); assert o['status']=='abstained' and o['reason']=='no_scored_attempts'
    one=run(request((True,))); assert one['histories'][0]['observation_count']==1
    assert one['learner_mastery_verified'] is False


@pytest.mark.parametrize('place', ['top', 'attempt', 'parameters'])
def test_unknown_schema_refuses(place):
    p=request()
    (p if place=='top' else p['attempts'][0] if place=='attempt' else p['parameters']['fractions'])['unsupported']=1
    with pytest.raises(KnowledgeTraceError):run(p)


def test_impossible_sequence_abstains_no_prior_fallback_and_other_skill_continues():
    p=request((True,False)); p['parameters']['fractions'].update(prior=1,learn=0,guess=0,slip=0)
    q=request((True,),skill='geometry'); p['parameters'].update(q['parameters']);p['attempts']+=q['attempts']
    o=run(p); assert o['status']=='partial_abstention'
    h=o['histories'][0];assert len(h['steps'])==1 and h['failed_attempt_id']==p['attempts'][1]['attempt_id']
    assert h['posterior'] is None and h['after_learning'] is None and h['predicted_success_next'] is None
    assert o['histories'][1]['status']=='conditional_calculation'


def test_bounds_exact_n_n_plus_one():
    from datetime import datetime,timedelta,timezone
    p=request((True,)); first=p['attempts'][0]
    p['attempts']=[dict(first,attempt_id=str(i),occurred_at=(datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(seconds=i)).isoformat()) for i in range(MAX_ATTEMPTS)]
    assert run(p)['histories'][0]['observation_count']==MAX_ATTEMPTS
    p['attempts'].append(dict(first,attempt_id='extra'))
    with pytest.raises(KnowledgeTraceError):run(p)
    p=request((True,)); params=p['parameters']['fractions'];p['parameters']={str(i):dict(params) for i in range(MAX_SKILLS)}
    p['attempts'][0]['skill']='0';assert run(p)['status']=='conditional_calculation'
    p['parameters']['extra']=dict(params)
    with pytest.raises(KnowledgeTraceError):run(p)


def test_heldout_known_process_against_frozen_prior_no_future_leakage():
    rng=random.Random(1458); params=dict(prior=.15,learn=.12,guess=.18,slip=.08,source_id='params')
    model_loss=frozen_loss=0.; total=0
    # Each generated learner held out; no estimation or tuning from outcomes.
    for learner in range(200):
        latent=rng.random()<params['prior']; scores=[]
        frozen=params['prior']*(1-params['slip'])+(1-params['prior'])*params['guess']
        prediction=frozen
        for i in range(12):
            score=rng.random()<((1-params['slip']) if latent else params['guess'])
            model_loss+=(prediction-score)**2; frozen_loss+=(frozen-score)**2;total+=1
            scores.append(score)
            p=request(scores,learner=str(learner));p['parameters']['fractions']=params
            out=run(p);prediction=out['histories'][0]['predicted_success_next']
            # Prefix predictions must not change when later outcomes are appended.
            if i:
                old=request(scores[:-1],learner=str(learner));old['parameters']['fractions']=params
                assert run(old)['histories'][0]['steps']==out['histories'][0]['steps'][:-1]
            if not latent:latent=rng.random()<params['learn']
    print({'known_process_seed':1458,'heldout_learners':200,'prequential_attempts':total,
           'brier':model_loss/total,'frozen_prior_brier':frozen_loss/total})
    assert model_loss < frozen_loss


def test_mounted_real_oidc_tenant_boundary_after_integrator_patch(monkeypatch,oidc_auth_headers):
    import os
    if os.getenv('KTRACE_WIRING_TEST')!='1':
        pytest.skip('separate integrator patch intentionally unapplied in author checkout')
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m20_general_cognitive_worker.education_routes import router
    monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    app=FastAPI();app.include_router(router,prefix='/api/modules/20');c=TestClient(app)
    path='/api/modules/20/education/knowledge_tracing';p=request();body={'payload':p}
    assert c.post(path,json=body).status_code==401
    h=oidc_auth_headers('a','owner');o=c.post(path,json=body,headers=h)
    assert o.status_code==200,o.text
    assert o.json()['result']['scope']=={'tenant_id':'a','actor_id':'owner'}
    assert c.post(path,json=body,headers=oidc_auth_headers('b','owner')).status_code==422
    assert c.post(path,json=body,headers={**h,'X-Tenant-ID':'b'}).status_code==403
    p['tenant_id']='b';assert c.post(path,json={'payload':p},headers=h).status_code==403
