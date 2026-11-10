# RIGHT HAND RULE V2

A free-standing Unitree G1 finds its way through unknown maze walls by touch.
The right arm feels the wall; the left arm probes ahead. The complete controller
receives **joint state and pelvis IMU only**: no camera, lidar, supplied layout,
simulator position or contact-force sensor.

V2 identifies command age from a small wrist excitation before navigation,
aligns inferred contact with past issued commands, and uses bounded turn and
wall-reacquisition recovery. Navigation and arm compliance are scripted.
Locomotion uses attributed pretrained NVIDIA GR00T Walk and Balance networks,
exported to equivalent NumPy inference; we did not train those weights.

[Judge's guide](JUDGES_GUIDE_V2.md) ? [V2 results](evaluation/results/v2/RESULTS.md) ?
[Plan audit](PROJECT_AUDIT_V2.md) ? [Competitive assessment](review/COMPETITIVE_V2.md)

**V2's declared simulation gate passed.** On 100 distinct held-out layouts per
delay, exits were **100/100 at 0 ms, 100/100 at 20 ms, and 95/100 at 40 ms**, with
zero primary checker stops or actual limit findings. The limit was 600 seconds.
All five navigation failures remain reported. Neutral and touch-off each exited
0/20 matched seeds at every delay; touch delayed by 3.4 s exited 3/20, 8/20 and
9/20. Delayed controls' findings are reported separately.

The exact released ARM64 image passed **3/3 standard and 3/3 actual-maze runs**,
with three designated exits. Supplemental straight/inner/outer primitives each
exited **50/50**, and the separate damping/push set exited **16/16**. The original
low-force and force-accuracy goals remain unmet. See the measured tables for
scope, all start outcomes and original-plan departures. V1 remains preserved
under v1.0.0. **No Arena submission or physical robot attempt has been made.**

## Run a development maze

Use Linux and Python 3.12. Saved-state rendering needs a working EGL driver
(e.g. Ubuntu libegl1 and libgl1-mesa-dri). Dependency versions are pinned.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

The script checks the environment, runs the tests, verifies the V2 source
freeze, evaluates development maze 0 with the selected configuration, and
renders `dist/reproduction.mp4`. Each run uses a unique evidence directory.
It preserves the published cohort and film. The complete protocol and native
ARM64 reproduction commands are in the judge's guide.

## Evidence and package

The declared final protocol uses **100 distinct held-out topologies** at each
of 0/20/40 ms command delay, a 600-second budget, and **180 matched control
trials**. The 92 development topologies include all retired V1 layouts and
are excluded from the geometry holdout. Source, settings and evaluator are
sealed before opening it. Every failure stays in the denominator.

`tools/audit_v2.py` independently re-scores exit crossings and checks all
seeds, actual walls, randomization draws, settings, dependency versions,
required active checks and source hashes. The final tables report each delay
stratum separately. A simulator-free sensor bundle checks exact command
reproduction from joint/IMU observations and local lifecycle signals.

The release package includes source/models/assets, notices, sensor contract,
all final reports and controls, version-matched native reports, a saved-state
film, source/image digests and an exact ARM64 image reference. Larger portable
motion archives and raw native traces are external release downloads. Use
`tools/check_motion_v2.py` to independently verify and score portable motions
without running physics. All film frames come from recorded qpos; scene
geometry comes from the recorded report. Wall transparency is rendering only.

The whole controller lives in one installed linux/arm64 ROS 2 Foxy image.
`g1-runner.json` declares only `joint_state` and `imu`. Native qualification
requires that exact archive, a byte-matched runtime filesystem, submitted
control after actual handoff, active checks and actual designated task exits.
Arena's automatic model screening does not execute containers, and a gait-only
model is not presented as our complete task.

## Material limits

The original **20 N contact gate remains unmet**, including body-wall impacts.
Inferred-force thresholds do not bound transient physical loads. Calibration
assumes a free-space start and a constant 0/20/40 ms command age; hardware
friction, actuator filtering and varying delays remain unqualified. Foot
odometry drifts, so touch maps and fitted wall heading are logging only.

All six native start poses are attempted on both scenes. Startup failures and
invalid initial penetrations are retained; `review_required` is not an all-pose
pass. Standard runs use the canonical vendor kit. Long task runs disclose an
isolated **post-run report-export RPC timeout extension from 10 to 60 s**;
plant, active control, gains, deadlines and safety thresholds are unchanged.

There are no physical G1 results or hardware authorization. The first proposed
supervised attempt is an instrumented compliant wall and one corner, after
HIM's qualification. See [hardware plan](HARDWARE_ATTEMPT.md),
[sensor contract](SENSOR_CONTRACT.md) and [remaining improvements](NEXT_IDEAS.md).

NVIDIA and Unitree provenance/licenses and original kit inventories are in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The custom scene preserves the
free base, all 29 actuators, IMU and original inertias. Its disclosed
low-friction hand capsules represent a surface treatment; stock palms require
separate qualification. Historical V1 results remain under `evaluation/results/`.
