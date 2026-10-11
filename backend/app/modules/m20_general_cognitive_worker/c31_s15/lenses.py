"""S1.5: explicit non-clinical thinking-strategy prompts, not disease models."""
import re
if __package__ == 'c31_s15':
    from c30_b1.chat_bind import policy as _shared_read_guard
elif __package__:
    from ..c30_b1.chat_bind import policy as _shared_read_guard
else:
    _shared_read_guard = None
from datetime import date
from types import MappingProxyType

DISCLAIMER = ('Thinking strategies only, not a diagnosis or imitation of a medical '
              'condition. These templates have no clinical validity and do not '
              'reproduce a person, disability, mood, or mind.')
DEFINITIONS = MappingProxyType({
    'pattern-first': (
        'Compare repeated patterns in {idea}. Which signals recur across cases?',
        'Find a counterexample to the strongest pattern in {idea}.',
        'Separate observed regularities from assumed causes in {idea}.',
        'Collect three comparable examples and one counterexample before choosing.'),
    'systemizing': (
        'Map inputs, outputs, constraints and feedback for {idea}.',
        'Which bottleneck limits {idea}, and how could you measure it?',
        'What local change in {idea} might create an unwanted downstream effect?',
        'Draw a dependency map and test the smallest reversible bottleneck change.'),
    'focused-depth': (
        'Choose one unresolved subproblem in {idea} and inspect it in detail.',
        'Which assumption in {idea} needs the strongest evidence?',
        'What stopping rule keeps work on {idea} from crowding out other needs?',
        'Timebox one subproblem, write the evidence, then reassess the larger goal.'),
    'reflective-depth': (
        'Consider the human cost and meaning of {idea} for the people affected.',
        'Which voices or tradeoffs are missing from the current framing of {idea}?',
        'How might a failure of {idea} change the needs of the people involved?',
        'Write two competing interpretations and ask affected people before acting.'),
    'analogy-transfer': (
        'Find a structurally similar problem in another field for {idea}.',
        'Which mechanism transfers to {idea}, and which assumptions do not?',
        'What observable test would falsify the proposed analogy for {idea}?',
        'Specify one transferred mechanism and one falsifiable test before building.'),
    'constraint-reversal': (
        'Invert a key assumption about {idea} and explore the resulting design.',
        'Which constraint on {idea} is essential and which is conventional?',
        'What fails if the inverted design for {idea} is taken literally?',
        'Compare the original and inverted designs against the same criteria.'),
})

class Refused(ValueError):
    pass

def _offline_guard(action):
    if _shared_read_guard is not None:
        return _shared_read_guard(action)
    if action != 'read':
        raise PermissionError('POLICY_REFUSED_OUTREACH')

def run(request, *, as_of, guard=_offline_guard):
    guard('read')
    if not isinstance(request, dict) or set(request) - {'idea','lenses','clinical_claim'} or not {'idea','lenses'} <= set(request):
        raise Refused('FLEET_REFUSED_SCHEMA')
    idea=request['idea']
    if not isinstance(idea,str) or not idea.strip() or len(idea)>2000:
        raise Refused('FLEET_REFUSED_IDEA')
    clinical=request.get('clinical_claim',False)
    if type(clinical) is not bool:
        raise Refused('FLEET_REFUSED_SCHEMA')
    # Plausibility guard only, not clinical intent understanding. No model exists.
    diagnostic = re.search(r'\bdiagnos\w*\b|\bdo i have\b',idea,re.I)
    imitation = re.search(r'\b(imitate|mimic|replicate|simulate)\b',idea,re.I)
    condition = re.search(r'\b(autism|autistic|depression|depressed|savant|syndrome|disorder|disease|clinical|medical|adhd)\b',idea,re.I)
    if clinical or diagnostic or (imitation and condition):
        raise Refused('FLEET_REFUSED_CLINICAL')
    keys=request['lenses']
    if not isinstance(keys,list) or not 1<=len(keys)<=len(DEFINITIONS) or not all(isinstance(k,str) and k in DEFINITIONS for k in keys) or len(set(keys))!=len(keys):
        raise Refused('FLEET_REFUSED_LENS')
    try:
        if not isinstance(as_of,str) or date.fromisoformat(as_of).isoformat()!=as_of:
            raise ValueError()
    except (ValueError,TypeError):
        raise Refused('FLEET_REFUSED_ASOF') from None
    angles=[]
    for key in keys:
        prompts=DEFINITIONS[key]
        angles.append(dict(lens=key,questions=[q.format(idea=idea.strip()) for q in prompts[:3]],next_step=prompts[3]))
    return dict(unit='S1.5',count=len(angles),angles=angles,disclaimer=DISCLAIMER,
                scope=dict(implemented='six deterministic non-clinical prompt strategies',
                           not_implemented='clinical models, diagnosis, disease imitation, autonomous action, novelty or quality guarantees',
                           data_source='supplied idea and fixed strategy definitions',as_of=as_of))
