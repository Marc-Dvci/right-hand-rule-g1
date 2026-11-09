import types
import numpy as np
from container.timing import TimedPolicy


def test_reconstruction_uses_held_motor_command_and_held_network_action():
    seen = []
    physical = {'q':np.ones(29)}
    controller = types.SimpleNamespace(last_command=physical,walker=types.SimpleNamespace(action=np.ones(15)))
    def act(obs,ready):
        seen.append((obs['q'].copy(),controller.last_command,controller.walker.action.copy()))
        command = {'q':obs['q'].copy()}
        controller.last_command = command
        controller.walker.action = np.full(15,7.)
        return command
    controller.act = act
    timed = TimedPolicy(controller)
    obs = dict(q=np.zeros(29),dq=np.zeros(29),quat=np.array([1.,0,0,0]),gyro=np.zeros(3))
    timed.act(obs,1,True)
    held = controller.last_command
    seen.clear()
    next_obs = dict(obs,q=np.full(29,3.),quat=np.array([-1.,0,0,0]))
    timed.act(next_obs,4,True)
    assert len(seen)==3
    for i,(q,command,action) in enumerate(seen):
        np.testing.assert_array_equal(q,np.full(29,i+1.))
        assert command is held
        np.testing.assert_array_equal(action,np.full(15,7.))
    assert controller.last_command is not held
