import numpy as np
import pytest
from policy.controller import ControlParameters,Controller
from policy.networks import DEFAULT


@pytest.mark.parametrize('kwargs',[{'walker_prediction':np.nan},{'waist_gravity':-1},
    {'action_filter':0},{'arm_stiffness':np.inf},{'bounded_navigation':'true'}])
def test_control_parameters_reject_invalid_settings(kwargs):
    with pytest.raises(ValueError):
        ControlParameters(**kwargs)


def test_bounded_navigation_limits_turn_translation_after_windup():
    c=Controller(control={'bounded_navigation':True})
    obs=dict(q=DEFAULT.copy(),dq=np.zeros(29),quat=np.array([1.,0,0,0]),gyro=np.zeros(3))
    c.act(obs)
    c.state='TURN'
    c.state_age=4
    c.heading=1.
    c.velocity_integral[:]=.25
    for _ in range(100):
        c.act(obs)
    assert np.all(abs(c.velocity_command[:2])<=.0600001)
    assert np.all(c.velocity_integral==0)
