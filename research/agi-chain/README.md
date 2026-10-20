# agi-chain research artifacts

Status of this folder, stated plainly:

- Lane results before c27 exist only as reported messages. Their artifacts were not recovered. Nothing from them is reconstructed or claimed here.
- c27 and c28: the scripts are re-creations from the transcript of the originals, re-executed. The outputs match the reported numbers (c27 real_exp 0.899 / iid_raw 0.901 at noise 0.5; c28 load 0.10 mag0.25 0.988 / rand0.25 0.742). They are not hash-identical to the lost originals.
- c29: the NK-landscape mutation-rate scout (c29mut.py, seeds 880013000-029, 0 fixture seeds) and the saved prior-art search output (prior-art-c29.log).
- c27 and c28 were both negative results. Firsts: 0.

## Contents

- c27/c27door.py, c27door.out, door_response_matrix.csv (DoOR master data, about 296 KB)
- c28/c28prune.py, c28prune.out
- c29/c29mut.py, prior-art-c29.log
- c30/c30wta.py, c30wta.out, prior-art-c30.log: k-WTA vs fixed threshold. Negative, firsts 0. WTA wins at every correlation and is gain invariant by construction.
