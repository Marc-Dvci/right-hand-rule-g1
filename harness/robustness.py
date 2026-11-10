"""Declared evaluator-only physical stresses; canonical kit source stays unchanged."""
import numpy as np


def configure(plant, specification):
    if not specification:
        return None
    if set(specification)-{'velocity_damping_scale','push'}:
        raise ValueError('Unknown robustness stress')
    scale=float(specification.get('velocity_damping_scale',1.))
    if not np.isfinite(scale) or not .8<=scale<=1.2:
        raise ValueError('Damping stress must stay within 0.8 to 1.2')
    original=plant._apply_arrays
    def with_damping(q,dq,kp,kd,tau):
        original(q,dq,kp,kd,tau)
        # Modify effective velocity damping after the host installs its approved
        # gains. Never compound the multiplier or change checker thresholds.
        plant.model.actuator_biasprm[plant.actuators,2]=-np.asarray(kd)*scale
    plant._apply_arrays=with_damping
    plant.model.actuator_biasprm[plant.actuators,2]*=scale
    push=specification.get('push')
    if push:
        if push['start']<10 or not 0<push['duration']<=.5 or np.linalg.norm(push['force'])>20:
            raise ValueError('Invalid bounded post-calibration push')
        if push['body']!='pelvis':
            raise ValueError('This stress protocol uses pelvis pushes only')
        plant.set_push(push)
    return dict(velocity_damping_scale=scale,push=push,
        effective_velocity_damping=((-plant.model.actuator_biasprm[plant.actuators,2]).tolist()),
        scope='Evaluator-only actuation damping uncertainty and optional canonical Plant.set_push. '
              'Nominal command gains, checker thresholds, robot assets and collision properties remain unchanged.')
