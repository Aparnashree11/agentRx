#!/usr/bin/env bash
# Rollback rehearsal for RELEASE_PLAN.md Section 4. Runs in a throwaway clone; never pushes.
# Usage: run from inside any clone of the repo:  bash rollback_rehearsal.sh [repo-url]
set -uo pipefail
SRC_URL="${1:-$(git remote get-url origin)}"
WORK="$(mktemp -d /tmp/rollback-rehearsal.XXXXXX)"
LOG="$WORK/rehearsal.log"
exec > >(tee "$LOG") 2>&1
ts() { date '+%Y-%m-%d %H:%M:%S %Z'; }
hr() { echo; echo "---------------- $* ----------------"; }

echo "Rehearsal started: $(ts)   scratch dir: $WORK"
echo "python3: $(command -v python3) ($(python3 --version 2>&1))   git: $(git --version)"
git clone -q "$SRC_URL" "$WORK/agentRx" || { echo "CLONE FAILED"; exit 1; }
cd "$WORK/agentRx"
git fetch -q --tags

hr "Step 1: record start"
T0=$(date +%s)
if git rev-parse -q --verify refs/tags/week11-release >/dev/null; then
  git checkout -q week11-release; START_REF=week11-release
else
  echo "week11-release tag NOT found -> starting from origin/main (merged branch)"
  git checkout -q --detach origin/main; START_REF=origin/main
fi
START=$(git rev-parse --short HEAD)
echo "start ref: $START_REF   HEAD: $START   ($(git log -1 --format='%ad %s' --date=iso))"
echo "data/benchmark_versions/tau_retail/:"; ls data/benchmark_versions/tau_retail/
for b in step-decomposition presentation-change-v2 step-decoy baseline-results; do
  git merge-base --is-ancestor "origin/$b" HEAD 2>/dev/null && echo "  $b: merged" || echo "  $b: NOT merged"
done

hr "Step 2: clear old reproducer output"
ls -l /tmp/baseline_r*.json 2>/dev/null || echo "(no old /tmp/baseline_r*.json)"
rm -f /tmp/baseline_r*.json; ls /tmp/baseline_r*.json 2>/dev/null || echo "cleared"

hr "Step 3: switch to target"
git fetch -q --tags && git checkout -q ac01913 && echo "checkout ac01913 OK -> $(git rev-parse --short HEAD)" \
  || { echo "CHECKOUT ac01913 FAILED (target unreachable)"; exit 2; }
git branch -r --contains ac01913 | sed 's/^/  reachable from /'

hr "Step 4: reproduce"
bash scripts/reproduce_baseline.sh; echo "reproduce_baseline.sh exit code: $?"
T4=$(date +%s)
echo "Computed values read from /tmp/baseline_r*.json:"
for r in r1 r2 r3; do
  python3 -c "import json;d=json.load(open('/tmp/baseline_$r.json'))['summary'];print('  $r step=%.4f category=%.4f'%(d['step_accuracy']['rate'],d['category_accuracy']['rate']))" \
    || echo "  $r: NO OUTPUT FILE"
done
echo "Scorer with stderr visible (separate output files):"
for r in r1 r2 r3; do
  python3 baselines/score_runs.py --ground-truth data/ground_truth/tau_ground_truth.json \
    --out "/tmp/rehearsal_vis_$r.json" "results/track_a/baseline/artifacts/tau_sol_$r.json" > "$WORK/scorer_$r.out" 2> "$WORK/scorer_$r.err"
  echo "  $r exit=$?  stderr_lines=$(wc -l < "$WORK/scorer_$r.err" | tr -d ' ')  stdout_lines=$(wc -l < "$WORK/scorer_$r.out" | tr -d ' ')"
  sed 's/^/      err: /' "$WORK/scorer_$r.err" | head -5
done
python3 - <<'PY'
import json
want = {"r1": (0.4138, 0.3448), "r2": (0.4138, 0.2759), "r3": (0.4138, 0.3103)}
ok = True
for r, (s, c) in want.items():
    d = json.load(open(f"/tmp/baseline_{r}.json"))["summary"]
    gs, gc = round(d["step_accuracy"]["rate"], 4), round(d["category_accuracy"]["rate"], 4)
    m = (gs, gc) == (s, c); ok &= m
    print(f"  {r}: step {gs} (want {s})  category {gc} (want {c})  {'MATCH' if m else 'MISMATCH'}")
print("KNOWN OUTPUT MATCHED:", "yes" if ok else "no")
PY

hr "Step 5: hash check must abort on a changed input"
GT=data/ground_truth/tau_ground_truth.json
python3 - "$GT" <<'PY'
import sys
p = sys.argv[1]; b = bytearray(open(p, "rb").read())
i = b.find(b"e"); b[i:i+1] = b"E"; open(p, "wb").write(bytes(b))
print(f"  changed 1 byte at offset {i} of {p}")
PY
rm -f /tmp/baseline_r*.json
bash scripts/reproduce_baseline.sh; RC=$?
echo "reproduce_baseline.sh exit code with tampered input: $RC  ($([ $RC -ne 0 ] && echo 'ABORTED as expected' || echo 'DID NOT ABORT'))"
ls /tmp/baseline_r*.json 2>/dev/null && echo "  WARNING: score files were written" || echo "  no score files written"
git checkout -- . && git status --short && echo "restored: $(git status --porcelain | wc -l | tr -d ' ') changed files"

hr "Step 6: bookkeeping on a throwaway branch (not pushed)"
git checkout -q -b rehearsal/withdraw-test
README=data/benchmark_versions/README.md
echo "" >> "$README"
echo "- **WITHDRAWN (rehearsal only, $(date +%Y-%m-%d))**: example release withdrawn under RELEASE_PLAN.md Section 4." >> "$README"
CL=$(ls CHANGELOG* 2>/dev/null | head -1); [ -z "$CL" ] && CL=CHANGELOG.md && echo "(no changelog file existed; created $CL)"
echo "- $(date +%Y-%m-%d): rehearsal - withdrew example release; rolled back to ac01913 (tau_retail/baseline/v1.0.0)." >> "$CL"
git add -A && git -c user.name=rehearsal -c user.email=rehearsal@local commit -q -m "rehearsal: withdraw example release" \
  && echo "committed locally on $(git branch --show-current): $(git log -1 --format=%h)"
git diff --stat HEAD~1 HEAD

hr "Step 7: switch back to the release"
if git rev-parse -q --verify refs/tags/week11-release >/dev/null; then git checkout -q week11-release; else git checkout -q --detach "$START"; fi
END=$(git rev-parse --short HEAD); T1=$(date +%s)
echo "HEAD now $END; recorded at step 1: $START  -> $([ "$END" = "$START" ] && echo MATCH || echo MISMATCH)"
echo "Time to switch (step 1 -> end of step 4): $((T4 - T0)) s"
echo "Total rehearsal time (step 1 -> step 7): $((T1 - T0)) s"
echo "Remotes pushed to: none. Rehearsal finished: $(ts)"
echo "LOG: $LOG"
