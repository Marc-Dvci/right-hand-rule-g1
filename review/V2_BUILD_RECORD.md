# V2 development record — 10 November 2026

> The sections below preserve the earlier RC1 development record. The selected
> RC2 now uses 0.5 Nm calibration and bounded wall reacquisition. All 64 source
> tests and 16 separate selected-controller damping/push stresses pass. A
> 7,797-call sensor-only replay matches every command exactly. Full fresh
> development and native checks are in progress; the topology-disjoint final
> cohort remains unopened. Current scope is in `PROJECT_AUDIT_V2.md`, and the
> final measured tables will be in `review/V2_RESULTS.md`.

V1.0.0 remains the qualified release. This branch contains the selected V2
candidate, which is still undergoing geometry, perturbation and exact-image
qualification. No Arena upload or robot attempt has been made.

## Completed evidence

The narrow turn correction was rerun on **all 100 retired V1 episodes** at the
same 400-second limit, nominal timing, randomized dynamics, widths and sensors.
Independent re-scoring checked both versions' trajectories and matched every
scene and randomization draw. Results: **94/100 → 99/100 exits**, zero checker
stops and actual limit findings in both versions. All six original failures
were repaired; seed 26111544 became stuck. Peak hand-force resultant fell from
175.36 to 112.70 N; peak thrash fell from 0.712 to 0.621. Median successful time
changed from 157.42 to 163.28 seconds. These are development data over 14
topologies, not a new holdout. The paired exact McNemar p-value is 0.125, so
the observed gain alone does not establish significance at 5%.

`review/results/turn-only-paired.json` records the complete paired inventory,
independent scores, source/trace/report hashes and all improvements/regressions.

The turn-only controller also exited **12/12 declared development topologies**
without findings. The first randomized gravity/prediction candidate completed
only **1/10** additional 40 ms mazes, including three thrash stops, and was
rejected. Reducing waist-yaw action/extra spring authority subsequently passed
**24/24** randomized flat walking/turning/sidestepping cases at 0/40 ms.

The touch estimator had been using newly issued commands even when an older
command was still applied. Aligning it with its own two-frame-old command
history repaired **3/3 matched delayed maze failures**, reducing their
bandwidth-matched force-estimation errors. A minimum-residual multi-hypothesis
alternative remained inconsistent (6/9 exits), and is disabled in the selected
candidate.

The selected candidate instead identifies command age before navigation. A
0.35 Nm wrist-roll PRBS excitation and a small local input/output regression
use only measured joint q/dq and locally issued commands. No evaluator delay,
contact or base state enters the policy. It identified **24/24 randomized
0/20/40 ms starts** correctly, with zero findings. The fit-confidence number is
a relative model-selection heuristic, not a statistical probability. An
ambiguous fit stops navigation while balance commands continue. Calibration
requires a free-space start and has not been qualified on a physical robot or
for arbitrary varying delays.

With one unchanged configuration, the calibrated controller exited
**18/18 development mazes**, six seeds at each of 0/20/40 ms, with zero checker
stops or actual limit findings. These use V2's **600-second** limit; one case
took 402.24 seconds, so this is not an 18/18 result at V1's 400-second limit.

The original stalled-case detector relied on instantaneous foot-odometry speed;
stance oscillation could prevent it firing despite zero net travel. Recovery
now checks five-second estimated displacement. Seed 26111544 exited in 275.16 s
under that isolated correction; seeds 26111503 and 26111594 also exited.
Recovery attempts are bounded. Left turns after an arc now anchor to measured
IMU yaw when the selected option is enabled, avoiding a mismatch between an
integrated arc reference and actual yaw.

## Reproduction and audit improvements

- Direct API, harness and ROS image load the same mandatory configuration.
  Missing settings fail explicitly. The ARM64 base image is pinned by digest.
- Physics-rate contact measurements now sum individual force magnitudes,
  record 100/250 ms mean loads, time above thresholds, accumulated load and
  nonhand wall contacts. Lower hand peaks do not establish lower total loads.
  Softer-arm variants were not promoted: some loads transferred to the body.
- A stalled pilot recorded a **361.38 N nonhand wall-load peak**; this serious
  simulation limitation must not be omitted or described as a gentle-contact
  or hardware-safety qualification. The original 20 N contact gate is unmet.
- Final topology evaluation refuses configuration/time/seed overrides,
  duplicates, held-out development geometry and selected subsets labeled as a
  full final cohort. The 100 distinct topology holdouts are still unopened.
- Native CI verifies the exact image filesystem, complete submitted control,
  active required checks, sufficient handoff coverage and zero actual findings.
- **56 development tests pass.** Canonical kit source/assets remain hash-checked.
  Extra damping and push tests are explicitly separate evaluator stresses.

## In progress / required before release

The selected settings are `config/control.json` (identical to
`review/candidates/calibrated-yaw-development.json`). Broader development
geometry and a 16-case damping/push suite are running. The new ARM64 image must
still be built/audited and run natively, and all six start outcomes retained.
Then freeze source/settings and evaluate the 100 distinct, previously unopened
topologies with each delay stratum reported separately. Rebuild the film,
judge-facing results and complete size-checked package from that version's
evidence only. Retain all failures. V1's published scores/image never qualify V2.

The live field and current runner guide were rechecked on 10 November.
The strongest distinction remains the complete task on standard joint/IMU
inputs. Competitors' other tasks are not a common benchmark; see
`COMPETITIVE_AUDIT.md` for source-linked comparisons. Competition-winning status
and universal technical superiority have not been established.
