from pathlib import Path
import sys
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from policy.controller import Controller
from policy.networks import Network, DEFAULT


def observation():
    return dict(q=DEFAULT.copy(), dq=np.zeros(29), quat=[1,0,0,0], gyro=[0,0,0])


@pytest.mark.parametrize('name', ['walker','balance'])
def test_exported_network_matches_recorded_onnx_fixture(name):
    with np.load(ROOT/f'tests/fixtures/{name}-parity.npz') as fixture:
        expected = fixture['expected']
        actual = Network(ROOT/f'policy/models/{name}.npz')(fixture['features'])
    np.testing.assert_allclose(actual, expected, atol=1e-4, rtol=0)


def test_privileged_fields_cannot_affect_actions():
    left, right = Controller(), Controller()
    class Restricted(dict):
        def __getitem__(self, key):
            assert key in ('q','dq','quat','gyro'), f'Privileged read: {key}'
            return super().__getitem__(key)
    for i in range(40):
        clean = observation()
        garbage = Restricted(clean, position=object(), base_velocity='invalid',
                             contact_force=float('nan'), maze='different', sim_time=-1e99)
        a, b = left.act(clean, ready=i>5), right.act(garbage, ready=i>5)
        for field in ('q','dq','kp','kd','tau'):
            assert a[field].shape == (29,)
            assert np.isfinite(a[field]).all()
            np.testing.assert_array_equal(a[field], b[field])


def test_navigation_clock_waits_for_actual_handoff():
    controller = Controller()
    for _ in range(20):
        controller.act(observation(), ready=False)
    assert controller.age == 0
    assert controller.state == 'ARMING'
    controller.act(observation(), ready=True)
    assert controller.age == .02


@pytest.mark.parametrize('field,value', [('q',[0]*28), ('dq',[float('nan')]*29),
                                       ('quat',[0,0,0,0]), ('gyro',[0,0,float('inf')])])
def test_invalid_telemetry_stops_output(field, value):
    obs = observation()
    obs[field] = value
    with pytest.raises(ValueError):
        Controller().act(obs)


def test_reset_discards_motion_and_contact_history():
    controller = Controller()
    controller.act(observation())
    controller.transition('TURN')
    controller.reset()
    assert controller.state == 'ARMING'
    assert controller.last_command is None
    assert not controller.events
    assert not controller.force_history
    assert controller.age == 0
