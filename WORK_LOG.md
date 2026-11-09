# RIGHT HAND RULE — build and audit log

## Objective

Implement the current `../01_PLAN.md`: touch navigation on a free-standing Unitree G1, with NVIDIA's attributed pretrained locomotion networks. Navigation is scripted. Only joint positions, joint velocities, pelvis quaternion and gyro enter the controller. Simulator state is reserved for evaluation.

## Gates fixed before evaluation

1. Network export: max absolute action error <= 1e-4 against ONNX Runtime on 10,000 recorded observations. Straight walking, lateral walking and relative turns under the unmodified kit's checker. Thrash peak <= 1.05; no recorded torque/speed exceedances or falls. Native ARM64 container checks are a separate gate.
2. Touch: compare inferred forces with simulator contact truth; tune on development seeds only. Validate straight walls and both corner directions.
3. Navigation: freeze final seeds before evaluation; >=90/100 exits, zero falls and checker findings. Neutral, absent and shuffled touch controls use identical seeds.
4. Package: exact controller in ARM64 ROS 2 container, actual scene, native ARM64 reports, source, notices, sensor contract, audited MP4. Do not claim this gate before actual container execution.

## Initial audit (2026-11-09)

- Read the current plan and competitor review. The archived GYRE plan is superseded.
- Checked the live challenge and G1 guide. Deadline remains November 15, 2026, 23:59 ET.
- Kit source includes torque and velocity warnings that do not necessarily stop a run. The evaluator will count these separately; `within_limits` alone is insufficient.
- Existing simulation dependencies are in Ubuntu-22.04 under `/home/dev/.cache/him-rallyforge/final-v1/.venv-linux`. Reuse dependencies without editing the earlier project.
- No publication, external messages, paid compute, or credential changes are part of this local build.

## Development audit and corrections

- Both original model binaries match the NVIDIA digests in the kit. The GitHub raw endpoint initially returned an LFS pointer; the binary was retrieved from GitHub's media endpoint and verified before use.
- The supplied plan incorrectly says the original kit hand has no collision geometry: the unchanged XML includes three palm spheres per hand. The custom scene disables these and uses the disclosed low-friction capsule. The original kit files match every `UPSTREAM_FILES.json` hash and the archived public ZIP. Fresh HTTP download returned 403; the cached archive's digest is recorded in `research/kit-integrity.json`.
- An early contact logger only counted the new capsule and missed original palm-sphere contact. `wall-001` force-truth numbers are invalid for estimator evaluation; later runs correctly count all palm geoms.
- An early maze exit condition accepted entering the exit half-plane from outside. `evidence/development/maze-000-soft` is invalid as maze-success evidence. The current metric requires an outward line crossing inside the doorway and rejects leaving via the entrance. This is a scoring correction, not a controller success.
- Early fixed right turns could become trapped at a partition end. A contour-seeking arc replaces the fixed right turn. Left turns remain relative IMU turns. Wall-line fits remain logging-only until odometry accuracy qualifies their use.
- Restoring the pretrained waist impedance through bounded feedforward eliminated the soft-waist saturation seen in early experiments. Arm contact uses lower effective stiffness through bounded feedback torque; the host profile is unchanged.
- Stance-foot odometry now accounts for foot rotation about the lowest sole contact, instead of treating the ankle origin as stationary.
- On 10,000 recorded histories per network, both NumPy exports match ONNX Runtime to max absolute error `2.6226043701171875e-6`. Test fixtures retain independent ONNX outputs.
- Twelve contract and physics tests pass. They include all upstream file hashes and randomized comparisons of arm FK, Jacobians and gravity against MuJoCo.
- Strictly scored development maze 0 was exited in 196.00 simulated seconds, no kit warnings, no fall, thrash peak 0.519. This is a development result, not a final-seed robustness claim.

Native ARM64 container checks, randomized evaluation, touch-accuracy gates and the final 100-maze gate remain unclaimed until their actual results exist.

## Container and tuning progress

- The ROS setup scripts require nounset to be disabled while sourcing their environment. This caused the first no-command run and is fixed in our entrypoint.
- With the default ARM interpreter, ROS could not discover the checker service. The installed QEMU 10.2.3 resolves discovery. The wrapper temporarily changes binfmt, runs the kit, and restores the exact original interpreter registration in `finally`.
- `evidence/container-qemu/standard-004-qemu10/builder-check.json` reports `simulation_checks_complete`: 60.04 simulated seconds, handoff at 2.00 seconds, 3,001 accepted commands, no warnings. This is a real ARM64-image container run under emulation, not native ARM64 or hardware qualification.
- CMA-ES tuning changes immutable parameter JSON per episode. It uses only development seeds 0, 4, 5 and verifies that policy source/weights do not change during the search. Trial 6 exits all three with no warnings. Held-out layouts and final-seed randomization remain separate.
- The Cartesian arm-impedance experiment and force-based heading snapping reduced navigation reliability and were rejected. The simpler compliant joint controller reproduces the strongest baseline (maze 0: 196.00 seconds).
- Added deterministic dynamics/sensor perturbations, including effective floor friction (foot priority otherwise overrides the plane). Seventeen tests pass.
- A 75-second development replay is in `dist/preview-development.mp4`. It replays saved qpos only. Transparency exposes the motion; the introductory contact trace is explicitly labeled as simulator reference data.
- The plan's public-repository assumption is outdated: GitHub's January 29, 2026 changelog allows standard ARM64 runners in private repositories against included minutes. No GitHub write, paid compute, publication or external message has been performed.

## Approved publication and final freeze

- The user explicitly approved publishing the project/image to a public GitHub repository and running free native ARM64 checks. Repository: https://github.com/Marc-Dvci/right-hand-rule-g1 . `validation-v0` preserves the early development image and replay. No HIM Arena upload or hardware attempt has occurred.
- CMA-ES completed 40 candidates using development seeds 0, 4 and 5. Trial 012 was selected after development validation: the same configuration exited all ten deterministic seeds 0–9 and all ten randomized seeds 10–19, at nominal timing. Other candidates' results are not pooled into that count. One deterministic run recorded diagnostic target clipping; there were no actual limit findings. These are development results.
- First native run: https://github.com/Marc-Dvci/right-hand-rule-g1/actions/runs/42645739577 . Standard scene passed 60 seconds/3,001 commands, no warnings. The 240-second task run ended with a report-time plant-response timeout and a truncated trace. Timing suggests report export exceeded its RPC deadline; this is an inference, not proof that the task passed. A disclosed isolated-copy patch extends only the post-run `report` RPC timeout from 10 to 60 seconds. Canonical kit, dynamics, active control deadlines and checks remain unchanged. The rerun must establish the outcome.
- Additional 20/40 ms command delays are separate stress tests. High-gain waist response is sensitive to full-frame delay. Fixed/limited-waist and prediction experiments did not generalize in mazes and were rejected; `harness/experimental_transport.py` is excluded from the image. Production uses only the bounded observation-gap adapter.
- Before opening the final 100 seeds, protocol v2 declares nominal timing as the primary distribution and records delay stress separately. This narrows the original plan's latency gate explicitly. No latency-robustness or hardware-readiness claim is made. Final source/configuration/assets are frozen by SHA-256, and no controller tuning is allowed after evaluation.
- 27 tests pass, covering model parity, sensor isolation, physics/kinematics, timing, original kit hashes, independent exit scoring, and isolation of the report-export fix.

## Completed evaluation and native task checks

- Frozen final split: 94/100 exits, zero falls, checker stops or actual limit findings; peak thrash 0.71166646, median successful time 157.42 s. These are 100 randomized episodes over 14 distinct topologies, not 100 distinct layouts. All six navigation failures are retained. Independent trace scoring and exact randomization/source/configuration checks agree for every episode.
- Matched first-ten controls: neutral 0/10, touch off 0/10, fixed 3.4 s touch delay 0/10, basic true-map/dead-reckoning baseline 0/10. The map baseline is explicitly evaluator-only; its separate source digest is recorded. The delayed-touch control recorded one episode with actual limit findings; it is not presented as clean.
- Extra full-frame command latency: 20 ms, 4/5 exits without checker findings; 40 ms, 0/5 with five angular-speed stops. These are separate stresses, not part of the 94/100 headline.
- Native ARM64 run https://github.com/Marc-Dvci/right-hand-rule-g1/actions/runs/42656538931 completed all three standard and three task repeats with `simulation_checks_complete`; each task crossed the designated exit. Peak native thrash from kit traces: 0.38955755. Exact archive SHA-256: `e6efe832912adb46f547911b29b8240a87234a6b68684bb26c0622852ac79f92`.
- Counterfactual standing passed on both scenes. Other recorded poses failed during startup, before handoff. Task seated, supine and left-side starts were rejected for substantial initial penetration and produced no report; the logs and explicit missing-report outcomes are retained. Both counterfactual suites require review. No all-pose or recovery capability is claimed.
- The expanded reproducible 10,000-history parity fixture gives maximum errors 3.5762786865234375e-6 (walk) and 2.86102294921875e-6 (balance). The earlier smaller source pool had a 2.6226e-6 maximum; both sets are well below the 1e-4 gate. All 10,000 inputs and independent ONNX outputs are now retained.
- Hero episode 26111500: matched-bandwidth force-vector RMSE 1.883 N (26.0% of target), endpoint odometry error 0.925 m, median logging-only contact-map error 0.390 m. Its raw 500 Hz peak hand load is 87.10 N; the primary cohort's worst peak is 175.36 N. This fails the original low-impulse contact target and requires force/latency qualification before hardware.
- Final documented `./run.sh` completed end to end: 28 tests passed, all 82 frozen file hashes matched, development maze 0 exited in 166.90 s with zero warnings, and the saved-state reproduction film rendered successfully. The separate final film is 82 seconds and uses only saved evaluation states.
