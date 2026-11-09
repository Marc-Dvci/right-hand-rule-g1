"""Transport contract tests without requiring ROS on the development machine."""
import importlib
import sys
import types
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'container'))


@pytest.fixture
def adapter(monkeypatch):
    for name in ('rclpy','rclpy.node','rclpy.qos','std_msgs','std_msgs.msg',
                 'std_srvs','std_srvs.srv','him_safety_interfaces','him_safety_interfaces.msg'):
        monkeypatch.setitem(sys.modules,name,types.ModuleType(name))
    sys.modules['rclpy.node'].Node = object
    for name in ('QoSProfile','ReliabilityPolicy','DurabilityPolicy'):
        setattr(sys.modules['rclpy.qos'],name,object)
    for module,names in [('std_msgs.msg',('String',)),('std_srvs.srv',('Trigger',)),
                         ('him_safety_interfaces.msg',('RobotFeedback','JointCommand','Abort'))]:
        for name in names:
            setattr(sys.modules[module],name,type(name,(),{}))
    sys.modules.pop('container.ros_node',None)
    module = importlib.import_module('container.ros_node')
    clock = [10.]
    monkeypatch.setattr(module.time,'monotonic',lambda:clock[0])
    node = module.TouchNode.__new__(module.TouchNode)
    node.session,node.sequence,node.sent,node.done = 'session-123',0,-1,False
    node.feedback,node.imu = {},{}
    sent,calls = [],[]
    node.publisher = types.SimpleNamespace(publish=sent.append)
    node.get_logger = lambda:types.SimpleNamespace(error=lambda _:None)
    def act(obs,ready):
        calls.append((obs,ready))
        return {k:np.zeros(29) for k in ('q','dq','kp','kd','tau')}
    node.controller = types.SimpleNamespace(act=act)
    return node,sent,calls,clock


def state(key=4):
    import json
    return types.SimpleNamespace(data=json.dumps(dict(observation_id=key,quat=[1,0,0,0],gyro=[0,0,0],
        control_ready=True,position=['garbage'],base_velocity='invalid',maze='private')))


def joints(key=4):
    return types.SimpleNamespace(observation_id=key,q=[0.]*29,dq=[0.]*29)


def test_pairs_matching_ids_and_discards_privileged_fields(adapter):
    node,sent,calls,_ = adapter
    node.on_feedback(joints())
    assert not sent
    node.on_state(state())
    assert len(sent) == 1
    assert sent[0].session_id == 'session-123'
    assert sent[0].observation_id == 4
    assert sent[0].sequence == 0
    assert set(calls[0][0]) == {'q','dq','quat','gyro'}
    node.on_state(state())
    assert len(sent) == 1


def test_mismatched_and_stale_pairs_produce_no_command(adapter):
    node,sent,_,clock = adapter
    node.on_feedback(joints(4))
    node.on_state(state(5))
    assert not sent
    clock[0] += .13
    node.on_state(state(4))
    assert not sent


def test_abort_latches_output_off(adapter):
    node,sent,_,_ = adapter
    node.on_abort(types.SimpleNamespace(reason='test_abort'))
    node.on_feedback(joints())
    node.on_state(state())
    assert node.done
    assert not sent


def test_missed_observations_advance_policy_clock_before_one_publication(adapter):
    node,sent,calls,_ = adapter
    node.on_feedback(joints(4))
    node.on_state(state(4))
    node.on_feedback(joints(7))
    node.on_state(state(7))
    assert len(sent)==2
    assert len(calls)==4
    assert node.timed_policy.reconstructed_frames==2
    assert sent[-1].observation_id==7


def test_excessive_observation_gap_stops_publication(adapter):
    node,sent,_,_ = adapter
    node.on_feedback(joints(4))
    node.on_state(state(4))
    node.on_feedback(joints(11))
    node.on_state(state(11))
    assert node.done
    assert len(sent)==1
