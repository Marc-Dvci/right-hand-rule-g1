"""Data-only ONNX contract for profile-gain G1 basketball controllers.

The submitted graph retains its own normalization and command clamps. No Python
from an upload is imported. Scene/profile semantics are pinned by bundle.json.
"""
import json
from pathlib import Path
import numpy as np
import onnx
import onnxruntime as ort

CONTRACT = 'g1-basketball-115-profile-v1'


def session(root):
    path = Path(root) / 'policy.onnx'
    if not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('Include policy.onnx (at most 16 MB) with the complete 115-input, 29-output basketball controller.')
    model = onnx.load_model(path, load_external_data=False)
    if any(t.external_data for t in model.graph.initializer):
        raise ValueError('Export this basketball controller as one self-contained policy.onnx file.')
    onnx.checker.check_model(model)
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    result = ort.InferenceSession(model.SerializeToString(), sess_options=options, providers=['CPUExecutionProvider'])
    for values, width in ((result.get_inputs(), 115), (result.get_outputs(), 29)):
        if len(values) != 1 or values[0].type != 'tensor(float)' or len(values[0].shape) != 2 or values[0].shape[1] != width or (isinstance(values[0].shape[0], int) and values[0].shape[0] != 1):
            raise ValueError('Export one float32 observation [1,115] to one float32 action [1,29], with optional dynamic batch. Include normalization and all controller clamps in the graph.')
    return result


def configure(sim, root):
    """Match the reviewed authored safety-mode gains and starting targets."""
    profile = json.loads((Path(root) / 'assets/arena_g1_profile.json').read_text())
    joints = profile['joints']
    m = sim.m
    if [j['name'] for j in joints] != [m.actuator(i).name for i in range(m.nu)]:
        raise ValueError('The basketball joint order differs from its declared profile.')
    kp, kd = (np.asarray([j[k] for j in joints], dtype=np.float64) for k in ('kp', 'kd'))
    original_kp = m.actuator_gainprm[:, 0].copy()
    sim.profile_stance_targets = {
        side: key.qpos[7:36] + (key.ctrl - key.qpos[7:36]) * original_kp / kp
        for side, key in sim.keys.items()
    }
    m.actuator_gainprm[:, 0] = kp
    m.actuator_biasprm[:, 1] = -kp
    m.actuator_biasprm[:, 2] = -kd
    limit = np.minimum(m.actuator_forcerange[:, 1], .98 * np.asarray([j['max_torque_nm'] for j in joints]))
    m.actuator_forcerange[:, 0], m.actuator_forcerange[:, 1] = -limit, limit
    m.actuator_forcelimited[:] = 1


def infer(session, observation):
    action = session.run(None, {session.get_inputs()[0].name: np.asarray(observation, np.float32)})[0]
    if action.shape != (1, 29) or not np.isfinite(action).all():
        raise ValueError('The basketball model returned invalid joint actions.')
    return action[0]
