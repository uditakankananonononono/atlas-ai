"""Real CPU diagnostic: run with PYTHONPATH=backend, not a quality benchmark."""
import json
import resource
import time
from app.modules.m09_knowledge_workspace.local_nlp import get_local_nlp
from app.modules.m09_knowledge_workspace.service import Service
start=time.perf_counter();runtime=get_local_nlp();load=time.perf_counter()-start
pairs=[('The cat sits on the mat.','The cat sits on the mat.'),
       ('The cat sits on the mat.','A kitten rests on a rug.'),
       ('The cat sits on the mat.','Database backups are scheduled every Sunday.')]
rows=[]
for a,b in pairs:
    t=time.perf_counter();score=Service._cosine(runtime.embed(a),runtime.embed(b))
    rows.append({'a':a,'b':b,'cosine':score,'passes_existing_0_78_threshold':score>=.78,
                 'inference_seconds':time.perf_counter()-t})
print(json.dumps({'embedding':runtime.identity,'entities':runtime.entity_identity,
                  'load_seconds':load,'peak_rss_kib_linux':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  'pairs':rows,'extraction':runtime.extract_entities('I visited Paris with Alice last summer.'),
                  'quality_claim':'No paraphrase accuracy claim; existing threshold unchanged.'},indent=2))
