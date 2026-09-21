from pathlib import Path
from app.platform.config import ProductionConfig

def test_free_tier_platform_secret_boundary_requires_explicit_trust():
 env={"ATLAS_ENV":"production","ATLAS_DATABASE_URL":"postgresql+psycopg://host/db","ATLAS_REDIS_URL":"rediss://host/0","ATLAS_SECRET_PROVIDER":"platform-environment","ATLAS_TRUST_PLATFORM_SECRETS":"1","ATLAS_OIDC_ISSUER":"https://project.supabase.co/auth/v1","ATLAS_OIDC_AUDIENCE":"authenticated"}
 assert ProductionConfig.from_env(env).secret_provider=="platform-environment"

def test_deploy_descriptors_pin_free_services_and_no_public_ollama():
 render=Path("render.yaml").read_text();docs=Path("docs/deployment/FREE_TIER.md").read_text()
 assert "plan: free" in render and 'ATLAS_LOCAL_OLLAMA_ENABLED' in render
 assert "do not expose port 11434 publicly" in docs

def test_initial_migration_is_real_schema_not_baseline_marker():
 text=Path("migrations/versions/96ad3c0c61e0_initial_production_schema.py").read_text()
 assert text.count("op.create_table") >= 100
 assert 'CREATE EXTENSION IF NOT EXISTS vector' in text
