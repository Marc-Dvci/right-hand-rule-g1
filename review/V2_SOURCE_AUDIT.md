# Selected V2 source audit

The selected policy fingerprint is
`e8d30b879629d8792e26e02b834e428ceba975a6c4308b755b5e15b65eda4bb9`.
The pre-holdout freeze is commit `92b735b`, published before opening final
geometry trials. Its 261-file inventory is checked before and after final
episodes. The exact image archive SHA-256 is
`db0ed1194f03a71d706f161e2ee1fbf368a09f3632dd5ff36329f9d303d00051`.

## Boundary and transport

The controller's explicit observation read set is q, dq, quaternion and gyro.
Host readiness and observation IDs are lifecycle inputs. The ROS adapter
discards privileged simulator fields, pairs matching observations, preserves
joint order, uses checker session/sequence IDs, fills every command slot and
latches abort. Invalid observations and excessive gaps stop publication.
`test_policy.py`, `test_transport.py` and `test_timing.py` exercise these paths,
including altered privileged fields and held inputs during reconstructed frames.

## Dynamics and contact

FK, Jacobians and gravity were compared against the pinned G1 model. Force
inference now uses the appropriate past issued command instead of a newer
command that may not yet be applied. Local input/output calibration uses only
real adjacent observations, checks excitation and physical response sign, and
halts navigation for ambiguous identification. Interpolation retains the
actually held action/input history. `test_calibration.py` and the transport
tests cover relevant failures. Calibration confidence is not a probability.

The arm's softened effective spring is implemented through bounded feedforward
under host-approved gains. It does not create a physical contact-force bound.
Physics-rate load metrics include nonhand collisions and sums of individual
contact magnitudes. Softer-arm, Cartesian spring-cap, slower approach, contact
transfer reset and snag-detection pilots did not justify replacing the selected
controller. Their failures and measurements are retained in
`results/rejected-contact-development.json`.

## Navigation

Turn/backoff integrators are bounded and reset, turn completion requires settled
IMU yaw, and left-turn references can anchor to measured yaw. Five-second net
estimated displacement detects stalls that instantaneous foot velocity missed.
ARC timeout can enter a bounded wall search; a failed search can reorient, with
at most eight recovery attempts. Initial empty-space search still stops.
`test_control_parameters.py` and `test_arc_reacquisition.py` exercise these bounds.

An additional ARC-to-FOLLOW integral reset was investigated. Its small pilot
did not establish consistent load improvements, so it is not in this selected
version. The audit does not claim every potentially useful control change has
been exhausted or that the current controller is mathematically optimal.

## Evaluation and assets

The topology catalog enumerates all 192 3x3 spanning trees. The final 100 are
disjoint from all 92 development topologies and every V1 DFS topology. Protocol
tests reject overlap, duplicate/incorrect seed-layout pairs, easier limits,
configuration overrides and selected subsets labeled as complete cohorts.

Exit scoring uses an outward crossing with interpolated doorway position,
before an entrance return. The independent scorer checks recorded trajectories.
A NumPy boolean serialization defect found in a development pilot was corrected
and covered by `test_evaluator_exit.py`; failed infrastructure runs were kept
separate from task results. Auditor tests reject easier exits, disabled checks,
missing provenance, duplicates and incomplete inventories.

Canonical kit source/assets are checked against `UPSTREAM_FILES.json`.
`test_physics_contract.py`, `test_randomization.py`, `test_robustness.py` and
`test_report_fix.py` check physics scope, actual parameter changes and the
isolated report-only timeout adjustment. No safety threshold is relaxed.

## Runtime and reproduction

All 19 extracted ARM64 runtime files/configs/models match reviewed source.
Direct API, evaluator and ROS runner load the same mandatory settings.
The native source suite passes 64 tests. `test_native_gate.py` refuses
startup-only or incomplete submitted-control evidence.

The selected 7,797-call sensor-only proof reproduces every target/feedforward
number exactly under the pinned host environment, without importing MuJoCo.
This proves that recorded command path; it does not replace native execution or
hardware qualification. Network-export parity is a separate 10,000-history
comparison per original NVIDIA network.

Final source ZIP verification checks inventory digests, private-file patterns,
one runner reference, executable run script, matching exact-image digest, video
decode and size limits. Extracted-package tests and reproduction are required
before releasing the completed package. Final outcomes belong in `V2_RESULTS.md`.
