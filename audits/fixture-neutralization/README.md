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

The second patch replaces synthetic names in the waiver-draft input/expected
bodies with UserA, and prefill fields with Sample Student and Sample School.
UserA preserves the five-character default-name length used by the existing
exact template/body-size boundary test.
Waiver draft IDs are compared to freshly computed hashes, not a pinned old-name
hash. Other explicit boundary profiles stay unchanged. Historical receipts are
not rewritten; name-bearing authority IDs, audit records, repository locators
and other remaining tracked files require separate review.
