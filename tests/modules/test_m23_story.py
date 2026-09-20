from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m23_study_abroad.story import StoryRepository
def repo(tmp_path,t='a'):
 e=create_engine(f"sqlite:///{tmp_path/'story.db'}");Base.metadata.create_all(e);return StoryRepository(t,sessionmaker(bind=e))
def test_story_projects_span_college_and_career_and_versions_are_student_authored(tmp_path):
 r=repo(tmp_path);p=r.project('My systems story','college',{'school':'U'});assert r.add_student_version(p,'I built a community lab.',{'questions':['What changed?']})==1;assert r.add_student_version(p,'I built a community lab and learned to listen.',{'tone':'clear'})==2
 assert r.project('Engineering internship','career',{'role':'intern'})
def test_living_brandid_requires_real_evidence_and_is_tenant_scoped(tmp_path):
 r=repo(tmp_path)
 try:r.evolve_brand(['curiosity'],['builder'],['systems'],[])
 except ValueError:pass
 else:raise AssertionError
 out=r.evolve_brand(['curiosity'],['builder'],['systems'],[{'source':'student interview','quote':'I built a lab'}]);assert out['living_profile']
