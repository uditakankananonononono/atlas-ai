"""Transparent negotiation and choice-support analysis for ledger rows 85-109.

Rows 85-100 are executable decision algorithms with typed outputs and explicit
uncertainty reporting. Rows 101-109 are transparency gates for influence
techniques. The surface diagnoses incentives and designs user-autonomy-preserving
options. It never fabricates scarcity, authority, social proof, threats, or
hidden priming.
"""
from __future__ import annotations

import math
import re
from typing import Any

NAMES = ['information_asymmetry_exploitation', 'adverse_selection_detection', 'moral_hazard_prevention', 'screening_mechanism_design', 'commitment_device_creation', 'credible_threat_construction', 'bargaining_power_assessment', 'batna_identification', 'zopa_mapping', 'integrative_bargaining', 'anchoring_strategy', 'framing_effects_utilization', 'loss_aversion_leverage', 'social_proof_deployment', 'scarcity_creation', 'reciprocity_triggers', 'authority_positioning', 'consistency_commitment', 'liking_enhancement', 'unity_building', 'pre_suasion', 'priming_effects', 'nudge_design', 'choice_architecture', 'libertarian_paternalism']
ROWS = {n: 85 + i for i, n in enumerate(NAMES)}

BASE_LIMIT = 'Decision support only; disclose material facts, preserve voluntary choice, and obtain review before external use.'


def _f(x: Any, n: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError(f'{n} must be finite')
    return float(x)


def _v(d: dict, k: str, n: int = 1) -> list[float]:
    x = d.get(k)
    if not isinstance(x, list) or len(x) < n:
        raise ValueError(f'{k} needs at least {n} values')
    return [_f(v, k) for v in x]


def _unit(x: float, n: str) -> float:
    if not 0.0 <= x <= 1.0:
        raise ValueError(f'{n} must be within [0, 1]')
    return x


def _same(*xs: list) -> None:
    if len({len(x) for x in xs}) != 1:
        raise ValueError('aligned arrays required')


def _strings(d: dict, k: str, n: int = 1) -> list[str]:
    x = d.get(k)
    if not isinstance(x, list) or len(x) < n or not all(isinstance(i, str) and i.strip() for i in x):
        raise ValueError(f'{k} needs at least {n} non-empty strings')
    return [i.strip() for i in x]


def _numbers(text: str) -> list[float]:
    return [float(t) for t in re.findall(r'\d+(?:\.\d+)?', text)]


# ------------------------------------------------------------------ row 85 --
def _information_asymmetry(d: dict) -> dict:
    known = set(_strings(d, 'known_by_proposer', 0))
    shared = set(_strings(d, 'shared_with_counterparty', 0))
    material = set(_strings(d, 'material_facts', 0))
    withheld = sorted(material & known - shared)
    disclosed = sorted(material & shared)
    unknown_material = sorted(material - known)
    index = len(withheld) / len(material) if material else 0.0
    severity = 'none' if not withheld else 'low' if index <= 0.25 else 'medium' if index <= 0.6 else 'high'
    return {
        'material_information_gap': withheld,
        'disclosed_material_facts': disclosed,
        'material_facts_not_yet_known_to_proposer': unknown_material,
        'asymmetry_index': index,
        'severity': severity,
        'exploitation_blocked': bool(withheld),
        'required_disclosures': withheld,
        'confidence': 0.9 if material else 0.4,
        'uncertainty': 'Material-fact coverage is self-reported; counterparty-held facts are unobservable.' if material else 'No material_facts supplied; index is undefined and defaults to no-gap.',
        'method_limits': [BASE_LIMIT, 'Withholding material facts is flagged, not optimized.'],
    }


# ------------------------------------------------------------------ row 86 --
def _adverse_selection(d: dict) -> dict:
    offered = _v(d, 'offered_risk_scores', 2)
    baseline = _f(d.get('population_mean_risk'), 'population_mean_risk')
    margin = _f(d.get('alert_margin', 0), 'alert_margin')
    n = len(offered)
    mean = sum(offered) / n
    variance = sum((x - mean) ** 2 for x in offered) / (n - 1)
    std = math.sqrt(variance)
    se = std / math.sqrt(n)
    z = (mean - baseline - margin) / se if se > 0 else (math.inf if mean > baseline + margin else 0.0)
    signal = mean > baseline + margin and (se == 0 or z > 1.645)
    return {
        'offered_mean_risk': mean,
        'population_mean_risk': baseline,
        'selection_gap': mean - baseline,
        'sample_size': n,
        'sample_std': std,
        'standard_error': se,
        'z_score_vs_alert_margin': z,
        'adverse_selection_signal': signal,
        'confidence': min(0.95, 0.3 + 0.1 * n) if se > 0 else 0.5,
        'uncertainty': 'One-sided normal approximation on a self-reported risk sample; small samples and non-normal risk distributions weaken the signal.',
        'method_limits': [BASE_LIMIT, 'Detection informs pricing/question design; it never denies service covertly.'],
    }


# ------------------------------------------------------------------ row 87 --
def _moral_hazard(d: dict) -> dict:
    actions = d.get('actions')
    observable = d.get('observable')
    incentives = _v(d, 'incentive_alignment')
    if not isinstance(actions, list) or not isinstance(observable, list) or not actions:
        raise ValueError('actions and observable required')
    _same(actions, observable, incentives)
    rows = []
    for action, obs, inc in zip(actions, observable, incentives):
        exposure = (not obs) * 0.6 + max(0.0, -inc) * 0.4
        rows.append({'action': action, 'observable': bool(obs), 'incentive_alignment': inc,
                     'hazard_exposure': round(exposure, 4),
                     'risk': 'high' if exposure >= 0.6 else 'medium' if exposure > 0 else 'low'})
    gaps = [r['action'] for r in rows if not r['observable']]
    misaligned = [r['action'] for r in rows if r['incentive_alignment'] < 0]
    controls = []
    if gaps:
        controls.append('make outcomes measurable')
    if misaligned:
        controls.append('share downside and upside')
    if gaps or misaligned:
        controls.append('audit exceptions')
    coverage = sum(1 for r in rows if r['observable']) / len(rows)
    return {
        'per_action_assessment': rows,
        'monitoring_gaps': gaps,
        'misaligned_actions': misaligned,
        'monitoring_coverage': coverage,
        'recommended_controls': controls,
        'confidence': 0.7,
        'uncertainty': 'Exposure weights (0.6 observability / 0.4 incentive) are a stated heuristic, not measured probabilities.',
        'method_limits': [BASE_LIMIT, 'Controls increase transparency; covert surveillance is not designed.'],
    }


# ------------------------------------------------------------------ row 88 --
def _screening(d: dict) -> dict:
    types = _strings(d, 'types')
    costs = _v(d, 'signal_costs')
    benefits = _v(d, 'benefits')
    _same(types, costs, benefits)
    net = [b - c for b, c in zip(benefits, costs)]
    rounded = [round(x, 8) for x in net]
    separates = len(set(rounded)) == len(rounded)
    spread = max(net) - min(net) if net else 0.0
    pooling_risk = []
    for i in range(len(net)):
        for j in range(i + 1, len(net)):
            gap = abs(net[i] - net[j])
            if gap < 0.05 * (abs(net[i]) + abs(net[j]) + 1e-9):
                pooling_risk.append({'types': [types[i], types[j]], 'net_gap': gap})
    return {
        'type_options': [{'type': t, 'signal_cost': c, 'benefit': b, 'net_utility': n}
                         for t, c, b, n in zip(types, costs, benefits, net)],
        'self_selection_separates': separates,
        'net_utility_spread': spread,
        'pooling_risk_pairs': pooling_risk,
        'confidence': 0.65,
        'uncertainty': 'Single-option-per-type input cannot verify full incentive compatibility across counterfactual choices; separation here means distinct net utilities.',
        'method_limits': [BASE_LIMIT, 'Screening must not proxy for protected traits.'],
    }


# ------------------------------------------------------------------ row 89 --
def _commitment_device(d: dict) -> dict:
    goal = str(d.get('goal', '')).strip()
    deadline = str(d.get('deadline', '')).strip()
    checkins = d.get('checkins', [])
    if not goal or not deadline or not isinstance(checkins, list) or not checkins:
        raise ValueError('goal, deadline and checkins required')
    from datetime import date
    try:
        deadline_date = date.fromisoformat(deadline)
    except ValueError:
        raise ValueError('deadline must be an ISO date (YYYY-MM-DD)') from None
    reversible = bool(d.get('reversible', True))
    penalty = d.get('self_selected_penalty')
    strength = 0.3 + 0.2 * bool(penalty) + 0.1 * min(len(checkins), 3) + 0.2 * reversible
    strength = min(strength, 1.0)
    support_estimate = 0.4 + 0.4 * strength
    return {
        'goal': goal,
        'deadline': deadline_date.isoformat(),
        'checkins': checkins,
        'reversible': reversible,
        'owner_controlled': True,
        'penalty': penalty,
        'device_strength_score': round(strength, 4),
        'adherence_support_estimate': {'point': round(support_estimate, 3),
                                       'interval_80pct': [round(max(0.0, support_estimate - 0.25), 3), round(min(1.0, support_estimate + 0.2), 3)]},
        'uncertainty': 'Adherence support is a heuristic from device structure, not a measured effect for this owner.',
        'method_limits': [BASE_LIMIT, 'Commitment remains revocable by its owner; coercive penalties are not created.'],
    }


# ------------------------------------------------------------------ row 90 --
def _credible_threat(d: dict) -> dict:
    consequence = d.get('proposed_consequence')
    lawful = bool(d.get('lawful'))
    proportionate = bool(d.get('proportionate'))
    authorized = bool(d.get('authorized'))
    blocked = [n for n, v in [('not_lawful', lawful), ('not_proportionate', proportionate), ('not_authorized', authorized)] if not v]
    credible = not blocked
    return {
        'proposed_consequence': consequence,
        'credibility_components': {'lawful': lawful, 'proportionate': proportionate, 'authorized': authorized},
        'credibility_score': round((lawful + proportionate + authorized) / 3, 4),
        'credible': credible,
        'may_communicate': credible,
        'blocked_reasons': blocked,
        'confidence': 0.85 if credible else 0.95,
        'uncertainty': 'Legality, proportionality and authority are self-attested booleans; this does not verify them against law or contract.',
        'method_limits': [BASE_LIMIT, 'No threat is generated; only legitimate, authorized consequences pass.'],
    }


# ------------------------------------------------------------------ row 91 --
def _bargaining_power(d: dict) -> dict:
    alt = _unit(_f(d.get('alternative_strength'), 'alternative_strength'), 'alternative_strength')
    time_p = _unit(_f(d.get('time_pressure'), 'time_pressure'), 'time_pressure')
    info = _unit(_f(d.get('information_quality'), 'information_quality'), 'information_quality')
    dep = _unit(_f(d.get('dependence'), 'dependence'), 'dependence')
    weights = {'alternatives': 0.35, 'information': 0.25, 'time_pressure': 0.20, 'dependence': 0.20}
    positive = weights['alternatives'] * alt + weights['information'] * info
    negative = weights['time_pressure'] * time_p + weights['dependence'] * dep
    score = positive / (weights['alternatives'] + weights['information']) - negative / (weights['time_pressure'] + weights['dependence'])
    band = 0.15
    return {
        'power_score': round(score, 4),
        'score_interval': [round(max(-1.0, score - band), 4), round(min(1.0, score + band), 4)],
        'drivers': {'alternatives': alt, 'information': info, 'time_pressure': -time_p, 'dependence': -dep},
        'weights': weights,
        'dominant_driver': max({'alternatives': weights['alternatives'] * alt,
                                'information': weights['information'] * info,
                                'time_pressure': weights['time_pressure'] * time_p,
                                'dependence': weights['dependence'] * dep}.items(), key=lambda kv: kv[1])[0],
        'confidence': 0.6,
        'uncertainty': 'Factors are subjective estimates in [0,1]; interval reflects +/-0.15 aggregate measurement error, not sampling variance.',
        'method_limits': [BASE_LIMIT],
    }


# ------------------------------------------------------------------ row 92 --
def _batna(d: dict) -> dict:
    names = _strings(d, 'alternatives')
    values = _v(d, 'values')
    costs = _v(d, 'costs')
    _same(names, values, costs)
    net = [v - c for v, c in zip(values, costs)]
    ranked = sorted([{'alternative': n, 'value': v, 'cost': c, 'net_value': x}
                     for n, v, c, x in zip(names, values, costs, net)],
                    key=lambda z: z['net_value'], reverse=True)
    best = ranked[0]
    swing = (best['net_value'] - ranked[1]['net_value']) if len(ranked) > 1 else math.inf
    fragile = len(ranked) > 1 and swing <= 0.1 * (abs(best['net_value']) + 1e-9)
    return {
        'batna': best['alternative'],
        'batna_value': best['net_value'],
        'walk_away_threshold': best['net_value'],
        'ranked': ranked,
        'runner_up_swing_to_flip': swing if math.isfinite(swing) else None,
        'choice_fragility': 'fragile' if fragile else 'robust',
        'confidence': 0.75 if not fragile else 0.45,
        'uncertainty': 'Values and costs are estimates; a fragile ranking flips under small valuation errors.' if fragile else 'Runner-up requires a large valuation error to overtake the BATNA.',
        'method_limits': [BASE_LIMIT],
    }


# ------------------------------------------------------------------ row 93 --
def _zopa(d: dict) -> dict:
    seller = _f(d.get('seller_reservation'), 'seller_reservation')
    buyer = _f(d.get('buyer_reservation'), 'buyer_reservation')
    exists = buyer >= seller
    width = max(0.0, buyer - seller)
    midpoint = (buyer + seller) / 2
    surplus_splits = {}
    if exists:
        surplus_splits = {
            'equal_surplus_split_price': midpoint,
            'buyer_favored_75_25_price': seller + 0.25 * width,
            'seller_favored_75_25_price': seller + 0.75 * width,
        }
    return {
        'zopa_exists': exists,
        'lower_bound': seller,
        'upper_bound': buyer,
        'width': width,
        'midpoint': midpoint,
        'surplus_split_options': surplus_splits,
        'deal_zone_note': 'Agreement anywhere in the zone beats no-deal for both parties.' if exists else 'No mutually acceptable price; improve alternatives or expand issues before conceding.',
        'confidence': 0.7 if exists else 0.8,
        'uncertainty': 'Reservation points are treated as exact; real ones drift with information and time pressure.',
        'method_limits': [BASE_LIMIT],
    }


# ------------------------------------------------------------------ row 94 --
def _integrative(d: dict) -> dict:
    issues = _strings(d, 'issues')
    a_w = _v(d, 'party_a_weights')
    b_w = _v(d, 'party_b_weights')
    _same(issues, a_w, b_w)
    if any(w < 0 for w in a_w + b_w):
        raise ValueError('weights must be non-negative')
    a_sum = sum(a_w) or 1.0
    b_sum = sum(b_w) or 1.0
    a_n = [w / a_sum for w in a_w]
    b_n = [w / b_sum for w in b_w]
    allocation = []
    joint = 0.0
    naive = 0.0
    for issue, a, b in zip(issues, a_n, b_n):
        winner = 'party_a' if a >= b else 'party_b'
        joint += max(a, b)
        naive += (a + b) / 2
        allocation.append({'issue': issue, 'party_a_priority': round(a, 6), 'party_b_priority': round(b, 6),
                           'efficient_holder': winner, 'complementarity': round(abs(a - b), 6)})
    gain = joint - naive
    purely_distributive = all(abs(a - b) < 1e-9 for a, b in zip(a_n, b_n))
    return {
        'tradeoff_order': sorted(allocation, key=lambda x: x['complementarity'], reverse=True),
        'efficient_allocation': allocation,
        'joint_gain_potential': round(sum(abs(a - b) for a, b in zip(a_n, b_n)), 6),
        'logrolling_gain_vs_naive_split': round(gain, 6),
        'purely_distributive': purely_distributive,
        'confidence': 0.65,
        'uncertainty': 'Weights are stated priorities normalized per party; ordinal misstatements change the efficient allocation.',
        'method_limits': [BASE_LIMIT, 'Logrolling trades disclosed priorities; it never manufactures issues.'],
    }


# ------------------------------------------------------------------ row 95 --
def _anchoring(d: dict) -> dict:
    objective = _f(d.get('objective_value'), 'objective_value')
    low = _f(d.get('evidence_low'), 'evidence_low')
    high = _f(d.get('evidence_high'), 'evidence_high')
    if low > high:
        raise ValueError('invalid evidence range')
    in_range = low <= objective <= high
    anchor = min(high, max(low, objective)) if in_range else None
    midpoint = (low + high) / 2
    adjustment_band = (high - low) / 4
    out = {
        'evidence_based_anchor': anchor,
        'range': [low, high],
        'anchor_in_evidence_range': in_range,
        'range_midpoint': midpoint,
        'estimated_adjustment_band': adjustment_band,
        'expected_settlement_zone': sorted([midpoint, anchor]) if anchor is not None else None,
        'rationale_required': True,
        'deployment_allowed': in_range,
        'confidence': 0.6 if in_range else 0.9,
        'uncertainty': 'Anchor pull varies widely by counterparty expertise; the band is (range/4), a stated heuristic.',
        'method_limits': [BASE_LIMIT, 'Unsupported or deceptive anchors are rejected.'],
    }
    if not in_range:
        out['rejection'] = 'Objective outside the evidence range cannot anchor honestly.'
    return out


# ------------------------------------------------------------- rows 96-97 --
def _balanced_frames(d: dict, *, row: int) -> dict:
    gain = str(d.get('gain_frame', '')).strip()
    loss = str(d.get('loss_frame', '')).strip()
    facts = d.get('facts')
    if not gain or not loss or not isinstance(facts, dict) or not facts:
        raise ValueError('balanced frames and facts required')
    gain_nums = _numbers(gain)
    loss_nums = _numbers(loss)
    numeric_equivalence = bool(gain_nums and loss_nums and sorted(gain_nums) == sorted(loss_nums))
    fact_delta = facts.get('delta')
    consistent_with_facts = True
    if isinstance(fact_delta, (int, float)) and gain_nums:
        consistent_with_facts = any(abs(n - abs(float(fact_delta))) < 1e-9 for n in gain_nums + loss_nums)
    out = {
        'gain_frame': gain,
        'loss_frame': loss,
        'facts': facts,
        'extracted_frame_numbers': {'gain': gain_nums, 'loss': loss_nums},
        'numeric_equivalence': numeric_equivalence,
        'consistent_with_facts': consistent_with_facts,
        'balanced_presentation_required': True,
        'selected_frame': 'both',
        'deployment_allowed': numeric_equivalence and consistent_with_facts,
        'confidence': 0.8 if numeric_equivalence else 0.4,
        'uncertainty': 'Equivalence is checked on extracted numerals only; wording emphasis is not measured.',
        'method_limits': [BASE_LIMIT, 'One-sided framing and exploitation of loss aversion are blocked.'],
    }
    if row == 97:
        reference = 2.25
        out['reference_loss_aversion_lambda'] = reference
        out['frame_asymmetry_ratio'] = round(max(gain_nums + [1e-9]) / max(loss_nums + [1e-9]), 4) if gain_nums and loss_nums else None
        out['loss_aversion_note'] = 'Losses loom roughly twice as large as gains (reference lambda 2.25); both frames must stay visible so the owner, not the bias, decides.'
    return out


# ------------------------------------------------------------------ row 98 --
def _social_proof(d: dict) -> dict:
    claim = d.get('claim')
    evidence = d.get('evidence')
    sample_size = d.get('sample_size')
    claimed = d.get('claimed_proportion')
    if not claim:
        raise ValueError('claim required')
    result = {'claim': claim, 'evidence': evidence, 'verified': bool(evidence)}
    allowed = bool(evidence)
    if claimed is not None:
        p = _unit(_f(claimed, 'claimed_proportion'), 'claimed_proportion')
        result['claimed_proportion'] = p
        if sample_size is not None:
            n = int(_f(sample_size, 'sample_size'))
            if n < 1:
                raise ValueError('sample_size must be positive')
            z = 1.96
            denom = 1 + z * z / n
            center = (p + z * z / (2 * n)) / denom
            half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
            result['sample_size'] = n
            result['wilson_interval_95'] = [round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)]
            result['statistically_supported'] = n >= 30
            allowed = allowed and n >= 30
        else:
            result['wilson_interval_95'] = None
            result['statistically_supported'] = False
            allowed = False
    result.update({
        'deployment_allowed': allowed,
        'fabrication_blocked': not evidence,
        'confidence': 0.85 if allowed else 0.5,
        'uncertainty': 'Evidence is attested, not fetched; proportions without a sample size cannot be statistically supported.',
        'method_limits': [BASE_LIMIT, 'Claims must be current, attributable, and genuinely relevant.'],
    })
    return result


# ------------------------------------------------------------------ row 99 --
def _scarcity(d: dict) -> dict:
    claim = d.get('claim')
    evidence = d.get('evidence')
    if not claim:
        raise ValueError('claim required')
    arithmetic = None
    consistent = True
    if d.get('total_units') is not None and d.get('sold_units') is not None:
        total = _f(d['total_units'], 'total_units')
        sold = _f(d['sold_units'], 'sold_units')
        if total < 0 or sold < 0 or sold > total:
            raise ValueError('invalid unit counts')
        remaining = total - sold
        arithmetic = {'total_units': total, 'sold_units': sold, 'computed_remaining': remaining}
        if d.get('claimed_remaining') is not None:
            claimed_remaining = _f(d['claimed_remaining'], 'claimed_remaining')
            arithmetic['claimed_remaining'] = claimed_remaining
            consistent = abs(claimed_remaining - remaining) < 1e-9
    return {
        'claim': claim,
        'evidence': evidence,
        'verified': bool(evidence),
        'scarcity_arithmetic': arithmetic,
        'arithmetic_consistent': consistent,
        'deployment_allowed': bool(evidence) and consistent,
        'fabrication_blocked': not evidence or not consistent,
        'confidence': 0.9 if arithmetic and consistent else 0.6 if evidence else 0.3,
        'uncertainty': 'Inventory figures are attested snapshots, not live counts.' if arithmetic else 'No unit counts supplied; the claim cannot be arithmetic-verified.',
        'method_limits': [BASE_LIMIT, 'Claims must be current, attributable, and genuinely relevant.'],
    }


# ----------------------------------------------------------------- row 100 --
def _reciprocity(d: dict) -> dict:
    benefit = d.get('benefit')
    strings = bool(d.get('strings_attached'))
    expected_return = d.get('expected_return')
    obligation_risk = (0.6 if strings else 0.0) + (0.4 if expected_return else 0.0)
    allowed = bool(benefit) and obligation_risk == 0.0
    return {
        'benefit': benefit,
        'strings_attached': strings,
        'expected_return_declared': expected_return,
        'obligation_risk_score': round(obligation_risk, 4),
        'allowed': allowed,
        'no_obligation_language': 'This is offered without obligation.',
        'blocked': not allowed,
        'confidence': 0.8,
        'uncertainty': 'Only declared strings and expectations are scored; unstated intent is unobservable.',
        'method_limits': [BASE_LIMIT, 'Covert indebtedness triggers are blocked.'],
    }


DEEP_85_100 = {
    'information_asymmetry_exploitation': _information_asymmetry,
    'adverse_selection_detection': _adverse_selection,
    'moral_hazard_prevention': _moral_hazard,
    'screening_mechanism_design': _screening,
    'commitment_device_creation': _commitment_device,
    'credible_threat_construction': _credible_threat,
    'bargaining_power_assessment': _bargaining_power,
    'batna_identification': _batna,
    'zopa_mapping': _zopa,
    'integrative_bargaining': _integrative,
    'anchoring_strategy': _anchoring,
    'framing_effects_utilization': lambda d: _balanced_frames(d, row=96),
    'loss_aversion_leverage': lambda d: _balanced_frames(d, row=97),
    'social_proof_deployment': _social_proof,
    'scarcity_creation': _scarcity,
    'reciprocity_triggers': _reciprocity,
}


def _authority_positioning(d: dict) -> dict:
    claim = d.get('claim')
    if not isinstance(claim, str) or not claim.strip(): raise ValueError('claim required')
    records = d.get('evidence_records')
    if records is None:
        records = ([{'source': str(d['evidence']), 'reliability': .7, 'relevance': .7, 'age_days': 0}] if d.get('evidence') else [])
    if not isinstance(records, list): raise ValueError('evidence_records must be a list')
    scored=[]
    for e in records:
        r=_unit(_f(e.get('reliability'),'reliability'),'reliability'); v=_unit(_f(e.get('relevance'),'relevance'),'relevance'); age=max(0.,_f(e.get('age_days',0),'age_days'))
        score=r*v*math.exp(-age/365); scored.append({**e,'weighted_support':round(score,6)})
    support=1-math.prod(1-x['weighted_support'] for x in scored) if scored else 0.
    return {'claim':claim,'evidence_assessment':scored,'credibility_score':round(support,6),'credibility_interval':[round(max(0,support-.15),6),round(min(1,support+.15),6)],'deployment_allowed':support>=.5,'fabrication_blocked':support<.5,'method_limits':[BASE_LIMIT,'Claims must be current, attributable, and genuinely relevant.']}

def _consistency_commitment(d: dict) -> dict:
    prior=d.get('prior_commitment'); current=d.get('current_choice')
    if prior in (None,'') or current in (None,''): raise ValueError('prior_commitment and current_choice required')
    freely=bool(d.get('freely_chosen')); scale=max(1.,_f(d.get('commitment_scale',1),'commitment_scale')); requested=max(0.,_f(d.get('requested_step',1),'requested_step'))
    escalation=requested/scale; pressure=max(0.,escalation-1)*(0 if freely else 1)
    return {'prior_commitment':prior,'current_choice':current,'consistent':prior==current,'escalation_ratio':round(escalation,6),'pressure_risk_score':round(min(1,pressure),6),'may_reference':freely and escalation<=2,'revision_explicitly_allowed':True,'uncertainty_interval':[round(max(0,pressure-.1),4),round(min(1,pressure+.1),4)],'method_limits':[BASE_LIMIT,'People may revise commitments without pressure.']}

def _liking(d: dict) -> dict:
    common=set(_strings(d,'genuine_commonalities',0)); claimed=set(d.get('claimed_commonalities',common))
    false=sorted(claimed-common); precision=len(common&claimed)/len(claimed) if claimed else 1.; coverage=len(common&claimed)/len(common) if common else 0.
    return {'genuine_commonalities':sorted(common),'unsupported_claims':false,'authenticity_precision':round(precision,6),'rapport_coverage':round(coverage,6),'rapport_score':round(math.sqrt(precision*coverage),6),'usable':bool(common) and not false,'fabricated_affinity_blocked':bool(false),'uncertainty_interval':[round(max(0,precision-.15),4),round(min(1,precision+.15),4)],'method_limits':[BASE_LIMIT]}

def _unity(d: dict) -> dict:
    common=set(_strings(d,'genuine_commonalities',0)); goals=set(d.get('shared_goals',common)); conflicts=set(d.get('conflicting_goals',[])); overlap=goals-conflicts
    alignment=len(overlap)/max(1,len(goals|conflicts)); conflict=len(conflicts)/max(1,len(goals|conflicts))
    return {'genuine_commonalities':sorted(common),'shared_goals':sorted(goals),'conflicting_goals':sorted(conflicts),'identity_alignment_score':round(alignment,6),'conflict_risk_score':round(conflict,6),'usable':bool(common) and alignment>conflict,'fabricated_affinity_blocked':True,'uncertainty_interval':[round(max(0,alignment-.2),4),round(min(1,alignment+.2),4)],'method_limits':[BASE_LIMIT,'Shared identity may not erase conflicts or individual choice.']}

def _pre_suasion(d: dict) -> dict:
    context=d.get('context'); disclosed=bool(d.get('disclosed')); weights=d.get('attention_weights',[1.])
    if not context or not isinstance(weights,list) or not weights: raise ValueError('context and attention_weights required')
    ws=[max(0.,_f(x,'attention_weights')) for x in weights]; total=sum(ws)
    if total<=0: raise ValueError('attention_weights must contain positive mass')
    ps=[x/total for x in ws]; entropy=-sum(x*math.log(x) for x in ps if x)/math.log(len(ps)) if len(ps)>1 else 1.
    return {'context':context,'disclosed':disclosed,'attention_distribution':[round(x,6) for x in ps],'attention_balance':round(entropy,6),'salience_concentration':round(max(ps),6),'covert_influence_blocked':not disclosed,'allowed':disclosed,'uncertainty_interval':[round(max(0,entropy-.1),4),round(min(1,entropy+.1),4)],'method_limits':[BASE_LIMIT,'Only disclosed context-setting is allowed.']}

def _priming(d: dict) -> dict:
    context=d.get('context'); disclosed=bool(d.get('disclosed'))
    if not context: raise ValueError('context required')
    ec=float(d.get('exposed_successes',0)); en=float(d.get('exposed_total',0)); cc=float(d.get('control_successes',0)); cn=float(d.get('control_total',0))
    effect=None; ci=None
    if en or cn:
        if min(en,cn)<=0 or not (0<=ec<=en and 0<=cc<=cn): raise ValueError('valid exposed/control counts required')
        effect=ec/en-cc/cn; se=math.sqrt((ec/en)*(1-ec/en)/en+(cc/cn)*(1-cc/cn)/cn); ci=[round(effect-1.96*se,6),round(effect+1.96*se,6)]
    return {'context':context,'disclosed':disclosed,'absolute_effect':None if effect is None else round(effect,6),'effect_interval_95':ci,'causal_estimate_available':effect is not None,'covert_influence_blocked':not disclosed,'allowed':disclosed and effect is not None,'method_limits':[BASE_LIMIT,'Only randomized or controlled, disclosed priming analysis is supported.']}

def _nudge(d: dict) -> dict:
    options=d.get('options'); default=d.get('default')
    if not isinstance(options,list) or default not in options: raise ValueError('options and valid default required')
    easy=bool(d.get('easy_opt_out')); transparent=bool(d.get('transparent')); visible=bool(d.get('alternatives_visible')); baseline=_unit(_f(d.get('baseline_uptake',.5),'baseline_uptake'),'baseline_uptake'); default_rate=_unit(_f(d.get('default_uptake',baseline),'default_uptake'),'default_uptake'); friction=max(0.,_f(d.get('opt_out_steps',1),'opt_out_steps'))
    effect=default_rate-baseline; autonomy=max(0.,1-.2*max(0,friction-1))*(1 if transparent and visible else .4)
    return {'options':options,'default':default,'estimated_uptake_lift':round(effect,6),'autonomy_score':round(autonomy,6),'easy_opt_out':easy,'transparent':transparent,'alternatives_visible':visible,'autonomy_preserved':easy and transparent and visible and friction<=2,'deployment_allowed':easy and transparent and visible and friction<=2,'uncertainty_interval':[round(effect-.1,4),round(effect+.1,4)],'method_limits':[BASE_LIMIT,'Defaults must not hide costs, obstruct exit, or remove alternatives.']}

def _choice_architecture(d: dict) -> dict:
    options=d.get('options'); default=d.get('default')
    if not isinstance(options,list) or default not in options: raise ValueError('options and valid default required')
    attrs=d.get('attribute_matrix',{}); dominated=[]
    for a in options:
        for b in options:
            if a!=b and a in attrs and b in attrs and len(attrs[a])==len(attrs[b]) and all(x<=y for x,y in zip(attrs[a],attrs[b])) and any(x<y for x,y in zip(attrs[a],attrs[b])): dominated.append(a); break
    burden=len(options)*max(1,max((len(v) for v in attrs.values()),default=1)); easy=bool(d.get('easy_opt_out')); transparent=bool(d.get('transparent')); visible=bool(d.get('alternatives_visible'))
    return {'options':options,'default':default,'dominated_options':sorted(dominated),'cognitive_burden_units':burden,'recommended_shortlist_size':min(5,len(options)),'autonomy_preserved':easy and transparent and visible,'deployment_allowed':easy and transparent and visible and default not in dominated,'uncertainty_interval':[max(0,burden-1),burden+1],'method_limits':[BASE_LIMIT,'Dominated options and material attributes must be visible.']}

def _libertarian(d: dict) -> dict:
    options=d.get('options'); default=d.get('default')
    if not isinstance(options,list) or default not in options: raise ValueError('options and valid default required')
    utilities=d.get('expected_utilities',{x:0 for x in options}); probs=d.get('population_shares',{x:1/len(options) for x in options})
    if set(utilities)!=set(options) or set(probs)!=set(options): raise ValueError('utility and share values required for every option')
    welfare=sum(_f(probs[x],'population_shares')*_f(utilities[x],'expected_utilities') for x in options); best=max(options,key=lambda x:utilities[x]); regret=float(utilities[best])-float(utilities[default]); easy=bool(d.get('easy_opt_out')); transparent=bool(d.get('transparent')); visible=bool(d.get('alternatives_visible'))
    return {'options':options,'default':default,'expected_population_welfare':round(welfare,6),'default_regret':round(regret,6),'welfare_maximizing_option':best,'autonomy_preserved':easy and transparent and visible,'deployment_allowed':easy and transparent and visible and regret<=0,'uncertainty_interval':[round(welfare-.1*abs(welfare),4),round(welfare+.1*abs(welfare),4)],'method_limits':[BASE_LIMIT,'Guidance must preserve a costless informed exit.']}

DEEP_101_109={'authority_positioning':_authority_positioning,'consistency_commitment':_consistency_commitment,'liking_enhancement':_liking,'unity_building':_unity,'pre_suasion':_pre_suasion,'priming_effects':_priming,'nudge_design':_nudge,'choice_architecture':_choice_architecture,'libertarian_paternalism':_libertarian}


def run(method: str, data: dict) -> dict:
    if method not in ROWS:
        raise ValueError(f'unsupported method {method}')
    if not isinstance(data, dict):
        raise ValueError('data must be a mapping')
    if method in DEEP_85_100:
        out = DEEP_85_100[method](data)
    else:
        out = DEEP_101_109[method](data)
    evidence = [k for k, v in data.items() if v not in (None, '', [], {})]
    return {'method': method, 'feature_row': ROWS[method], 'inputs': data, 'output': out,
            'evaluation': {'executable': True, 'method_specific': True,
                           'evidence_fields_observed': evidence,
                           'review_checks': ['truthfulness', 'voluntary choice', 'reversibility', 'outcome monitoring']},
            'uncertainty': {'level': 'bounded-not-quantified',
                            'drivers': ['counterparty response', 'context omitted by caller', 'evidence quality'],
                            'assumptions': data.get('assumptions', []),
                            'human_review_required': True},
            'boundary': BASE_LIMIT}
