"""Bounded record counter: formats, cap enforced on the read, no guessing."""
import io
import pytest
from app.modules.instinct_doc import dataset_count_reader_p254 as m


def count(data, fmt):
    return m.count_records(io.BytesIO(data), fmt)


@pytest.mark.parametrize("data,fmt,n", [
    (b'{"a":1}\n{"a":2}\n{"a":3}\n', "jsonl", 3),
    (b'{"a":1}\n{"a":2}', "jsonl", 2),
    (b"id,name\n1,x\n2,y\n", "csv", 2),
    (b"id,name\n", "csv", 0),
    (b'id,name\n1,"multi\nline"\n', "csv", 1),
    (b'[{"a":1},{"a":2},5]', "json", 3),
    (b"[]", "json", 0),
])
def test_counts_by_format(data, fmt, n):
    r = count(data, fmt)
    assert r["status"] == "COUNTED" and r["counted_records"] == n
    assert r["bytes_read"] == len(data) and r["authorship_verified"] is False


@pytest.mark.parametrize("data,fmt", [
    (b'{"a":1}\n\n{"a":2}\n', "jsonl"),
    (b'{"a":1}\nnot json\n', "jsonl"),
    (b"a,b\n\n1,2\n", "csv"),
    (b"", "csv"),
    (b"   \n", "jsonl"),
    (b'{"a":1}', "json"),
    (b"[1,", "json"),
    (b"\xff\xfe", "jsonl"),
])
def test_malformed_or_empty_unverified(data, fmt):
    r = count(data, fmt)
    assert r["status"] == "UNVERIFIED" and r["counted_records"] is None


@pytest.mark.parametrize("fmt", ["xml", "parquet", "", None, 5, "JSONL"])
def test_unsupported_format_not_guessed(fmt):
    r = count(b'{"a":1}\n', fmt)
    assert r["status"] == "UNVERIFIED" and r["reason"] == "unsupported format"


def test_cap_boundary_exact(monkeypatch):
    monkeypatch.setattr(m, "MAX_BYTES", 20)
    ok = b"[" + b"1," * 8 + b"1 ]"
    assert len(ok) == 20
    assert count(ok, "json")["counted_records"] == 9
    r = count(ok + b" ", "json")
    assert r["status"] == "UNVERIFIED" and r["reason"] == "over byte cap"


class Endless:
    def __init__(self):
        self.requested = 0
        self.returned = 0

    def read(self, n):
        self.requested += n
        self.returned += n
        return b"0" * n


def test_endless_stream_stops_at_cap():
    s = Endless()
    r = m.count_records(s, "jsonl")
    assert r["status"] == "UNVERIFIED" and r["reason"] == "over byte cap"
    assert s.returned == m.MAX_BYTES + 1


def test_oversized_chunk_from_stream_refused():
    class Greedy:
        def read(self, n):
            return b"x" * (n + 1)
    assert m.count_records(Greedy(), "csv")["status"] == "UNVERIFIED"
    class Bad:
        def read(self, n):
            return "text"
    assert m.count_records(Bad(), "csv")["status"] == "UNVERIFIED"


def test_declared_match_mismatch_and_bad_declared():
    data = b"id\n1\n2\n"
    assert m.check_declared(io.BytesIO(data), "csv", 2)["status"] == "COUNT_MATCH"
    assert m.check_declared(io.BytesIO(data), "csv", 999)["status"] == "COUNT_MISMATCH"
    for bad in (True, "2", 2.0, -1, None):
        assert m.check_declared(io.BytesIO(data), "csv", bad)["status"] == "UNVERIFIED"
    r = m.check_declared(io.BytesIO(b"x\n"), "yaml", 1)
    assert r["status"] == "UNVERIFIED"


def test_identical_bytes_do_not_imply_count():
    data = b"id\n1\n"
    a = m.check_declared(io.BytesIO(data), "csv", 1)
    b = m.check_declared(io.BytesIO(data), "csv", 999)
    assert a["status"] == "COUNT_MATCH" and b["status"] == "COUNT_MISMATCH"


def test_artifact_path_uses_safe_file(tmp_path):
    (tmp_path / "d.jsonl").write_bytes(b'{"a":1}\n{"a":2}\n')
    assert m.check_artifact(tmp_path, "d.jsonl", "jsonl", 2)["status"] == "COUNT_MATCH"
    assert m.check_artifact(tmp_path, "d.jsonl", "jsonl", 3)["status"] == "COUNT_MISMATCH"
    (tmp_path / "link").symlink_to(tmp_path / "d.jsonl")
    for p in ("missing", "../x", "/etc/passwd", "link"):
        r = m.check_artifact(tmp_path, p, "jsonl", 2)
        assert r["status"] == "UNVERIFIED" and r["reason"].startswith("artifact unavailable")
    assert "d.jsonl" not in str(m.check_artifact(tmp_path, "d.jsonl", "jsonl", 2))


def test_oversize_file_refused_before_read(tmp_path, monkeypatch):
    from app.modules.instinct_doc import repo_evidence
    monkeypatch.setattr(repo_evidence, "MAX_FILE_BYTES", 5)
    (tmp_path / "d.json").write_bytes(b"[1,2,3,4]")
    assert m.check_artifact(tmp_path, "d.json", "json", 4)["status"] == "UNVERIFIED"


class Trickle:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def read(self, n):
        out = self.data[self.pos:self.pos + min(n, 4)]
        self.pos += len(out)
        return out


def test_cap_boundary_with_short_reads(monkeypatch):
    monkeypatch.setattr(m, "MAX_BYTES", 20)
    ok = b"[" + b"1," * 8 + b"1 ]"
    assert m.count_records(Trickle(ok), "json")["counted_records"] == 9
    r = m.count_records(Trickle(ok + b" "), "json")
    assert r["status"] == "UNVERIFIED" and r["reason"] == "over byte cap"


def test_stream_returning_more_than_requested_is_refused():
    class Over:
        def __init__(self):
            self.asked = []

        def read(self, n):
            self.asked.append(n)
            return b"1" * (n + 10)
    s = Over()
    r = m.count_records(s, "json")
    assert r["status"] == "UNVERIFIED" and r["reason"].startswith("read failed")
    assert s.asked == [m.CHUNK]


@pytest.mark.parametrize("data,fmt", [
    (b"[NaN]", "json"), (b"[Infinity]", "json"), (b"[-Infinity]", "json"),
    (b'{"a":NaN}\n', "jsonl"), (b'{"a":1}\n{"a":Infinity}\n', "jsonl"),
])
def test_nan_and_infinity_constants_refused(data, fmt):
    r = count(data, fmt)
    assert r["status"] == "UNVERIFIED" and r["counted_records"] is None
    assert r["reason"].startswith("malformed content")


def test_other_json_leniency_is_not_claimed():
    # Python json accepts duplicate keys and big ints; these still count.
    assert count(b'[{"a":1,"a":2}, 123456789012345678901234567890]', "json")["counted_records"] == 2


class Recording:
    def __init__(self, data, step):
        self.data, self.step, self.pos = data, step, 0
        self.requests, self.returned = [], 0

    def read(self, n):
        self.requests.append(n)
        out = self.data[self.pos:self.pos + min(n, self.step)]
        self.pos += len(out)
        self.returned += len(out)
        return out


def test_short_reads_summed_requests_exceed_cap_but_returned_bytes_do_not(monkeypatch):
    monkeypatch.setattr(m, "MAX_BYTES", 20)
    s = Recording(b"0" * 1000, 1)
    r = m.count_records(s, "jsonl")
    assert r["reason"] == "over byte cap"
    assert s.returned == m.MAX_BYTES + 1
    assert sum(s.requests) > m.MAX_BYTES + 1
    assert all(n <= m.MAX_BYTES + 1 for n in s.requests)
