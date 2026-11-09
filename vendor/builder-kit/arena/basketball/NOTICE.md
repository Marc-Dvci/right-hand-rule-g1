# Basketball compatibility bridge

`policy.py` and the `Sim`/`yaw_matrix` portions of `simulation.py` are derived from the public G1 Brunson submission (Arena source_641045110d48de6239e5), whose README declares MIT licensing. The original controller and observation semantics are preserved. The archive fingerprint is recorded in bundle.json. Robot assets are read only from fingerprint-matching submissions; they are not embedded here.

# Third-party notices

- **Unitree G1 robot description** (`assets/g1_robot.xml`, `assets/assets/g1/*.STL`, `assets/provenance/*`):
  Copyright Unitree Robotics, BSD-3-Clause, from https://github.com/unitreerobotics/unitree_ros
  (`robots/g1_description`, commit 7d6075f) and https://github.com/unitreerobotics/unitree_rl_mjlab
  (`src/assets/robots/unitree_g1/xmls/g1.xml`, commit 1425b15; actuator constants from
  `g1_constants.py` and `deploy.yaml`).
- **MuJoCo / MJX** (Apache-2.0), **Brax** (Apache-2.0), **MuJoCo Playground** (Apache-2.0; PPO
  hyper-parameters and env structure follow its G1 examples), **JAX** (Apache-2.0).
- Coaching references used for the task definition: "Ball Handling Skills & Drills" (Winnetka
  coaching handout), basketballarmy.com "How to dribble between your legs", xbotgo.com "How to do a
  crossover dribble". Ball/court standards: NBA Official Rules Rule 1, FIBA Official Basketball Rules
  (Basketball Equipment).
