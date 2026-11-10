import numpy as np
import pytest
from policy.controller import ControlParameters,Controller,Parameters
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


def test_disabled_waist_yaw_sends_neutral_target_without_delayed_extra_spring():
    c=Controller(control={'waist_yaw_scale':0.,'turn_safety':True})
    q=DEFAULT.copy()
    q[12]=.1
    obs=dict(q=q,dq=np.zeros(29),quat=np.array([1.,0,0,0]),gyro=np.zeros(3))
    command=c.act(obs)
    assert command['q'][12]==command['tau'][12]==c.walker.action[12]==0.


def test_touch_estimation_uses_the_declared_applied_command_not_new_unapplied_targets():
    q=DEFAULT.copy()
    obs=dict(q=q,dq=np.zeros(29),quat=np.array([1.,0,0,0]),gyro=np.zeros(3))
    c=Controller(control={'force_command_age_steps':2})
    c.act(obs)
    kin=c.model.evaluate(q,obs['quat'])
    gravity=np.r_[np.zeros(15),kin['left']['gravity'],kin['right']['gravity']]
    applied=dict(q=q.copy(),tau=gravity)
    future=dict(q=q+.1,tau=gravity.copy())
    c.command_history.clear()
    c.command_history.extend([applied,future,future])
    c.last_command=future
    c.act(obs)
    np.testing.assert_allclose(c.force,0,atol=1e-9)


def test_robust_touch_uses_only_past_commands_and_exposes_uncertainty():
    q=DEFAULT.copy()
    obs=dict(q=q,dq=np.zeros(29),quat=np.array([1.,0,0,0]),gyro=np.zeros(3))
    c=Controller(control={'robust_touch':True})
    c.act(obs)
    kin=c.model.evaluate(q,obs['quat'])
    gravity=np.r_[np.zeros(15),kin['left']['gravity'],kin['right']['gravity']]
    c.command_history.clear()
    c.command_history.extend([dict(q=q.copy(),tau=gravity),dict(q=q+.1,tau=gravity)])
    c.last_command=c.command_history[-1]
    c.act(obs)
    np.testing.assert_allclose(c.force,0,atol=1e-9)
    assert (c.force_ambiguity>1).all()
    np.testing.assert_array_equal(c.force_age,[1,1])


def test_stagnation_recovery_requires_persistent_sensor_only_no_progress():
    c=Controller(control={'stagnation_recovery':True,'turn_safety':True})
    obs=dict(q=DEFAULT.copy(),dq=np.zeros(29),quat=np.array([1.,0,0,0]),gyro=np.zeros(3))
    c.act(obs)
    c.started=True
    c.age=10
    c.state='FOLLOW'
    c.state_age=4
    # Suppress wall-loss transition while testing an arm/body snag.
    c.navigation_force[1,1]=7
    c.force[1,1]=7
    c.parameters=Parameters(**{**c.parameters.__dict__,'lost_seconds':100.})
    kin=c.model.evaluate(obs['q'],obs['quat'])
    gravity=np.r_[np.zeros(15),kin['left']['gravity'],kin['right']['gravity']]
    for _ in range(255):
        c.last_command=dict(q=obs['q'].copy(),tau=gravity)
        c.act(obs)
    assert c.recoveries==1
    assert any(e.get('cause')=='joint_odometry_stagnation' for e in c.events)
