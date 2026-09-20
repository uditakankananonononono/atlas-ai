from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m02_competition_manager.schemas import Competition,RuleSet
from app.modules.m02_competition_manager.sql_repository import SqlCompetitionRepository

def test_competition_sql_is_tenant_scoped(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'m2.db'}"); Base.metadata.create_all(engine); sessions=sessionmaker(bind=engine)
    a=SqlCompetitionRepository("a",sessions); b=SqlCompetitionRepository("b",sessions)
    item=Competition(id="c",name="Prize",official_rules_url="https://example.org/rules",rules=RuleSet(summary="s"),checklist=[])
    a.save(item)
    assert a.get("c").name == "Prize" and b.get("c") is None
