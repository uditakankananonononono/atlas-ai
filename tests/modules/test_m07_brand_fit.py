import math, pytest
from app.modules.m07_brand_collaboration.brand_fit import rank_brands, tokens

C = ("science education for girls", ["education", "stem"])
BR = [("sci", "Funding science education programs for girls", ["stem", "education"]),
      ("gas", "Premium gasoline and car accessories", ["auto"]),
      ("edu", "Online education tools for teachers", ["education"])]

def test_ranking_order_and_evidence():
    r = rank_brands(*C, BR)
    assert [f.brand_id for f in r] == ["sci", "edu", "gas"]
    assert r[0].score > r[1].score > r[2].score == 0.0
    assert r[0].shared_terms == ["education", "girl", "science"]
    assert r[0].shared_tags == ["education", "stem"] and r[1].shared_tags == ["education"]

def test_stemming_matches_inflections():
    assert tokens("girls Educating") == tokens("girl educating") == ["girl", "educat"]
    r = rank_brands("teaching girls", [], [("a", "girl teacher programs", [])])
    assert r[0].text_cosine > 0

def test_identical_text_and_tags_score_one():
    r = rank_brands("alpha beta gamma", ["x"], [("a", "alpha beta gamma", ["x"])])
    assert math.isclose(r[0].score, 1.0, abs_tol=1e-9)

def test_idf_downweights_common_terms():
    cands = [("rare", "astronomy zebra", []), ("common", "program zebra", []),
             ("f1", "program garden", []), ("f2", "program kitchen", []), ("f3", "program tools", [])]
    r = {f.brand_id: f for f in rank_brands("program astronomy", [], cands)}
    assert r["rare"].text_cosine > r["common"].text_cosine > 0

def test_deterministic_ties_and_validation():
    c = [("b", "same words", []), ("a", "same words", [])]
    assert [f.brand_id for f in rank_brands("same words", [], c)] == ["a", "b"]
    with pytest.raises(ValueError): rank_brands("x y", [], [("a", "x", []), ("a", "y", [])])
    with pytest.raises(ValueError): rank_brands("x y", [], [], tag_weight=1.5)
    assert rank_brands("", [], [("a", "", [])])[0].score == 0.0
    assert rank_brands("x y", [], []) == []

def test_tag_weight_changes_outcome():
    cands = [("tagged", "unrelated words here", ["stem"]), ("texty", "stem outreach program", [])]
    hi = rank_brands("stem outreach program", ["stem"], cands, tag_weight=0.9)
    lo = rank_brands("stem outreach program", ["stem"], cands, tag_weight=0.0)
    assert hi[0].brand_id == "tagged" and lo[0].brand_id == "texty"
