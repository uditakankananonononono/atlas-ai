"""Real local model critique on synthetic student drafts (not user data). Prints every item with its label."""
import json, os, time
from app.modules.m23_study_abroad.essay_critique import critique, router_from_env
DRAFTS = {
"A": ("I consider myself a dedicated student and I am passionate about helping people. When my grandfather's hearing aid broke "
      "and the repair cost more than our monthly rent, I taught myself to solder from library books and fixed it in three "
      "weekends. Now I build low cost hearing devices for my neighbors. I want to study mechanical engineering."),
"B": ("Leadership is important to me. I am a determined leader and a natural leader. As captain of the debate team I led "
      "practices every Tuesday, helped novices write their first cases, and stayed late when our coach was sick, and at "
      "the state tournament our youngest member won her round after we rehearsed her closing argument twelve times in the "
      "school parking lot while it rained and everyone else had already gone home."),
}
r = router_from_env()
for k, d in DRAFTS.items():
    t0 = time.time(); out = critique(d, r)
    print(f"\n=== draft {k} ({time.time()-t0:.1f}s) mode={out['mode']} model={out['model']} detail={out['detail']!r}")
    for i in out["items"]:
        print(" -", i["source"], i["type"], "| quote:", repr(i["quote"][:90]), "|", i.get("observation", ""), "|", i["question"])
    print(" rejected model lines:", out["rejected_model_lines"])
