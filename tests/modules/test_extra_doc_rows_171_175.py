"""Extra 171-175 v9: bounded output-contract pins for m12 rows 140-144.
Row 173 (m12 142) is HELD and excluded. Row mapping Extra N = module row N-31
was checked only against module ROWS, not the external ledger.
Whole v9 retains all v8 assertions and adds train/validation coercion pins.
Assertions cover the source-enumerated common and row-local
p.get default, including implicit None. Static output flags remain asserted.
Companion evidence distinguishes pre-existing kills from new coverage.
These tests do not establish execution of the named ML algorithms.
Scope: common ml output defaults/flags are IN for direct assertions and the
25 selected source-derived mutants only. Row140/141 and specs143/144 are IN.
Rows136-139, row142, and specs145-169 (including 145/147/151/159/160) are OUT.
Other common-ml mutations are unadjudicated. No 519-mutant clearance is claimed.
Shared execute boundary string is IN for one direct assertion and one selected
same-length mutation. Shared execute execution_kind, primary_model_training_performed,
primary_algorithm_execution_claimed, and input_fields_observed filtering are OUT
of scope. Full-module sweep NOT performed: SCOPED, not VERIFIED.
Builder self-report. No production edits.
"""
import math
import pytest

from app.modules.m12_ai_research_lab.research_methods_135_184 import execute

S = {"title": "Paper", "url": "https://example.org/paper"}


def E(name, **kw):
    return execute(name, {"source": S, **kw})["result"]


def test_row171_overfitting_exact_gap_and_strict_boundary():
    # Kills M171a (gap doubled): exact gap value pinned. Kills M171b (>->=):
    # a gap exactly equal to the tolerance is NOT flagged; a gap above it is.
    out = E("overfitting_detection", task="x", train_score=.9, validation_score=.5)
    assert out["overfitting"]["generalization_gap"] == pytest.approx(.4)
    assert out["overfitting"]["flagged"] is True
    # Boundary uses exactly-representable values: .5625 - .5 == .0625 in binary
    # float (a .05 gap is NOT exactly representable and would pin float noise).
    at = E("overfitting_detection", task="x", train_score=.5625, validation_score=.5,
           tolerance=.0625)
    assert at["overfitting"]["generalization_gap"] == .0625
    assert at["overfitting"]["flagged"] is False
    over = E("overfitting_detection", task="x", train_score=.56, validation_score=.5)
    assert over["overfitting"]["flagged"] is True
    neg = E("overfitting_detection", task="x", train_score=.4, validation_score=.5)
    assert neg["overfitting"]["generalization_gap"] == pytest.approx(-.1)
    assert neg["overfitting"]["flagged"] is False


def test_row172_regularization_defaults():
    # Kills M172d (kind default l2->l1), M172a (selected_with_validation
    # False), M172c (bias_variance_tradeoff False). M172b
    # (standardize_within_fold False) is already killed by existing
    # test_141_regularization_fold_standardizes; assert kept as regression
    # guard. Default kind is l2; supplied kind echoes.
    out = E("regularization_application", task="x")
    reg = out["regularization"]
    assert reg["kind"] == "l2"
    assert reg["selected_with_validation"] is True
    assert reg["standardize_within_fold"] is True
    assert reg["bias_variance_tradeoff"] is True
    assert E("regularization_application", task="x", kind="l1")["regularization"]["kind"] == "l1"


def test_row174_transfer_learning_guard_values():
    # Kills M174a (frozen_then_finetune False), M174b (domain_shift_check
    # False), M174c (catastrophic_forgetting_check False): value pinned.
    m = E("transfer_learning", task="x")["method"]
    assert m["frozen_then_finetune"] is True
    assert m["domain_shift_check"] is True
    assert m["catastrophic_forgetting_check"] is True


def test_row175_few_shot_guard_values():
    # Kills M175a (query_set_separate False), M175b (episode_design False).
    m = E("few_shot_learning", task="x")["method"]
    assert m["query_set_separate"] is True
    assert m["episode_design"] is True


def test_row171_overfitting_defaults_and_guard_flags():
    # Kills M171c (validation_score default 0->1), M171d (tolerance default
    # .05->.1), M171e (learning_curve_required False), M171f
    # (independent_test_confirmation False). Witness shapes from the peer's
    # audit file, absorbed here; the .57/.5 case separates default .05 from
    # a .1 mutant (gap .07).
    o = E("overfitting_detection", task="x")["overfitting"]
    assert o["generalization_gap"] == 0 and o["flagged"] is False
    assert E("overfitting_detection", task="x",
             train_score=.5)["overfitting"]["generalization_gap"] == .5
    assert E("overfitting_detection", task="x", train_score=.5,
             validation_score=.1)["overfitting"]["flagged"] is True
    assert E("overfitting_detection", task="x", train_score=.53,
             validation_score=.5)["overfitting"]["flagged"] is False
    assert E("overfitting_detection", task="x", train_score=.57,
             validation_score=.5)["overfitting"]["flagged"] is True
    assert o["learning_curve_required"] is True
    assert o["independent_test_confirmation"] is True


def test_row172_strength_echo_and_no_regularization_leak():
    # Kills strength echo -> None and exact forced-True guard leakage (M172g).
    # The moved guard (M172f, row 141 -> 140) is a different sibling, already
    # caught by the existing suite; the absence assertion checks row 140.
    out = E("regularization_application", task="x", strength=.3)
    assert out["regularization"]["strength"] == .3
    assert "regularization" not in E("overfitting_detection", task="x")


def test_row174_pretrained_model_echo():
    # Kills M174d (pretrained_model echo -> None). Output-contract echo only.
    m = E("transfer_learning", task="x", pretrained_model="m")["method"]
    assert m["pretrained_model"] == "m"


def test_row175_support_examples_echo():
    # Kills M175c (support_examples echo -> None). Output-contract echo only.
    m = E("few_shot_learning", task="x", support_examples=[1])["method"]
    assert m["support_examples"] == [1]


@pytest.mark.parametrize('name', ['overfitting_detection', 'regularization_application',
                                  'transfer_learning', 'few_shot_learning'])
def test_common_ml_defaults_and_explicit_overrides(name):
    # Exhaustive common p.get defaults found by enumerate_defaults.py.
    out = E(name, task='x')
    assert out['task'] == 'x'
    assert out['data_split'] == {'train': .7, 'validation': .15, 'test': .15}
    assert out['metrics'] == []
    assert out['random_seed'] == 42
    assert out['test_set_locked'] is True
    assert out['pipeline_fit_on_training_only'] is True
    explicit = E(name, task='y', data_split={'train': .6, 'test': .4},
                 metrics=['accuracy'], random_seed=0)
    assert explicit['task'] == 'y'
    assert explicit['data_split'] == {'train': .6, 'test': .4}
    assert explicit['metrics'] == ['accuracy']
    assert explicit['random_seed'] == 0


def test_row171_default_tolerance_between_point04_and_point05():
    # Peer survivor .05 -> .04. Gap is .04500000000000004, strictly in (.04,.05).
    m = E('overfitting_detection', task='x', train_score=.545,
          validation_score=.5)['overfitting']
    assert .04 < m['generalization_gap'] < .05
    assert m['flagged'] is False


def test_rows172_174_175_omitted_values_have_exact_defaults():
    assert E('regularization_application', task='x')['regularization']['strength'] is None
    assert E('transfer_learning', task='x')['method']['pretrained_model'] is None
    assert E('few_shot_learning', task='x')['method']['support_examples'] == []


def test_row171_default_tolerance_upper_side_float_witness():
    # Peer upper-side survivors .05 -> .06 or .0500001. This intentionally
    # exercises float noise at .55-.5, unlike the explicit binary boundary.
    m = E('overfitting_detection', task='x', train_score=.55,
          validation_score=.5)['overfitting']
    assert m['generalization_gap'] == .050000000000000044
    assert m['flagged'] is True


def test_row171_default_tolerance_near_lower_side_float_witness():
    # Peer lower-default survivors: .049999, .04999999999, .04999999999999.
    # This gap is immediately below .05 in this binary float evaluation.
    m = E('overfitting_detection', task='x', train_score=.5,
          validation_score=.45)['overfitting']
    assert m['generalization_gap'] == .04999999999999999
    assert m['flagged'] is False


def test_row171_exact_default_and_next_float_above():
    # Peer ULP witness, expressed as direct output assertions. With validation
    # zero, the train score is the exact gap, avoiding subtraction rounding.
    exact = E('overfitting_detection', task='x', train_score=.05,
              validation_score=0)['overfitting']
    assert exact['generalization_gap'] == .05
    assert exact['flagged'] is False
    next_above = math.nextafter(.05, 1)
    above = E('overfitting_detection', task='x', train_score=next_above,
              validation_score=0)['overfitting']
    assert above['generalization_gap'] == next_above
    assert above['flagged'] is True


def test_execute_boundary_exact_text():
    # Same-length one-character onlZ mutant must not pass a length-only pin.
    out = execute('overfitting_detection', {'source': S, 'task': 'x'})
    assert out['boundary'] == 'Planning support and explicitly returned scalar calculations only; named ML/ARIMA/MCMC methods are not executed here. Research support only. Lock test data, preserve provenance and assumptions, quantify uncertainty, test alternatives, and require expert review before consequential use.'


def test_row171_tolerance_invalid_string_exact_valueerror():
    # float() owns conversion and its ValueError, not comparison TypeError.
    with pytest.raises(ValueError, match=r"^could not convert string to float: 'x'$"):
        E('overfitting_detection', task='x', train_score=.9,
          validation_score=.5, tolerance='x')


def test_row171_numeric_string_tolerance_is_parsed():
    m = E('overfitting_detection', task='x', train_score=.57,
          validation_score=.5, tolerance='0.1')['overfitting']
    assert m['generalization_gap'] == pytest.approx(.07)
    assert m['flagged'] is False


@pytest.mark.parametrize('field', ['train_score', 'validation_score'])
def test_row171_score_invalid_strings_exact_valueerror(field):
    with pytest.raises(ValueError, match=r"^could not convert string to float: 'x'$"):
        E('overfitting_detection', task='x', **{field: 'x'})


def test_row171_numeric_string_train_score_is_parsed():
    m = E('overfitting_detection', task='x', train_score='0.9',
          validation_score=.5)['overfitting']
    assert m['generalization_gap'] == pytest.approx(.4)
    assert m['flagged'] is True


def test_row171_numeric_string_validation_score_is_parsed():
    m = E('overfitting_detection', task='x', train_score=.9,
          validation_score='0.4')['overfitting']
    assert m['generalization_gap'] == pytest.approx(.5)
    assert m['flagged'] is True
