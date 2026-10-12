"""Fast sanity pins for experiment E5 (experiments/e5_gate_quality). Not a gate test."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "experiments" / "e5_gate_quality"))
import corpus  # noqa: E402
import mutants  # noqa: E402
import run_experiment as e5  # noqa: E402


def test_mutant_generator_is_deterministic_and_nonempty_for_most_templates():
    counts = []
    for t in corpus.T.values():
        a, b = mutants.generate(t["good"]), mutants.generate(t["good"])
        assert a == b
        counts.append(len(a))
    assert all(c > 0 for c in counts)


def test_case_matrix_shape():
    cases = e5.build_cases()
    assert len(cases) == 12 * 6 + 1
    assert {c["cond"] for c in cases} == set("ABCDEFG")
    assert len({c["id"] for c in cases}) == len(cases)
