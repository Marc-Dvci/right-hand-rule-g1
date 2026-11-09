# Technical review before Arena submission

The v1 release is preserved. Development is isolated in the `review/v2` worktree/branch. No Arena submission is authorized by this review, and none is made here.

## Public field checked 9 November 2026

The live [challenge listing](https://arena.himrobotics.com/challenges/open-build) still shows the principal projects in the earlier competitor review. These are different tasks, so their task scores cannot be ranked on a common scale.

| Project | Strongest evidence | Dependency or gap relevant to a supervised attempt |
|---|---|---|
| [G1 Brunson](https://arena.himrobotics.com/uploads/source_7f78ed6a9ef52baa891f) | Learned whole-body controller; 12 clean official basketball-screen episodes. Public source archive digest verified as `e862d6b05b1cb5cd0cd6e4d60dfa7033078fa73cc36cae75c146c3d948d24b46`; archive README reports 35/36 clean extended screens and one fall in its 12-episode task evaluation. | Camera input needs qualification. Arena records the image reference as unverified. The archive also has source, clamps, training provenance and counterfactual evidence; it is a serious technical competitor. |
| [Neural Taiko Festival](https://arena.himrobotics.com/uploads/source_0607d96bfc0a17fc5264) | Builder reports 181/181 notes over three charts, visual perception and several causal controls. | Known drum/base pose, camera and wrist-mounted sticks. Page records no screening or hardware test. |
| [G1 Rickshaw](https://arena.himrobotics.com/uploads/source_64238e10a9417cf5a540) | Builder reports free-base pulling, load transfer and disconnected controls. | Assisted grips and privileged state. Individual page could not be retrieved; listing claims are not independently reproduced. |
| [Free-Base Keeper](https://arena.himrobotics.com/uploads/source_b60f1cf5f6eeadfc7498) | Listing reports 60/60 shot saves across 20 seeds, neutral 1/60. | Different task, with ball-state needs. Individual page retrieval failed; do not infer absence of evidence from that failure. |

Our defensible advantage is a whole contact-navigation task on the standard joint/IMU interface, with repeated exact-image native ARM64 execution and independent trajectory scoring. Our weaknesses are the 40 ms command-delay failures, excessive transient contact loads, limited topology diversity, six navigation failures and lack of physical qualification. We must improve or clearly bound those weaknesses rather than claim universal superiority.

## Review findings and experiments

- V1 velocity integration can saturate translation while the state machine is trying to turn in place. Recorded failures include almost 0.4 m/s forward or 0.3 m/s lateral commands during TURN. Development adds bounded translation, integrator antiwindup and settled-yaw completion.
- Lower waist stiffness/gravity compensation alone does not cure 40 ms delay. Tests show low waist angle during failure, so attributing the entire issue to the waist was too strong. A joint/IMU predictor is being validated with the actual gait and contact controller.
- V1's DFS generator reaches only a small subset of the 192 possible 3x3 spanning trees. The next holdout will use distinct topologies, explicitly excluding every legacy DFS topology from its geometry holdout.
- A spherical-contact odometry correction was checked offline. It did not materially reduce drift in the recorded episodes; it is not promoted as a solution.
- The original exact image is also being tested for 200 seconds in the entirely unmodified kit. If report export fits the original deadline, this can remove the task-report workaround from the primary qualification evidence.

The 200-second native test still hit `plant_error: mujoco plant response timed out` during export ([run](https://github.com/Marc-Dvci/right-hand-rule-g1/actions/runs/42697162383)); it does not qualify as a pass. The report-only timeout fix remains necessary for the long rollout. Broadly bounding every navigation state reduced contact peaks in development but damaged maze completion, so that combined change is not promoted. The next ablation isolates the turn/backoff windup correction from wall-following behavior.

## Submission completeness target

The final review must cover the complete source ZIP and film, same-image ARM64 execution, sensor/abort contract, all start outcomes, reproducible dependency and asset inventories, baseline controls, version-matched episode data and checksums, an independent portable trajectory scorer, a small HIM-adoptable maze screen, a concise judge's guide and a calibrated statement of physical-transfer limits. Optional model screening must never substitute gait-only evidence for the complete task.

The [current official guide](https://arena.himrobotics.com/docs/g1-policy-checks) still pins kit `e93c49267a7b6b905c6666c8c70668f8ee7ac397`, standard joint/IMU inputs and the 100 MB combined ZIP/video limit. Competition artifacts and raw downloads are read-only inputs; competitor code is never executed or copied into our controller.
