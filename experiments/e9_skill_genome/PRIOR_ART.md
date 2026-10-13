# E9 prior-art check (no novelty claim)

Searched 2026-10-13 with web search; abstracts/pages read at the URLs below. Claims are limited to what those pages state.

| Idea in E9 | Prior work | Source |
|---|---|---|
| Learn a library of reusable program abstractions across tasks, then use it to speed up search (wake-sleep library learning) | DreamCoder (Ellis et al., PLDI 2021) | https://dl.acm.org/doi/10.1145/3453483.3454080 ; https://royalsocietypublishing.org/rsta/article/381/2251/20220050/112456/DreamCoder-growing-generalizable-interpretable |
| Corpus-guided library learning by top-down synthesis | Stitch (Bowers et al., POPL 2023) | https://arxiv.org/abs/2211.16605 |
| Library induction by compression plus documentation, with LLM-guided synthesis | LILO (Grand et al., ICLR 2024) | https://arxiv.org/abs/2310.19791 ; https://proceedings.iclr.cc/paper_files/paper/2024/hash/819cebb05f993840e8a52d7564c5c282-Abstract-Conference.html |
| Ever-growing library of executable-code skills, added after generation and verification, retrieved for new tasks, lifelong learning without parameter updates; iterative prompting on execution feedback | Voyager (Wang et al., 2023) | https://arxiv.org/abs/2305.16291 |
| Skill-library lifecycle survey (admission, validation, evolution) | Awesome-Dynamic-Agent-Skills survey page (not read in full; listed as a lead only) | https://yubol-bobo.github.io/Awesome-Dynamic-Agent-Skills/ |

What E9 does that these cover: library learning, executable skills, no-retraining acquisition, verification before adding (Voyager-style own-test check), retrieval into search.
What I did not find in the pages I read, and did not exhaustively search for: preconditions/expected-output contracts as explicit genome fields checked at run time, validation-gated admission scored on unseen tasks with a set-level (batch) variant and leave-one-out retirement. Absence from the pages I read is not evidence of absence from the literature. No novelty claim is made; E9 is a small controlled replication-style study of library admission policy in an authored synthetic domain.
