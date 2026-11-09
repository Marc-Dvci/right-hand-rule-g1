"""Check the reviewed Brunson graph against its authored clamp equations."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def verify(root):
    import numpy as np
    from basketball.policy import MLPPolicy, ACTION_SCALE
    from basketball.profile_controller import session, infer
    from basketball.screen import BasketballSimulation, validate_weights
    validate_weights(root / 'policy_weights.npz')
    model, mlp = session(root), MLPPolicy(root / 'policy_weights.npz')
    profile = json.loads((root / 'assets/arena_g1_profile.json').read_text())
    rate = np.asarray([j['max_velocity_rad_s']*.02 for j in profile['joints']], np.float32) / ACTION_SCALE
    first = .8 * profile['initial_position_tolerance_rad'] / ACTION_SCALE
    rng, worst = np.random.default_rng(20261012), 0.
    for side in range(2):
        sim = BasketballSimulation(root, 1000 + side, side)
        np.testing.assert_allclose(sim.kp, [j['kp'] for j in profile['joints']])
        assert np.max(abs(sim.data.ctrl - sim.data.qpos[7:36])) <= .005
        lo = np.maximum([j['position_min_rad'] for j in profile['joints']], sim.bounds[:, 0]) + .01
        hi = np.minimum([j['position_max_rad'] for j in profile['joints']], sim.bounds[:, 1]) - .01
        for i in range(256):
            obs = (mlp.mean + mlp.std * rng.normal(size=115)).astype(np.float32)
            obs[114] = 1 if side == 0 else -1
            obs[64:93] = 0 if i % 4 == 0 else rng.uniform(-1, 1, 29)
            limit = first if not np.any(obs[64:93]) else rate
            expected = np.clip(mlp.forward(obs), obs[64:93] - limit, obs[64:93] + limit)
            expected = np.clip(expected, (lo - sim.source.stance_ctrl) / ACTION_SCALE, (hi - sim.source.stance_ctrl) / ACTION_SCALE)
            actual = infer(model, obs[None])
            np.testing.assert_allclose(actual, expected, atol=2e-5, rtol=2e-5)
            worst = max(worst, float(abs(actual - expected).max()))
    return {'test_inputs': 512, 'max_absolute_error': worst}


if __name__ == '__main__':
    from evaluate import unpack
    release = json.loads(Path('/opt/release.json').read_text())
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        unpack(Path(sys.argv[1]), root, release)
        base = next(root.rglob('policy_weights.npz')).parent
        print(json.dumps(verify(base)))
