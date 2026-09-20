from app.market.factors import FactorPipeline

def test_factor_pipeline_uses_real_payload_values_only():
    factors=FactorPipeline().extract("sec",{"assets":10,"tags":["a","b"],"flags":{"public":True}})
    got={f.key:f.value for f in factors}
    assert got=={"sec:assets":10.0,"sec:tags.count":2.0,"sec:flags.public":1.0}
