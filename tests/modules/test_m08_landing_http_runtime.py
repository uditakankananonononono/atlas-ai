from hashlib import sha256
from io import BytesIO
import json
import zipfile
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m08_startup_growth import routes, sql_repository
from app.modules.m08_startup_growth.runtime_service import Service


def test_mounted_landing_archive_sqlite_and_tenant_visibility(tmp_path, monkeypatch, oidc_auth_headers):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH', '0')
    monkeypatch.setenv('ATLAS_ENV', 'production')
    engine = create_engine('sqlite:///' + str(tmp_path / 'builds.db'))
    monkeypatch.setattr(sql_repository, 'engine', engine)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(routes, 'Repository', lambda tenant_id: sql_repository.Repository(tenant_id, sessions))
    assert routes.Service is Service
    app = FastAPI(); app.include_router(routes.router)
    payload = dict(project_id='p', product_name='Atlas {literal}', hero='Build <safely>', features=['A & B'])
    with TestClient(app) as client:
        assert client.post('/startup-growth/landing-pages', json=payload).status_code == 401
        response = client.post('/startup-growth/landing-pages', json=payload, headers=oidc_auth_headers('tenant-a'))
        assert response.status_code == 201
        build = response.json()
        repo = sql_repository.Repository('tenant-a', sessions)
        row = repo.get(build['id'])
        assert row is not None and row.sha256 == sha256(row.archive).hexdigest() == build['sha256']
        assert sql_repository.Repository('tenant-b', sessions).get(build['id']) is None
        with zipfile.ZipFile(BytesIO(row.archive)) as archive:
            assert 'app/layout.tsx' in archive.namelist()
            assert 'package.json' in archive.namelist()
            assert json.loads(archive.read('app/content.json'))['product_name'] == payload['product_name']
        invalid = client.post('/startup-growth/landing-pages', json=payload | {'waitlist_table': 'bad-name'}, headers=oidc_auth_headers('tenant-a'))
        assert invalid.status_code == 422
    engine.dispose()
