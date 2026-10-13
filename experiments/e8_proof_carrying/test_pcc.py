import pcc
from pcc import Conclusion, verify, sha

def test_factorization_ok_and_tamper():
    assert verify(Conclusion("91 composite", "factorization", dict(n=91, factors=[7, 13])))["status"] == "VERIFIED"
    assert verify(Conclusion("91 composite", "factorization", dict(n=91, factors=[7, 11])))["status"] == "UNVERIFIED"
    assert verify(Conclusion("x", "factorization", dict(n=91, factors=[1, 91])))["status"] == "UNVERIFIED"

def test_confidence_never_upgrades():
    r = verify(Conclusion("91 composite", "factorization", dict(n=91, factors=[7, 11]), confidence=0.999))
    assert r["status"] == "UNVERIFIED" and r["confidence"] == 0.999

def test_analysis_rerun():
    s = "print(sum(range(10)))\n"
    assert verify(Conclusion("sum", "analysis", dict(script=s, output_sha256=sha(b"45\n"))))["status"] == "VERIFIED"
    assert verify(Conclusion("sum", "analysis", dict(script=s, output_sha256=sha(b"46\n"))))["status"] == "UNVERIFIED"
    assert verify(Conclusion("sum", "analysis", dict(script="raise SystemExit(3)", output_sha256=sha(b""))))["status"] == "UNVERIFIED"

def test_code_change_needs_real_pass():
    src = "def add(a, b):\n    return a + b\n"; t = "from mod import add\ndef test_a():\n    assert add(1, 2) == 3\n"
    assert verify(Conclusion("add works", "code_change", dict(source=src, tests=t, expected_passed=1)))["status"] == "VERIFIED"
    bad = "def add(a, b):\n    return a - b\n"
    assert verify(Conclusion("add works", "code_change", dict(source=bad, tests=t, expected_passed=1)))["status"] == "UNVERIFIED"
    assert verify(Conclusion("add works", "code_change", dict(source=src, tests="def test_x():\n    pass\n", expected_passed=3)))["status"] == "UNVERIFIED"

def test_sourced_quote():
    txt = "Mutation testing injects faults and checks whether tests fail."
    ev = dict(source_text=txt, source_sha256=sha(txt.encode()), quote="injects faults")
    assert verify(Conclusion("q", "sourced_quote", ev))["status"] == "VERIFIED"
    assert verify(Conclusion("q", "sourced_quote", dict(ev, quote="guarantees correctness")))["status"] == "UNVERIFIED"
    assert verify(Conclusion("q", "sourced_quote", dict(ev, source_sha256="0" * 64)))["status"] == "UNVERIFIED"

def test_unverifiable_kind_reports_impossible():
    r = verify(Conclusion("this plan is wise", "opinion", {}, confidence=0.9))
    assert r["status"] == "VERIFICATION_IMPOSSIBLE" and "no checker" in r["reason"]


def test_expected_count_is_exact_not_substring():
    src = "def add(a, b):\n    return a + b\n"
    eleven = "from mod import add\n" + "".join(f"def test_{i}():\n    assert add(1, 2) == 3\n" for i in range(11))
    assert verify(Conclusion("c", "code_change", dict(source=src, tests=eleven, expected_passed=11)))["status"] == "VERIFIED"
    assert verify(Conclusion("c", "code_change", dict(source=src, tests=eleven, expected_passed=1)))["status"] == "UNVERIFIED"

def test_skipped_tests_do_not_count_as_verification():
    src = "def add(a, b):\n    return a + b\n"
    t = "import pytest\nfrom mod import add\ndef test_a():\n    assert add(1, 2) == 3\n@pytest.mark.skip\ndef test_b():\n    assert False\n"
    assert verify(Conclusion("c", "code_change", dict(source=src, tests=t, expected_passed=1)))["status"] == "UNVERIFIED"

def test_zero_test_suite_exit_5_rejected():
    src = "def add(a, b):\n    return a + b\n"
    r = verify(Conclusion("c", "code_change", dict(source=src, tests="def helper():\n    pass\n", expected_passed=1)))
    assert r["status"] == "UNVERIFIED" and "exit 5" in r["reason"]
