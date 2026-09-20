import json
from uuid import uuid4

from app.modules.m17_advice_essay.schemas import AdviceSource, SourceKind
from app.modules.m17_advice_essay.sql_repository import SqlModule17Repository


class Cursor:
    def __init__(self): self.calls = []; self.rows = []
    def execute(self, query, params=None): self.calls.append((query, params))
    def fetchall(self): return self.rows
    def fetchone(self): return self.rows[0] if self.rows else None


class Connection:
    def __init__(self): self.c = Cursor(); self.commits = 0; self.rollbacks = 0
    def cursor(self): return self.c
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


def test_repository_parameterizes_owner_and_serializes_payload():
    connection = Connection(); repo = SqlModule17Repository(connection); owner = uuid4()
    source = AdviceSource(owner_id=owner, source_kind=SourceKind.USER_SUBMITTED, platform="notes", content="Write concretely.", permission_basis="owner upload")
    repo.add_source(source)
    query, params = connection.c.calls[-1]
    assert "%s" in query and str(owner) in params
    assert json.loads(params[2])["content"] == "Write concretely."
    assert connection.commits == 1


def test_reads_are_tenant_scoped():
    connection = Connection(); repo = SqlModule17Repository(connection); owner = uuid4()
    connection.c.rows = [(AdviceSource(owner_id=owner, source_kind=SourceKind.USER_SUBMITTED, platform="notes", content="Use detail.", permission_basis="owner upload").model_dump(mode="json"),)]
    result = repo.list_sources(owner)
    assert len(result) == 1
    query, params = connection.c.calls[-1]
    assert "owner_id = %s" in query
    assert params == [str(owner)]
