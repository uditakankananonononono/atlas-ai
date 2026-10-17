"""LocalKnowledgePipeline-level regression tests for the descriptor-anchored
delete / manifest write. AUTHORED FOR THE REVIEWER; NOT RUN by the author (no
pydantic/fastapi in the scratch environment). Do not treat as proof until run
in the real repo environment. Races are simulated by swapping a path inside a
patched hook, so each test is deterministic; real concurrent races stay open."""
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.modules.m25_knowledge_copilot_training import fs_safe
from app.modules.m25_knowledge_copilot_training.pipeline import KnowledgeError, LocalKnowledgePipeline
from app.modules.m25_knowledge_copilot_training.schemas import ConsentRecord, IngestRequest, SourceRegistration

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _req(sid="src1", text="hello world. second paragraph."):
    src = SourceRegistration(
        source_id=sid, kind="file", title="t",
        consent=ConsentRecord(granted_by="u", granted_at=NOW, purposes=["knowledge_ingestion"], evidence="e"),
    )
    return IngestRequest(source=src, content=text, mime_type="text/plain", actor_id="actor")


class PipelineDescriptorBoundary(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.p = LocalKnowledgePipeline(self.root / "mnt", "tenant", "actor", clock=lambda: NOW)
        self.out = self.root / "outside"
        self.out.mkdir()
        (self.out / "precious").write_text("keep")

    def test_delete_verified_removes_owned_source(self):
        self.p.ingest(_req())
        self.assertTrue(self.p.delete_verified("src1")["deleted"])
        self.assertFalse((self.p.workspace / "src1").exists())

    def test_delete_verified_does_not_follow_source_dir_swapped_to_symlink(self):
        self.p.ingest(_req())
        real = fs_safe.remove_child_tree
        shutil.rmtree(self.p.workspace / "src1")
        os.symlink(self.out, self.p.workspace / "src1")
        # The real pipeline refuses at _contained (symlinked component) before
        # fs_safe is reached - a STRONGER refusal than the originally asserted
        # deleted=False. fs_safe's own guard is covered by test_m25_fs_safe.
        with self.assertRaises(KnowledgeError):
            self.p.delete_verified("src1")
        self.assertEqual((self.out / "precious").read_text(), "keep")
        self.assertTrue((self.p.workspace / "src1").is_symlink())
        self.assertIs(real, fs_safe.remove_child_tree)

    def test_manifest_write_refuses_source_dir_swapped_to_symlink(self):
        rec = self.p.register(_req().source)
        shutil.rmtree(self.p.workspace / "src1")
        os.symlink(self.out, self.p.workspace / "src1")
        with self.assertRaises((OSError, KnowledgeError)):
            self.p._persist_manifest(rec)
        self.assertEqual([x.name for x in self.out.iterdir()], ["precious"])

    def test_manifest_roundtrip_after_ingest(self):
        self.p.ingest(_req())
        self.assertTrue((self.p.workspace / "src1" / "manifest.json").is_file())
        self.assertEqual([x.name for x in (self.p.workspace / "src1").iterdir() if ".tmp-" in x.name], [])


if __name__ == "__main__":
    unittest.main()

class IngestDescriptorBoundary(unittest.TestCase):
    """Pipeline-level regressions for the descriptor-anchored ingest write path.
    AUTHORED FOR THE REVIEWER; NOT RUN by the author (no pydantic/fastapi in the
    scratch environment). Swaps are placed by monkeypatching os.lstat/os.mkdir
    at deterministic seams; real concurrent races stay open."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.p = LocalKnowledgePipeline(self.root / "mnt", "tenant", "actor", clock=lambda: NOW)
        self.out = self.root / "outside"
        self.out.mkdir()
        (self.out / "precious").write_text("keep")

    def _swap_sid_to_link(self):
        d = self.p.workspace / "src1"
        if d.is_symlink():
            return
        if d.exists():
            shutil.rmtree(d)
        os.symlink(self.out, d)

    def _out_entries(self):
        return sorted(e.name for e in self.out.iterdir() if e.name != "precious")

    def test_ingest_refuses_source_dir_swapped_to_symlink(self):
        import unittest.mock as mock
        real_open = os.open
        calls = {"n": 0}
        def wrapped(*a, **kw):
            # The registration manifest persist opens the source dir by name
            # first; swap only at the SECOND matching open, which is ingest's
            # own source-dir acquisition.
            if a and str(a[0]) == "src1" and kw.get("dir_fd") is not None:
                calls["n"] += 1
                if calls["n"] == 2:
                    self._swap_sid_to_link()
            return real_open(*a, **kw)
        with mock.patch("os.open", wrapped):
            with self.assertRaises((OSError, KnowledgeError)):
                self.p.ingest(_req())
        self.assertEqual(self._out_entries(), [])
        self.assertEqual((self.out / "precious").read_text(), "keep")
        self.assertEqual(len(self.p.records["src1"].versions), 0)

    def test_ingest_tmp_create_cannot_be_redirected_by_swap(self):
        import unittest.mock as mock
        real_lstat = os.lstat
        def wrapped(*a, **kw):
            try:
                r = real_lstat(*a, **kw)
            except FileNotFoundError:
                if str(a[0]) == "v1" and "dir_fd" in kw:
                    self._swap_sid_to_link()
                raise
            if str(a[0]) == "v1" and "dir_fd" in kw:
                self._swap_sid_to_link()
            return r
        with mock.patch("os.lstat", wrapped):
            try:
                self.p.ingest(_req())
            except (OSError, KnowledgeError):
                pass
        self.assertEqual(self._out_entries(), [])

    def test_ingest_refuses_dangling_symlink_planted_at_target(self):
        (self.p.workspace / "src1").mkdir(parents=True)
        os.symlink(self.out / "nonexistent", self.p.workspace / "src1" / "v1")
        with self.assertRaises((OSError, KnowledgeError)):
            self.p.ingest(_req())
        self.assertTrue((self.p.workspace / "src1" / "v1").is_symlink())
        self.assertEqual(self._out_entries(), [])

    def test_ingest_normal_and_dedup_still_work(self):
        v1 = self.p.ingest(_req(text="alpha body"))
        self.assertEqual(v1.number, 1)
        v2 = self.p.ingest(_req(text="beta body"))
        self.assertEqual(v2.number, 2)
        v3 = self.p.ingest(_req(text="beta body"))
        self.assertEqual(v3.number, 2)
        self.assertEqual((self.p.workspace / "src1" / "v1" / "source.bin").read_bytes(), b"alpha body")
        leftovers = [e.name for e in (self.p.workspace / "src1").iterdir() if ".tmp-" in e.name]
        self.assertEqual(leftovers, [])

