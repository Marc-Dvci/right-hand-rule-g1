# V2 implementation and contest audit

RIGHT HAND RULE implements the supplied contact-navigation plan with NVIDIA's
attributed pretrained locomotion networks. Navigation, arm compliance, local
command-age identification and recovery are our scripted controller. We did
not train those locomotion weights or incorporate competitor code.

## Plan coverage

| Planned item | V2 implementation and qualification scope |
|---|---|
| Whole task using standard sensors | Joint-state/IMU allowlist in API and ROS runner; no supplied maze, world coordinates, contact labels, camera or lidar. Sensor-only command replay checks the recorded implementation. |
| Straight wall and both corners | Physical static walls; right contour-seeking arc; forward-probe contact initiates backoff and a left turn. Development cases are separate from the geometry holdout. |
| Fast walking | Selected nominal target is about 0.102 m/s. Actual commands include odometry feedback and slew limits. Reliability was prioritized. |
| Force RMS at most 25% of target; raw force at most 20 N | **Not passed.** V1's hero matched RMS was about 26%. V2 loads still exceed 20 N; nonhand wall impacts are also recorded. Filtered inferred force cannot bound physical impulses. |
| 50 straight walls and 50 of each corner | These complete 50-run gates have not been executed. Do not infer their completion from maze results. |
| Delay robustness | V2 identifies constant 0/20/40 ms command age using wrist q/dq and its own command history. Three final strata at 600 s are reported separately. Calibration confidence is a relative fit heuristic. |
| 100 final mazes | V2 declares 100 **distinct** topologies excluded from 92 development topologies, including every retired V1 topology. Three delay strata and 180 matched controls must all be retained. |
| Damping uncertainty and body pushes | Separate stress suite: effective damping scales 0.8/1.2 and a 10 N, 0.25 s pelvis push in each lateral direction. This is not a broad push-recovery qualification. |
| Wall heading from touch-map fit | Logging only. Foot-odometry drift prevents treating the reconstructed map as ground truth. |
| Shuffled-touch control | Historical mode `touch_shuffled` is a **fixed 3.4 s delay**, explicitly labeled delayed touch. |
| Original physics and checks | Vendor kit is hash-verified. Standard native checks use it directly. Long native tasks use an isolated post-run report-RPC timeout extension from 10 to 60 s. Plant, active deadlines and check thresholds are unchanged. |
| Every start pose | Six attempted on both native scenes. Standing results and startup failures/invalid initial penetrations are separate. `review_required` is not an all-pose pass. |
| Second traversal from memory; guided-hand mode | Not implemented or claimed. |

## Audit controls

`evaluation/frozen-v2.json` seals selected policy, models, settings, evaluator,
protocol, tests, assets and original vendor files before opening the final
geometry holdout. Final runs require new output directories. Overwriting
evidence, using development geometry as holdout, easier limits or selected
subsets labeled as a full cohort is refused.

`tools/audit_v2.py` independently scores recorded exit crossings and checks all
seed/layout pairs, actual walls, randomization draws, settings, dependencies,
active checks and source hashes. It rejects duplicates and incomplete
inventories. All failures remain in the denominator. Diagnostic target clipping
and actual limit findings are counted separately.

Physics-rate contact metrics sum individual force magnitudes, so opposing
contacts cannot cancel. They include 100/250 ms means, time above thresholds,
accumulated load, nonhand wall contacts and offending body identities. Moving
load from the hand to the hip is not accepted as an improvement.

The exact runner archive is identified by SHA-256. Docker engines may display
its OCI manifest ID or image-config ID; both are recorded. The extracted runtime
filesystem must match all 19 source/config/model files. An older version's
native results never qualify a new image.

Film frames replay recorded qpos with `mj_forward`, with no physics steps.
Scenes are reconstructed from actual report walls and exit. Wall transparency,
clip selection and source hashes are disclosed. Portable motions retain exact
time/qpos arrays for independent scoring. Full local sensor traces are
fingerprinted; a separate sensor-only bundle proves command reproduction
without importing MuJoCo.

## Remaining physical limits

There are no physical G1 results or hardware authorization. The inferred-force
guard is a functional hold, not a certified force limit. Softer arms, spring
force caps, slower acquisition and alternate corner strategies were examined
but not promoted without consistent reliability and load improvements.

The simulated low-friction hand capsule represents a surface treatment. Stock
palm collisions, hardware variants, actuator filtering, friction, wrist
calibration and varying delay require instrumented qualification. Begin with a
compliant wall and one corner under HIM supervision; see `HARDWARE_ATTEMPT.md`.

V1 results remain under `evaluation/results/` and release v1.0.0. Current V2
results live under `reports/v2/` and the V2 write-up; their limits differ.
