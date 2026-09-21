from pathlib import Path
import json
def test_generated_audit_covers_current_register():
 rows=json.loads(Path('audits/coverage-register.json').read_text())['rows']; text=Path('docs/IMPLEMENTATION_AUDIT.md').read_text()
 assert text.count('\n| ')>=len(rows)+1
 assert all(f"| {row['row']} |" in text for row in rows)
