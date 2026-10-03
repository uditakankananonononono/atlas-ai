"""Multi-turn run of the adaptive student interviewer against a REAL local model server.

Usage (llama.cpp / Ollama OpenAI-compatible server on loopback):
  INSTINCT_ORNITH_URL=http://127.0.0.1:8089/v1 INSTINCT_ORNITH_MODEL=qwen2.5-0.5b \
  ATLAS_DATABASE_URL=sqlite:////tmp/esai-real.db PYTHONPATH=backend python scripts/verification/esai_interview_real_model.py

Student answers are a SYNTHETIC persona written for this test, not a real student.
Prints every question the model wrote, every quote it extracted (kept/rejected), and counts.
No success is claimed: the output shows what the model did, including rejections and fallbacks.
"""
import json, os, sys, time
from app.modules.m23_study_abroad.adaptive_interviewer import interviewer_from_env
from app.modules.m23_study_abroad.interview import IdentityInterviewRepository
from app.modules.m23_study_abroad.story import BrandIdRow
from app.core.database import SessionLocal

ANSWERS = [
    "When my family moved to a new town in eighth grade I didn't know anyone, so I started a robotics club at my school because nobody else would, and I taught twelve younger kids to solder.",
    "I stayed after school every day even when only two people came, because I promised the younger kids that the club would still be there next week.",
    "I get the most energy when I take something broken and make it work again, like repairing the old radio my grandfather left and hearing it play.",
    "My teachers say I'm patient. Last spring a sophomore couldn't get her circuit to work and I sat with her for two hours until she found the loose wire herself.",
    "I want to study mechanical engineering and build low cost medical devices, because my grandfather's hearing aid cost more than our rent.",
]

interviewer = interviewer_from_env()
if interviewer is None:
    sys.exit("set INSTINCT_ORNITH_URL (loopback) and INSTINCT_ORNITH_MODEL")
repo = IdentityInterviewRepository("real-model-check", interviewer=interviewer)
s = repo.start("college")
print("OPENING (fixed script):", s["next_question"])
for i, a in enumerate(ANSWERS, 1):
    t0 = time.time()
    s = repo.answer(s["id"], a)
    t = s["interviewer"]["turns"][-1]
    print(f"\n--- turn {i} ({time.time()-t0:.1f}s) ---\nSTUDENT: {a}")
    print("NEXT QUESTION:", s["next_question"], f"[{s['next_question_source']}]")
    print("extraction:", t["extraction_mode"], "proposed", t["proposed_items"], "rejected", t["rejected_items"], "|", t["detail"])
with SessionLocal() as db:
    b = db.get("BrandIdRow" and BrandIdRow, "real-model-check")
    grounded = [e for e in b.evidence if e.get("provenance")]
print("\nBRANDID values:", b.values, "\nstrengths:", b.strengths, "\npatterns(beyond raw answers):", b.patterns[3:])
print("proposed (UNCONFIRMED) evidence items:")
for g in grounded:
    print(" ", g["kind"], "|", g["label"], "| quote:", repr(g["quote"]), "| turn", g["turn"])
print("\nSUMMARY", json.dumps({"turns": len(ANSWERS), "model_backed_question_turns": sum(1 for x in s["interviewer"]["turns"][:-1] if x["question_source"] == "adaptive_local_model"),
      "fallback_question_turns": sum(1 for x in s["interviewer"]["turns"][:-1] if x["question_source"] == "fixed_script_fallback"),
      "grounded_items": len(grounded), "rejected_items": sum(x["rejected_items"] for x in s["interviewer"]["turns"])}))
