from app.modules.m01_opportunity_discovery.classifier import fine_tune_ready

def test_fine_tuning_requires_real_balanced_labels():
    assert not fine_tune_ready({"eligible": 500})
    assert fine_tune_ready({"eligible": 200, "ineligible": 150, "unclear": 150})
