"""Error-coding repair pins for learning_reasoning_810_859 (rows 813/841/846 + resource_refs).

SOURCE repair (module), tests added here. Golden results captured from the
pre-repair module at base 94fe792d; valid-input outputs must stay byte-identical.
"""
import json
import pytest
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import (
    execute, LearningReasoningError)

BASE = {'tenant_id': 't', 'objective': 'learn algebra', 'problem': 'p',
        'source': {'title': 't', 'url': 'https://x'}}
EXPL = {'explanation_target': 'q', 'explanation_facts': [{'atom': 'q', 'source': 's'}],
        'explanation_rules': [{'id': 'r1', 'if': ['q'], 'then': 'p', 'source': 's'}]}
SCHED = {'items': [{'id': 'i1', 'evidence_id': 'e1', 'quality': 4,
                    'reviewed_at': '2026-10-01T00:00:00+00:00'}]}

GOLDENS = json.loads(r'''{
 "813_0": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Elaborative Interrogation",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "learning",
  "result": {
   "explanation_practice": {
    "attempt_results": [],
    "boundary": "Finite positive Horn structured explanation and counterfactual fact-deletion checks only; exact rule/premise/ordered-step validation, not free-text semantics or learner understanding. Source records are supplied premises, not verified truth.",
    "condition_checks": [
     {
      "removed_fact": "q",
      "target_still_entailed": false
     }
    ],
    "derivation": [],
    "derived_atoms": [
     "p",
     "q"
    ],
    "fact_provenance": [
     {
      "atom": "q",
      "source": "s"
     }
    ],
    "learner_understanding": null,
    "source_truth_verified": false,
    "status": "practice_ready",
    "target_entailed": true,
    "task": {
     "condition_question": "Which supplied fact removals prevent deriving q?",
     "mode": "elaborative_interrogation",
     "question": "Which supplied rules and prerequisite facts justify q?",
     "target": "q"
    }
   },
   "feedback_is_actionable": true,
   "learner_control": true,
   "objective": "learn algebra",
   "prompts": [
    "Why is learn algebra true, and under what conditions?"
   ]
  },
  "row_id": 813,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "813_1": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Elaborative Interrogation",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "learning",
  "result": {
   "explanation_practice": {
    "attempt_results": [],
    "boundary": "Finite positive Horn structured explanation and counterfactual fact-deletion checks only; exact rule/premise/ordered-step validation, not free-text semantics or learner understanding. Source records are supplied premises, not verified truth.",
    "condition_checks": [
     {
      "removed_fact": "q",
      "target_still_entailed": false
     }
    ],
    "derivation": [],
    "derived_atoms": [
     "p",
     "q"
    ],
    "fact_provenance": [
     {
      "atom": "q",
      "source": "s"
     }
    ],
    "learner_understanding": null,
    "source_truth_verified": false,
    "status": "practice_ready",
    "target_entailed": true,
    "task": {
     "condition_question": "Which supplied fact removals prevent deriving q?",
     "mode": "elaborative_interrogation",
     "question": "Which supplied rules and prerequisite facts justify q?",
     "target": "q"
    }
   },
   "feedback_is_actionable": true,
   "learner_control": true,
   "objective": "learn algebra",
   "prompts": [
    "Why is claim one true, and under what conditions?",
    "Why is claim two true, and under what conditions?"
   ]
  },
  "row_id": 813,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "813_2": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Elaborative Interrogation",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "learning",
  "result": {
   "explanation_practice": {
    "attempt_results": [],
    "boundary": "Finite positive Horn structured explanation and counterfactual fact-deletion checks only; exact rule/premise/ordered-step validation, not free-text semantics or learner understanding. Source records are supplied premises, not verified truth.",
    "condition_checks": [
     {
      "removed_fact": "q",
      "target_still_entailed": false
     }
    ],
    "derivation": [],
    "derived_atoms": [
     "p",
     "q"
    ],
    "fact_provenance": [
     {
      "atom": "q",
      "source": "s"
     }
    ],
    "learner_understanding": null,
    "source_truth_verified": false,
    "status": "practice_ready",
    "target_entailed": true,
    "task": {
     "condition_question": "Which supplied fact removals prevent deriving q?",
     "mode": "elaborative_interrogation",
     "question": "Which supplied rules and prerequisite facts justify q?",
     "target": "q"
    }
   },
   "feedback_is_actionable": true,
   "learner_control": true,
   "objective": "learn algebra",
   "prompts": [
    "Why is 1 true, and under what conditions?",
    "Why is 2.5 true, and under what conditions?"
   ]
  },
  "row_id": 813,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "813_3": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Elaborative Interrogation",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "learning",
  "result": {
   "explanation_practice": {
    "attempt_results": [],
    "boundary": "Finite positive Horn structured explanation and counterfactual fact-deletion checks only; exact rule/premise/ordered-step validation, not free-text semantics or learner understanding. Source records are supplied premises, not verified truth.",
    "condition_checks": [
     {
      "removed_fact": "q",
      "target_still_entailed": false
     }
    ],
    "derivation": [],
    "derived_atoms": [
     "p",
     "q"
    ],
    "fact_provenance": [
     {
      "atom": "q",
      "source": "s"
     }
    ],
    "learner_understanding": null,
    "source_truth_verified": false,
    "status": "practice_ready",
    "target_entailed": true,
    "task": {
     "condition_question": "Which supplied fact removals prevent deriving q?",
     "mode": "elaborative_interrogation",
     "question": "Which supplied rules and prerequisite facts justify q?",
     "target": "q"
    }
   },
   "feedback_is_actionable": true,
   "learner_control": true,
   "objective": "learn algebra",
   "prompts": [
    "Why is {'k': 1} true, and under what conditions?"
   ]
  },
  "row_id": 813,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "813_4": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Elaborative Interrogation",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "learning",
  "result": {
   "explanation_practice": {
    "attempt_results": [],
    "boundary": "Finite positive Horn structured explanation and counterfactual fact-deletion checks only; exact rule/premise/ordered-step validation, not free-text semantics or learner understanding. Source records are supplied premises, not verified truth.",
    "condition_checks": [
     {
      "removed_fact": "q",
      "target_still_entailed": false
     }
    ],
    "derivation": [],
    "derived_atoms": [
     "p",
     "q"
    ],
    "fact_provenance": [
     {
      "atom": "q",
      "source": "s"
     }
    ],
    "learner_understanding": null,
    "source_truth_verified": false,
    "status": "practice_ready",
    "target_entailed": true,
    "task": {
     "condition_question": "Which supplied fact removals prevent deriving q?",
     "mode": "elaborative_interrogation",
     "question": "Which supplied rules and prerequisite facts justify q?",
     "target": "q"
    }
   },
   "feedback_is_actionable": true,
   "learner_control": true,
   "objective": "learn algebra",
   "prompts": [
    "Why is a true, and under what conditions?",
    "Why is b true, and under what conditions?"
   ]
  },
  "row_id": 813,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "841_0": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Quantitative Reasoning",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "reasoning",
  "result": {
   "assumptions": [],
   "conclusion_status": "candidate until checked",
   "premises": [],
   "quantitative": {
    "count": 3,
    "mean": 2.0,
    "range": 2.0,
    "significant_digits_not_invented": true,
    "sum": 6.0,
    "units": null
   },
   "uncertainties": []
  },
  "row_id": 841,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "841_1": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Quantitative Reasoning",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "reasoning",
  "result": {
   "assumptions": [],
   "conclusion_status": "candidate until checked",
   "premises": [],
   "quantitative": {
    "count": 3,
    "mean": 0.5,
    "range": 3.5,
    "significant_digits_not_invented": true,
    "sum": 1.5,
    "units": null
   },
   "uncertainties": []
  },
  "row_id": 841,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "841_2": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Quantitative Reasoning",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "reasoning",
  "result": {
   "assumptions": [],
   "conclusion_status": "candidate until checked",
   "premises": [],
   "quantitative": {
    "count": 2,
    "mean": 51.25,
    "range": 97.5,
    "significant_digits_not_invented": true,
    "sum": 102.5,
    "units": null
   },
   "uncertainties": []
  },
  "row_id": 841,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "841_3": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Quantitative Reasoning",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "reasoning",
  "result": {
   "assumptions": [],
   "conclusion_status": "candidate until checked",
   "premises": [],
   "quantitative": {
    "count": 2,
    "mean": 0.5,
    "range": 1.0,
    "significant_digits_not_invented": true,
    "sum": 1.0,
    "units": null
   },
   "uncertainties": []
  },
  "row_id": 841,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "841_4": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Quantitative Reasoning",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "reasoning",
  "result": {
   "assumptions": [],
   "conclusion_status": "candidate until checked",
   "premises": [],
   "quantitative": {
    "count": 1,
    "mean": 0.0,
    "range": 0.0,
    "significant_digits_not_invented": true,
    "sum": 0.0,
    "units": null
   },
   "uncertainties": []
  },
  "row_id": 841,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "846_0": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Probabilistic Reasoning",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "reasoning",
  "result": {
   "assumptions": [],
   "bayes": {
    "assumptions_verified": false,
    "likelihoods": [
     0.5,
     0.5
    ],
    "posterior": 0.5,
    "prior": 0.5,
    "real_world_truth_verified": false,
    "status": "supplied_probability_bayes_calculation"
   },
   "conclusion_status": "candidate until checked",
   "premises": [],
   "uncertainties": []
  },
  "row_id": 846,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "846_1": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Probabilistic Reasoning",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "reasoning",
  "result": {
   "assumptions": [],
   "bayes": {
    "assumptions_verified": false,
    "likelihoods": [
     0.5,
     0.5
    ],
    "posterior": 0.3,
    "prior": 0.3,
    "real_world_truth_verified": false,
    "status": "supplied_probability_bayes_calculation"
   },
   "conclusion_status": "candidate until checked",
   "premises": [],
   "uncertainties": []
  },
  "row_id": 846,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "846_2": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Probabilistic Reasoning",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "reasoning",
  "result": {
   "assumptions": [],
   "bayes": {
    "assumptions_verified": false,
    "likelihoods": [
     0.9,
     0.1
    ],
    "posterior": 0.7941176470588235,
    "prior": 0.3,
    "real_world_truth_verified": false,
    "status": "supplied_probability_bayes_calculation"
   },
   "conclusion_status": "candidate until checked",
   "premises": [],
   "uncertainties": []
  },
  "row_id": 846,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "846_3": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Probabilistic Reasoning",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "reasoning",
  "result": {
   "assumptions": [],
   "bayes": {
    "assumptions_verified": false,
    "likelihoods": [
     0.5,
     0.25
    ],
    "posterior": 0.6666666666666666,
    "prior": 0.5,
    "real_world_truth_verified": false,
    "status": "supplied_probability_bayes_calculation"
   },
   "conclusion_status": "candidate until checked",
   "premises": [],
   "uncertainties": []
  },
  "row_id": 846,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "846_4": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Probabilistic Reasoning",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "reasoning",
  "result": {
   "assumptions": [],
   "bayes": {
    "assumptions_verified": false,
    "likelihoods": [
     1.0,
     0.0
    ],
    "posterior": 1.0,
    "prior": 1.0,
    "real_world_truth_verified": false,
    "status": "supplied_probability_bayes_calculation"
   },
   "conclusion_status": "candidate until checked",
   "premises": [],
   "uncertainties": []
  },
  "row_id": 846,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "846_5": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Probabilistic Reasoning",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "reasoning",
  "result": {
   "assumptions": [],
   "bayes": {
    "assumptions_verified": false,
    "likelihoods": [
     1.0,
     0.0
    ],
    "posterior": 1.0,
    "prior": 1.0,
    "real_world_truth_verified": false,
    "status": "supplied_probability_bayes_calculation"
   },
   "conclusion_status": "candidate until checked",
   "premises": [],
   "uncertainties": []
  },
  "row_id": 846,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "refs_0": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Spaced Repetition",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "learning",
  "result": {
   "algorithm": "SM-2 interval/state calculation",
   "algorithm_source": "https://super-memory.com/english/ol/sm2.htm",
   "boundary": "Supplied quality grades, timestamps and prior state are not independently verified. Due dates are plan data, not scheduled reminders. No empirically optimal timing or retention gain claim. Same-session repeats flagged, not simulated.",
   "feedback_is_actionable": true,
   "learner_control": true,
   "objective": "learn algebra",
   "schedule": [
    {
     "due_at": "2026-10-02T00:00:00+00:00",
     "ease": 2.5,
     "evidence_id": "e1",
     "id": "i1",
     "interval_days": 1,
     "lapse": false,
     "previous_state": {
      "ease": 2.5,
      "interval_days": 0,
      "repetitions": 0
     },
     "quality": 4,
     "repetitions": 1,
     "reviewed_at": "2026-10-01T00:00:00+00:00",
     "same_session_retry_required": false
    }
   ]
  },
  "row_id": 810,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "refs_1": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Spaced Repetition",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 0.833,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "learning",
  "result": {
   "algorithm": "SM-2 interval/state calculation",
   "algorithm_source": "https://super-memory.com/english/ol/sm2.htm",
   "boundary": "Supplied quality grades, timestamps and prior state are not independently verified. Due dates are plan data, not scheduled reminders. No empirically optimal timing or retention gain claim. Same-session repeats flagged, not simulated.",
   "feedback_is_actionable": true,
   "learner_control": true,
   "objective": "learn algebra",
   "schedule": [
    {
     "due_at": "2026-10-02T00:00:00+00:00",
     "ease": 2.5,
     "evidence_id": "e1",
     "id": "i1",
     "interval_days": 1,
     "lapse": false,
     "previous_state": {
      "ease": 2.5,
      "interval_days": 0,
      "repetitions": 0
     },
     "quality": 4,
     "repetitions": 1,
     "reviewed_at": "2026-10-01T00:00:00+00:00",
     "same_session_retry_required": false
    }
   ]
  },
  "row_id": 810,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "refs_2": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Spaced Repetition",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "learning",
  "result": {
   "algorithm": "SM-2 interval/state calculation",
   "algorithm_source": "https://super-memory.com/english/ol/sm2.htm",
   "boundary": "Supplied quality grades, timestamps and prior state are not independently verified. Due dates are plan data, not scheduled reminders. No empirically optimal timing or retention gain claim. Same-session repeats flagged, not simulated.",
   "feedback_is_actionable": true,
   "learner_control": true,
   "objective": "learn algebra",
   "schedule": [
    {
     "due_at": "2026-10-02T00:00:00+00:00",
     "ease": 2.5,
     "evidence_id": "e1",
     "id": "i1",
     "interval_days": 1,
     "lapse": false,
     "previous_state": {
      "ease": 2.5,
      "interval_days": 0,
      "repetitions": 0
     },
     "quality": 4,
     "repetitions": 1,
     "reviewed_at": "2026-10-01T00:00:00+00:00",
     "same_session_retry_required": false
    }
   ]
  },
  "row_id": 810,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 },
 "refs_3": {
  "boundary": "Restricted computation on supplied inputs only; no full capability or independent truth claim.",
  "capability": "Spaced Repetition",
  "evaluation": {
   "capability_executed": true,
   "independent_verification_required": true,
   "input_completeness": 1.0,
   "input_completeness_is_not_validity": true,
   "status": "restricted_computation",
   "uncertainty_count": 0
  },
  "family": "learning",
  "result": {
   "algorithm": "SM-2 interval/state calculation",
   "algorithm_source": "https://super-memory.com/english/ol/sm2.htm",
   "boundary": "Supplied quality grades, timestamps and prior state are not independently verified. Due dates are plan data, not scheduled reminders. No empirically optimal timing or retention gain claim. Same-session repeats flagged, not simulated.",
   "feedback_is_actionable": true,
   "learner_control": true,
   "objective": "learn algebra",
   "schedule": [
    {
     "due_at": "2026-10-02T00:00:00+00:00",
     "ease": 2.5,
     "evidence_id": "e1",
     "id": "i1",
     "interval_days": 1,
     "lapse": false,
     "previous_state": {
      "ease": 2.5,
      "interval_days": 0,
      "repetitions": 0
     },
     "quality": 4,
     "repetitions": 1,
     "reviewed_at": "2026-10-01T00:00:00+00:00",
     "same_session_retry_required": false
    }
   ]
  },
  "row_id": 810,
  "source": {
   "title": "t",
   "url": "https://x"
  },
  "tenant_id": "t",
  "uncertainty": {
   "calibration": "caller evidence and domain review required",
   "drivers": []
  }
 }
}''')

def _cases():
    cases = {}
    for i, claims in enumerate([None, ['claim one', 'claim two'], [1, 2.5], [{'k': 1}], 'ab']):
        p = dict(BASE, **EXPL)
        if claims is not None:
            p['claims'] = claims
        cases[f'813_{i}'] = ('elaborative_interrogation', p)
    for i, vals in enumerate([[1, 2, 3], [2.5, -1.0, 0], ['2.5', '1e2'], [True, False], [0]]):
        cases[f'841_{i}'] = ('quantitative_reasoning', dict(BASE, values=vals))
    for i, extra in enumerate([{}, {'prior': 0.3},
                               {'prior': 0.3, 'likelihood_given_h': 0.9, 'likelihood_given_not_h': 0.1},
                               {'prior': '0.5', 'likelihood_given_h': '0.5', 'likelihood_given_not_h': '0.25'},
                               {'prior': 1, 'likelihood_given_h': 1, 'likelihood_given_not_h': 0},
                               {'prior': True, 'likelihood_given_h': 1, 'likelihood_given_not_h': 0}]):
        cases[f'846_{i}'] = ('probabilistic_reasoning', dict(BASE, **extra))
    for i, refs in enumerate([None, [], [{'tenant_id': 't'}],
                              [{'tenant_id': 't', 'id': 1}, {'tenant_id': 't'}]]):
        p = dict(BASE, **SCHED)
        if refs is not None:
            p['resource_refs'] = refs
        cases[f'refs_{i}'] = ('spaced_repetition', p)
    return cases

@pytest.mark.parametrize('name', sorted(GOLDENS))
def test_valid_input_output_byte_identical(name):
    method, payload = _cases()[name]
    assert execute(method, payload) == GOLDENS[name]

def test_golden_battery_covers_all_cases():
    assert sorted(_cases()) == sorted(GOLDENS)
    assert len(GOLDENS) == 20

# --- defect pins: raw escapes now coded as LearningReasoningError ---

@pytest.mark.parametrize('claims', [True, False, 0, 1, 1.5, None])
def test_813_non_iterable_claims_coded(claims):
    p = dict(BASE, **EXPL, claims=claims)
    with pytest.raises(LearningReasoningError, match='claims must be an iterable of claim texts'):
        execute('elaborative_interrogation', p)

@pytest.mark.parametrize('bad', [None, {}, [1], {'k': 1}, object()])
def test_841_non_numeric_values_coded(bad):
    with pytest.raises(LearningReasoningError, match='values must contain only real numbers'):
        execute('quantitative_reasoning', dict(BASE, values=[1, bad]))

def test_841_huge_int_overflow_coded():
    with pytest.raises(LearningReasoningError, match='values must contain only real numbers'):
        execute('quantitative_reasoning', dict(BASE, values=[10 ** 400]))

@pytest.mark.parametrize('field', ['prior', 'likelihood_given_h', 'likelihood_given_not_h'])
@pytest.mark.parametrize('bad', [None, {}, [1], {'k': 1}])
def test_846_non_numeric_probabilities_coded(field, bad):
    with pytest.raises(LearningReasoningError, match='prior and likelihoods must be real numbers'):
        execute('probabilistic_reasoning', dict(BASE, **{field: bad}))

def test_846_huge_int_overflow_coded():
    with pytest.raises(LearningReasoningError, match='prior and likelihoods must be real numbers'):
        execute('probabilistic_reasoning', dict(BASE, prior=10 ** 400))

@pytest.mark.parametrize('refs', [True, 0, 1.5, 'ab', {'tenant_id': 't'}, b'x'])
def test_resource_refs_non_list_coded(refs):
    with pytest.raises(LearningReasoningError, match='resource_refs must be a list of objects'):
        execute('spaced_repetition', dict(BASE, **SCHED, resource_refs=refs))

@pytest.mark.parametrize('ref', [None, 'x', 1, 1.5, True, [1]])
def test_resource_refs_non_object_entry_coded(ref):
    with pytest.raises(LearningReasoningError, match='resource_refs entries must be objects'):
        execute('spaced_repetition', dict(BASE, **SCHED, resource_refs=[ref]))

# --- pre-existing coded behavior preserved ---

def test_cross_tenant_reference_still_rejected():
    with pytest.raises(LearningReasoningError, match='cross-tenant resource reference rejected'):
        execute('spaced_repetition', dict(BASE, **SCHED, resource_refs=[{'tenant_id': 'other'}]))

def test_846_out_of_range_probabilities_still_rejected():
    with pytest.raises(LearningReasoningError, match='invalid probabilities'):
        execute('probabilistic_reasoning', dict(BASE, prior=1.5))
    with pytest.raises(LearningReasoningError, match='invalid probabilities'):
        execute('probabilistic_reasoning', dict(BASE, prior=float('nan')))

def test_error_is_value_error_subclass():
    assert issubclass(LearningReasoningError, ValueError)
