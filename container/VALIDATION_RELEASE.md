This is a development validation image for RIGHT HAND RULE, not a hardware-qualified controller or a final HIM Arena submission.

The archive contains the complete linux/arm64 ROS 2 policy image, with joint-state/IMU navigation, attributed NVIDIA locomotion weights, and the tested observation-gap adapter. All dependencies are installed at build time. Its SHA-256 sidecar identifies the exact bytes used by native ARM64 CI.

The local standard-scene container run passed the unmodified HIM builder kit under QEMU 10.2.3. The task-scene validation and navigation parameter search remain in progress. Reports are retained and claims are limited to what was actually tested.

The optional development MP4 replays a saved successful simulation. It is not hardware evidence.
