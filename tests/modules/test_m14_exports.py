"""Tests for the Module 14 export system."""

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.modules.m14_project_builder.artifacts import build_manifest as artifact_manifest
from app.modules.m14_project_builder.exports import (
    ExportError,
    ReadmeContext,
    build_manifest,
    create_zip,
    render_readme,
    safe_join,
    sha256_file,
    verify_export,
    write_project_files,
)
from app.modules.m14_project_builder.milestones import instantiate_template

UTC = timezone.utc
NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


@pytest.fixture
def project_dir(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    return root


class TestSafeJoin:
    def test_rejects_absolute(self, project_dir):
        with pytest.raises(ExportError):
            safe_join(project_dir, "/etc/passwd")

    def test_rejects_dotdot(self, project_dir):
        with pytest.raises(ExportError):
            safe_join(project_dir, "../escape.txt")
        with pytest.raises(ExportError):
            safe_join(project_dir, "a/../../escape.txt")

    def test_rejects_empty(self, project_dir):
        with pytest.raises(ExportError):
            safe_join(project_dir, "  ")

    def test_nested_ok(self, project_dir):
        target = safe_join(project_dir, "data/raw/out.csv")
        assert target == project_dir.resolve() / "data/raw/out.csv"


class TestWriteFiles:
    def test_writes_and_entries_hash(self, project_dir):
        entries = write_project_files(
            project_dir, {"a.txt": b"alpha", "sub/b.txt": b"beta"}
        )
        assert (project_dir / "a.txt").read_bytes() == b"alpha"
        assert (project_dir / "sub/b.txt").read_bytes() == b"beta"
        by_path = {e.relative_path: e for e in entries}
        assert by_path["a.txt"].byte_size == 5
        assert by_path["sub/b.txt"].byte_size == 4

    def test_refuses_overwrite_by_default(self, project_dir):
        write_project_files(project_dir, {"a.txt": b"one"})
        with pytest.raises(ExportError):
            write_project_files(project_dir, {"a.txt": b"two"})
        assert (project_dir / "a.txt").read_bytes() == b"one"
        write_project_files(project_dir, {"a.txt": b"two"}, overwrite=True)
        assert (project_dir / "a.txt").read_bytes() == b"two"

    def test_rejects_non_bytes(self, project_dir):
        with pytest.raises(ExportError):
            write_project_files(project_dir, {"a.txt": "text"})

    def test_rejects_escape_path(self, project_dir):
        with pytest.raises(ExportError):
            write_project_files(project_dir, {"../evil": b"x"})


class TestManifest:
    def test_manifest_order_and_hash(self, project_dir):
        e1 = write_project_files(project_dir, {"b.txt": b"2", "a.txt": b"1"})
        m1 = build_manifest("p1", e1, generated_at=NOW)
        e2 = write_project_files(project_dir,
                                 {"b.txt": b"2", "a.txt": b"1"}, overwrite=True)
        m2 = build_manifest("p1", tuple(reversed(e2)), generated_at=NOW)
        assert [e.relative_path for e in m1.entries] == ["a.txt", "b.txt"]
        assert m1.content_sha256 == m2.content_sha256
        assert m1.total_bytes == 2
        assert m1.generated_at == NOW.isoformat()
        dumped = m1.to_dict()
        assert dumped["project_id"] == "p1"
        assert len(dumped["entries"]) == 2

    def test_empty_project_id_rejected(self):
        with pytest.raises(ExportError):
            build_manifest("", [])



class TestReadme:
    def _context(self):
        milestones = tuple(instantiate_template("research_project", "p1", NOW))
        artifact = artifact_manifest(
            "p1", "t1", "dataset", "workspace://p1/t1/data.csv", b"csv",
            {"source": "https://example.org", "retrieved_at": NOW.isoformat()},
        )
        return ReadmeContext(
            project_id="p1", goal="Build an ISEF project", status="planned",
            milestones=milestones, artifacts=(artifact,),
            overall_progress=0.42, assumptions=("Public data suffices",),
            risks=("Compute budget",), generated_at=NOW,
        )

    def test_renders_all_sections(self):
        text = render_readme(self._context())
        assert text.startswith("# Build an ISEF project")
        assert "**Progress:** 42%" in text
        for section in ("## Milestones", "## Artifacts", "## Assumptions",
                        "## Risks", "## Verification"):
            assert section in text
        assert "Literature review" in text
        assert "workspace://p1/t1/data.csv" in text
        assert "https://example.org" in text

    def test_pipes_in_goal_escaped(self):
        ctx = self._context()
        ctx = ReadmeContext(**{**ctx.__dict__, "goal": "a | b\nc"})
        text = render_readme(ctx)
        assert "a \\| b c" in text

    def test_minimal_context(self):
        text = render_readme(ReadmeContext(
            project_id="p1", goal="g", status="draft", generated_at=NOW,
        ))
        assert "## Milestones" not in text
        assert "## Verification" in text


class TestZip:
    def test_deterministic_bytes(self, project_dir, tmp_path):
        write_project_files(project_dir, {"a.txt": b"alpha", "sub/b.txt": b"beta"})
        z1 = create_zip(project_dir, tmp_path / "one.zip")
        z2 = create_zip(project_dir, tmp_path / "two.zip")
        assert z1.sha256 == z2.sha256
        with zipfile.ZipFile(tmp_path / "one.zip") as archive:
            assert archive.namelist() == ["a.txt", "sub/b.txt"]
            assert archive.read("a.txt") == b"alpha"

    def test_empty_dir_rejected(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(ExportError):
            create_zip(empty, tmp_path / "x.zip")

    def test_missing_dir_rejected(self, tmp_path):
        with pytest.raises(ExportError):
            create_zip(tmp_path / "nope", tmp_path / "x.zip")


class TestVerify:
    def test_roundtrip_passes(self, project_dir):
        entries = write_project_files(
            project_dir, {"a.txt": b"alpha", "sub/b.txt": b"beta"}
        )
        manifest = build_manifest("p1", entries, generated_at=NOW)
        (project_dir / "export_manifest.json").write_text(
            json.dumps(manifest.to_dict()))
        result = verify_export(project_dir, manifest)
        assert result.passed
        assert result.missing == result.mismatched == result.extra == ()

    def test_detects_missing(self, project_dir):
        entries = write_project_files(project_dir, {"a.txt": b"alpha"})
        manifest = build_manifest("p1", entries)
        (project_dir / "a.txt").unlink()
        result = verify_export(project_dir, manifest)
        assert not result.passed
        assert result.missing == ("a.txt",)

    def test_detects_tampering(self, project_dir):
        entries = write_project_files(project_dir, {"a.txt": b"alpha"})
        manifest = build_manifest("p1", entries)
        (project_dir / "a.txt").write_bytes(b"tampered")
        result = verify_export(project_dir, manifest)
        assert not result.passed
        assert result.mismatched == ("a.txt",)

    def test_detects_extra(self, project_dir):
        entries = write_project_files(project_dir, {"a.txt": b"alpha"})
        manifest = build_manifest("p1", entries)
        (project_dir / "sneaky.txt").write_bytes(b"x")
        result = verify_export(project_dir, manifest)
        assert not result.passed
        assert result.extra == ("sneaky.txt",)
