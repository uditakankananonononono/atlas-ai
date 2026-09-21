from pathlib import Path
import json,yaml
ROOT=Path(__file__).parents[2]
def test_cloud_run_manifest_is_revision_pinned_and_secret_free():
 text=(ROOT/'deploy/cloud-run/service.yaml').read_text(); doc=yaml.safe_load(text); container=doc['spec']['template']['spec']['containers'][0]
 assert '@sha256:' in container['image']; assert 'password' not in text.lower(); assert doc['kind']=='Service'
def test_ci_gate_scripts_present_workflow_permission_pending():
 assert (ROOT/'scripts/validate_config.py').exists()
 assert (ROOT/'scripts/check_migrations.py').exists()
 matrix=(ROOT/'docs/DEPLOYMENT_EVIDENCE_MATRIX.md').read_text()
 assert 'GitHub workflow permission' in matrix
def test_evidence_matrix_names_exactly_nine_blocked_scale_claims():
 text=(ROOT/'docs/DEPLOYMENT_EVIDENCE_MATRIX.md').read_text(); numbered=[line for line in text.splitlines() if line[:2] in {f'{i}.' for i in range(1,10)}]; assert len(numbered)==9
