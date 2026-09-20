from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m03_grant_writer.corpus import FundedAward,FundedCorpusRepository
from app.modules.m03_grant_writer.render import render_docx_pdf

def test_corpus_is_tenant_scoped_and_deduped(tmp_path):
 engine=create_engine(f"sqlite:///{tmp_path/'m3.db'}"); Base.metadata.create_all(engine); sessions=sessionmaker(bind=engine)
 a=FundedCorpusRepository("a",sessions); b=FundedCorpusRepository("b",sessions); award=FundedAward("nih_reporter","1","Cancer AI","Abstract","https://example.org/1")
 assert a.upsert([award],"ai")==1 and a.upsert([award],"ai")==0
 assert len(a.search_text("Cancer"))==1 and b.search_text("Cancer")==[]

def test_docx_pdf_renderer_creates_real_files(tmp_path):
 paths=render_docx_pdf("Proposal","ABSTRACT:\n\nEvidence based proposal text.",tmp_path)
 assert all(__import__('pathlib').Path(p).stat().st_size>100 for p in paths.values())
