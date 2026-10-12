#!/bin/bash
# E4 step 2 on Colab free T4. Arms: base (published archive), A-only, B-only, joint A+B. One seed.
# Run from a dir holding gen_tasks.py and eval_tasks.py. Writes to a NEW timestamped run dir (refuses to reuse one).
# Every command's full output goes to logs/NAME.log and its exit status plus wall seconds to logs/status.tsv.
# After each arm it prints a base64 tar of logs between ===BUNDLE markers so logs can be copied off the VM immediately.
# The script exits non-zero and prints SUMMARY FAIL unless every arm has a built archive and a complete 18-row eval file.
# Needs: pip install "cactus-needle[train,gpu]==3.0.5" "jax[cuda12]==0.9.0" "flax==0.10.7"; checkpoint at /content/ck/checkpoints/needle3.safetensors
set -uo pipefail
export NEEDLE_TELEMETRY=0 DO_NOT_TRACK=1
CK=/content/ck/checkpoints/needle3.safetensors
FAILS=0
RUN=run_$(date -u +%Y%m%dT%H%M%SZ)
[ -e "$RUN" ] && { echo "refusing existing $RUN"; exit 2; }
mkdir -p "$RUN/logs" "$RUN/art" || exit 2
cp gen_tasks.py eval_tasks.py "$RUN"/ || exit 2
cd "$RUN" || exit 2
echo "RUNDIR=$PWD"
printf 'name\trc\twall_s\tflags\tcommand\n' > logs/status.tsv
bundle() { tag=$1; { sha256sum art/*.safetensors art/*.cact 2>/dev/null; ls -l --time-style=full-iso art; } > logs/hashes_$tag.txt; echo "===BUNDLE $tag"; tar czf - logs | base64 -w0; echo; echo "===ENDBUNDLE $tag"; }
# run1 NAME CMD...: one attempt (first deletes the files listed in $OUTS so no partial output from an earlier attempt survives), full log, status row. Returns the command's exit status.
run1() { name=$1; shift; rm -f $OUTS; t0=$SECONDS; "$@" > logs/$name.log 2>&1; rc=$?; printf '%s\t%s\t%s\t%s\t%s\n' "$name" "$rc" "$((SECONDS-t0))" "${XLA_FLAGS:-none}" "$*" >> logs/status.tsv; echo "### $name exit=$rc"; return $rc; }
# run NAME CMD...: one plain attempt; on failure one retry with XLA_FLAGS=--xla_gpu_enable_triton_gemm=false (workaround guess, cause not isolated). Both logs kept.
run() { name=$1; shift; run1 "$name" "$@" && return 0; XLA_FLAGS=--xla_gpu_enable_triton_gemm=false run1 "${name}_retry" "$@"; }
python gen_tasks.py > logs/gen_tasks.log 2>&1 || { echo "gen_tasks failed"; exit 2; }
cat A_train.jsonl B_train.jsonl > AB_train.jsonl || exit 2
# rows_ok ARM: eval file has exactly 18 lines, each parseable JSON with a "match" key.
rows_ok() { python - "logs/rows_$1.jsonl" <<'PY'
import json, sys
try:
    rows = [json.loads(l) for l in open(sys.argv[1])]
    ok = len(rows) == 18 and all("match" in r for r in rows)
except Exception:
    ok = False
sys.exit(0 if ok else 1)
PY
}
arm_fail() { echo "ARM $1 incomplete: $2"; FAILS=$((FAILS+1)); }
# base: build and eval must both return 0, archive nonempty, 18 parsed rows
rm -f logs/rows_base.jsonl
if OUTS="art/base.cact" run build_base needle build $CK --out art/base.cact && [ -s art/base.cact ] && OUTS="logs/rows_base.jsonl" run eval_base python eval_tasks.py art/base.cact logs/rows_base.jsonl A_test.jsonl B_test.jsonl && rows_ok base; then :; else arm_fail base "build/eval rc nonzero, empty archive, or rows not 18 parsed"; fi
bundle base
for arm in A B AB; do
  rm -f art/ad$arm.safetensors art/ad$arm.cact logs/rows_$arm.jsonl
  # every step's final return code must be 0 and its output file nonempty and fresh (removed above), else the arm fails
  if OUTS="art/ad$arm.safetensors" run finetune_$arm needle finetune ${arm}_train.jsonl --checkpoint $CK --epochs 1 --batch-size 4 --lora-rank 4 --max-len 256 --val-split 0 --out art/ad$arm.safetensors --checkpoint-dir art/ck_$arm \
     && [ -s art/ad$arm.safetensors ] \
     && OUTS="art/ad$arm.cact" run build_$arm needle build $CK --lora art/ad$arm.safetensors --out art/ad$arm.cact && [ -s art/ad$arm.cact ] \
     && OUTS="logs/rows_$arm.jsonl" run eval_$arm python eval_tasks.py art/ad$arm.cact logs/rows_$arm.jsonl A_test.jsonl B_test.jsonl && rows_ok $arm; then :; else arm_fail $arm "finetune/build/eval rc nonzero, empty artifact, or rows not 18 parsed"; fi
  bundle $arm
done
if [ $FAILS -eq 0 ]; then echo "SUMMARY OK: all 4 arms complete"; else echo "SUMMARY FAIL: $FAILS arm(s) incomplete; see logs/status.tsv"; fi
exit $FAILS
