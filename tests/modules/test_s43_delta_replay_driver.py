"""Trusted-local replay driver mechanics, no historical execution claim."""
import importlib.util
from pathlib import Path
import pytest


def test_missing_audit_parent_created_and_output_not_overwritten(tmp_path,monkeypatch):
    root=Path(__file__).resolve().parents[2]
    loader=importlib.util.spec_from_file_location('driver',root/'tests/modules/s43_delta_mutations.py')
    driver=importlib.util.module_from_spec(loader);loader.loader.exec_module(driver)
    repo=tmp_path/'repo';(repo/'scripts/release').mkdir(parents=True)
    (repo/'audits/s43-delta').mkdir(parents=True)
    (repo/'audits/s43-delta/operators.json').write_text('{}')
    (repo/'scripts/release/scoped_mutations.py').write_text(
        'def execute(spec,output):\n'
        '    assert output.parent.is_dir()\n'
        '    if output.exists():raise ValueError("evidence output exists")\n'
        '    output.mkdir()\n'
        '    return {"all_caught": True}\n')
    monkeypatch.setattr(driver,'R',repo)
    output=tmp_path/'absent/audit/fresh'
    assert driver.replay(output)=={'all_caught':True}
    with pytest.raises(ValueError,match='exists'):driver.replay(output)
