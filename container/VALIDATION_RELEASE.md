This is a development validation image for RIGHT HAND RULE, not a hardware-qualified controller or a final HIM Arena submission.

The archive contains the complete linux/arm64 ROS 2 policy image, with joint-state/IMU navigation, attributed NVIDIA locomotion weights, and the tested observation-gap adapter. All dependencies are installed at build time. Its SHA-256 sidecar identifies the exact bytes used by native ARM64 CI.

The selected navigation configuration exited 20 development episodes at nominal timing. Final randomized evaluation remains separate. An earlier native standard-scene run passed. Its task report hit a plant-response timeout during export; the next workflow discloses a report-only RPC timeout fix in an isolated kit copy. Active control, dynamics, gains and safety checks are unchanged. This release is for exact-image validation and does not itself establish a native task pass.

An extra full 20 ms command delay is a known limitation. Production excludes the rejected prediction/waist experiments. The image uses config/navigation.json and config/deployment.json from this release's source commit.

The optional development MP4 replays a saved successful simulation. It is not hardware evidence.
