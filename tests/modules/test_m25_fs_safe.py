"""Descriptor-anchored workspace removal (real scratch filesystem only)."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from app.modules.m25_knowledge_copilot_training.fs_safe import remove_child_tree, write_file_in_child_dir


class RemoveChildTree(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        self.ws = self.root / "ws"
        self.ws.mkdir()
        self.src = self.ws / "src1"
        (self.src / "v1").mkdir(parents=True)
        (self.src / "v1" / "source.bin").write_bytes(b"x")
        (self.src / "manifest.json").write_text("{}")
        self.out = self.root / "outside"
        self.out.mkdir()
        (self.out / "precious").write_text("p")

    def test_removes_tree_and_verifies(self):
        self.assertTrue(remove_child_tree(self.ws, "src1"))
        self.assertFalse(self.src.exists())

    def test_already_absent_is_verified_true(self):
        shutil.rmtree(self.src)
        self.assertTrue(remove_child_tree(self.ws, "src1"))

    def test_symlink_at_name_left_alone_false(self):
        shutil.rmtree(self.src)
        os.symlink(self.out, self.src)
        self.assertFalse(remove_child_tree(self.ws, "src1"))
        self.assertTrue(self.src.is_symlink())
        self.assertTrue((self.out / "precious").exists())

    def test_regular_file_at_name_false(self):
        shutil.rmtree(self.src)
        self.src.write_text("f")
        self.assertFalse(remove_child_tree(self.ws, "src1"))
        self.assertTrue(self.src.exists())

    def test_inner_symlinks_not_followed(self):
        os.symlink(self.out, self.src / "v1" / "dirlink")
        os.symlink(self.out / "precious", self.src / "filelink")
        self.assertTrue(remove_child_tree(self.ws, "src1"))
        self.assertTrue((self.out / "precious").exists())

    def test_bad_names_refused_without_touching(self):
        for bad in ("", ".", "..", "a/b"):
            self.assertFalse(remove_child_tree(self.ws, bad))
        self.assertTrue(self.src.exists())
        self.assertTrue((self.out / "precious").exists())

    def test_parent_missing_or_not_dir_false(self):
        self.assertFalse(remove_child_tree(self.root / "nope", "src1"))
        f = self.root / "file"
        f.write_text("x")
        self.assertFalse(remove_child_tree(f, "src1"))

    def test_parent_symlink_not_followed(self):
        link = self.root / "wslink"
        os.symlink(self.ws, link)
        self.assertFalse(remove_child_tree(link, "src1"))
        self.assertTrue(self.src.exists())

    def test_name_swapped_to_symlink_after_lstat_not_followed(self):
        real_open = os.open
        state = {"n": 0}

        def hook(p, flags, *a, **k):
            if p == "src1" and k.get("dir_fd") is not None and state["n"] == 0:
                state["n"] = 1
                shutil.rmtree(self.src)
                os.symlink(self.out, self.src)
            return real_open(p, flags, *a, **k)

        os.open = hook
        try:
            self.assertFalse(remove_child_tree(self.ws, "src1"))
        finally:
            os.open = real_open
        self.assertEqual(state["n"], 1)
        self.assertTrue((self.out / "precious").exists())

    def test_name_swapped_to_other_dir_between_lstat_and_open(self):
        real_open = os.open
        state = {"n": 0}

        def hook(p, flags, *a, **k):
            if p == "src1" and k.get("dir_fd") is not None and state["n"] == 0:
                state["n"] = 1
                os.rename(self.src, self.root / "detached")
                self.src.mkdir()
                (self.src / "foreign").write_text("f")
            return real_open(p, flags, *a, **k)

        os.open = hook
        try:
            self.assertFalse(remove_child_tree(self.ws, "src1"))
        finally:
            os.open = real_open
        self.assertTrue((self.src / "foreign").exists())
        self.assertTrue((self.root / "detached" / "manifest.json").exists())

    def test_empty_foreign_dir_swapped_before_final_check_survives(self):
        real = os.lstat
        state = {"n": 0}

        def hook(p, *a, **k):
            if k.get("dir_fd") is not None and p == "src1":
                state["n"] += 1
                if state["n"] == 2:  # the pre-rmdir identity lstat
                    os.rename(self.src, self.root / "detached")
                    self.src.mkdir()
            return real(p, *a, **k)

        os.lstat = hook
        try:
            self.assertFalse(remove_child_tree(self.ws, "src1"))
        finally:
            os.lstat = real
        self.assertTrue(self.src.is_dir())

    def test_inner_subdir_swapped_to_symlink_not_followed(self):
        real_open = os.open
        state = {"n": 0}

        def hook(p, flags, *a, **k):
            if p == "v1" and k.get("dir_fd") is not None and state["n"] == 0:
                state["n"] = 1
                shutil.rmtree(self.src / "v1")
                os.symlink(self.out, self.src / "v1")
            return real_open(p, flags, *a, **k)

        os.open = hook
        try:
            # the symlink now sitting at v1 cannot be removed as a directory
            # (nothing is followed), so the tree is NOT fully removed: False
            self.assertFalse(remove_child_tree(self.ws, "src1"))
        finally:
            os.open = real_open
        self.assertEqual(state["n"], 1)
        self.assertTrue((self.out / "precious").exists())

    def test_deep_tree(self):
        p = self.src
        for _ in range(70):
            p = p / "d"
            p.mkdir()
        self.assertTrue(remove_child_tree(self.ws, "src1"))


class WriteFileInChildDir(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        self.ws = self.root / "ws"
        self.ws.mkdir()
        self.out = self.root / "outside"
        self.out.mkdir()

    def test_creates_dir_and_file(self):
        write_file_in_child_dir(self.ws, "src1", "manifest.json", b"abc")
        self.assertEqual((self.ws / "src1" / "manifest.json").read_bytes(), b"abc")
        self.assertEqual([p.name for p in (self.ws / "src1").iterdir()], ["manifest.json"])

    def test_replaces_existing_atomically_no_tmp_left(self):
        write_file_in_child_dir(self.ws, "src1", "manifest.json", b"one")
        write_file_in_child_dir(self.ws, "src1", "manifest.json", b"two")
        self.assertEqual((self.ws / "src1" / "manifest.json").read_bytes(), b"two")
        self.assertEqual(len(list((self.ws / "src1").iterdir())), 1)

    def test_symlinked_child_dir_refused_nothing_written(self):
        os.symlink(self.out, self.ws / "src1")
        with self.assertRaises(OSError):
            write_file_in_child_dir(self.ws, "src1", "manifest.json", b"x")
        self.assertEqual(list(self.out.iterdir()), [])

    def test_symlinked_parent_refused(self):
        link = self.root / "wslink"
        os.symlink(self.ws, link)
        with self.assertRaises(OSError):
            write_file_in_child_dir(link, "src1", "manifest.json", b"x")
        self.assertFalse((self.ws / "src1").exists())

    def test_child_swapped_to_symlink_after_caller_check_cannot_redirect(self):
        (self.ws / "src1").mkdir()
        real_open = os.open
        state = {"n": 0}

        def hook(p, flags, *a, **k):
            if p == "src1" and k.get("dir_fd") is not None and state["n"] == 0:
                state["n"] = 1
                os.rmdir(self.ws / "src1")
                os.symlink(self.out, self.ws / "src1")
            return real_open(p, flags, *a, **k)

        os.open = hook
        try:
            with self.assertRaises(OSError):
                write_file_in_child_dir(self.ws, "src1", "manifest.json", b"x")
        finally:
            os.open = real_open
        self.assertEqual(state["n"], 1)
        self.assertEqual(list(self.out.iterdir()), [])

    def test_preexisting_symlink_manifest_not_written_through(self):
        (self.ws / "src1").mkdir()
        (self.out / "target").write_text("keep")
        os.symlink(self.out / "target", self.ws / "src1" / "manifest.json")
        write_file_in_child_dir(self.ws, "src1", "manifest.json", b"new")
        self.assertEqual((self.out / "target").read_text(), "keep")
        self.assertFalse((self.ws / "src1" / "manifest.json").is_symlink())
        self.assertEqual((self.ws / "src1" / "manifest.json").read_bytes(), b"new")

    def test_failed_write_unlinks_own_tmp_and_keeps_previous(self):
        write_file_in_child_dir(self.ws, "src1", "manifest.json", b"old")
        real_fsync = os.fsync
        state = {"n": 0}

        def bad(fd):
            state["n"] += 1
            raise OSError("boom")

        os.fsync = bad
        try:
            with self.assertRaises(OSError):
                write_file_in_child_dir(self.ws, "src1", "manifest.json", b"new")
        finally:
            os.fsync = real_fsync
        self.assertEqual(state["n"], 1)
        self.assertEqual((self.ws / "src1" / "manifest.json").read_bytes(), b"old")
        self.assertEqual([p.name for p in (self.ws / "src1").iterdir()], ["manifest.json"])

    def test_tmp_collision_with_symlink_not_written_through(self):
        import uuid
        (self.ws / "src1").mkdir()
        (self.out / "target").write_text("keep")
        fixed = uuid.UUID(int=7)
        os.symlink(self.out / "target", self.ws / "src1" / ("manifest.json.tmp-" + fixed.hex))
        real = uuid.uuid4
        uuid.uuid4 = lambda: fixed
        try:
            with self.assertRaises(OSError):
                write_file_in_child_dir(self.ws, "src1", "manifest.json", b"new")
        finally:
            uuid.uuid4 = real
        self.assertEqual((self.out / "target").read_text(), "keep")
        self.assertFalse((self.ws / "src1" / "manifest.json").exists())

    def test_file_and_directory_are_both_fsynced(self):
        import stat as st
        real = os.fsync
        kinds = []

        def spy(fd):
            kinds.append(st.S_ISDIR(os.fstat(fd).st_mode))
            return real(fd)

        os.fsync = spy
        try:
            write_file_in_child_dir(self.ws, "src1", "manifest.json", b"x")
        finally:
            os.fsync = real
        self.assertEqual(kinds, [False, True])

    def test_bad_names_refused(self):
        for d, f in (("", "m"), (".", "m"), ("..", "m"), ("a/b", "m"), ("s", ""), ("s", "a/b")):
            with self.assertRaises(OSError):
                write_file_in_child_dir(self.ws, d, f, b"x")
        self.assertEqual(list(self.ws.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
