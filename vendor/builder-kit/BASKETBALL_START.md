# Exact basketball screening starts

Use screen_basketball.py to reproduce the same reviewed code; do not run the submitted evaluation scripts as a substitute. MuJoCo 3.3.7 CPU; 2 ms physics, 20 ms controller. Default episodes n=0..11 use seed=1000+n, stance=n%2. Stance 0 is left foot forward; 1 right foot forward. Each episode has an independent NumPy default_rng(seed).

The full reset is in arena/basketball/simulation.py. Order matters:

1. Load the selected stance keyframe. Resolve target positions using the controller gains in assets/arena_g1_profile.json. Initialize joints at those targets plus 29 independent uniform(-0.005,+0.005) draws. Retain the keyframe pelvis height. The v11 reference corrects the authored stance and uses 10 solver and 10 line-search iterations.
2. Draw yaw uniformly from [-pi,pi] and compose the pelvis quaternion. Forward the model to calculate feet and pelvis positions.
3. Draw a uniform coin; values below 0.3 select the moving-ball start. next_hand=1-stance; side=-1 for next_hand=1, otherwise +1. R is the pelvis yaw rotation; gate is the midpoint between the two foot sites.
4. Moving start (30%): pos=pelvis+R@[0.32,0.30*side,0]; replace world z with 0.38; add three world-axis uniform(-0.03,+0.03) draws. Draw tf uniformly from [0.15,0.28]. Set horizontal velocity=(gate.xy-pos.xy)/tf; vertical velocity=min(-((pos.z-ball_radius)/tf-0.5*9.81*tf),0).
5. Stationary start (70%): pos=pelvis+R@[0.22,0.30*side,0]; replace world z with 0.50; add three world-axis uniform(-0.04,+0.04) draws. Set linear velocity to zero.
6. Ball quaternion is identity, angular velocity zero. Both branches start tracker expect=0 (waiting for hand contact); a spawned ball never scores on its own. No ball respawn.

Ball position/velocity observations are relative to the pelvis in its yaw frame (velocity subtracts pelvis velocity), delayed by one control step. Noise: position ±0.015 m, velocity ±0.15 m/s. Three six-value frames are stacked newest first; initialize history by repeating the first frame. Other sensor noise and task cue calculations are in the exact included bridge. No camera images are used.

Observation noise is enabled: gyro ±0.2 rad/s, gravity components ±0.05, joint positions ±0.01 rad and joint velocities ±1.5 rad/s, all uniform. The v11 uploaded arena_screen_cpu.py disables observation noise and chooses random stances; its 36 clean episodes are not identical to Arena's test distribution. Use this kit to reproduce the actual screen before changing your controller.

Each scenario's ball_start records the actual world position, linear velocity, pelvis pose, hand and release state. task_metrics.crossovers and task_summary report observed behavior separately from the unchanged safety verdict. A simulation with no findings may still fail to dribble. Physical placement is a separate supervised test plan, not specified by this random simulation reset.
