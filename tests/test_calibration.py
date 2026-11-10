import numpy as np
import pytest
from policy.calibration import CommandAgeCalibration


@pytest.mark.parametrize('delay',[0,1,2])
def test_command_age_identification_handles_unknown_inertia_and_sensor_noise(delay):
    c=CommandAgeCalibration()
    rng=np.random.default_rng(2110+delay)
    q,dq=0.,0.
    queue=[]
    for frame in range(100):
        c.observe(q+rng.normal(0,.0007),dq+rng.normal(0,.005))
        torque=c.excitation(frame)
        c.issued(0.,torque)
        queue.append(torque)
        applied=queue[max(0,len(queue)-1-delay)]
        for _ in range(10):
            acceleration=(applied-60*q-1.5*dq-.005*np.sign(dq))/.011
            dq+=.002*acceleration
            q+=.002*dq
    assert c.fit()==delay
    assert c.confidence>.15


def test_unexcited_calibration_fails_without_guessing_a_delay():
    c=CommandAgeCalibration()
    for _ in range(100):
        c.observe(0.,0.)
        c.issued(0.,0.)
    with pytest.raises(ValueError,match='excitation'):
        c.fit()
    assert c.selected is None
