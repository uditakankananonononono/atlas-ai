"""Run real offline execution checks. No credentials, downloads or sends."""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.troop.roles import TemplatePlanner, ActionWorker, RuleReviewer
from app.troop.runner import TroopRunner
from app.troop.evaluation import evaluate
from app.modules.c32.psyche import tag_evidence
from app.modules.c32.teardown import teardown_sources
from app.modules.c33.channel_adaptation import adapt
from app.modules.c36.workforce import execute_blueprint
from app.modules.c37.learning_experiment import experiment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    class BrokenBaseline:
        def run(self, task):
            raise RuntimeError('deliberately failing regression baseline')
    troop = TroopRunner(TemplatePlanner(), ActionWorker(), RuleReviewer())
    cases = [{'task': {'id':'numeric', 'kind':'sum_table', 'rows':[{'x':2},{'x':3}]},
              'expected': {'totals':{'x':5}}}]
    training = [{'id':'a1','features':[0.],'label':'a'}, {'id':'a2','features':[1.],'label':'a'},
                {'id':'b1','features':[8.],'label':'b'}, {'id':'b2','features':[10.],'label':'b'}]
    heldout = [{'id':'h1','features':[0.7],'label':'a'}, {'id':'h2','features':[8.5],'label':'b'}]
    blueprint = {'id':'offline-workers','offer':'Analyze numeric observations',
                 'worker_graph':{'nodes':['researcher','analyst'],
                                 'edges':[{'from':'researcher','to':'analyst'}], 'isolated':[]}}
    workers = execute_blueprint(blueprint, {'researcher':lambda a,i,n,f:[2,3],
                                            'analyst':lambda a,i,n,f:sum(i['researcher'])})
    result = {'troop_comparison': evaluate({'atlas':troop,'deliberately_broken':BrokenBaseline()},cases),
              'psychology_cues': tag_evidence('I made a saddle. Not happy. I love learning.'),
              'brand_quotes': teardown_sources('Fixture Brand', [{'url':'https://example.invalid/fixture',
                                          'text':'Founder Jane started it. Ingredients include rose.'}]),
              'channel_drafts': adapt([{'id':'notes','title':'Field notes','text':'Our measured sum is five.',
                                       'owner_authored':True}],['x','linkedin']),
              'workforce': {'status':workers.status,'outputs':workers.outputs},
              'learning':experiment(training,heldout,model_output=root/'centroid-model.json'),
              'limits': 'Synthetic offline acceptance cases only; no vendor superiority, real image/audio inference, '
                        'breakthrough or live pitch delivery verified.'}
    (root/'results.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({'output':str(root/'results.json'), 'workforce':workers.status,
                      'heldout_accuracy':result['learning']['accuracy'],
                      'majority_baseline':result['learning']['majority_baseline_accuracy']}))


if __name__ == '__main__':
    main()
