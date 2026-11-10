# RIGHT HAND RULE V2 — review guide

A free-standing G1 navigates unknown maze walls using only joint state and its
pelvis IMU. The right hand feels the wall; the left arm probes ahead. Contact
inference and navigation are scripted over attributed pretrained NVIDIA GR00T
locomotion. No layout, camera, simulator contact label or world position enters
the deployed controller.

Read [audited results](evaluation/results/v2/RESULTS.md), then
[plan coverage and limitations](PROJECT_AUDIT_V2.md). The film replays measured
states; its complete-run segment, corner closeups and four-layout grid have
disclosed selection and speed labels. Every final failure stays in the tables.

## What to inspect

- `policy/calibration.py`: local wrist input/output identification of command
  age, with explicit ambiguity handling and no evaluator timing label.
- `policy/controller.py`: past-command-aligned inferred contact, bounded turns,
  odometry stagnation detection and bounded wall reacquisition.
- `container/ros_node.py`: full safety interface, 29 command slots, matched
  observation/session IDs and latched abort behavior.
- `evaluation/frozen-v2.json`, `tools/audit_v2.py`: topology-disjoint protocol,
  exact source/settings/assets, complete episode inventory and independent scoring.
- `evidence/sensor-proof/v2-selected.npz`: allowed-sensor command proof. Run
  `python tools/sensor_replay.py --bundle evidence/sensor-proof/v2-selected.npz`.
  This requires NumPy and the controller, with no MuJoCo import.
- `reports/v2/`: every primary/control outcome, exact-image native evidence and
  all startup outcomes. Larger portable motions and raw native traces are
  external release artifacts with SHA-256 digests.

## Reproduce

Use Linux, Python 3.12 and `pip install -r requirements.txt`. A working EGL
driver is needed for saved-state rendering. Run `./run.sh` for tests, source
freeze verification, a development maze and its replay. Evidence uses a new
timestamped directory and does not replace the published results.

The entire final protocol can be reproduced in new evidence directories:

```bash
python harness/catalog_cohort.py --final --name reproduce-v2-primary --control-config config/control.json --workers 4
for mode in neutral touch_off touch_shuffled; do
  python harness/catalog_cohort.py --final --name "reproduce-v2-$mode" --mode "$mode" --control-config config/control.json --workers 4
done
python tools/audit_v2.py evidence/catalog/reproduce-v2-primary evidence/catalog/reproduce-v2-neutral evidence/catalog/reproduce-v2-touch_off evidence/catalog/reproduce-v2-touch_shuffled --output reports/v2/reproduction-audit.json
```

For native ARM64, obtain the image referenced by `g1-runner.json`, verify its
archive digest, put it in `dist/submission.tar`, load it with Docker and run
`python tools/audit_image.py`. Then use
`python screen_maze.py --container --seed 0 --seconds 300` for the complete task.
This uses the disclosed report-export-only RPC extension. Standard kit checks
and the six start outcomes are separate; no all-pose or hardware pass is claimed.

The original low-force gate is unmet. This is simulation evidence for a
supervised qualification proposal. [Hardware limits](HARDWARE_ATTEMPT.md) and
[next improvements](NEXT_IDEAS.md) remain part of the entry.
