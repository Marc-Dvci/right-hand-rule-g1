import numpy as np
from policy.controller import Controller
from policy.networks import DEFAULT


def test_arc_timeout_enters_bounded_sensor_only_reacquisition():
    c=Controller(control={'arc_reacquire':True})
    obs=dict(q=DEFAULT.copy(),dq=np.zeros(29),quat=np.array([1.,0,0,0]),gyro=np.zeros(3))
    c.act(obs)
    c.state='ARC'
    c.arc_start=0.
    c.state_age=35.
    c.age=40.
    c.velocity_integral[:]=.25
    c.act(obs)
    assert c.state=='FIND' and c.seek_forward
    assert c.recoveries==1
    assert c.events[-1]['cause']=='arc_wall_reacquisition'
    c.recoveries=8
    c.state='ARC'
    c.state_age=35.
    c.act(obs)
    assert c.state=='STOP'


def test_wall_search_recovers_only_after_previous_contact_search_not_initial_empty_space():
    obs=dict(q=DEFAULT.copy(),dq=np.zeros(29),quat=np.array([1.,0,0,0]),gyro=np.zeros(3))
    c=Controller(control={'arc_reacquire':True})
    c.act(obs)
    c.state='FIND'
    c.state_age=25.
    c.age=40.
    c.act(obs)
    assert c.state=='STOP'
    c.state='FIND'
    c.state_age=25.
    c.recoveries=1
    c.act(obs)
    assert c.state=='RETRACT_LEFT'
    assert c.recoveries==2
