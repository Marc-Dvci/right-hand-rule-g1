# Prioritized improvements after the frozen V2 evaluation

1. Reduce hand and body impact loads together. Instrument a compliant wall;
   identify actuator filtering and force-estimator bias; add clearance-aware
   contact acquisition and verify load envelopes over a broad development set.
   A spring-torque cap alone did not bound physical impacts. Separate filtered
   navigation memory from fast load guarding and validate sustained no-contact
   periods as well as the declared instantaneous sample criterion.
2. Qualify varying command delay and hardware model mismatch. Current local
   identification covers constant 0/20/40 ms in free space. Detecting changes
   during contact needs a different validation protocol.
3. Repair the frozen cohort's remaining navigation failure modes using **new**
   development data. Never retune on the reported geometry holdout and keep
   calling it unseen.
4. Use the completed 50-per-primitive records to improve contact continuity and
   force control, then qualify larger grids, different wall geometry and
   compliant surface materials on newly declared data.
5. Improve stance-foot odometry before enabling map-based heading correction,
   memory traversal or guided-hand operation. Existing maps are logging only.
6. Resolve startup-pose failures and invalid initial contacts with HIM, while
   preserving original safety thresholds and reporting pre-handoff outcomes.
7. Attempt a single instrumented wall and corner on a real G1 only after HIM's
   separate hardware qualification of the exact image, timing and torque response.
