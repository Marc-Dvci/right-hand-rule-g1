# Supervised hardware attempt

This project has no physical robot results. Simulation results and a container check do not authorize hardware. HIM must qualify the image, sensors, torque response and operating area before any motion.

Begin with a wall and one corner, not a maze. Use a stable partition at least 0.9 m tall, a clear floor, HIM's normal gantry/tether and emergency stop, and no people within reach. Confirm gantry travel before enabling translation. A thin smooth mitten may be needed; the simulated hand surface has lower friction than the kit's original palm spheres.

Before walking, log a stationary no-contact arm extension and light wall contact. Compare inferred force with an independent force gauge. Confirm feedforward sign, motor order, quaternion convention, timestamps and the actual joint profile. The arm model is the kit's G1 model; hardware variants, covers, carried masses and waist configuration can invalidate it.

The host waist gains remain 60/1.5. V2 uses additional bounded 40/3.5 waist feedback and gravity compensation, with the waist-yaw target and additional yaw feedforward suppressed. Qualify the complete torque response at measured transport latency. V2 identifies a constant 0/20/40 ms command age using a 0.5 Nm wrist-roll excitation before navigation. This requires a free-space calibration start. It does not qualify arbitrary, changing or longer delays, hardware friction or unknown actuator filtering.

Raw simulated hand-force impulses exceed 20 N, and development has recorded nonhand wall impacts above 300 N. The filtered force guard does not bound those impulses. The original low-force gate is unmet. Start with a compliant, instrumented surface and a force-gauge comparison before considering a rigid wall. The logging-only touch map has odometry drift and must not be used for personnel or obstacle clearance.

The runner balances first. After handoff, the arms extend slowly; the robot searches to its right, follows contact, and reacts to the forward probe or a disappearing wall. A missing wall ends the bounded search and holds a stand. A high inferred force enters a guard hold. The host owns all safety stops.

Abort for any kit stop, unexpected contact, a person entering the path, a slipping wall, excessive hand load, loss of tether clearance or poor force-estimator agreement. Do not use this as a firefighting or life-safety system.

Record joint/IMU/command logs, the image digest, wall dimensions and material, overhead and side video, and measured contact force. Test only the smallest motion whose simulation and hardware evidence has been reviewed.
