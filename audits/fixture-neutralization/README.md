# Neutral registration and agency test fixtures

The current registration-pipeline reviewer labels and agency reviewer/brand labels
use Reviewer A and Sample Studio instead of personal names. These labels are
synthetic test data, not identity or owner-approval evidence. Reviewer values feed
a runtime artifact digest; the tests compare freshly computed values and contain
no pinned digest for the old names. The brand palette test checks shape, not a
pinned palette. Both brand input and expected name changed together.

Product code, historical receipts and their recorded test-file hashes are unchanged.
The historical hashes describe their original bytes, not these revised tests.
This does not claim to remove personal names throughout the repository or its Git
history. No new mutation replay or row promotion follows from this fixture edit.
