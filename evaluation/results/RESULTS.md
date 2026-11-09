# Measured results

Frozen controller: `eb00abad80dc9764ff75136e3e462e2b87eb4403a4409c86016fbe52c8695152`. Primary split: **94/100 exits**, 0 falls, 0 checker stops, 0 episodes with actual limit findings. Median successful time 157.42 s; peak thrash 0.711666 / 1.5.

There are 14 distinct maze topologies across 100 randomized episodes. All seed draws, raw per-episode results, hashes and an independent full-trace audit are preserved.

| Comparison | Exits | Checker stops | Episodes with actual limit findings |
|---|---:|---:|---:|
| Neutral | 0/10 | 0 | 0 |
| Touch off | 0/10 | 0 | 0 |
| Touch delayed 3.4 s | 0/10 | 0 | 1 |
| True map + basic dead reckoning | 0/10 | 0 | 0 |
| Additional 20 ms command delay | 4/5 | 0 | 0 |
| Additional 40 ms command delay | 0/5 | 5 | 0 |

The complete touch controller exited 9/10 on the matched control seeds. Controls use the first ten primary seeds; command-delay stresses use the first five. The map baseline deliberately receives the true static map; it is never deployed. The delayed-touch control is a fixed delay, not random shuffling.

## All six primary navigation failures

| Seed | Final state | Simulated seconds |
|---|---|---:|
| 26111503 | FOLLOW | 400.00 |
| 26111551 | STOP | 138.52 |
| 26111559 | STOP | 103.92 |
| 26111569 | STOP | 121.02 |
| 26111590 | STOP | 82.46 |
| 26111594 | STOP | 159.28 |

No failed episode is replaced or removed.

## Native ARM64

Exact archive SHA-256: `e6efe832912adb46f547911b29b8240a87234a6b68684bb26c0622852ac79f92`. Standard 3/3; task 3/3; designated exits 3/3. Peak native thrash: 0.389558.

| Task repeat | Exit time (s) | Checker |
|---|---:|---|
| 1 | 168.175630 | simulation_checks_complete |
| 2 | 168.175630 | simulation_checks_complete |
| 3 | 168.175630 | simulation_checks_complete |

Task runs disclose the post-run report-RPC-only timeout fix. Canonical vendor files, active deadlines, physics and checks are unchanged. [Raw workflow](https://github.com/Marc-Dvci/right-hand-rule-g1/actions/runs/42656538931).

## Every counterfactual start

| Scene | Start | Outcome | Handoff |
|---|---|---|---|
| standard | left_side | base_angular_speed_limit | none |
| standard | prone | base_angular_speed_limit | none |
| standard | right_side | base_angular_speed_limit | none |
| standard | seated | base_angular_speed_limit | none |
| standard | standing | within_limits | 2.00 s |
| standard | supine | base_angular_speed_limit | none |
| task | left_side | Rejected: initial penetration; no report | none |
| task | prone | base_angular_speed_limit | none |
| task | right_side | base_angular_speed_limit | none |
| task | seated | Rejected: initial penetration; no report | none |
| task | standing | within_limits | 2.00 s |
| task | supine | Rejected: initial penetration; no report | none |

Both suites return `review_required`; floor-pose violations and errors are not claimed as passes.

## Force and physical transfer

The worst raw 500 Hz hand-contact impulse in the primary split is **175.36 N**. The hero force-vector RMS is 1.883 N (26.0% of target), with 0.925 m endpoint odometry error. The original 20 N peak-force and 25% force-error gates are not met. No hardware authorization or delay-robustness claim is made. See [the implementation audit](../../PROJECT_AUDIT.md) and [hardware qualification notes](../../HARDWARE_ATTEMPT.md).
