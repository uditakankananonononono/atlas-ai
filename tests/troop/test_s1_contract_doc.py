"""S1.1-S1.3 contract doc pins: verbatim source lines, source pin, interpretation tags, refusal codes."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = (ROOT / "docs/TROOP_S1_FLEET_CONTRACT.md").read_text()


def test_source_lines_verbatim():
    for line in (
        "Has a whole troop of agents inspired but better than Cellcog, strawberry browser and similar tools maybe search up yc companies and replicate them and integrate into atlas",
        "replicate them and integrate into atlas",
        "actually integrate it into themselves if its opensource of build it into themselves if itsnt",
        "a whole troop of agents",
        "Autonomously build whole digital companies with autonomous worker ai bots",
        "typed worker roles (researcher, analyst, builder, writer, critic, auditor)",
    ):
        assert line in DOC


def test_pin_provenance_and_tags():
    assert "Source pin: instinct doc S1.1-S1.3" in DOC
    assert "I did not see the spec itself" in DOC
    assert DOC.count("INTERPRETATION CHOICE") >= 12


def test_codes_documented():
    for code in ("FLEET_REFUSED_NOSOURCE", "FLEET_REFUSED_UNLICENSED", "FLEET_REFUSED_SPEND", "S1.1:", "S1.2:", "S1.3:"):
        assert code in DOC
    for f in ("fleet_common", "landscape", "replicate", "roster"):
        src = (ROOT / "backend/app/troop" / (f + ".py")).read_text()
        for code in re.findall(r'"(FLEET_REFUSED_[A-Z]+)"', src):
            assert code in DOC
        assert "relayed" in src or f == "fleet_common"


def test_survey_fixture_note_present_and_small_edit():
    s = (ROOT / "docs/yc_survey.md").read_text()
    assert "## Scanner fixture note (S1.1)" in s


def test_honest_scope_section():
    low = DOC.lower()
    for phrase in ("fixture-runner bookkeeping prototype", "not an m20 or model troop", "not autonomous companies",
                   "per-job runner pool size", "jobs run sequentially", "no worker injection",
                   "re-derived from the supplied pages", "planner_error"):
        assert phrase in low, phrase
