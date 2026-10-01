# E: preference dataset permutation validation

Base: 313309be2a960a84b909d1834c3046f884e21a7e.
Local branch: fix/approval-binding-and-rank-permutation.

The native baseline accepted options ['a','b'] with ranking ['a','a','b']. No training executed. See baseline-native.txt and reproduce_baseline.py.

## Changes

Require lists of nonblank text option IDs and ranking IDs, at least two options, equal lengths, unique option IDs, unique ranked IDs and equal membership. Reject malformed ranking records/collections and non-text contexts. Copy input lists into dataset examples to prevent later input mutation from silently changing the hashed examples.

Optional empty context remains allowed for compatibility. Empty or whitespace-only option/ranking text is rejected. Unicode IDs retain exact codepoint identity without silent normalization. The existing minimum is preserved at 20 rankings; no new maximum is invented.

## Acceptance

Command: PYTHONPATH=backend python -m pytest tests/test_preference_dataset_permutation_native.py -v

29 passed in 1.35s. Full stdout: acceptance-E.txt.

Committed negative JSON fixture, duplicated/missing/unknown IDs, duplicate option IDs, malformed types, blank ID text, generated permutations for every size 2 through 6 with duplicate mutations (872 valid permutations), sample boundaries 0/1/19/20/21/2001, empty context, Unicode text, hash repeatability/order sensitivity and input-alias protection.

Combined native regression run with A, existing personalization, Module 0 and impact preview: 103 passed, 1 warning in 20.11s. Warning: upstream Starlette/httpx test client deprecation. See expanded-tests.txt. Existing tests were not weakened or changed.

## Limits

No real training, GPU work, publishing, accounts or outside effects. Dataset hashes are not evidence of training quality. TrainingDataset still contains mutable examples, as before; this change prevents aliasing from the original caller lists, not deliberate post-creation mutation by a holder of the dataset. Full repository suite and full ML/browser dependencies were not exercised.
