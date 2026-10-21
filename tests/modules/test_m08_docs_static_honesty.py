"""Static-response honesty for M08 documentation generation.

Statically discovered endpoints must NOT fabricate a '200 Success' response
the generator never observed. Honest output marks each operation's response
explicitly unspecified ('default' key), labels the evidence bundle
'partial_static_inventory', and records limitations. No runtime schema or
status inference (e.g. 201 for POST) is claimed either.
"""
import io, json, zipfile
from test_m08_startup_growth import Repo, Approvals
from app.modules.m08_startup_growth.service import Service
from app.modules.m08_startup_growth.schemas import DocumentationIn

SRC = '''from fastapi import FastAPI
app = FastAPI()
@app.get("/items")
def items(): return []
@app.post("/items")
def create(): return {}
'''

def _build():
    repo = Repo(); svc = Service(repo, Approvals())
    out = svc.documentation(DocumentationIn(project_id='p', title='API',
        code_files={'api.py': SRC, 'notes.md': '# not python'}))
    with zipfile.ZipFile(io.BytesIO(repo.get(out.id).archive)) as z:
        files = {n: z.read(n) for n in z.namelist()}
    return json.loads(files['openapi.json']), json.loads(files['evidence.json'])

def test_no_fabricated_success_status_on_discovered_get():
    spec, _ = _build()
    responses = spec['paths']['/items']['get']['responses']
    assert '200' not in responses, 'statically discovered GET must not claim an unobserved 200'
    assert 'default' in responses and 'unspecified' in responses['default']['description'].lower()

def test_no_status_inference_on_discovered_post():
    spec, _ = _build()
    responses = spec['paths']['/items']['post']['responses']
    assert '200' not in responses and '201' not in responses, \
        'static discovery must not infer success statuses such as 201 for POST'
    assert 'default' in responses and 'unspecified' in responses['default']['description'].lower()

def test_evidence_labels_partial_inventory_and_limitations():
    _, evidence = _build()
    assert evidence['completeness'] == 'partial_static_inventory'
    assert any('not inspected' in w for w in evidence['limitations'])
