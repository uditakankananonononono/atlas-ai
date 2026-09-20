from datetime import datetime,timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m06_social_media_manager.service import ContentPlan,PlatformDraft,Platform
from app.modules.m06_social_media_manager.sql_repository import SqlSocialRepository

def test_social_sql_is_tenant_scoped(tmp_path):
 engine=create_engine(f"sqlite:///{tmp_path/'m6.db'}"); Base.metadata.create_all(engine); sessions=sessionmaker(bind=engine)
 a=SqlSocialRepository("a",sessions); b=SqlSocialRepository("b",sessions); plan=ContentPlan(id="p",brief="brief",drafts=[PlatformDraft(platform=Platform.INSTAGRAM,format="carousel",post_copy="copy")],created_at=datetime.now(timezone.utc)); a.save_plan(plan)
 assert a.get_plan("p").drafts[0].post_copy=="copy" and b.get_plan("p") is None
