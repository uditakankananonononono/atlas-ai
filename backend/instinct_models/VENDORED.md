# Vendored copy of instinct_models

Source of truth: https://github.com/uditakankananonononono/shared-models
Pinned commit: 4cd3944

Do not edit here. Change shared-models, then re-sync with `scripts/sync_shared_models.sh <commit>`.

Exception (e11 rev0, disclosed): stepverify.py was added here directly
via the e11 rev0 patch, not through scripts/sync_shared_models.sh. Its
canonical home is the shared-models patch agi-stepverify-sm.patch (file
sha256 6a2e38f8e84b4af3736b36c3447379315c8fa5b7f81e4dfc8f7284fe93ec4de4,
applies against tip 97aae1f; not yet committed there). Keep the two
copies byte-identical; re-sync manually until the patch lands upstream.
