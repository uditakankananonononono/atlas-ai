from io import BytesIO
import zipfile
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m08_startup_growth import routes, sql_repository

def test_mounted_generated_archive_contains_build_runtime(tmp_path,monkeypatch,oidc_auth_headers):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    engine=create_engine('sqlite:///'+str(tmp_path/'builds.db'))
    monkeypatch.setattr(sql_repository,'engine',engine)
    sessions=sessionmaker(bind=engine);Base.metadata.create_all(engine)
    monkeypatch.setattr(routes,'Repository',lambda tenant_id:sql_repository.Repository(tenant_id,sessions))
    app=FastAPI();app.include_router(routes.router)
    with TestClient(app) as client:
        response=client.post('/startup-growth/landing-pages',json=dict(project_id='p',product_name='Atlas',hero='Ship safely',features=['A']),headers=oidc_auth_headers('tenant-a'))
        assert response.status_code==201
    row=sql_repository.Repository('tenant-a',sessions).get(response.json()['id'])
    with zipfile.ZipFile(BytesIO(row.archive)) as z:
        assert {'package.json','app/layout.tsx','tsconfig.json','tailwind.config.ts'} <= set(z.namelist())
    engine.dispose()
