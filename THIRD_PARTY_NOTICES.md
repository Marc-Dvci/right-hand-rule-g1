# Third-party notices and provenance

## HIM G1 builder kit

Public release `g1-builder-kit-e93c492-v1.zip`, runner revision `e93c49267a7b6b905c6666c8c70668f8ee7ac397`:
https://arena.himrobotics.com/docs/g1-policy-checks

The vendored public kit retains its original notices and per-file `UPSTREAM_FILES.json` hashes. A test verifies every manifest entry. The evaluation harness imports its original `Runner` and `Plant`; the transport and navigation controller are our additions. Local in-process runs are not submitted-container runs.

## NVIDIA pretrained locomotion models

Repository: https://github.com/NVlabs/GR00T-WholeBodyControl

Revision: `b042411fae38ee4d1af9aac82a37a1f8d14d6dd0`.

The original Walk and Balance networks are redistributed under the NVIDIA Open Model License retained verbatim at `policy/models/LICENSE-NVIDIA`. The exact original filenames, source paths and SHA-256 digests are in `policy/models/provenance.json`. The `.npz` files contain those original weights for equivalent NumPy inference. They are not newly trained policies. The navigation and arm-compliance logic is scripted.

## Unitree robot assets

G1 geometry and inertial parameters are from the assets included in HIM's public kit. Original Unitree notices and BSD license are retained under `scene/robot/third_party/unitree_g1/` and the vendored kit. `scene/robot/g1_touch.xml` is a generated derivative: self-contained mesh paths, a visual blindfold, original palm spheres disabled and low-friction hand capsules enabled. Masses and inertial parameters are unchanged; the capsules have zero additional mass and represent the existing hands. These scene changes are disclosed and are not changes to the runner or checker.

## Software

MuJoCo, NumPy, ONNX, ONNX Runtime, SciPy, Pillow, pytest and FFmpeg are third-party dependencies. Their licenses remain with their respective distributions. Runtime container inference requires NumPy and ROS 2 Foxy; ONNX Runtime and MuJoCo do not run inside the submitted policy process.
