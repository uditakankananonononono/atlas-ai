"""Error-coding repair pins for app.modules.m20_general_cognitive_worker.education (rows 1410-1459).

SOURCE repair (education.py): junk caller inputs that previously escaped as raw
AttributeError/TypeError/OverflowError/ZeroDivisionError now raise coded
EducationError (a ValueError). Every repair is crash-only: each defect case below
raised a raw non-ValueError on the pre-repair module (verified), and every input
that succeeded pre-repair is byte-identical post-repair (golden canonical-JSON
sha256 pins below, hashes computed on the pre-repair module).

Fuzz provenance: harvested valid payloads from the landed suite
(test_m20_education_1410_1459.py, 80 payloads covering all 50 capabilities),
deep leaf corruption - 12,000 corruptions, 0 uncoded escapes post-repair.
"""
import copy
import hashlib
import json

import pytest

from app.modules.m20_general_cognitive_worker.education import EducationError, execute

_DEFECT_CASES = json.loads('[{"id": "delivery_junk_unit_int", "capability": "flipped_classroom", "payload": {"units": [{"title": "Week 1"}, 5], "constraints": {"bandwidth": "low"}, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "note": "units entry int -> AttributeError on .get"}, {"id": "delivery_junk_unit_list", "capability": "blended_learning", "payload": {"units": [[{"title": "x"}]], "constraints": {"bandwidth": "low"}, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "note": "units entry list -> AttributeError"}, {"id": "micro_target_minutes_list", "capability": "microlearning", "payload": {"units": ["a"], "constraints": {"bandwidth": "low"}, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "target_minutes": [7]}, "note": "target_minutes list -> TypeError in int()"}, {"id": "mastery_list", "capability": "adaptive_learning", "payload": {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "mastery": [0.5]}, "note": "mastery list -> TypeError in float()"}, {"id": "mastery_huge_int", "capability": "adaptive_learning", "payload": {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "mastery": 10000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000}, "note": "mastery huge int -> OverflowError"}, {"id": "zpd_unhashable", "capability": "zone_of_proximal_development", "payload": {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "independent_skills": [["a"]]}, "note": "unhashable skill -> TypeError in set()"}, {"id": "zpd_mixed_types", "capability": "zone_of_proximal_development", "payload": {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "independent_skills": [], "assisted_skills": ["b", 1]}, "note": "mixed-type sorted -> TypeError"}, {"id": "rubric_criterion_int", "capability": "rubric_creation", "payload": {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "criteria": [5]}, "note": "criterion int -> AttributeError on .get"}, {"id": "rubric_weight_str", "capability": "rubric_creation", "payload": {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "criteria": [{"name": "a", "weight": "heavy"}]}, "note": "weight str -> TypeError in sum"}, {"id": "rubric_zero_total", "capability": "rubric_creation", "payload": {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "criteria": [{"name": "a", "weight": 0}]}, "note": "zero total -> ZeroDivisionError"}, {"id": "edm_min_support_list", "capability": "educational_data_mining", "payload": {"events": [{"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": true, "duration_seconds": 20}, {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": false, "duration_seconds": 40}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "min_support": [2]}, "note": "min_support list -> TypeError in int()"}, {"id": "edm_unhashable_event_type", "capability": "educational_data_mining", "payload": {"events": [{"learner_id": "p1", "skill": "fractions", "event_type": ["attempt"], "correct": true, "duration_seconds": 20}, {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": false, "duration_seconds": 40}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "min_support": 2}, "note": "unhashable event_type -> TypeError dict key"}, {"id": "edm_mixed_event_types", "capability": "educational_data_mining", "payload": {"events": [{"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": true, "duration_seconds": 20}, {"learner_id": "p1", "skill": "fractions", "event_type": 5, "correct": false, "duration_seconds": 40}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "min_support": 2}, "note": "mixed-type sorted -> TypeError"}, {"id": "bkt_prior_list", "capability": "knowledge_tracing", "payload": {"events": [{"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": true, "duration_seconds": 20}, {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": false, "duration_seconds": 40}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "prior_mastery": [0.2]}, "note": "prior_mastery list -> TypeError in float()"}, {"id": "bkt_prior_huge", "capability": "knowledge_tracing", "payload": {"events": [{"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": true, "duration_seconds": 20}, {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": false, "duration_seconds": 40}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "prior_mastery": 10000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000}, "note": "prior_mastery huge int -> OverflowError"}, {"id": "affect_unhashable_event_type", "capability": "affect_detection", "payload": {"events": [{"learner_id": "p", "skill": "course", "event_type": ["self_report"], "value": "frustrated", "confidence": 0.7}, {"learner_id": "p", "skill": "course", "event_type": "camera_face", "value": "sad"}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "note": "unhashable event_type -> TypeError in set membership"}, {"id": "moocs_cohort_list", "capability": "moocs", "payload": {"units": ["a"], "constraints": {"bandwidth": "low"}, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "cohort_scale": [100]}, "note": "cohort_scale list -> TypeError in float()"}, {"id": "moocs_channels_dict", "capability": "moocs", "payload": {"units": ["a"], "constraints": {"bandwidth": "low"}, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "cohort_scale": 1000, "moderation_channels": {"n": 2}}, "note": "moderation_channels dict -> TypeError in int()"}, {"id": "design_duration_huge", "capability": "curriculum_design", "payload": {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 10000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "note": "duration huge int -> OverflowError in float()"}, {"id": "analytics_duration_huge", "capability": "learning_analytics", "payload": {"events": [{"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": true, "duration_seconds": 10000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000}, {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": false, "duration_seconds": 40}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "note": "duration_seconds huge int -> OverflowError in mean"}]')
_GOLDENS = json.loads('[["adaptive_learning", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "mastery": 0.4}, "75d97534f67d56236a66f0a40bb67ad9a68f2085d99ddefc040e97eb45edc0ec"], ["intelligent_tutoring", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "c097013e8f13bfe1797c4cac84732aa5ca26f3c2fb5bd5418089e2025c2f72e0"], ["affect_detection", {"events": [{"learner_id": "p", "skill": "course", "event_type": "self_report", "value": "frustrated", "confidence": 0.7}, {"learner_id": "p", "skill": "course", "event_type": "camera_face", "value": "sad"}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "7df0824a5b94ac12e1a9631a01853b92de9aaa01802bf30b173292354c887fc7"], ["artificial_intelligence_in_education", {"use_case": "practice hints", "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "12b238cdcf7fe9da9ace72f3d20db36a15357ff6be676ba46493629c83a2c1e7"], ["knowledge_tracing", {"events": [{"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": true, "duration_seconds": 20}, {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": false, "duration_seconds": 40}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "360015b6972e30defce2d52062306b8634a57cd7a677dc401d1a9778ec28f63a"], ["knowledge_tracing", {"events": [{"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": true, "duration_seconds": 20}, {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": false, "duration_seconds": 40}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "prior_mastery": 0.3, "learn_rate": 0.2, "slip": 0.15, "guess": 0.25}, "6f10f498a168ef8195bb6c269cbafdcbf6b7f2075a58f87fe8a856cab8bd4b07"], ["cognitive_apprenticeship", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "0c7017a35318294c6067525bc55c0c9eef1546c1e6ce669f8623a5e49fbf1208"], ["educational_data_mining", {"events": [{"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": true, "duration_seconds": 20}, {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": false, "duration_seconds": 40}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "min_support": 2}, "1e7daa20ada7ef5b6b1cedaad113cb9aa735baf348ad694fbe1b087ee152aa48"], ["curriculum_design", {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "cd9cfb185d467554fa892771d58ba653c7b192089e4c05e12811d0d9118ba6ed"], ["learning_objective_writing", {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "9d4fdcacb1457754e0c2a91969448d7fa97d9bd1dcd53cfae6434771972c0ebf"], ["assessment_design", {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "a65a4bfdc671c437c03873701bbe9c9e3ff014b92ce82d21c4b329fd7d9d3f90"], ["rubric_creation", {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "criteria": ["accuracy"]}, "cff1654f24030b2c1f35a09998c1ff682c093f30b0e5cb1ef26ccec2bf0f62e3"], ["lesson_planning", {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "a883878432d5c1a777add978c19e82f602d0bd5902130c20002b9caf84b7ba34"], ["unit_planning", {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "962f098cc0d2cbc45540998eb8375ea9f637bb5552d8c26490d1f0f97b5d5b57"], ["course_design", {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "106af57a250f03ac47dcfece62bc772770bf252295f107fdd815aa3ba0c0a0ac"], ["syllabus_creation", {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "b5d4b7a3cf0d4243db672876609172fd9141a4c3aff3f5e477d0e8c918ddedf1"], ["instructional_design", {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "5931f3883bceb839f7daf04423b56995a562118ccc4e2d76345a2131209369c9"], ["addie_model", {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "4f72b58f60d9f088046e45ed7e17430980015c19be472380f05803a2ec5ce653"], ["sam_model", {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "d2111be9ae491eb17f8b85b3eaa724a226cde7a47572dfc045d49c0eb9ef4fa3"], ["backward_design", {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "6a6a2fe6f411a917772d518753ac7d81d7c9d2ed6eb2ffbb610e9d92fdeaecbe"], ["universal_design_for_learning", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "a9e74ad4fa2ee1d546525dd22562c5bd9726d911d1c50ce74dee452c6e9520e6"], ["differentiated_instruction", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "001e407302133b480c7ace269811498bf95dd1e2c551b0c772673140309ad066"], ["personalized_learning", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "a336764ccd936062d5e3cfdc388ba46e4b032abe7d835b1975299ecf30dd11a0"], ["adaptive_learning", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "mastery": 0.4}, "75d97534f67d56236a66f0a40bb67ad9a68f2085d99ddefc040e97eb45edc0ec"], ["intelligent_tutoring", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "c097013e8f13bfe1797c4cac84732aa5ca26f3c2fb5bd5418089e2025c2f72e0"], ["scaffolding", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "6a676a4528dc274d335db4685571f274a9f3837be4b4447422d2f7bca2077f03"], ["zone_of_proximal_development", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "a8d65152b119d552caa690acfd7260aefdb2145ca207ef88e5ab6969e4c3808c"], ["cognitive_apprenticeship", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "0c7017a35318294c6067525bc55c0c9eef1546c1e6ce669f8623a5e49fbf1208"], ["situated_learning", {"challenge": "Reduce school waste", "objectives": ["Evaluate evidence"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "ca6e5fceafdcafa785e0bf654515908dc87f8141638c6fc72266be4852f16057"], ["anchored_instruction", {"challenge": "Reduce school waste", "objectives": ["Evaluate evidence"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "d6c41470259c1087004efa4c1dd13b584b7c7d2ba0e7b9a5378dee827c1c3a7f"], ["problem_based_learning", {"challenge": "Reduce school waste", "objectives": ["Evaluate evidence"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "d22ca19516c4f2b83d509e2b83c9f08e4b6c325d45b997d5b74470738860533a"], ["project_based_learning", {"challenge": "Reduce school waste", "objectives": ["Evaluate evidence"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "ef1be34fdc69f6849210dbd69a46b3b8632199be08db1595806d2bb55b945c6c"], ["inquiry_based_learning", {"challenge": "Reduce school waste", "objectives": ["Evaluate evidence"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "4da895adc864930189ea2652287ddf51df3dd637cdd8a813f85b5192ff91ffe7"], ["discovery_learning", {"challenge": "Reduce school waste", "objectives": ["Evaluate evidence"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "2a97d4a7081231b24ee462c7d83069776bf3f7f1508af2026aa41da1034d6ab5"], ["experiential_learning", {"challenge": "Reduce school waste", "objectives": ["Evaluate evidence"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "4ba827adc70898faa644217a4b71a048c23efcec18fbb7547015ee1ae398fc10"], ["service_learning", {"challenge": "Reduce school waste", "objectives": ["Evaluate evidence"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "6ce5d556ba1d9072a8311653ef8cf093cc5d8f305f49be079e550a0fd4ca7c22"], ["cooperative_learning", {"challenge": "Reduce school waste", "objectives": ["Evaluate evidence"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "ed5ffbd71bbc4d9652a2d777cc23073f36d19f95cd232b652d9f91d3f111f7f9"], ["collaborative_learning", {"challenge": "Reduce school waste", "objectives": ["Evaluate evidence"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "53b47a75b028ab72cb0dcd440f9be017681584d9a2a5a69fca67ebdca79682b8"], ["peer_instruction", {"challenge": "Reduce school waste", "objectives": ["Evaluate evidence"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "3721be2d535876182cc9162fa92cd95f0a654d669cd081e4225547a764753edf"], ["flipped_classroom", {"units": ["Foundations", "Application"], "constraints": {"bandwidth": "low"}, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "324ebe7bbdcbbc54c86461ba594f93c31345fe3193c9829bfb77a0920a19cc4c"], ["blended_learning", {"units": ["Foundations", "Application"], "constraints": {"bandwidth": "low"}, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "77afc93629d1e7c26941925bc3f6557df470de3a7f26b221aec01a1212365f69"], ["online_learning", {"units": ["Foundations", "Application"], "constraints": {"bandwidth": "low"}, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "2aa005091ec47ccbfcccb9124a3bdc29ab27286e92cb48609be85ac6f01ef8bc"], ["distance_education", {"units": ["Foundations", "Application"], "constraints": {"bandwidth": "low"}, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "03073b4bf4fe7fa0b92c3e3df017c0889569e198b918b2c1e5f3540df0421d38"], ["moocs", {"units": ["Foundations", "Application"], "constraints": {"bandwidth": "low"}, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "cohort_scale": 1000}, "7d1c0d710c88244d69c5357d33a99ce1bc52838c1d5c3373be7bf532f667e566"], ["microlearning", {"units": ["Foundations", "Application"], "constraints": {"bandwidth": "low"}, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "b9660bc78f6fa6b37095fe6dfb0a0001f85ac16eef97ed1622f2c4652050d6da"], ["mobile_learning", {"units": ["Foundations", "Application"], "constraints": {"bandwidth": "low"}, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "b1617916ff2061a2e0a40d0e28d1c4a49f293961597a6d50dde150885da03fb2"], ["game_based_learning", {"objective": "Apply safety procedure", "mechanic": "branching decision", "alignment_rationale": "requires choosing each step", "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "45d00f8c72d01bfd9fe616525db5788d3f7a6d89c1c12cbae44e66c3d4f3c847"], ["gamification", {"objective": "Apply safety procedure", "mechanic": "branching decision", "alignment_rationale": "requires choosing each step", "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "9082bbfceb096f19577be80beb5677704839cf8c542a7e614f60c25eb63134b9"], ["simulation_based_learning", {"objective": "Apply safety procedure", "mechanic": "branching decision", "alignment_rationale": "requires choosing each step", "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "315b9e3e8b402d958fb829175afd8bcca6e3e06d4438b28fbc44a64b204cb9bf"], ["virtual_reality_learning", {"objective": "Apply safety procedure", "mechanic": "branching decision", "alignment_rationale": "requires choosing each step", "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "aba4b87595574609a9a79a17e81df8ddb65699e5437ba4883fd620caebda784f"], ["augmented_reality_learning", {"objective": "Apply safety procedure", "mechanic": "branching decision", "alignment_rationale": "requires choosing each step", "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "a00c0838e8b1ac59831de52a847032bf02dec178cfc29de63f2f25ad14965c12"], ["mixed_reality_learning", {"objective": "Apply safety procedure", "mechanic": "branching decision", "alignment_rationale": "requires choosing each step", "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "2abccc7483027bb6ed17c22fbff2f25ae13d59b0d746b20c6f98ddf81d157097"], ["artificial_intelligence_in_education", {"use_case": "practice hints", "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "12b238cdcf7fe9da9ace72f3d20db36a15357ff6be676ba46493629c83a2c1e7"], ["learning_analytics", {"events": [{"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": true, "duration_seconds": 20}, {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": false, "duration_seconds": 40}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "3632133c809a5289fe35f40daa734f40c51c26a2a54a5a50807464619fac9a8b"], ["educational_data_mining", {"events": [{"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": true, "duration_seconds": 20}, {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": false, "duration_seconds": 40}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "4b394736e2513ebb9b7b72f2b7141c684d6687fcb87df4ac37dfbda6fc360a7f"], ["student_modeling", {"events": [{"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": true, "duration_seconds": 20}, {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": false, "duration_seconds": 40}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "db6fc9c5a79049dae5a1f397d571f511469e2742edf55ea270b2904ca8dde64b"], ["knowledge_tracing", {"events": [{"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": true, "duration_seconds": 20}, {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": false, "duration_seconds": 40}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "360015b6972e30defce2d52062306b8634a57cd7a677dc401d1a9778ec28f63a"], ["affect_detection", {"events": [{"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": true, "duration_seconds": 20}, {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": false, "duration_seconds": 40}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "b72e64604ec11be5134955c0f425eeeeff61785f3cf829e98335157d03221042"], ["gamification", {"objective": "Apply safety procedure", "mechanic": "branching decision", "alignment_rationale": "requires choosing each step", "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "9082bbfceb096f19577be80beb5677704839cf8c542a7e614f60c25eb63134b9"], ["learning_analytics", {"events": [{"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": true, "duration_seconds": 20}, {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": false, "duration_seconds": 40}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "3632133c809a5289fe35f40daa734f40c51c26a2a54a5a50807464619fac9a8b"], ["knowledge_tracing", {"events": [{"learner_id": "p", "skill": "x", "event_type": "voluntary_check_in", "value": "ok"}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "3671d6338b6964eedbb34a92226d2c4b18149ec77b61f0f02b83fd5afa6723ee"], ["knowledge_tracing", {"events": [{"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": true, "duration_seconds": 20}, {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": false, "duration_seconds": 40}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "prior_mastery": 0.4}, "d955e2ba75b6aba7d355e90085a755c056cd78b07c3ca1a9742fc7df83f3b00b"], ["moocs", {"units": ["Foundations", "Application"], "constraints": {"bandwidth": "low"}, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "9f099ef7c7e2b1ded5ca8a301a3441c9a33d43477e430dc2c62394381aca57ea"], ["microlearning", {"units": ["Foundations", "Application"], "constraints": {"bandwidth": "low"}, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "b9660bc78f6fa6b37095fe6dfb0a0001f85ac16eef97ed1622f2c4652050d6da"], ["mobile_learning", {"units": ["Foundations", "Application"], "constraints": {"bandwidth": "low"}, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "b1617916ff2061a2e0a40d0e28d1c4a49f293961597a6d50dde150885da03fb2"], ["learning_objective_writing", {"topic": "Fractions", "learners": {"grade": 5}, "objectives": ["Understand fractions"], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "d454910668900b927673bddac6c33caf55ad1a06a690830d2785a44a9b607a6f"], ["rubric_creation", {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "criteria": [{"name": "reasoning", "weight": 3}, {"name": "accuracy", "weight": 1}]}, "e984475f0fcc2109c6b0ef977bf98eb720de24238e079457260d878e6b11a2d2"], ["adaptive_learning", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "mastery": 0.2}, "01ab4a4344df1a6ee631a951eb5c8f57ed80c8a87b256c41a4b9d60e688e3594"], ["adaptive_learning", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "mastery": 0.8}, "3ab87c851d42549b95e3cd83ecfabaeb476cf16237e9ccae9ee7384c2e4864e8"], ["learning_analytics", {"events": [{"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": true, "duration_seconds": 20}, {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": false, "duration_seconds": 40}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "3632133c809a5289fe35f40daa734f40c51c26a2a54a5a50807464619fac9a8b"], ["learning_analytics", {"events": [{"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": true, "duration_seconds": 20}, {"learner_id": "p1", "skill": "fractions", "event_type": "attempt", "correct": true, "duration_seconds": 20}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "5b97e02f457a2937471666f41c313f51a298965ba123dba175dbfec862e31e4e"], ["affect_detection", {"events": [{"learner_id": "p", "skill": "s", "event_type": "self_report", "value": "ok"}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "0b2c9e955ba6e92944252efb41e8e7ac6ff7e9ae457de42cc7312042f0f175b4"], ["affect_detection", {"events": [{"learner_id": "p", "skill": "s", "event_type": "self_report", "value": "ok"}, {"learner_id": "p", "skill": "s", "event_type": "camera_face", "value": "sad"}], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "20653a0ad1aa31af98236ea592251c3b96bc731022b446e590d328a914d805d4"], ["scaffolding", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "6a676a4528dc274d335db4685571f274a9f3837be4b4447422d2f7bca2077f03"], ["zone_of_proximal_development", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"}, "supports": ["worked examples"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}, "independent_skills": ["a"], "assisted_skills": ["a", "b"]}, "86f3e9ea8af55c63d8ef1ed61b226cde2470cc692390d5de54ca7da4382a2a2a"], ["service_learning", {"challenge": "Reduce school waste", "objectives": ["Evaluate evidence"], "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "6ce5d556ba1d9072a8311653ef8cf093cc5d8f305f49be079e550a0fd4ca7c22"], ["syllabus_creation", {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "b5d4b7a3cf0d4243db672876609172fd9141a4c3aff3f5e477d0e8c918ddedf1"], ["curriculum_design", {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "cd9cfb185d467554fa892771d58ba653c7b192089e4c05e12811d0d9118ba6ed"], ["assessment_design", {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "a65a4bfdc671c437c03873701bbe9c9e3ff014b92ce82d21c4b329fd7d9d3f90"], ["lesson_planning", {"topic": "Fractions", "learners": {"grade": 5}, "objectives": [{"id": "o1", "statement": "Compare fractions"}], "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}], "duration_minutes": 50, "source": {"title": "Teaching evidence", "url": "https://example.edu/evidence"}}, "a883878432d5c1a777add978c19e82f602d0bd5902130c20002b9caf84b7ba34"]]')


def _canon(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


@pytest.mark.parametrize("case", _DEFECT_CASES, ids=[c["id"] for c in _DEFECT_CASES])
def test_junk_inputs_raise_coded_education_error(case):
    """Pre-repair these raised raw AttributeError/TypeError/OverflowError/ZeroDivisionError."""
    with pytest.raises(EducationError):
        execute(case["capability"], copy.deepcopy(case["payload"]))


@pytest.mark.parametrize("name,payload,expected_sha256", _GOLDENS, ids=[g[0] + "#" + str(i) for i, g in enumerate(_GOLDENS)])
def test_valid_input_output_byte_identical(name, payload, expected_sha256):
    """Hashes were computed on the pre-repair module; repair must not alter them."""
    out = execute(name, copy.deepcopy(payload))
    assert _canon(out) == expected_sha256


# --- preservation pins: inputs that SUCCEEDED pre-repair must keep working ---


def test_rubric_bool_weight_preserved():
    out = execute("rubric_creation", {"topic": "T", "learners": {"grade": 5},
        "objectives": [{"id": "o1", "statement": "Compare fractions"}],
        "criteria": [{"name": "reasoning", "weight": True}, {"name": "accuracy", "weight": 1}],
        "source": {"title": "S", "url": "https://example.edu/x"}})
    assert out["result"]["normalized_weights"][0]["weight"] == 0.5


def test_numeric_string_bkt_params_preserved():
    out = execute("knowledge_tracing", {"events": [
        {"learner_id": "p", "skill": "fractions", "event_type": "attempt", "correct": True}],
        "prior_mastery": "0.3", "learn_rate": "0.1", "slip": "0.1", "guess": "0.2",
        "source": {"title": "S", "url": "https://example.edu/x"}})
    assert out["result"]["knowledge_state"][0]["mastery_probability"] == 0.6927  # base-computed BKT posterior, string params preserved


def test_homogeneous_int_event_types_still_mine():
    out = execute("educational_data_mining", {"events": [
        {"learner_id": "p", "skill": "s", "event_type": 7},
        {"learner_id": "p", "skill": "s", "event_type": 5},
        {"learner_id": "p", "skill": "s", "event_type": 7}],
        "min_support": 1, "source": {"title": "S", "url": "https://example.edu/x"}})
    assert out["result"]["frequent_patterns"] == [{"event_type": 5, "support": 1}, {"event_type": 7, "support": 2}]


def test_string_min_support_preserved():
    out = execute("educational_data_mining", {"events": [
        {"learner_id": "p", "skill": "s", "event_type": "attempt", "correct": True},
        {"learner_id": "p", "skill": "s", "event_type": "attempt", "correct": False}],
        "min_support": "2", "source": {"title": "S", "url": "https://example.edu/x"}})
    assert out["result"]["frequent_patterns"] == [{"event_type": "attempt", "support": 2}]


def test_units_as_strings_and_dicts_preserved():
    out = execute("flipped_classroom", {"units": ["week 1", {"title": "week 2"}],
        "source": {"title": "S", "url": "https://example.edu/x"}})
    assert [u["unit"] for u in out["result"]["delivery_plan"]] == ["week 1", "week 2"]


def test_nan_duration_minutes_preexisting_quirk_preserved():
    # NaN duration_minutes passed the >0 guard pre-repair and produced NaN minutes;
    # crash-only repair must not change this pre-existing quirk.
    out = execute("curriculum_design", {"topic": "T", "learners": {"grade": 5},
        "objectives": [{"id": "o1", "statement": "Compare fractions"}],
        "duration_minutes": float("nan"),
        "source": {"title": "S", "url": "https://example.edu/x"}})
    assert out["result"]["sequence"][0]["minutes"] != out["result"]["sequence"][0]["minutes"]  # NaN


# --- cl1410r2: auditor-delta pins (Lane 8 b512h) ---
# Classes below mirror the audit harness's hostile actors.


class _LieInt(int):
    def __lt__(self, other): return False
    def __gt__(self, other): return False


class _EqInt(int):
    def __eq__(self, other): raise RuntimeError("FUZZ_HOSTILE_EQ")
    __hash__ = int.__hash__


class _HostileTuple(tuple):
    def __eq__(self, other): raise RuntimeError("FUZZ_HOSTILE_EQ")
    __hash__ = tuple.__hash__


class _IndexObject:
    def __index__(self): raise RuntimeError("FUZZ_HOSTILE_INDEX")


_SRC = {"title": "Teaching evidence", "url": "https://example.edu/evidence"}
_DESIGN_PAYLOAD = {"topic": "Fractions", "learners": {"grade": 5},
                   "objectives": [{"id": "o1", "statement": "Compare fractions"}],
                   "assessments": [{"name": "exit ticket", "objective_ids": ["o1"]}],
                   "duration_minutes": 50, "source": _SRC}


@pytest.mark.parametrize("bad", [None, 1410, 5.5, True, ["curriculum_design"], {"x": 1}, b"curriculum_design"])
def test_capability_non_string_coded(bad):
    """Pre-repair: raw AttributeError from .lower / TypeError from regex on bytes."""
    with pytest.raises(EducationError, match="unknown capability"):
        execute(bad, copy.deepcopy(_DESIGN_PAYLOAD))


@pytest.mark.parametrize("kw", [{"tenant_id": None}, {"tenant_id": 5}, {"tenant_id": ["x"]}, {"tenant_id": _LieInt(3)},
                                {"actor_id": None}, {"actor_id": 5}, {"actor_id": {"x": 1}}])
def test_tenant_actor_non_string_coded(kw):
    """Pre-repair: raw AttributeError from .strip."""
    with pytest.raises(EducationError, match="tenant_id and actor_id are required"):
        execute("curriculum_design", copy.deepcopy(_DESIGN_PAYLOAD), **kw)


@pytest.mark.parametrize("bad_ids", [None, 5, 1.5, _LieInt(7)])
def test_assessment_objective_ids_non_iterable_coded(bad_ids):
    """Pre-repair: raw TypeError ('NoneType'/'int'/'float' object is not iterable)."""
    p = copy.deepcopy(_DESIGN_PAYLOAD)
    p["assessments"] = [{"name": "exit ticket", "objective_ids": bad_ids}]
    with pytest.raises(EducationError, match="objective_ids must be iterable"):
        execute("curriculum_design", p)


def test_assessment_objective_ids_string_quirk_preserved():
    """A string objective_ids iterates into characters pre-repair and succeeds; crash-only repair keeps it."""
    p = copy.deepcopy(_DESIGN_PAYLOAD)
    p["assessments"] = [{"name": "exit ticket", "objective_ids": "o1"}]
    out = execute("curriculum_design", p)
    assert out["result"]["assessments"][0]["objective_ids"] == ["o", "1"]


def test_hostile_index_object_numeric_fields_coded():
    """float()/int() on an object whose __index__ raises RuntimeError: raw escape pre-repair."""
    with pytest.raises(EducationError):
        execute("adaptive_learning", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"},
                                      "supports": ["worked examples"], "mastery": _IndexObject(), "source": _SRC})
    with pytest.raises(EducationError):
        execute("knowledge_tracing", {"events": [{"learner_id": "p", "skill": "fractions", "event_type": "attempt", "correct": True}],
                                      "prior_mastery": _IndexObject(), "source": _SRC})


def test_hostile_eq_objects_do_not_raise_runtimeerror():
    """EqInt/HostileTuple values must not escape via depth_quality _present or observed_evidence __eq__ calls."""
    out = execute("adaptive_learning", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"},
                                        "supports": ["worked examples"], "mastery": _EqInt(0), "source": _SRC})
    assert out["result"]["mastery"] == 0.0
    out = execute("zone_of_proximal_development", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"},
                                                   "supports": ["worked examples"], "independent_skills": _HostileTuple(("a",)),
                                                   "assisted_skills": _HostileTuple(("b",)), "source": _SRC})
    assert out["result"]["zpd_candidates"] == ["b"]


def test_lie_int_still_rejected_by_range_checks():
    """LieInt bypasses </> but range membership still refuses out-of-range values."""
    with pytest.raises(EducationError):
        execute("adaptive_learning", {"objectives": ["Solve equations"], "learner_profile": {"prior_knowledge": "variable"},
                                      "supports": ["worked examples"], "mastery": _LieInt(5), "source": _SRC})


def test_truthy_hostile_eq_event_type_coded():
    """EqInt(1) is truthy, passes the presence check, then hits event_type == 'attempt'."""
    p = {"events": [{"learner_id": "p", "skill": "s", "event_type": _EqInt(1), "correct": True}],
         "source": _SRC}
    with pytest.raises(EducationError):
        execute("knowledge_tracing", p)


def test_truthy_hostile_eq_result_value_no_runtimeerror():
    """safe_failure flows raw into the result; observed_evidence must not invoke its __eq__."""
    out = execute("game_based_learning", {"objective": "Identify fractions", "mechanic": "sorting game",
                                          "alignment_rationale": "mechanic requires identifying fractions",
                                          "safe_failure": _EqInt(1), "source": _SRC})
    assert "safe_failure" in out["evaluation"]["observed_evidence"]


# --- cl1410r3 pins: string-valued numerics must raise coded EducationError ---
# Each verified raising raw ValueError on the cl1410r2 module.

def test_adaptive_learning_string_mastery_coded():
    with pytest.raises(EducationError):
        execute("adaptive_learning", {"objectives": ["Solve equations"], "learner_profile": {"id": 1},
                                      "mastery": "bad", "source": _SRC})


def test_adaptive_learning_string_threshold_coded():
    with pytest.raises(EducationError):
        execute("adaptive_learning", {"objectives": ["Solve equations"], "learner_profile": {"id": 1},
                                      "advance_at": "soon", "source": _SRC})


def test_knowledge_tracing_string_probabilities_coded():
    ev = [{"learner_id": "l", "skill": "s", "event_type": "attempt", "correct": True}]
    for key in ("prior_mastery", "learn_rate", "slip", "guess"):
        with pytest.raises(EducationError):
            execute("knowledge_tracing", {"events": ev, key: "bad", "source": _SRC})


def test_moocs_string_cohort_scale_coded():
    with pytest.raises(EducationError):
        execute("moocs", {"units": ["u1"], "cohort_scale": "lots", "source": _SRC})


def test_moocs_string_moderation_channels_coded():
    with pytest.raises(EducationError):
        execute("moocs", {"units": ["u1"], "moderation_channels": "some", "source": _SRC})


def test_educational_data_mining_string_min_support_coded():
    ev = [{"learner_id": "l", "skill": "s", "event_type": "attempt", "correct": True}]
    with pytest.raises(EducationError):
        execute("educational_data_mining", {"events": ev, "min_support": "two", "source": _SRC})


def test_microlearning_string_target_minutes_coded():
    with pytest.raises(EducationError):
        execute("microlearning", {"units": ["u1"], "target_minutes": "seven", "source": _SRC})


def test_unit_planning_none_objective_ids_coded():
    with pytest.raises(EducationError):
        execute("unit_planning", {"topic": "Fractions", "learners": {"id": 1}, "objectives": ["Explain halves"],
                                  "assessments": [{"name": "quiz", "objective_ids": None}], "source": _SRC})


def test_junk_keys_for_other_rows_do_not_escape():
    # cl1410r3: the distinctive-computation table built eagerly, so e.g. a junk
    # duration_minutes on an analytics row raised raw ValueError from an
    # unrelated row's float(). Now lazy: unrelated junk keys cannot escape.
    out = execute("learning_analytics", {"events": [{"learner_id": "l", "skill": "s", "event_type": "attempt", "correct": True}],
                                         "duration_minutes": "bad", "mastery": "bad", "min_support": "x",
                                         "cohort_scale": "huge", "target_minutes": "y", "source": _SRC})
    assert out["result"]["distinctive_computation"]["name"] == "attempt_weighted_accuracy"
