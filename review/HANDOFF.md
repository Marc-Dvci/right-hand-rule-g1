# RIGHT HAND RULE — pre-submission handoff

**9 November 2026. Review closed at the user's request. No HIM Arena submission has been made.**

## Current decision

A complete, tested submission bundle exists as **v1.0.0**. It is preserved unchanged. The additional review found a real navigation-control defect and produced a promising correction, but **v2 is development code, not a qualified replacement release**. Do not combine v1's results with v2's source or claim that the unfinished version has passed the final evaluation.

The next most useful step is to finish validating the narrow turn/backoff correction, then build and qualify its exact container. The wider predictor/gravity changes need more evidence before adoption.

## 1. What is complete

[Public v1 release and downloads](https://github.com/Marc-Dvci/right-hand-rule-g1/releases/tag/v1.0.0).

| Deliverable | Status |
|---|---|
| Complete controller | Scripted touch navigation on attributed NVIDIA GR00T locomotion; only joint state and pelvis IMU enter the policy |
| Free-base simulation | Actual joint control and collision physics; no scripted pelvis or privileged maze/base/contact input to navigation |
| ARM64 runner | Full ROS 2 image, installed dependencies, session/observation protocol, all 29 command slots and abort handling |
| Source ZIP | `RightHandRule/dist/RightHandRule.zip`, 88,074,686 bytes |
| Final film | `RightHandRule/dist/result.mp4`, 82 seconds, 3,688,093 bytes; saved simulation states only |
| Upload-size check | ZIP + film = **91,762,779 bytes**, below 100 MB |
| Evidence | Per-episode reports, full selected traces, all 100 portable base trajectories, native reports/traces, model parity fixtures and checksums |
| Documentation | README, sensor contract, hardware-attempt notes, third-party notices, implementation audit and prepared contest caption |
| Package verification | ZIP integrity and file hashes, runner reference, full video decode and fresh-extraction checks passed |
| Public delivery | All five main remote artifact SHA-256 values match the sealed local manifest; public ZIP and image URLs returned HTTP 200 |

Qualified source commit: `17bcb4ad706e8e3776fc9781afe24374e212fe78`.

Tested image archive SHA-256:
`e6efe832912adb46f547911b29b8240a87234a6b68684bb26c0622852ac79f92`.

## 2. What v1 actually demonstrated

| Measurement | Result |
|---|---|
| Frozen randomized split, nominal timing | **94/100 exits** within 400 simulated seconds |
| Geometry diversity | **14 distinct topologies**, not 100 distinct mazes |
| Primary falls / checker stops / actual limit findings | **0 / 0 / 0** |
| Median successful episode | 157.42 simulated seconds |
| Primary peak thrash | 0.712 against the 1.500 threshold |
| Native ARM64 | **3/3 standard and 3/3 maze runs** completed checks; every maze exit independently scored from its kit trace |
| Native peak thrash | 0.389558 |
| Neutral / touch-off / delayed-touch controls | 0/10 exits each; the complete controller exited 9/10 on those matched seeds |
| Model export | 10,000 histories per network; maximum NumPy/ONNX action difference 3.58e-6 |
| Reproduction | 28 tests passed, including from the extracted ZIP; documented run command completed end to end |

[Native qualification workflow](https://github.com/Marc-Dvci/right-hand-rule-g1/actions/runs/42656538931).

These qualifications have important boundaries:

- Task runs use a disclosed **report-export-only** RPC timeout extension in an isolated kit copy. Canonical kit files, dynamics, active deadlines and checks remain unchanged. A further 200-second test with the entirely unmodified kit still returned a plant-response timeout; it is not a pass. [That experiment](https://github.com/Marc-Dvci/right-hand-rule-g1/actions/runs/42697162383) is preserved.
- Standing counterfactual starts passed. Other starts produced startup violations or invalid-initial-penetration errors before handoff. Both counterfactual suites require review; there is no all-pose or recovery claim.
- Extra 20 ms command delay exited 4/5; extra 40 ms exited 0/5 with checker stops.
- The worst raw 500 Hz hand-contact impulse was **175.36 N**. The original 20 N contact target was not met.
- The hero force-vector RMS was 1.883 N, or 26% of target, slightly above the original 25% gate. Its endpoint odometry error was 0.925 m. The touch map remains logging-only.
- The original full 50-run straight-wall and 50-run-per-corner gates were not executed. Body-push and joint-damping robustness have not been established.
- There is no physical robot result or hardware authorization.

## 3. What the additional review accomplished

Work is isolated in `RightHandRule-v2`, on Git branch `review/v2`. The original release and qualified source directory remain intact.

### Concrete navigation defect found

In several failed episodes, velocity-integrator windup could request approximately **0.4 m/s forward or 0.3 m/s lateral translation while the state machine was trying to turn in place**. Slow braking could also consume much of the short backoff phase before motion reversed.

The narrow correction adds maneuver-specific integrator resets, bounded turn translation, faster bounded backoff braking, yaw antiwindup and settled-yaw completion. It preserves the tuned wall-following behavior.

With the turn-only candidate, five previously failing v1 episodes now exited cleanly:

| Retired v1 seed | Corrected completion time | Checker findings |
|---|---:|---:|
| 26111503 | 267.98 s | 0 |
| 26111551 | 217.08 s | 0 |
| 26111559 | 274.28 s | 0 |
| 26111569 | 171.16 s | 0 |
| 26111590 | 179.98 s | 0 |

Seed **26111594 was interrupted**, so this is **5 completed successes**, not a 6/6 result. These published v1 episodes are now development data; they cannot be relabeled as a fresh holdout.

Exact candidate settings: `review/candidates/turn-only.json`.

### Delayed-control research

- Waist gravity compensation was implemented and checked against MuJoCo. Changing waist stiffness alone did **not** fix 40 ms delay. Attributing the whole failure to waist stiffness was too strong.
- Joint/IMU-only state prediction produced clean delayed-control cases. The gravity + 20 ms prediction candidate completed both checked development mazes at both nominal timing and 40 ms delay: four completed cases, with no checker stops or limit findings. This is a small pilot, not broad qualification.
- Other prediction/filter variants produced torque findings or navigation failures. They must not be pooled into a successful headline.
- Broadly limiting all navigation states reduced some contact peaks but damaged task reliability: only 2/20 development maze exits. That combined variant was rejected.
- A spherical-foot odometry correction did not materially improve the recorded position drift and was not adopted.

Second candidate settings: `review/candidates/gravity-predictor20ms.json`.

### Stronger evaluation prepared

The new maze catalogue contains all **192** spanning trees of the 3x3 grid. Its count was checked against the independent matrix-tree theorem. Exhaustive enumeration confirms that the old DFS generator can produce only 14 of these geometries.

The declared new split has **92 development topologies and 100 distinct held-out topologies**, excluding every legacy DFS topology. All 100 holdouts remain unopened. No v2 final source freeze has been created.

The protocol proposes separate 0/20/40 ms timing strata and a 600-second limit. This is a harder, differently timed benchmark than v1's 400-second split; scores must be reported separately rather than compared as if the setups were identical.

Files: `review/evaluation_v2_protocol.json`, `harness/maze_catalog.py`, `harness/catalog_evaluate.py`, `harness/catalog_cohort.py`, `tools/freeze_v2.py`.

### Package/reproduction review

A host-dependency preflight was added. Rendering now locates DejaVu fonts bundled with the pinned Matplotlib dependency, avoiding reliance on an Ubuntu font directory. The current development source passes **37 tests**.

The final turn pilot was closed with **16/24 cases complete, four interrupted and four not started**. The retired-failure batch has five complete cases and one interrupted. Partial traces are excluded from completed counts. No review experiment processes remain running.

Detailed evidence: `review/review_snapshot.json` and `review/run_closeout.json`. Raw local evidence remains under `RightHandRule-v2/evidence/`.

## 4. Position against competitors

The live field, current guide and strongest competitor's public source archive were reviewed. The archive digest was checked before inspection; competitor code was not executed or copied into our controller.

Our strongest defensible distinction is **the whole task running on standard joint/IMU inputs with repeated exact-image native execution**. Strong competitors also have serious learned controllers, perception, causal controls and safety evidence. Their task scores are not directly comparable to maze exits.

**Universal technical superiority has not been established.** The next version needs stronger delay, force and geometry evidence before making a broader claim. See `review/COMPETITIVE_AUDIT.md` for source-linked comparisons and retrieval limitations.

## 5. Improvements still required, in priority order

1. **Finish qualifying the turn-only correction.** Complete the interrupted sixth regression in a new output directory, then rerun the entire retired 100-episode split as a paired regression. Require no new checker findings or falls and no loss of completion rate. Do not infer 100/100 from the five repaired examples.
2. **Choose the deployment candidate.** Compare the conservative turn-only correction against gravity/prediction alternatives. Current predictor evidence is too small for promotion. Validate full walking/turning scripts, wall contact and randomization at every claimed delay.
3. **Make configuration loading consistent.** Experimental settings currently enter through `--control-config`; they are not wired into a replacement ROS image. Direct `Controller()` calls can also fall back to generic navigation defaults when explicit settings are omitted. The released ROS image and run script explicitly use the selected v1 settings and are unaffected. Align direct API, harness and deployment defaults before freezing v2.
4. **Freeze and run the new geometry holdout.** Integrate the selected settings, update the reproduction script to the v2 freeze, then seal source/assets/configuration before opening holdout episodes. Report all failures and each timing stratum separately. Never tune on those results.
5. **Reduce and characterize contact loads.** Correct braking/force-control behavior without weakening checks or adjusting scene compliance merely to improve numbers. Measure all relevant contact modes, force-estimator error, raw impulses and sustained loads. A filtered inferred-force guard does not bound physical impacts.
6. **Complete the missing robustness evidence.** Run systematic straight-wall and inner/outer-corner trials. Add explicitly declared body pushes and effective damping uncertainty. Preserve failures and verify that each randomized factor actually changes the dynamics.
7. **Rebuild and qualify the exact new image.** Audit its runtime files against source; run three native standard/task repeats and all starts. Keep the report-timeout workaround disclosed unless an unmodified-kit run genuinely succeeds. No v2 image has been built or qualified yet.
8. **Refresh the submission package last.** Update results, judge-facing summary, hardware notes, caption and film only from completed evidence. Rebuild ZIP/video, verify all hashes and size limits, test a fresh extraction, and publish a new version without overwriting v1. Do not submit the current development branch as if it were qualified.

Secondary improvements: improve odometry/contact mapping before using it for decisions; strengthen the basic map/no-touch baseline and match its low-level controller settings; rename the fixed-delay control to avoid calling it random shuffling; add route memory only after the first-run controller is qualified. Hardware still needs supervised timing, surface and independent force-gauge tests.

## 6. Where to resume

```text
Qualified project: D:\Boulot temp\HIM Robotics\Open build challenge\RightHandRule
Development:       D:\Boulot temp\HIM Robotics\Open build challenge\RightHandRule-v2
Development branch: review/v2
```

From WSL, the existing pinned environment can be reused without modifying the qualified project:

```bash
cd '/mnt/d/Boulot temp/HIM Robotics/Open build challenge/RightHandRule-v2'
RHR_PYTHON='../RightHandRule/.venv/bin/python'
"$RHR_PYTHON" -m pytest -q tests
"$RHR_PYTHON" harness/evaluate.py --scene maze --seed 26111594 --seconds 400 \
  --randomize --transport --latency-steps 0 --parameters config/navigation.json \
  --control-config review/candidates/turn-only.json \
  --output evidence/resumed-retired-seed94-turn-only
```

Use new evidence directories when resuming. Interrupted files are retained for provenance, not accepted as results. The old freeze belongs to v1; the v2 freeze should remain absent until a deployment configuration has actually been selected and integrated.
