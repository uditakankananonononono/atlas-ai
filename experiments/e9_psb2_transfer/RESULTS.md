# Atlas E9: open PSB2 macro-library and transfer rerun

Run: 2026-10-13, Python 3.12.14, numpy 2.5.4, pytest 9.1.1. Harness base: audited E6/E7/E8 v2 originally pinned to f7ae6fe7ab78e3181c36cff4ae969a8885bbe1ae. Final clean replay used live main 4f68f54a0d0742982192aa643c2fa92d61437c9b, which already contained the audited harness. This directory adds files only. No novelty claim. Directions 1 and 7 remain PARTIAL: source-library gain is not established.

## Answer

The apparent E7 library benefit does **not** carry into this open benchmark. The unchanged E7 pipeline language solves zero of four arity-compatible PSB2 problems; learned source macros do not change that. A separately labelled, manually extended language solves two of six at budgets 1000 through 10000, five of six at 30000, and all six with 600000-budget base search. Source-library transfer gives exactly zero additional solved problems. Target-specific macro learning solves four of six at smaller evaluation budgets, but needs a separate generous discovery pass and is not cross-domain transfer or an equal-total-compute gain.

## Data and filter

PSB2 is an external published benchmark, not newly authored task data. Its random data itself is benchmark-author-generated, not natural human execution traces. Select every PSB2 task with at least one list-of-int input, all remaining inputs integer scalars, and all outputs integer scalars or lists of ints: basement, cut-vector, find-pair, fuel-cost, leaders, luhn (6/25). Exclude float-vector problems. The exact E7-compatible subset has exactly one input and one output: basement, fuel-cost, leaders, luhn (4/25). Both exclusions are fixed by type/arity, not performance. Empty-list cases remain in the extended track. Cut-vector and find-pair multi-output labels are intact; neither is replaced by a scalar stand-in.

For each task we scanned the complete official one-million-record random JSONL, selecting 4096 unique uniformly sampled line indices with seed 9371, plus all official edge cases. `download_manifest.json` records exact URLs, full-file SHA256, selected indices and million-row counts. Data and its MIT notice are included. The independent downloader contains no EPL sampler code. From this snapshot, each of seeds 0..4 builds 200 train examples (all edge cases plus random) and 1000 test examples. Duplicate inputs are removed before splitting; no input occurs in train and test. Test labels are never read by target search or its within-target learning. All five splits share a snapshot and many test examples: five seeds do **not** mean five independent problem sets.

An early prefix-only sampling attempt was rejected after it allowed a spurious cut-vector program to pass. Files are strata-ordered. All final artifacts use uniform selection across the complete files. The bad prefix artifacts are not included.

## Methods and named baselines

Exact track calls audited `e7_library_transfer/dsl.py` unchanged. Baseline **BFS-14** is its breadth-first enumerative induction over 14 primitives, depth <=4, all train IO must match, then all 1000 held-out test IO must match. Budget counts candidate programs, including invalid candidates, not wall time or expanded macro instruction count.

Extended track uses the same enumeration structure and E7 library candidate extraction/promotion functions, but appends 14 explicitly authored operations and preserves original arguments alongside the current intermediate. It supports floor division, subtraction, alternating positions, digit operations, first-negative index, suffix maxima, original-value selection, split/pair records, numeric scores, argmin and record selection. **BFS-28** is this no-library baseline. No primitive alone solves a whole selected task on training IO (tested). Still, the language was chosen after inspecting benchmark definitions: suffix-max/equality composition and cut-vector tie handling are task-informed engineering, not discoveries. This track is not the exact reproduction. Generic record operators and manually supplied language extensions cannot support an AGI claim.

Controls on identical target IO and budgets:
- `base`: no library.
- `transfer`: E7 library trained on its existing 40 **authored** source tasks, across its four input-generator domains. Extended source adaptation changes only the input container, not source labels. Target task never enters source learning.
- `random`: random library with EXACTLY the same size as source transfer (including zero), same E7 random generation, per-split fixed seeds.
- `psb_lopo`: leave-one-PSB-problem-out library, target problem omitted completely.
- `within`: eight shards of target **training** IO, with independent train/validation halves within shards, then unchanged E7 promotion with min_domains=1. These are pseudo-tasks of one problem, not eight independent programs or environments.

E7 learns macros from 20000-budget discovery per fit task and promotes only if they improve the other half's validated solved count. This cost is additional to target evaluation, and candidate promotions require further searches. Do not present within's lower target evaluation budget as equal-total-compute superiority. At least 80000 fit-shard candidate budget is available before within evaluation, plus validation. Source learning also has a separate compute cost. The public-only exact leave-one-problem-out fit half has only one task, so E7's >=2-fit-task candidate requirement makes it degenerate. That diagnostic is reported, not silently relaxed. Extended public-only leave-one-problem-out learns no useful transferable macros here.

## Results

Counts below are distinct problems solved on **every** split seed; all five seeds have identical counts. Raw 200 task/split/budget rows are in `rows.jsonl`, with programs and evaluation counts. Macros/promotion logs are in `libraries.json`.

| Track | Budget | Base | Source transfer | Size-matched random | PSB leave-one-problem-out | Within-target |
|---|---:|---:|---:|---:|---:|---:|
| Exact BFS-14 | 1000 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 |
| Exact BFS-14 | 3000 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 |
| Exact BFS-14 | 10000 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 |
| Exact BFS-14 | 30000 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 |
| Extended BFS-28 | 1000 | 2/6 | 2/6 | 2/6 | 2/6 | 4/6 |
| Extended BFS-28 | 3000 | 2/6 | 2/6 | 2/6 | 2/6 | 4/6 |
| Extended BFS-28 | 10000 | 2/6 | 2/6 | 2/6 | 2/6 | 4/6 |
| Extended BFS-28 | 30000 | 5/6 | 5/6 | 5/6 | 5/6 | 5/6 |

At smaller extended budgets, base solves basement and leaders. Within adds fuel-cost using `floor3,minus2` and luhn using `alternating_double,digit_sum` macros. At 30000 base also solves find-pair, fuel-cost and luhn. A separate no-library coverage search at 600000 (seed 0 only, not part of control comparison) finds cut-vector at candidate 501673 and verifies it. All six discovered high-budget programs and hand-authored language expressivity witnesses match held-out public examples (`coverage.json`). Witnesses are never provided to search or learning.

Source library size exact: 2,1,0,0 at budgets 1000,3000,10000,30000. Extended: 3,2,1,0. In every target/split/budget, source transfer minus base solved indicator = 0. Random-library indicators also match base. This is a finite six-problem negative result, **not** proof that library learning can never help. No confidence interval treating 30 repeated task instances as independent tasks is reported. No statistically established cross-problem gain exists in these data.

## Claim ledger

| Claim | Status | Boundary |
|---|---|---|
| Correct public-data snapshot, integer-list filter and disjoint-input splits | VERIFIED | Official files scanned fully; 4096-line snapshot per task, not full-million evaluation |
| Exact E7 source-library gain on PSB2 is zero in tested settings | VERIFIED / SCOPED | Four native tasks, five repeat splits, four budgets; arity excludes two more |
| Extended DSL represents all six full tasks, including multiple outputs and empties | VERIFIED / SCOPED | Hand-engineered vocabulary, witness and discovered programs tested on held-out IO |
| Learned source transfer improves extended BFS-28 | PARTIAL, negative | Exactly zero gain on all six tasks and budgets tested |
| Within-target macros lower needed target-search budget for fuel-cost/luhn | VERIFIED / SCOPED | Separate discovery spend; no equal-total-compute or cross-domain benefit |
| A PSB2 gain against DreamCoder, Stitch or PushGP | PARTIAL / not tested | Only named BFS-14/BFS-28 are directly run |
| General abstraction learning, scientific-domain transfer or AGI | PARTIAL / not established | Six different program problems are not biology/physics/code reasoning domains |
| Novel method | PARTIAL / not claimed | E7 reuse plus task-informed language coverage engineering |

Tests: 27 passed. `test_psb2.py` checks snapshot integrity, uniform index coverage, all six witnesses, leakage, empty output, multi-argument output, exact backend restoration, zero-size random controls, no whole-task primitive, no witness injection, finite-budget acceptance and within's training-only access. Executable replay is required before relying on VERIFIED beyond this run; separate auditor can re-run commands below.

## Replay

Install free Python 3.12 with numpy/pytest. On original f7ae6fe7, apply audited E6/E7/E8 first, then this new-files patch. On current main 4f68f54 the harness is already present, so apply only this patch. From the repo root:

```sh
python3.12 -m pip install -r experiments/e9_psb2_transfer/requirements.txt
python3.12 -m pytest -q experiments/e9_psb2_transfer/test_psb2.py
python3.12 experiments/e9_psb2_transfer/psb2_run.py --seeds 5 --budgets 1000 3000 10000 30000
python3.12 experiments/e9_psb2_transfer/analyze.py
python3.12 experiments/e9_psb2_transfer/coverage.py
```

Data regeneration (downloads/scans ~six million official records) is optional: `python3.12 experiments/e9_psb2_transfer/download.py`; rerun psb2_run to refresh snapshot hashes afterward. Frozen local replay needs no network, GPU, paid API or Colab. Full control replay took about 86 seconds on this CPU; timings are not a benchmark claim.

## Sources and prior-art boundary

- PSB2 v1.0.1 publication, data format, use and MIT license: https://zenodo.org/records/5084812
- Official dataset license retrieved verbatim: https://psb2-datasets.s3.amazonaws.com/PSB2/LICENSE
- Official dataset README: https://psb2-datasets.s3.amazonaws.com/PSB2/README.md
- Benchmark overview and reference implementation links: https://www.cs.hamilton.edu/~thelmuth/PSB2/PSB2.html
- Exact original reference release checked, definitions inspected without copying code: https://github.com/thelmuth/Clojush/releases/tag/psb2-v1.0 (commit 8f7d2d78c6cbc69baf3b20400a1499525c94322f)
- Sampler code (EPL-2.0, NOT copied): https://github.com/thelmuth/psb2-python
- DreamCoder library-learning prior art: https://arxiv.org/abs/2006.08381
- Stitch library-learning prior art: https://arxiv.org/abs/2211.16605
- PushGP/PSB2 evaluation context: https://link.springer.com/article/10.1007/s10710-022-09434-y

No source's published results are used as a matched-budget head-to-head. Only our named enumerative baselines have identical training/test snapshots and budgets here. Cite Helmuth and Kelly, PSB2: The Second Program Synthesis Benchmark Suite, GECCO 2021, DOI 10.1145/3449639.3459285.
