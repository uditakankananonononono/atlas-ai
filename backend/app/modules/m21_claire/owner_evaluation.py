"""Score held-out owner decisions without claiming owner-thinking or authority."""
from pydantic import BaseModel, Field, model_validator

class DecisionCase(BaseModel):
    case_id: str = Field(min_length=1, max_length=120)
    domain: str = Field(min_length=1, max_length=80)
    choices: list[str] = Field(min_length=2, max_length=20)
    owner_choice: str = Field(min_length=1, max_length=120)
    predicted_choice: str = Field(min_length=1, max_length=120)
    source_reference: str = Field(min_length=1, max_length=240)

    @model_validator(mode='after')
    def valid_choices(self):
        if len(set(self.choices)) != len(self.choices) or any(not x.strip() or len(x) > 120 for x in self.choices):
            raise ValueError('distinct nonempty bounded choices are required')
        if self.owner_choice not in self.choices or self.predicted_choice not in self.choices:
            raise ValueError('owner and predicted choices must be offered choices')
        return self

class Evaluation(BaseModel):
    calibration_case_ids: list[str] = Field(default_factory=list, max_length=1000)
    cases: list[DecisionCase] = Field(min_length=1, max_length=1000)

    @model_validator(mode='after')
    def held_out(self):
        ids = [x.case_id for x in self.cases]
        if len(ids) != len(set(ids)) or set(ids) & set(self.calibration_case_ids):
            raise ValueError('held-out cases must be unique and disjoint from calibration')
        return self

def evaluate(data: Evaluation) -> dict:
    groups = {}
    for case in data.cases:
        group = groups.setdefault(case.domain, {'correct': 0, 'total': 0})
        group['correct'] += case.owner_choice == case.predicted_choice
        group['total'] += 1
    correct = sum(g['correct'] for g in groups.values())
    n = len(data.cases)
    # Wilson interval, not a confidence promise about future decisions.
    p, z = correct / n, 1.96
    den = 1 + z*z/n
    center = (p + z*z/(2*n)) / den
    margin = z * ((p*(1-p)/n + z*z/(4*n*n)) ** .5) / den
    return {'correct': correct, 'total': n, 'agreement': p,
            'wilson_95': [max(0, center-margin), min(1, center+margin)],
            'domains': groups, 'source_references': [c.source_reference for c in data.cases],
            'held_out_identity_claim': 'caller-attested; not independently proven',
            'owner_thinking_model_verified': False, 'external_action_permission': False}
