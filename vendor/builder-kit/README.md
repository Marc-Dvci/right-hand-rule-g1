# G1 builder kit

Download from https://arena.himrobotics.com/docs/g1-policy-checks. No GitHub access is needed.
This is an explicitly selected subset of the runner at e93c49267a7b6b905c6666c8c70668f8ee7ac397, plus Arena's simulation launcher and report coverage guard. UPSTREAM_FILES.json records every copied source and SHA-256. Hardware launchers, motor transports, account configuration and session data are excluded.

## Build, test, submit

Install Docker with Compose and Python 3. On an x86 host, enable Docker's ARM64 emulation or build/test on an ARM64 machine. From this folder:

```sh
docker buildx build --platform linux/arm64 --load -f template/Dockerfile -t g1-submission:local .
docker image inspect g1-submission:local --format '{{.Os}}/{{.Architecture}} {{json .Config.Entrypoint}}'
mkdir -p containers/upload
docker save g1-submission:local -o containers/upload/submission.tar
bash sim.sh --seconds 60
bash sim.sh --seconds 60 --counterfactuals
```

The template is an interface example that holds the starting pose, not a basketball controller or a demonstrated safe policy. Replace template/policy.py with your complete controller and install all dependencies/models in the Dockerfile. Build from the kit root so the exact ROS message definitions are included. Never install dependencies at runtime. No setup.sh is required in your submission.

Simulation uses an isolated Docker loopback network, no robot interface, and the pinned shared checks with thrash enforcement. The original simulator may end before the policy takes control; check_report.py therefore requires a recorded handoff and at least 10 simulated seconds under submitted control. Increase --seconds when needed. It preserves the raw report and writes builder-check.json. An example/template failure is not proof that your controller is wrong. Review the first finding, scene, startup and coverage.

Save containers/sim/output/ immediately after each run or use --output to keep separate runs. Publish source ZIP + MP4, the image (or g1-runner.json public archive URL and SHA-256), and evidence. Arena's automatic ONNX screening and this submitted-container test are separate. Neither authorizes hardware.

## Exact interface

ros2/him_safety_interfaces contains the original .msg/.srv definitions. Read /safety/policy_observation (RobotFeedback) and /safety/policy_state (std_msgs/String containing JSON). Arm through /safety/checker/arm (std_srvs/Trigger); its message is the session ID. Publish JointCommand on /safety/precheck, using that session ID, the received observation_id, and an increasing sequence. Publish all 29 q, dq, kp, kd, tau values; hold unused joints. Subscribe to /safety/abort and stop publishing. The host owns effective gains and motor output. Never publish rt/lowcmd or rt/arm_sdk.

State includes timestamped joints, quaternion wxyz and gyro. See robot_safety/hardware_constants.py for joint order. Observation freshness and next-command deadlines are 0.2 seconds; first command timeout is 30 seconds. The optional rt/lowstate SDK publisher is unavailable unless its dependencies are installed; use the standard policy_state feed for IMU in this kit.

## Custom tasks and basketball

Put a complete scene under containers/upload/environment and add --scene containers/upload/environment/scene.xml to each simulation command. The container simulator requires the 29 named G1 joints/actuators, floating_base_joint, pelvis, its named IMU sensors and a stand keyframe. A basketball screening scene is not automatically compatible with this separate container simulator.

No camera stream or ball-position topic is provided by the current standard runner. Do not invent or assume one. Package your tracker code and dependencies in the image, declare camera in required_sensors, and include SENSOR_CONTRACT.md specifying camera model, frame format/resolution/rate, timestamps, intrinsics/extrinsics, ball position/velocity units and coordinate frame, latency and lost-track behavior. A runner must qualify and connect this input before a physical attempt. The automatic basketball screen uses simulator ball state only.

For an exact local replica of Arena's basketball screen:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-screen.txt
python screen_basketball.py /path/to/submission.zip --output ./basketball-result
```

This uses the same reviewed bridge, reference fingerprints, original ONNX graph and PR #10 checks as Arena. It never imports submitted Python. Default: 12 episodes, seeds 1000–1011, alternating stance 0/1, 20 simulated seconds each. --episodes 36 extends the consecutive seed sequence; this differs from choosing random stances or seeds 2000 onward. The report records exact ball starting position/velocity and task crossovers. See BASKETBALL_START.md for reset details.

## Scope and notices

Host battery/circle/local examples are not submitted-container tests and are intentionally unavailable from this launcher. No robot setup or motor-output code is shipped. The unchanged shared checker remains provisional; inspect both findings and task performance. Unitree robot assets retain the notices under packages/policy_safety/src/policy_safety/robots/g1/third_party. The NVIDIA startup balance model retains examples/policies/walker/LICENSE and provenance.json. The basketball bridge retains its NOTICE.md. These third-party notices apply to their respective files.
