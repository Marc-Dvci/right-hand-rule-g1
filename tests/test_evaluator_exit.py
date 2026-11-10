import json
import numpy as np
from harness.evaluate import crossed_exit


def test_crossing_checks_interpolated_doorway_position_and_returns_a_json_boolean():
    spec=dict(axis=0,value=1.,sign=1,min_y=0.,max_y=1.)
    # Endpoint is outside, but the actual crossing occurs inside the doorway.
    result=crossed_exit(np.array([.9,.85,0]),[1.1,1.1,0],spec)
    assert result and type(result) is bool
    assert json.dumps({'exited':result})=='{"exited": true}'
    assert not crossed_exit([.9,1.2,0],np.array([1.1,.9,0]),spec)
    assert not crossed_exit([1.1,.5,0],[.9,.5,0],spec)
