"""hz28: claim-manifest writes are anchored to the HELD source-dir descriptor.
Regression pin for the real-dir-replacement split-state reproduced on
2026-10-17 (repro_splitstate.py): pre-fix, a source dir REPLACED by a real
directory mid-ingest left the claim manifest recording v1 in the replacement
dir while v1's bytes stayed in the held original - a live manifest with no
content behind it. The fix threads the held dirfd into the claim persist so
the manifest and the bytes it records stay co-located. Seams are deterministic
(monkeypatched os.lstat); real concurrent races stay open. Not claimed: survival
of path replacement across LATER operations (each write is truthful, the path
itself is not pinned).
"""
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.modules.m25_knowledge_copilot_training.pipeline import KnowledgeError, LocalKnowledgePipeline
from app.modules.m25_knowledge_copilot_training.schemas import ConsentRecord, IngestRequest, SourceRegistration

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _src():
    return SourceRegistration(source_id="s1", kind="website", canonical_url="https://example.test/s1",
                              author="A", published_at=NOW, title="T",
                              consent=ConsentRecord(granted_by="o", granted_at=NOW,
                                                    purposes=["knowledge_ingestion"], evidence="e"))


class ManifestAnchoring(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.p = LocalKnowledgePipeline(self.root / "mnt", "tenant-a", "actor-a", clock=lambda: NOW)
        self.ws = self.root / "mnt" / "tenant-a"

    def test_claim_manifest_co_located_with_version_bytes(self):
        import unittest.mock as mock
        real_lstat = os.lstat
        state = {"done": False}
        def wrapped(*a, **kw):
            try:
                r = real_lstat(*a, **kw)
            except FileNotFoundError:
                if str(a[0]) == "v1" and "dir_fd" in kw and not state["done"]:
                    state["done"] = True
                    os.rename(self.ws / "s1", self.ws / "s1_moved")
                    (self.ws / "s1").mkdir()
                raise
            return r
        with mock.patch("os.lstat", wrapped):
            v = self.p.ingest(IngestRequest(source=_src(), content="Alpha fact.",
                                            mime_type="text/plain", actor_id="actor-a"))
        self.assertEqual(v.number, 1)
        self.assertTrue(state["done"])  # the seam must actually fire
        moved = self.ws / "s1_moved"
        # The manifest recording v1 must live WITH v1's bytes (the held dir),
        # and the replacement dir must not receive a manifest it has no bytes for.
        self.assertEqual((moved / "v1" / "source.bin").read_bytes(), b"Alpha fact.")
        self.assertEqual([x["number"] for x in json.loads((moved / "manifest.json").read_text())["versions"]], [1])
        self.assertFalse((self.ws / "s1" / "manifest.json").exists())
        self.assertEqual(list((self.ws / "s1").iterdir()), [])

    def test_normal_ingest_and_dedup_unchanged(self):
        req = IngestRequest(source=_src(), content="Alpha fact.", mime_type="text/plain", actor_id="actor-a")
        v = self.p.ingest(req)
        self.assertEqual(v.number, 1)
        again = self.p.ingest(IngestRequest(source=_src(), content="Alpha fact.",
                                            mime_type="text/plain", actor_id="actor-a"))
        self.assertEqual(again.number, 1)
        d = self.ws / "s1"
        self.assertEqual((d / "v1" / "source.bin").read_bytes(), b"Alpha fact.")
        self.assertEqual([x["number"] for x in json.loads((d / "manifest.json").read_text())["versions"]], [1])

    def test_failed_claim_write_leaves_no_tmp_in_held_dir(self):
        import unittest.mock as mock
        # Register first, then arm: fail the manifest tmp-file fsync during the
        # CLAIM persist only (the second manifest tmp write overall).
        self.p.register(_src())
        real_fsync = os.fsync
        state = {"seen": 0}
        def wrapped(fd):
            try:
                name = os.readlink(f"/proc/self/fd/{fd}")
            except OSError:
                name = ""
            if name.rsplit("/", 1)[-1].startswith("manifest.json.tmp-"):
                state["seen"] += 1
                if state["seen"] == 2:
                    raise OSError("armed claim-write fsync failure")
            return real_fsync(fd)
        with mock.patch("os.fsync", wrapped):
            with self.assertRaises((OSError, KnowledgeError)):
                self.p.ingest(IngestRequest(source=_src(), content="Alpha fact.",
                                            mime_type="text/plain", actor_id="actor-a"))
        self.assertEqual(state["seen"] >= 2, True)
        leftovers = [e.name for e in (self.ws / "s1").iterdir() if ".tmp-" in e.name]
        self.assertEqual(leftovers, [])

    def test_symlinked_manifest_name_in_held_dir_refused_no_tmp_left(self):
        (self.ws / "s1").mkdir(parents=True)
        os.symlink(self.root / "outside-target", self.ws / "s1" / "manifest.json")
        with self.assertRaises((OSError, KnowledgeError)):
            self.p.ingest(IngestRequest(source=_src(), content="Alpha fact.",
                                        mime_type="text/plain", actor_id="actor-a"))
        self.assertTrue((self.ws / "s1" / "manifest.json").is_symlink())
        leftovers = [e.name for e in (self.ws / "s1").iterdir() if ".tmp-" in e.name]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
