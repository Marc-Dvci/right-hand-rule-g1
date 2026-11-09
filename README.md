# RIGHT HAND RULE

A blindfolded Unitree G1 navigates by touch: its right arm feels the wall, its left arm probes ahead, and its legs keep it moving. The controller receives joint state and pelvis IMU only. It has no camera, lidar, supplied maze layout, simulator position or contact-force input.

Navigation and arm compliance are scripted. Locomotion uses NVIDIA's attributed pretrained GR00T Walk and Balance networks, exported to equivalent NumPy inference. The base is free and all motion comes from the joint controller; the maze consists of static collision geometry.

## Measured build status

This is an active development build. The frozen 100-maze evaluation and native ARM64 container qualification have not yet passed. Do not treat the project as hardware-ready or as a completed competition submission.

- The unmodified HIM in-process Runner has completed straight-wall and both corner tests without torque/speed warnings or falls.
- A correctly scored development maze was exited in 196.00 simulated seconds, with no kit warnings and a thrash peak of 0.519 against the 1.500 threshold.
- Both NumPy networks match ONNX Runtime on 10,000 recorded histories: maximum absolute action error `2.6226043701171875e-6`.
- Fifteen tests verify the sensor boundary, protocol pairing and abort behavior, upstream hashes, model parity, and arm kinematics/Jacobians/gravity against MuJoCo.
- A local `linux/arm64` ROS 2 image builds. Container startup/protocol evaluation is still being debugged; packaging alone is not a simulator pass.

Development experiments, including failures and invalidated early measurements, are recorded in [WORK_LOG.md](WORK_LOG.md). Final headline numbers must come from version-matched evidence, not selected development episodes.

## Reproduce

Use Python 3.12 on Linux with EGL-capable graphics for rendering. The project pins MuJoCo 3.3.7, matching the public builder simulator's supported series.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q tests
python harness/evaluate.py --scene maze --seed 0 --seconds 400 --output evidence/reproduction
python tools/render.py --episode evidence/reproduction --output dist/result.mp4
```

The renderer only replays saved simulation states. It does not drive joints, step physics or change the outcome. Wall transparency in the film is a rendering choice to expose the robot's motion.

To build and test the complete ROS 2 image:

```bash
bash tools/build_container.sh
python tools/run_kit.py --seconds 60 --name standard-local
python tools/run_kit.py --scene maze-0-w1.250 --seconds 400 --name maze-local
python tools/run_kit.py --seconds 60 --counterfactuals --name counterfactuals-local
```

Run the maze evaluation first to generate its static scene. Local x86 Docker uses ARM64 emulation; those reports are kept separate from native ARM64 evidence.

## What is measured

The harness imports the original HIM `Runner`, `Plant`, startup balance, joint checker and enforced thrash detector. It passes only an explicit joint/IMU allowlist to the controller. Ground truth remains in the evaluator for exit crossings, force comparison and replay.

Success requires an outward crossing through the designated exit segment. Leaving through the entrance is a failure. A latched controller stop, safety finding or time limit is retained as a failure. Parameter tuning uses development seeds; the 100 final seeds are fixed in `evaluation_protocol.json` and must never be used for tuning.

The kit's warning dictionary contains both actual limit exceedances and diagnostic target clipping. Reports retain both. `within_limits` alone does not establish container coverage, task success or hardware approval. The exact image must satisfy the kit's `simulation_checks_complete` coverage guard in a real container run.

## What a real attempt needs

Start with one stable wall and one corner under HIM supervision, their normal tether/gantry, and emergency stop. Review [HARDWARE_ATTEMPT.md](HARDWARE_ATTEMPT.md) and [SENSOR_CONTRACT.md](SENSOR_CONTRACT.md). Force estimates depend on the model, gains, feedforward response and surface friction; simulation contact does not establish physical force accuracy.

## Dependencies and scene changes

The original kit, model provenance, NVIDIA license and Unitree asset notices are retained. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

The custom G1 scene preserves the original free base, 29 joints/actuators, IMU and inertial parameters. It disables the original palm collision spheres and uses disclosed low-friction capsules representing the existing rubber hands. The blindfold is visual only. The runner and safety-check source files are unchanged and hash-verified.
