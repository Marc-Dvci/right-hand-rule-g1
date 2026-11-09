"""NumPy inference of the original NVIDIA GR00T WBC networks (no retraining)."""
from pathlib import Path
import numpy as np

MODELS = Path(__file__).resolve().parent / 'models'
DEFAULT = np.zeros(29, dtype=np.float32)
DEFAULT[:15] = [-.1, 0, 0, .3, -.2, 0, -.1, 0, 0, .3, -.2, 0, 0, 0, 0]
LOWER = np.array([-2.5307, -.5236, -2.7576, -.087267, -.87267, -.2618,
                  -2.5307, -2.9671, -2.7576, -.087267, -.87267, -.2618, -2.618, -.52, -.52])
UPPER = np.array([2.8798, 2.9671, 2.7576, 2.8798, .5236, .2618,
                 2.8798, .5236, 2.7576, 2.8798, .5236, .2618, 2.618, .52, .52])


def rotation(quat):
    w, x, y, z = np.asarray(quat, dtype=float)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-w*z), 2*(x*z+w*y)],
                     [2*(x*y+w*z), 1-2*(x*x+z*z), 2*(y*z-w*x)],
                     [2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y)]])


def elu(x):
    return np.maximum(x, 0) + np.expm1(np.minimum(x, 0))


class Network:
    def __init__(self, path):
        with np.load(path, allow_pickle=False) as z:
            self.weights = {k: z[k].copy() for k in z.files}

    def linear(self, x, name):
        return x @ self.weights[name + '.weight'].T + self.weights[name + '.bias']

    def __call__(self, features):
        x = np.asarray(features, dtype=np.float32)
        if x.ndim == 1:
            x = x[None, :]
        if x.ndim != 2 or x.shape[1] != 516 or not np.isfinite(x).all():
            raise ValueError('Expected finite [batch, 516] features')
        z = self.linear(elu(self.linear(elu(self.linear(x, 'estimator.0')), 'estimator.2')), 'estimator.4')
        latent = z[:, 3:]
        latent = latent / np.maximum(np.linalg.norm(latent, axis=1, keepdims=True), np.float32(1e-12))
        a = np.concatenate((x[:, -86:], z[:, :3], latent), axis=1)
        for name in ('actor.0', 'actor.2', 'actor.4'):
            a = elu(self.linear(a, name))
        return self.linear(a, 'actor.6')


class Walker:
    def __init__(self):
        self.walk = Network(MODELS / 'walker.npz')
        self.balance = Network(MODELS / 'balance.npz')
        self.reset()

    def reset(self):
        self.history = np.zeros((6, 86), np.float32)
        self.action = np.zeros(15, np.float32)
        self.seeded = False
        self.last_features = np.zeros(516, np.float32)

    def update(self, q, dq, quat, gyro, command):
        obs = np.zeros(86, np.float32)
        obs[:3] = np.asarray(command) * [2, 2, .5]
        obs[3] = .74
        obs[7:10] = np.asarray(gyro) * .5
        obs[10:13] = -rotation(quat)[2, :]
        obs[13:42] = np.asarray(q) - DEFAULT
        obs[42:71] = np.asarray(dq) * .05
        obs[71:] = self.action
        if not self.seeded:
            self.history[:] = obs
            self.seeded = True
        else:
            self.history[:-1] = self.history[1:]
            self.history[-1] = obs
        self.last_features = self.history.reshape(-1).copy()
        net = self.balance if np.linalg.norm(command) < 1e-6 else self.walk
        self.action = net(self.last_features)[0]
        if not np.isfinite(self.action).all():
            raise ValueError('Nonfinite network output')
        return np.clip(self.action * .25 + DEFAULT[:15], LOWER, UPPER)
