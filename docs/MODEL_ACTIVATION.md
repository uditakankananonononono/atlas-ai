# Model activation gates

Eligibility uses DeBERTa zero-shot inference immediately. Fine-tuning activates only after at least 500 real, human-reviewed eligibility labels exist, with at least 100 labels in each of eligible, ineligible, and unclear. Training data version, class balance, holdout metrics, and calibration are recorded. No synthetic labels fill the threshold.

Competition critique uses bounded cross-model rounds: GPT/OpenAI, Claude/Anthropic, and Gemini/Google, default 3 and maximum 10, followed by a factual human-voice edit. It never fabricates activities or treats repeated model agreement as proof.

Funded-proposal corpus uses NIH RePORTER and NSF Award Search official APIs plus verified public proposal collections. The corpus target is 1,000+ real awards; source and award ID stay attached to every record.
