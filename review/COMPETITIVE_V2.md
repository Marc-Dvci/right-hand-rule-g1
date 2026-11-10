# V2 competitive assessment — 10 November 2026

The [live field](https://arena.himrobotics.com/challenges/open-build) and
[current runner guide](https://arena.himrobotics.com/docs/g1-policy-checks)
were rechecked on 10 November. The competition selects HIM's favorite; its
different tasks have no published common performance metric. Winning or
universal technical superiority cannot be established from these scores.

## Strongest competitors and the practical comparison

| Entry | Evidence and scope | Our defensible point of comparison |
|---|---|---|
| [G1 Brunson](https://arena.himrobotics.com/uploads/source_7f78ed6a9ef52baa891f) | Learned whole-body basketball; 12 clean official model-screen episodes. The source archive README reports 35/36 clean extended screens and one fall among 12 task evaluations. Camera is a declared input requiring qualification. Arena records the image as unverified. | Our complete task uses the standard joint/IMU interface, and our exact image is separately executed on native ARM64. Brunson also ships a container and builder-provided container evidence; absence of Arena verification is not proof it cannot run. |
| [Neural Taiko Festival](https://arena.himrobotics.com/uploads/source_0607d96bfc0a17fc5264) | Builder reports 181/181 notes across three charts, camera processing, learned arms and causal controls; known drum/base pose and fixed wrist sticks. | Our task continually translates and turns a free base through unknown collision geometry without camera input. Taiko offers a more theatrical presentation and learned arm behavior. |
| [G1 Free Kick](https://arena.himrobotics.com/uploads/source_bc66464f0f6fbd2caed4) | Listing describes a single network controlling all 29 joints through approach, alignment, kick and stand. The individual page could not be retrieved. | A serious learned whole-body competitor. We must emphasize our measured sensor contract and independent qualification, without inventing missing evidence for this entry. |
| [Unitree G1 football](https://arena.himrobotics.com/uploads/source_c1f0cfeac0e383301c8b) | Listing describes head-camera ball finding/kicking, custom C++ PPO and a 60 s standing kit check. Individual page retrieval timed out. | Our standard-sensor task avoids the extra camera qualification, and we retain actual-task native evidence. This does not compare their respective training quality. |
| [Free-Base Keeper](https://arena.himrobotics.com/uploads/source_b60f1cf5f6eeadfc7498) | Listing reports 60/60 saves over 20 seeds and neutral 1/60. Individual page retrieval failed. | Both require physical interaction with a free base. Different tasks and sensor needs prevent ranking their success percentages. |
| [G1 Rickshaw](https://arena.himrobotics.com/uploads/source_64238e10a9417cf5a540) | Builder describes a substantial pulling demonstration, with assisted grips and privileged feedback. Individual page retrieval failed. | Our complete control loop has no external grip constraint or supplied world state. Their load manipulation remains a compelling, different achievement. |
| [G1 Learned Kick](https://arena.himrobotics.com/uploads/source_baac54d51223e1b66448) | Page reports 32/32 held-out goals. Screening identifies a welded pelvis, six controlled joints, missing normalization and missing referenced robot assets; no supported simulation pass is established there. | Our free base, self-contained models/assets, full safety interface and reproducible task package directly address those packaging and scope gaps. |

Competitor archives were inspected as read-only research inputs. No competitor
controller was executed, copied or incorporated. Older Brunson headlines and
superseded cards are not substituted for the current fingerprinted package.

## What V2 should lead with

1. **A whole task through the standard interface.** The controller uses joint
   q/dq and pelvis quaternion/gyro, plus host readiness and sequence IDs. It
   receives neither a layout nor simulator contact/base state.
2. **Timing-aware inferred touch.** A small wrist excitation identifies local
   command age; past issued commands are aligned with current joint motion
   before estimating contact. This is implemented without evaluator delay
   labels. Calibration assumptions and failure behavior are documented.
3. **Unusually reviewable evidence.** Separate development and distinct geometry
   holdouts, all latency strata, matched interventions, independent exit
   scoring, exact source/image hashes and simulator-free command reproduction.
4. **A runnable complete image.** Full ROS protocol, abort/session handling,
   all 29 command slots, installed dependencies and native execution of the
   actual task. Gait-only ONNX screening is not presented as the complete task.

The final measured tables are in [V2 results](V2_RESULTS.md). Those results
must be complete before any claim about the declared qualification gates.

## Where the entry still needs to improve

Transient contact loads and body-wall impacts are the largest technical
weakness. The original low-force gate is unmet. Calibration is not qualified
for varying delay or hardware actuator filtering, odometry drifts, and no
physical G1 or all-pose recovery result exists. A learned locomotion component
does not make the scripted navigation a learned policy. These points should
remain explicit in the submission and supervised-attempt proposal.

The appropriate competitive claim is a strong, reproducible standard-sensor
contact-navigation entry with verified scope. It is not a claim that all
other projects are inferior or that the physical attempt is already safe.
