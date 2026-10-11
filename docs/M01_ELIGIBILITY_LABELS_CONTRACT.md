# M1 eligibility label harness: contract

Module: `backend/app/modules/m01_opportunity_discovery/eligibility_labels.py`
Tests: `tests/modules/test_m01_eligibility_labels.py`

## Purpose

The M1 eligibility classifier is zero-shot today. `classifier.py` defines `fine_tune_ready`, the gate that says a
fine-tune needs at least 500 labels in total and at least 100 per class. This unit is the bookkeeping for collecting
labels that can meet that gate. It does not train, load or score a model, and it never generates, infers or fills in a
label. Every label comes from a caller and must be marked `human_reviewed`.

Build-time assumption, not a repo statement: a public-dataset search at build time found no licensed dataset that
labels opportunity eligibility in this domain (clinical-trial matching sets, scholarship and scheme lists and
resume-fit sets were checked; none fits the task or the licence need). The mitigation is that this module refuses every
label that is not `human_reviewed`, so a mismatched or synthetic set cannot be counted toward the gate. If a suitable
licensed dataset turns up, its labels would still need human review before this module accepts them.

## Contract of record

Readiness is exactly `fine_tune_ready` imported from `classifier.py`, with its thresholds `MIN_FINE_TUNE_LABELS` (500
labels in total) and `MIN_PER_CLASS` (100 per class). This module restates neither number as its own constant. If the
classifier thresholds change, this module follows.

## Behavior

Record: a dict with exactly the keys `record_id`, `group_id`, `text`, `profile`, `label`, `label_source`, `reviewer`,
`reviewed_at`. All values are exact `str`; subclasses are refused.

- `label`: `eligible`, `ineligible` or `unclear`.
- `label_source`: only `human_reviewed` is accepted. `synthetic`, `model_generated` and `rule_derived` are refused with
  `ELIGLAB_REFUSED_SYNTHETIC:label_source`; any other value is `BAD_VALUE`.
- `add_label(records, record)` returns a new list; inputs are not modified.
- `gate_status(records)` returns total, per-class counts, shortfalls against the gate, and `ready` from
  `fine_tune_ready`. It always reports `model_trained` false and `labels_generated` false.
- `split_records(records, seed)` returns a deterministic split by `group_id`; all records of a group land in the same
  split. Refuses below the gate.
- `evaluate(records, predictions, seed)` scores caller-supplied predictions (`{record_id: label}`) against the gold
  labels of the test split only. It returns accuracy, macro F1, per-class support, precision, recall and F1, a
  confusion matrix and the majority-class baseline, all rounded to 6 decimals. It refuses below the gate. It trains
  nothing and fabricates nothing: the numbers come only from supplied gold labels and supplied predictions.

All refusals raise `ValueError` whose text is `ELIGLAB_REFUSED_<REASON>:<field>`. The text never contains the offending
value.

Validation order: preflight fence (list and dict types, record count, key count, key length, raw string length; no
per-character work, subclasses refused unmeasured), then keys (an unknown key is reported before a missing key), then
each field's own cap across all records, then content and shape errors. Oversize is reported before content errors.

Content rules: ids (`record_id`, `group_id`, seed) match `[A-Za-z0-9_.:-]`; reviewer matches `[A-Za-z0-9_.@-]`;
`reviewed_at` is a real calendar date `YYYY-MM-DD` in ASCII digits. `text` and `profile` must not be blank. Control and
format characters (categories Cc, Cf, Zl, Zp) are refused in every string; `text` and `profile` may contain newline,
carriage return and tab. Duplicate `record_id` values are refused.

## Caps

20000 records; 8 keys per record; key length 64; raw string length 10000 (preflight); record_id and group_id 128;
text 8000; profile 4000; label and label_source 16; reviewer 64; reviewed_at 10; seed 64; predictions 20000.
Each cap is exact: N passes, N+1 is refused.

## INTERPRETATION CHOICE items

1. Split hash: sha256 of `seed|group_id`, reduced modulo 10000. Below 8000 is train, below 9000 is dev, the rest is
   test (about 80/10/10). The ratios and hash are this unit's choice; the repo defines none.
2. Grouped split: records sharing a `group_id` never straddle splits, so near-duplicate opportunities cannot leak from
   train into test.
3. `evaluate` uses only the test split. The dev split is returned by `split_records` for the caller's own tuning and is
   not scored here.
4. `evaluate` refuses with `EMPTY_CLASS:test` when the test split lacks any of the three classes, rather than report a
   metric over a class with no support. A small or unlucky seed can trigger this; the caller picks another seed or adds
   labels.
5. Only `human_reviewed` counts. The other three source values exist so they can be refused by name.
6. Reviewer and date grammars, and all caps above, are bounds chosen here. `reviewer` is a handle, not an identity
   check.
7. Only the character categories Cc, Cf, Zl and Zp are refused. Category Co code points and every other category are
   treated as ordinary text.
8. Macro F1 is the mean of the three unrounded per-class F1 values, rounded once. A class with no predicted records has
   precision 0 and F1 0.

## Training guidance (untested, no code in this repo)

This is guidance only, and nothing in this repo runs it. Fine-tuning would run outside this repo, for example in a
Google Colab free-tier notebook on a T4 GPU. A plausible setup is a DeBERTa-v3 base checkpoint, fp16, max sequence
length near 256, a small batch size with gradient accumulation, trained on the train split and tuned on the dev split.
Then export predictions for the test split and pass them to `evaluate`. These settings have not been tried here. Free
T4 sessions are time-limited and can be reclaimed, so save checkpoints as you go.

## Checkpoint location

A trained checkpoint is never committed to this repo. It lives where the owner chooses (for example the owner's own
cloud drive or local storage) and the owner supplies the path at load time. This unit stores no path and loads nothing.

## LIMITS

- Labels are caller-supplied. This unit cannot check that a reviewer exists or that a review happened.
- No model is trained, loaded or evaluated here. Metrics describe only the supplied gold labels and supplied
  predictions.
- Metrics cover the supplied test split only and say nothing about other opportunity types, sources or applicants.
- Readiness is `fine_tune_ready` over `human_reviewed` labels. Passing the gate does not make a model good.
- Not wired into any pipeline, route or script by this unit.
- Offline and pure: no files, network or randomness.
