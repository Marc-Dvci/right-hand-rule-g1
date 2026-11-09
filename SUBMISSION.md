# Contest card

**Title:** RIGHT HAND RULE — a blindfolded G1 finds its way by touch

**Caption:** A blindfolded, free-standing G1 follows walls using joint state + IMU only. No camera, lidar or supplied map. Scripted touch navigation on NVIDIA GR00T locomotion. 94/100 untouched randomized episodes exited, with no falls or checker findings at nominal timing. Neutral, touch-off and delayed-touch controls: 0/10 each. Exact ARM64 image tested in HIM's runner. Source, raw reports and known transfer limits included.

**Files:** `dist/RightHandRule.zip` and `dist/result.mp4`.

**Run command:** `./run.sh`

**Robot:** Unitree G1. **Simulator:** MuJoCo. **Challenge:** Open Build Challenge. **Kind:** policy + simulation.

The GitHub release is public. This package has not been uploaded to HIM Arena by this build workflow. No hardware result or authorization is claimed. The container reference describes the complete task controller; there is deliberately no gait-only `arena-policy.json`.
