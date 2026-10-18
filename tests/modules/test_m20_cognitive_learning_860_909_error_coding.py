"""Error-coding repair pins for cognitive_learning_860_909 (cl860r2).

SOURCE repair: (1) references guard (non-list refs / non-dict entries were
raw TypeError/AttributeError), (2) sources=_source(payload) wrapped
(TypeError/AttributeError from junk source entries), (3) result=_operation
wrapped - KeyError -> 'missing required input key' and
TypeError/AttributeError/IndexError/OverflowError/ZeroDivisionError ->
'invalid input structure'. Golden pins captured from the pre-repair module
at base 94fe792d; valid-input outputs stay byte-identical. OVERLAP NOTE:
site (3) textually conflicts with cl860r's narrower wrap (KeyError/TypeError
only) at the same 3-line region; this patch's wrap is the superset. If both
land, this version of the hunk should win; cl860r's row-881 theory_scores
coding is untouched and complementary.
"""
import hashlib
import json
import pytest
from app.modules.m20_general_cognitive_worker.cognitive_learning_860_909 import (
    execute, CognitiveLearningError)

GOLD = json.loads(r'''{
 "cases": {
  "860": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "causal_claim": "causal_claim evidence",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "contextualize": "contextualize evidence",
     "continuity_change": "continuity_change evidence",
     "corroborate": "corroborate evidence",
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "source": "source evidence",
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 860
  },
  "861": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "alternatives": "alternatives evidence",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "assumptions": "assumptions evidence",
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "claim": "claim evidence",
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "judgment": "judgment evidence",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 861
  },
  "862": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "elaborate": "elaborate evidence",
     "evaluate": "evaluate evidence",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "ideate": "ideate evidence",
     "identity_safety": 0.9,
     "incubate": "incubate evidence",
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prepare": "prepare evidence",
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 862
  },
  "863": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "movement": "movement evidence",
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "provocation": "provocation evidence",
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "random_entry": "random_entry evidence",
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 863
  },
  "864": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "defer_judgment": "defer_judgment evidence",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "flexibility": "flexibility evidence",
     "fluency": "fluency evidence",
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "originality": "originality evidence",
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "prompt": "prompt evidence",
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 864
  },
  "865": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "compare": "compare evidence",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "criteria": "criteria evidence",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "screen": "screen evidence",
     "seed": "a",
     "select_for_review": "select_for_review evidence",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 865
  },
  "866": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explain_link": "explain_link evidence",
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "remote_connection": "remote_connection evidence",
     "retention": 0.7,
     "retrieve_associations": "retrieve_associations evidence",
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 866
  },
  "867": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "changed_implications": "changed_implications evidence",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 867
  },
  "868": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "agreements": "agreements evidence",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "differences": "differences evidence",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "situated_perspectives": "situated_perspectives evidence",
     "solution_score": 0.7,
     "stakeholders": "stakeholders evidence",
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 868
  },
  "869": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "alternative_paradigm": "alternative_paradigm evidence",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_paradigm": "current_paradigm evidence",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "predictions": "predictions evidence",
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "transition_costs": "transition_costs evidence",
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 869
  },
  "870": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "attributes": "attributes evidence",
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "boundary_cases": "boundary_cases evidence",
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "non_examples": "non_examples evidence",
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "rule": "rule evidence",
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 870
  },
  "871": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "cross_links": "cross_links evidence",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "propositions": "propositions evidence",
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 871
  },
  "872": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "cross_links": "cross_links evidence",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "subbranches": "subbranches evidence",
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 872
  },
  "873": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "facets": "facets evidence",
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "grouping_rules": "grouping_rules evidence",
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "items": "items evidence",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "retrieval_paths": "retrieval_paths evidence",
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 873
  },
  "874": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "definitions": "definitions evidence",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hierarchy": "hierarchy evidence",
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "polyhierarchy_review": "polyhierarchy_review evidence",
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "scope": "scope evidence",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 874
  },
  "875": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "competency_questions": "competency_questions evidence",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "scope": "scope evidence",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 875
  },
  "876": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "paths": "paths evidence",
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "unsupported_edges": "unsupported_edges evidence",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 876
  },
  "877": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "accommodation": "accommodation evidence",
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "assimilation": "assimilation evidence",
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_information": "new_information evidence",
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_schema": "prior_schema evidence",
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 877
  },
  "878": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "assumptions": "assumptions evidence",
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "entities": "entities evidence",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "predictions": "predictions evidence",
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "purpose": "purpose evidence",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "relationships": "relationships evidence",
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 878
  },
  "879": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prediction_error": "prediction_error evidence",
     "prior_confidence": 0.4,
     "prior_model": "prior_model evidence",
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revised_model": "revised_model evidence",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 879
  },
  "880": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "conflicts": "conflicts evidence",
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_beliefs": "prior_beliefs evidence",
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "reliability": "reliability evidence",
     "retention": 0.7,
     "revised_confidence": "revised_confidence evidence",
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 880
  },
  "881": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "comparative_fit": "comparative_fit evidence",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "current_theory": "current_theory evidence",
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "research_needed": "research_needed evidence",
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "rivals": "rivals evidence",
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 881
  },
  "882": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "discrepant_evidence": "discrepant_evidence evidence",
     "dominant_pattern": "centralize",
     "elicitation": "elicitation evidence",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reconstruction": "reconstruction evidence",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_check": "transfer_check evidence",
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 882
  },
  "883": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "knowledge_gaps": "knowledge_gaps evidence",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_explanation": "learner_explanation evidence",
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision": "revision evidence",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "topic": "topic evidence",
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 883
  },
  "884": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempt": "attempt evidence",
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "authentic_task": "authentic_task evidence",
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "objective": "objective evidence",
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 884
  },
  "885": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "attention_cues": "attention_cues evidence",
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_check": "inference_check evidence",
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model": "model evidence",
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 885
  },
  "886": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "adaptation": "adaptation evidence",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "fidelity_check": "fidelity_check evidence",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "guided_rehearsal": "guided_rehearsal evidence",
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model": "model evidence",
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 886
  },
  "887": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "error_pattern": "error_pattern evidence",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "goal": "goal evidence",
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "outcomes": "outcomes evidence",
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 887
  },
  "888": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "impasse": "impasse evidence",
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "representation": "representation evidence",
     "restructuring_prompt": "restructuring_prompt evidence",
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 888
  },
  "889": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "associations": "associations evidence",
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "context": "context evidence",
     "credential_boundary": "no credential",
     "cues": "cues evidence",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "retrieval_test": "retrieval_test evidence",
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 889
  },
  "890": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": true,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "conditioned_response": "conditioned_response evidence",
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "extinction_plan": "extinction_plan evidence",
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "neutral_stimulus": "neutral_stimulus evidence",
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "pairings": "pairings evidence",
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "unconditioned_stimulus": "unconditioned_stimulus evidence",
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 890
  },
  "891": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": true,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "antecedent": "antecedent evidence",
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "ethical_review": "ethical_review evidence",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_behavior": "target_behavior evidence",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 891
  },
  "892": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model": "model evidence",
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "reproduction": "reproduction evidence",
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 892
  },
  "893": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "interaction": "interaction evidence",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "participation": "participation evidence",
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "shared_artifacts": "shared_artifacts evidence",
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 893
  },
  "894": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "direct_practice": "direct_practice evidence",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_inference": "observer_inference evidence",
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "similarity_limits": "similarity_limits evidence",
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 894
  },
  "895": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "abstract_conceptualization": "abstract_conceptualization evidence",
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "concrete_experience": "concrete_experience evidence",
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "reflective_observation": "reflective_observation evidence",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 895
  },
  "896": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "description": "description evidence",
     "dominant_pattern": "centralize",
     "evaluation": "evaluation evidence",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "experience": "experience evidence",
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "feelings": "feelings evidence",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 896
  },
  "897": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "set_members": "set_members evidence",
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 897
  },
  "898": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "critique_revision": "critique_revision evidence",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "driving_question": "driving_question evidence",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "inquiry": "inquiry evidence",
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 898
  },
  "899": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "ill_structured_problem": "ill_structured_problem evidence",
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_directed_inquiry": "self_directed_inquiry evidence",
     "self_direction": 0.9,
     "solution": "solution evidence",
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 899
  },
  "900": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explanation": "explanation evidence",
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "investigation": "investigation evidence",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "question": "question evidence",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 900
  },
  "901": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "environment": "environment evidence",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "exploration": "exploration evidence",
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "pattern": "pattern evidence",
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 901
  },
  "902": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "exploration_space": "exploration_space evidence",
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "fading": "fading evidence",
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hints": "hints evidence",
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 902
  },
  "903": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check": "check evidence",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "guided_practice": "guided_practice evidence",
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "independent_practice": "independent_practice evidence",
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model": "model evidence",
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "objective": "objective evidence",
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "review": "review evidence",
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 903
  },
  "904": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explanation": "explanation evidence",
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "guided_practice": "guided_practice evidence",
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "independent_practice": "independent_practice evidence",
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "objective": "objective evidence",
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "think_aloud": "think_aloud evidence",
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 904
  },
  "905": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_explanations": "alternative_explanations evidence",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "awareness_check": "awareness_check evidence",
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "exposure": "exposure evidence",
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "patterns": "patterns evidence",
     "performance_change": "performance_change evidence",
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 905
  },
  "906": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "primary_activity": "primary_activity evidence",
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 906
  },
  "907": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "evaluation": "evaluation evidence",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "goal": "goal evidence",
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "practice": "practice evidence",
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 907
  },
  "908": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment": "assessment evidence",
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "curriculum": "curriculum evidence",
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "provider": "provider evidence",
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 908
  },
  "909": {
   "payload": {
    "actor_id": "actor-a",
    "ethical_review": false,
    "inputs": {
     "action": "try",
     "action_plan": "retry",
     "active_experimentation": "test",
     "activity": "activity evidence",
     "alternative_frame": "investment",
     "analysis": "lesson",
     "anomalies": [
      "a"
     ],
     "assessment_score": 0.8,
     "association_strength": 0.2,
     "assumption_risk": 0.25,
     "attempts": [
      {
       "id": "1",
       "score": 0.2
      },
      {
       "id": "2",
       "score": 0.8
      }
     ],
     "attention": 0.8,
     "audience_questions": [
      "why"
     ],
     "awareness": 0.2,
     "baseline_score": 0.3,
     "behavior_probability": 0.3,
     "branches": [
      {
       "depth": 2,
       "name": "b"
      }
     ],
     "bridges": [
      "m"
     ],
     "candidate": "distributed path",
     "central_topic": "topic",
     "check_score": 0.85,
     "clarity_score": 0.9,
     "classes": [
      "A"
     ],
     "community": "peer",
     "concepts": [
      "a",
      "b"
     ],
     "consequence": 1,
     "constraints": [
      {
       "name": "c",
       "satisfied": true
      }
     ],
     "credential_boundary": "no credential",
     "current_frame": "cost",
     "current_score": 0.8,
     "debrief": "review",
     "dominant_pattern": "centralize",
     "events": [
      {
       "event": "later",
       "year": 2
      },
      {
       "event": "early",
       "year": 1
      }
     ],
     "evidence": [
      {
       "weight": 0.8
      },
      {
       "weight": -0.2
      }
     ],
     "evidence_considered": [
      "note"
     ],
     "evidence_direction": 1,
     "evidence_of_learning": [
      "artifact"
     ],
     "evidence_quality": 0.8,
     "evidence_reliability": 0.5,
     "examples": [
      {
       "attributes": [
        "living",
        "moves"
       ]
      },
      {
       "attributes": [
        "living",
        "grows"
       ]
      }
     ],
     "explained_anomalies": [
      "a"
     ],
     "explorations": [
      "e"
     ],
     "faded_to": 1,
     "feedback": "retry",
     "first_score": 0.3,
     "groups": {
      "g": [
       "i"
      ]
     },
     "guided_accuracy": 0.8,
     "hint_level": 3,
     "hypothesis": "h",
     "ideas": [
      "new-a",
      "new-b"
     ],
     "identity_safety": 0.9,
     "independent_accuracy": 0.75,
     "inference_confidence": 0.7,
     "initial_conception": "old",
     "initial_participation": 0.2,
     "insight": "pattern",
     "known_ideas": [
      "old"
     ],
     "knowns": [
      "k"
     ],
     "later_participation": 0.7,
     "later_score": 0.8,
     "learner_rule": "r",
     "learning_rate": 0.5,
     "matched_steps": 0.8,
     "milestones": [
      {
       "done": true
      },
      {
       "done": false
      }
     ],
     "model_outcome": 0.8,
     "monitoring": [
      "weekly"
     ],
     "motivation": 0.9,
     "new_questions": [
      "n"
     ],
     "new_representation": "diagram",
     "next_attempt": "harder",
     "next_experiment": "vary one factor",
     "nodes": [
      "a",
      "b"
     ],
     "observations": [
      "step"
     ],
     "observed": 0.8,
     "observer_similarity": 0.5,
     "options": [
      {
       "name": "a",
       "scores": {
        "fit": 0.8
       }
      },
      {
       "name": "b",
       "scores": {
        "fit": 0.4
       }
      }
     ],
     "perspectives": [
      {
       "priority": "access",
       "stakeholder": "learner"
      }
     ],
     "post_exposure": 0.7,
     "post_score": 0.7,
     "pre_exposure": 0.3,
     "pre_score": 0.2,
     "predicted": 0.2,
     "prior_confidence": 0.4,
     "prior_version": 1,
     "public_product": "demo",
     "questions": [
      "q"
     ],
     "real_problem": "p",
     "reconstructed_conception": "new",
     "reflection": "worked",
     "relations": [
      {
       "from": "a",
       "to": "b",
       "type": "is_a"
      }
     ],
     "retention": 0.7,
     "revised_explanation": "because",
     "revision_count": 2,
     "schedule": "fixed",
     "seed": "a",
     "self_direction": 0.9,
     "setting": "setting evidence",
     "solution_score": 0.7,
     "strategy": "spacing",
     "strength": 0.2,
     "target": "z",
     "target_sequence": [
      "a"
     ],
     "terms": [
      {
       "parent": null,
       "term": "root"
      },
      {
       "parent": "root",
       "term": "leaf"
      }
     ],
     "theory_scores": {
      "t1": [
       0.8,
       0.9
      ],
      "t2": [
       0.2,
       0.4
      ]
     },
     "transfer": "use",
     "transfer_accuracy": 0.8,
     "transfer_score": 0.8,
     "transition_cost": 0.2,
     "typed_edges": [
      {
       "from": "a",
       "to": "b",
       "type": "related"
      }
     ],
     "typed_links": [
      {
       "from": "a",
       "to": "b",
       "type": "causes"
      }
     ],
     "unconditioned_response": 1,
     "units": [
      {
       "complete": true
      },
      {
       "complete": false
      }
     ],
     "unknowns": [
      "u"
     ],
     "unplanned_learning": "fact",
     "verification": true,
     "verification_score": 0.8,
     "weights": {
      "fit": 1
     }
    },
    "learner_goals": [
     "learn"
    ],
    "sources": [
     {
      "kind": "primary",
      "observed_at": "2026-10-18T15:56:13.716431+00:00",
      "source_id": "s"
     }
    ],
    "tenant_id": "tenant-a"
   },
   "row": 909
  }
 },
 "sha256_pins": {
  "860": "9dc3cbb234cc3287175ad906dcdb33f0d77ef396f2e50b5ab753e873cce02c8e",
  "861": "7fea1207d7f4c564eab6eb22b841de52320784f60ba07fa730cb0a190a2c970f",
  "862": "41076dbb12fb8aebbe31e4fda023ca1119a7e2ab52509198a7ebcdceb9287307",
  "863": "2ba7417c1876167ebf8fe3533e87d133deedb36cf95e460b53ebc8af446ead96",
  "864": "54e6b1650e3968cde73c53d9d3dc4ed67ac75f9f8cb6e624ec94e48b35c70b33",
  "865": "10510efc8a8c76d89f3cdb493036d135390917055291dd8286a3f43bd6e4d645",
  "866": "39b8a25dd3539649f3d11a3a58623bc0e5a33df025b8dfcc4b97f220276ba855",
  "867": "1e67f54e5d53a0702f0f007391524049661af2d305d2d45d43948fdfe2cd1762",
  "868": "94e2f27fc163695c4e3b4a9a7783daf4f1b954bebaf3fa58c5fb6ec8e29df92f",
  "869": "45eb255d0ddb2eac39abde67ef9a832506f3d5388f4d2f2ea63f914887720789",
  "870": "5af7f25d040de54f206088d4206ed7ddfa58690e2c798b92ad89cfc06d7a4455",
  "871": "92deec088d50993daae093663783ad1c087acf4f703fb9c16bec2cc1afd203e2",
  "872": "a41f3fd6621f8953d802a0a6a2fe30ffc80aa68aaaff39cfb68127c6c36dfec7",
  "873": "9bc2ba8cf558579c8e1e3586332ed3590198035961a1c6a7368fc41532afb277",
  "874": "12082ad2a7f4080afd9c270a99a8542e5960669e19b6d8b568da3eeeb572bdc7",
  "875": "e17d11039ca098953b5d50c43d538b5290a9eabaf08a2ae62c24f77d15131c64",
  "876": "7f54a2fc137d18d590b356cb63fc10158a13115afbc9009b4661bdc77db9ab41",
  "877": "1a5c7f098f8a642b1598d58d4b430b5866a07e0a2a10e88a63a5fcdf2dd8225f",
  "878": "c2b9e5e9fbb30067f7d82e7678d905e18f5843384484b7c7563d16f2dcdc3095",
  "879": "f4c22134fc55a35606698fb18c1e37732af5ca4c40ce94dac719c070fa6cc27b",
  "880": "3b85a156bf699bc4002546cc3e0f28bf8ed06745dcf11896efbc84898527a8a5",
  "881": "32c31f765401bf8e19a35522b0f8ed322e074fd33318ed10ef6d68c6cbb6f81c",
  "882": "fdca0bc5ca8ed4e2f422bf4955448d863960a5acfe37b11fef6630cb671b0a7f",
  "883": "c889d08869e49813f2d1955674a3f64dead861c6d6df65ed4c4753b3ddd3e8f0",
  "884": "25dee2bc7352204bf6b6979c7016aab5d01aac2bffc40811d887fa6ba43ecb74",
  "885": "b2798b97fce87dd9fb5e7b878b99350e16d36ea7107a11b227007fe70ece601b",
  "886": "84781beb4277f192e0f99449057fc750546071de06cefc6d58246ed5c8cafcfa",
  "887": "62a08112b218d73983dd5f5fbe0a5086f8efb8ee765bc108933223c2839a9f0c",
  "888": "271bfe86c8235859e5f71fe16f870d5b8fa8fdf175e2e44f2550cb8b302a91ab",
  "889": "e42ed95c722708de63a6fa4150721985ba3c8e7885a08efccc340d9646450fba",
  "890": "ad874d79282631e57a6399d73129837e6eebf6a838876aa6e59805a856ddb4d1",
  "891": "14f06a59e9174e1ec5a1440031dfca465f0024e964e4ea3adbb6ce5af4c92929",
  "892": "a40b268fb41f70e90d2f35258bf4dff1b2e6df9642d2c1beb31c6b0bf89a49a4",
  "893": "fc13b95833c9de8fb6d59dc47f1d271def420d54066fed63cd80da70f0c90297",
  "894": "c2c833a6f7d257ddf0342b574fce327a876f5f10f2c89e37afe153ff26ebf317",
  "895": "7fbfc71f51fc8a11459ca5fe652825783135b6ecfe3018c5528bf9363c07ea8c",
  "896": "1e2000cbd56c09d10ee05d204d55b1ec46fc7f00efd5d773d5681ecf057f5ca8",
  "897": "1921cfd34515ddd1618480d851044a39d021df44302a5716b5ea4d68d181a17a",
  "898": "23a287222eab21d14cf7641b2ac5bdc5a3719f32bc59c4416a18c0b7518e62d5",
  "899": "089ecf2a672477fd2520467679b39d3809e55286d5d90077c064199dd1f388e4",
  "900": "4afab334260d8d65d00af62488984fceeff1040f49a1a71e18c605b65a2de711",
  "901": "fb319511e3b8f93b6689c9cbaebaf49db049c7bab681a2dc2dd7e74a73ecc68f",
  "902": "ac67bfc5235dfad69de8b75682240167e38982865c65cdd6a1121a1f7e564b27",
  "903": "b94f6fc8d3800d1fed49b870f7336626aebcb56c418dbf920c9dae1f0505644a",
  "904": "8ee24dd1b3b0e9e1883239c123685c37c103178dce04159de6313b82320b0358",
  "905": "c758616d00d1f51d99e63a7f50a888bf710c8658d8dbedd7c0e3be00b6641911",
  "906": "41b8a9bf06bda30b970cc9e53dc1f8bc18f60694ee97f1ee5eec184d7d31d56a",
  "907": "2594f563e6b96a7a4095d44c538c5a97f62c17c0150ad9a2264a3dc6887932f0",
  "908": "a551484ca49a300bd6d8d8e05588e78907b7474dc5d9e3e493631e92b6a860a9",
  "909": "872d6a79ab57c4951c053b332a0d4e27c49607c9c5fd2af8df01bd8fd8cc7009"
 }
}''')

def canon(result):
    return hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()

@pytest.mark.parametrize("key", sorted(GOLD["cases"], key=int))
def test_valid_input_output_byte_identical(key):
    case = GOLD["cases"][key]
    assert canon(execute(case["row"], case["payload"])) == GOLD["sha256_pins"][key]

def test_battery_covers_all_50_rows():
    assert {int(k) for k in GOLD["cases"]} == set(range(860, 910))

# --- defect pins: each fails on the pre-repair module with the raw exception ---

def test_860_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["860"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(860, d)

def test_860_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["860"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(860, d)

def test_860_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["860"]["payload"]))
    d["inputs"]['events'] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(860, d)

def test_861_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["861"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(861, d)

def test_861_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["861"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(861, d)

def test_861_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["861"]["payload"]))
    d["inputs"]['evidence_quality'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(861, d)

def test_862_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["862"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(862, d)

def test_862_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["862"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(862, d)

def test_862_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["862"]["payload"]))
    d["inputs"]['ideas'] = None
    with pytest.raises(CognitiveLearningError):
        execute(862, d)

def test_863_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["863"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(863, d)

def test_863_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["863"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(863, d)

def test_864_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["864"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(864, d)

def test_864_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["864"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(864, d)

def test_865_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["865"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(865, d)

def test_865_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["865"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(865, d)

def test_865_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["865"]["payload"]))
    d["inputs"]['options'] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(865, d)

def test_866_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["866"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(866, d)

def test_866_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["866"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(866, d)

def test_866_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["866"]["payload"]))
    d["inputs"]['bridges'] = None
    with pytest.raises(CognitiveLearningError):
        execute(866, d)

def test_867_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["867"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(867, d)

def test_867_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["867"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(867, d)

def test_868_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["868"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(868, d)

def test_868_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["868"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(868, d)

def test_868_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["868"]["payload"]))
    d["inputs"]['perspectives'] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(868, d)

def test_869_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["869"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(869, d)

def test_869_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["869"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(869, d)

def test_869_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["869"]["payload"]))
    d["inputs"]['anomalies'] = None
    with pytest.raises(CognitiveLearningError):
        execute(869, d)

def test_870_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["870"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(870, d)

def test_870_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["870"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(870, d)

def test_870_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["870"]["payload"]))
    d["inputs"]['examples'] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(870, d)

def test_871_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["871"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(871, d)

def test_871_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["871"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(871, d)

def test_871_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["871"]["payload"]))
    d["inputs"]['concepts'] = None
    with pytest.raises(CognitiveLearningError):
        execute(871, d)

def test_872_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["872"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(872, d)

def test_872_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["872"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(872, d)

def test_872_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["872"]["payload"]))
    d["inputs"]['branches'] = None
    with pytest.raises(CognitiveLearningError):
        execute(872, d)

def test_873_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["873"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(873, d)

def test_873_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["873"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(873, d)

def test_873_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["873"]["payload"]))
    d["inputs"]['groups'] = None
    with pytest.raises(CognitiveLearningError):
        execute(873, d)

def test_874_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["874"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(874, d)

def test_874_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["874"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(874, d)

def test_874_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["874"]["payload"]))
    d["inputs"]['terms'] = None
    with pytest.raises(CognitiveLearningError):
        execute(874, d)

def test_875_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["875"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(875, d)

def test_875_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["875"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(875, d)

def test_875_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["875"]["payload"]))
    d["inputs"]['relations'] = True
    with pytest.raises(CognitiveLearningError):
        execute(875, d)

def test_876_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["876"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(876, d)

def test_876_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["876"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(876, d)

def test_876_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["876"]["payload"]))
    d["inputs"]['nodes'] = None
    with pytest.raises(CognitiveLearningError):
        execute(876, d)

def test_877_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["877"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(877, d)

def test_877_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["877"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(877, d)

def test_877_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["877"]["payload"]))
    d["inputs"]['prior_version'] = None
    with pytest.raises(CognitiveLearningError):
        execute(877, d)

def test_878_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["878"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(878, d)

def test_878_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["878"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(878, d)

def test_879_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["879"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(879, d)

def test_879_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["879"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(879, d)

def test_879_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["879"]["payload"]))
    d["inputs"]['predicted'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(879, d)

def test_880_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["880"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(880, d)

def test_880_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["880"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(880, d)

def test_880_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["880"]["payload"]))
    d["inputs"]['prior_confidence'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(880, d)

def test_881_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["881"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(881, d)

def test_881_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["881"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(881, d)

def test_881_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["881"]["payload"]))
    d["inputs"]['theory_scores'] = None
    with pytest.raises(CognitiveLearningError):
        execute(881, d)

def test_882_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["882"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(882, d)

def test_882_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["882"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(882, d)

def test_882_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["882"]["payload"]))
    d["inputs"]['transfer_accuracy'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(882, d)

def test_883_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["883"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(883, d)

def test_883_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["883"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(883, d)

def test_883_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["883"]["payload"]))
    d["inputs"]['pre_score'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(883, d)

def test_884_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["884"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(884, d)

def test_884_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["884"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(884, d)

def test_884_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["884"]["payload"]))
    d["inputs"]['first_score'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(884, d)

def test_885_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["885"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(885, d)

def test_885_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["885"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(885, d)

def test_885_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["885"]["payload"]))
    d["inputs"]['inference_confidence'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(885, d)

def test_886_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["886"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(886, d)

def test_886_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["886"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(886, d)

def test_886_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["886"]["payload"]))
    d["inputs"]['matched_steps'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(886, d)

def test_887_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["887"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(887, d)

def test_887_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["887"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(887, d)

def test_887_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["887"]["payload"]))
    d["inputs"]['attempts'] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(887, d)

def test_888_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["888"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(888, d)

def test_888_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["888"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(888, d)

def test_889_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["889"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(889, d)

def test_889_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["889"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(889, d)

def test_889_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["889"]["payload"]))
    d["inputs"]['learning_rate'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(889, d)

def test_890_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["890"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(890, d)

def test_890_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["890"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(890, d)

def test_890_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["890"]["payload"]))
    d["inputs"]['learning_rate'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(890, d)

def test_891_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["891"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(891, d)

def test_891_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["891"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(891, d)

def test_891_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["891"]["payload"]))
    d["inputs"]['consequence'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(891, d)

def test_892_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["892"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(892, d)

def test_892_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["892"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(892, d)

def test_892_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["892"]["payload"]))
    d["inputs"]['attention'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(892, d)

def test_893_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["893"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(893, d)

def test_893_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["893"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(893, d)

def test_893_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["893"]["payload"]))
    d["inputs"]['identity_safety'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(893, d)

def test_894_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["894"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(894, d)

def test_894_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["894"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(894, d)

def test_894_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["894"]["payload"]))
    d["inputs"]['model_outcome'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(894, d)

def test_895_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["895"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(895, d)

def test_895_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["895"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(895, d)

def test_896_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["896"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(896, d)

def test_896_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["896"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(896, d)

def test_896_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["896"]["payload"]))
    d["inputs"]['evidence_considered'] = None
    with pytest.raises(CognitiveLearningError):
        execute(896, d)

def test_897_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["897"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(897, d)

def test_897_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["897"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(897, d)

def test_897_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["897"]["payload"]))
    d["inputs"]['questions'] = None
    with pytest.raises(CognitiveLearningError):
        execute(897, d)

def test_898_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["898"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(898, d)

def test_898_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["898"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(898, d)

def test_898_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["898"]["payload"]))
    d["inputs"]['milestones'] = None
    with pytest.raises(CognitiveLearningError):
        execute(898, d)

def test_899_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["899"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(899, d)

def test_899_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["899"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(899, d)

def test_899_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["899"]["payload"]))
    d["inputs"]['solution_score'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(899, d)

def test_900_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["900"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(900, d)

def test_900_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["900"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(900, d)

def test_900_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["900"]["payload"]))
    d["inputs"]['evidence'] = None
    with pytest.raises(CognitiveLearningError):
        execute(900, d)

def test_901_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["901"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(901, d)

def test_901_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["901"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(901, d)

def test_901_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["901"]["payload"]))
    d["inputs"]['verification_score'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(901, d)

def test_902_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["902"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(902, d)

def test_902_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["902"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(902, d)

def test_902_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["902"]["payload"]))
    d["inputs"]['hint_level'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(902, d)

def test_903_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["903"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(903, d)

def test_903_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["903"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(903, d)

def test_903_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["903"]["payload"]))
    d["inputs"]['check_score'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(903, d)

def test_904_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["904"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(904, d)

def test_904_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["904"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(904, d)

def test_904_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["904"]["payload"]))
    d["inputs"]['clarity_score'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(904, d)

def test_905_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["905"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(905, d)

def test_905_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["905"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(905, d)

def test_905_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["905"]["payload"]))
    d["inputs"]['post_exposure'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(905, d)

def test_906_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["906"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(906, d)

def test_906_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["906"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(906, d)

def test_906_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["906"]["payload"]))
    d["inputs"]['pre_score'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(906, d)

def test_907_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["907"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(907, d)

def test_907_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["907"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(907, d)

def test_907_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["907"]["payload"]))
    d["inputs"]['current_score'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(907, d)

def test_908_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["908"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(908, d)

def test_908_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["908"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(908, d)

def test_908_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["908"]["payload"]))
    d["inputs"]['units'] = None
    with pytest.raises(CognitiveLearningError):
        execute(908, d)

def test_909_junk_sources_coded():
    d = json.loads(json.dumps(GOLD["cases"]["909"]["payload"]))
    d["sources"] = True
    with pytest.raises(CognitiveLearningError):
        execute(909, d)

def test_909_junk_references_coded():
    d = json.loads(json.dumps(GOLD["cases"]["909"]["payload"]))
    d["references"] = [None]
    with pytest.raises(CognitiveLearningError):
        execute(909, d)

def test_909_operation_escape_coded():
    d = json.loads(json.dumps(GOLD["cases"]["909"]["payload"]))
    d["inputs"]['self_direction'] = 10 ** 400
    with pytest.raises(CognitiveLearningError):
        execute(909, d)


@pytest.mark.parametrize("refs", [True, 0, 1.5, "x", b"x"])
def test_references_non_list_coded(refs):
    d = json.loads(json.dumps(GOLD["cases"]["861"]["payload"]))
    d["references"] = refs
    with pytest.raises(CognitiveLearningError, match="references must be a list of objects"):
        execute(861, d)

def test_cross_tenant_reference_still_rejected():
    d = json.loads(json.dumps(GOLD["cases"]["861"]["payload"]))
    d["references"] = [{"tenant_id": "other", "actor_id": "actor-a"}]
    with pytest.raises(CognitiveLearningError, match="cross-tenant"):
        execute(861, d)

def test_cross_actor_reference_still_rejected():
    d = json.loads(json.dumps(GOLD["cases"]["861"]["payload"]))
    d["references"] = [{"tenant_id": "tenant-a", "actor_id": "other-actor"}]
    with pytest.raises(CognitiveLearningError, match="cross-tenant"):
        execute(861, d)

def test_same_tenant_references_accepted():
    d = json.loads(json.dumps(GOLD["cases"]["861"]["payload"]))
    d["references"] = [{"tenant_id": "tenant-a", "actor_id": "actor-a"}, {"tenant_id": "tenant-a"}]
    out = execute(861, d)
    assert out["row_id"] == 861
