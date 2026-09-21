from pathlib import Path

def test_local_paired_stack_is_default_and_persistent():
 text=Path('deploy/local/docker-compose.yml').read_text()
 assert 'postgres:16-alpine' in text and 'redis:7-alpine' in text
 assert 'atlas-postgres' in text and 'atlas-redis' in text

def test_evidence_matrix_blocks_paid_cloud_claims():
 text=Path('docs/DEPLOYMENT_EVIDENCE_MATRIX.md').read_text()
 assert 'Paid Google Cloud is declined' in text
 assert 'stop rather than incur a paid upgrade' in text

def test_free_tier_doc_never_promises_availability():
 text=Path('deploy/free-tier/platforms.md').read_text()
 assert 'does not claim an account, capacity, uptime or zero cost' in text
 assert 'instead of spending' in text
