# Sensor contract

The complete controller uses joint state and pelvis IMU only. There is no camera, lidar, map input, contact sensor, base-state input or simulator import in `policy/`.

| Input | Format | Units and frame | Rate |
|---|---|---|---|
| Joint position `q` | 29 finite numbers, exact HIM/Unitree SDK motor order | radians | 50 Hz |
| Joint velocity `dq` | same order | radians/second | 50 Hz |
| `quat` | `[w,x,y,z]`, unit quaternion | pelvis orientation in the inertial frame | 50 Hz |
| `gyro` | 3 finite numbers | pelvis angular velocity, radians/second in pelvis frame | 50 Hz |
| `control_ready` | boolean host lifecycle signal | enables the routine clock after actual handoff | 50 Hz |

Transport: joint state from `/safety/policy_observation` and IMU from `/safety/policy_state`. They must have the same observation ID. The adapter caches at most 16 messages per stream, rejects duplicate/out-of-order IDs and pairs older than 120 ms, uses the checker-issued session ID, and publishes all 29 slots to `/safety/precheck`.

The adapter copies only quaternion, gyro and control readiness from the JSON feed. It discards simulator position, base velocity, object state and any other fields. A test replaces these fields with invalid values and checks bitwise equality of commands. Distances and translations used by the policy are estimates obtained from stance-foot joint kinematics, with the IMU providing relative orientation. Their errors are evaluated against simulator truth in the harness; truth never crosses the policy boundary.

Invalid joint/IMU shape, nonfinite values or an invalid quaternion stop publication. Missing/freshness failures let the host's normal deadlines stop output. `/safety/abort` latches the adapter off. The image never publishes motor commands directly.

Touch is inferred from the previous requested command, the observed arm deflection/velocity, the host's fixed gains, and an exported arm gravity/Jacobian model. This estimates contact; it does not directly measure motor torque. Feedforward feedback softens arm contact and restores the pretrained walker's waist impedance while retaining host-approved gains. These assumptions require supervised hardware qualification.
