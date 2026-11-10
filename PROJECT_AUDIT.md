# Implementation and contest audit

> Historical V1 audit. Current V2 implementation and remaining gates are in
> [PROJECT_AUDIT_V2.md](PROJECT_AUDIT_V2.md). V1 measurements do not qualify V2.

The project implements RIGHT HAND RULE from the supplied plan. Its strongest distinction is a complete contact-navigation task using only the runner's joint state and pelvis IMU, with the same ARM64 image tested in the actual ROS kit. Navigation is scripted; the locomotion networks are NVIDIA's pretrained weights, not our training result.

## What changed from the plan

| Planned item | Implemented scope and reason |
|---|---|
| Fixed right-angle turn after wall loss | A bounded right contour-seeking arc reacquires contact more reliably at partition ends. Forward-probe contact still triggers a backed-off left turn. |
| 0.2–0.3 m/s walking | Selected nominal forward target is about 0.102 m/s, with slew limits and joint/IMU velocity feedback. Reliability takes priority over a faster film. |
| Wall heading from contact-point fit | Fit retained for logging only. Stance-foot odometry has substantial drift, so the fit was not qualified for heading feedback. |
| Force RMS ≤25% of target and raw force ≤20 N | These are **not claimed as passed**. The hero's bandwidth-matched vector RMS is about 26% of target, and unfiltered 500 Hz hand-force impulses exceed 20 N. All raw peak measurements are retained. A model-based contact estimate is not a calibrated force sensor. |
| 50 straight walls and 50 of each corner | Those complete 50-run gates were not executed. Development included straight walls, inner/outer corners, parameter search, ten deterministic and ten randomized maze episodes. The final split is reported separately. |
| 0/20/40 ms delay mixed into the main evaluation | Protocol v2 separated nominal timing from extra full-frame delay **before opening the final seeds**. Added 20 ms delay destabilizes the trained waist feedback. The original combined latency-robustness gate remains unmet. |
| Body pushes and joint damping randomization | Current declared distribution randomizes joint friction loss, not damping, and does not apply body pushes. It also perturbs real motor-force caps, mass/inertia, effective floor friction, sensor noise, drift and starting pose. |
| 100 final mazes | 100 seeded randomized **episodes** of 3×3 perfect mazes; distinct topology count is reported because layouts can repeat. No controller parameter is changed after the final freeze. |
| Shuffled-touch control | The existing control is a fixed 3.4-second delay. It is reported as delayed touch, with the historical code name retained for traceability. |
| Map/no-touch control | Evaluator-only true-map BFS and joint/IMU waypoint dead reckoning. This is one explicit basic baseline, not a claim about the best possible navigation with a supplied map. It never enters the deployed image. |
| Unmodified kit for every run | Standard scene uses the original kit. Task runs disclose a one-line isolated-copy change extending only the post-run report RPC deadline to 60 s. The canonical kit, checker, plant and active deadlines are unchanged and hash-verified. The first unpatched task report timed out during export. |
| Second run from memory / guided hand mode | Not implemented or claimed. Reliable first-run task execution and reproducible evidence were prioritized. |

## Version and measurement controls

`evaluation/frozen.json` fingerprints policy, weights, timing adapter, settings, harness, protocol and robot assets. The final runner verifies this inventory before and after all 100 episodes. `tools/audit_final.py` re-scores every saved trajectory with an independent geometric crossing test and checks the exact seed inventory, randomization draws, controller digest and configuration. Every failure remains in the denominator.

The public image is identified by its archive SHA-256. Docker's containerd image store and classic overlay2 expose different image IDs for the same archive: the former reports an OCI manifest digest; the latter reports the image config digest. `tools/audit_image.py` records both and compares the actual extracted runtime files with source. This avoids treating engine-specific IDs as different policy versions.

The warning dictionary contains both diagnostic target clipping and actual limit findings. Summaries count them separately and retain the raw dictionaries. A checker stop or missing report is never accepted as task success. Native task exits are scored from the original kit's saved floating-base trajectory; a later return does not erase an earlier valid exit.

The film replays saved qpos with `mj_forward`; it never steps dynamics. Transparent walls and the contact-reference graphic are explicitly rendering/evaluation overlays. Film selection is recorded, and aggregate claims come from all episodes, not the displayed clips.

## Physical transfer

No physical G1 performance is claimed. The bounded waist feedforward restores much of the pretrained impedance on top of the host's 60/1.5 waist profile. The effective response, timing sensitivity, high contact impulses and inferred-force bias require supervised qualification. The custom low-friction hand capsule represents a surface treatment/mitten; it does not prove that an untreated stock palm behaves the same way.

The navigation has bounded missing-wall search and an estimated-force guard, but those are functional behaviors, not certified safety limits. A filtered inferred-force threshold cannot bound transient physical force. HIM's supervisor, tether, clear area and emergency stop remain necessary. See `HARDWARE_ATTEMPT.md` for the smallest proposed trial.
