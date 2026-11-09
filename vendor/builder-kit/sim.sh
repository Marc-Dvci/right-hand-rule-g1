#!/usr/bin/env bash
# Public simulation-only entry point; the upstream checker is unchanged.
set -euo pipefail
kit_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
case "${1:---help}" in
  --help|-h) echo 'Usage: ./sim.sh --seconds 60 [--image NAME] [--scene containers/upload/environment/scene.xml] [--counterfactuals] [--output DIR]'; echo 'Docker Compose and Python 3 required. Put submission.tar in containers/upload. Simulation only.'; exit 0 ;;
  stop) G1_SIM_BACKEND=compose bash "$kit_dir/sim-upstream.sh" stop; exit ;;
esac
out="$kit_dir/containers/sim/output"
counterfactuals=0
args=()
while [[ $# -gt 0 ]]; do
 case "$1" in
 --seconds|--image|--scene|--output)
   flag="$1"; value="${2:?Missing flag value}"
   [[ "$flag" != --output ]] || out="$value"
   args+=("$flag" "$value"); shift 2 ;;
 --counterfactuals) counterfactuals=1; args+=("$1"); shift ;;
 --safety-checks) shift ;;
 *) echo "Unsupported builder-kit flag: $1. This kit tests submitted containers with safety checks enabled." >&2; exit 2 ;;
 esac
done
export G1_SIM_BACKEND=compose G1_SIM_THRASH_MODE=enforce
status=0
bash "$kit_dir/sim-upstream.sh" --safety-checks "${args[@]}" || status=$?
python3 "$kit_dir/check_report.py" "$out" --counterfactuals "$counterfactuals" || exit 2
exit "$status"
