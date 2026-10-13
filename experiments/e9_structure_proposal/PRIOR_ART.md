# Prior art checked 2026-10-13

No novelty claim. Six primary research sources were read; these establish that
active causal discovery, online approximate structure learning and active program
synthesis are existing areas. This is not a systematic novelty review or a
comparative reproduction of their results. Primary literature is the relevant
source type here, not product reviews or community opinions.

- He and Geng, 2008, JMLR, "Active Learning of Causal Networks with Intervention
  Experiments and Optimal Designs". Learns a Markov equivalence class from
  observations, then uses optimal interventions to orient edges. E9 does not
  implement their latent/DAG structure discovery.
  https://www.jmlr.org/papers/v9/he08a.html
- Zemplenyi and Miller, 2021 preprint, "Bayesian optimal experimental design for
  inferring causal structure". Posterior-entropy intervention choice and graph
  posterior sampling. E9 reuses E6's simpler exact binary entropy computation.
  https://ar5iv.labs.arxiv.org/html/2103.15229
- "Optimal experimental design via Bayesian optimization: active causal
  structure learning for Gaussian process networks", 2019 preprint. Active
  causal structure learning with GP mechanisms. E9's finite Boolean programs
  are a much narrower setting.
  https://ar5iv.labs.arxiv.org/html/1910.03962
- "Active Learning for Neurosymbolic Program Synthesis", 2025 preprint.
  Synthesized programs and query selection to prune hypothesis spaces. E9
  combines bounded bottom-up synthesis with EIG/cost, no neural components.
  https://ar5iv.labs.arxiv.org/html/2508.15750
- "Active learning for optimal intervention design in causal models", Nature
  Machine Intelligence, 2023-10-02. Relevant existing active-intervention work;
  no head-to-head benchmark against this paper is claimed.
  https://www.nature.com/articles/s42256-023-00719-0
- Bramley, Dayan, Griffiths and Lagnado, "Formalizing Neurath's Ship:
  Approximate Algorithms for Online Causal Learning". Existing approximate
  online causal-model revision and intervention selection; E9's beam is not
  their method and no biological-learning claim follows.
  https://cocosci.princeton.edu/papers/Bramley_PsychRev.pdf
