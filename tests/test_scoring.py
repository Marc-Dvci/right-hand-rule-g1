import numpy as np
import pytest
from harness.scoring import score_trajectory

EXIT = dict(axis=0,value=3.375,sign=1,min_y=1.875,max_y=3.125)


def test_requires_actual_outward_crossing_inside_doorway():
    assert score_trajectory([0,1],[[3.3,2.5,0],[3.4,2.5,0]],EXIT)['exited']
    assert not score_trajectory([0,1],[[3.5,3.5,0],[3.5,2.5,0]],EXIT)['exited']
    assert not score_trajectory([0,1],[[3.4,2.5,0],[3.3,2.5,0]],EXIT)['exited']


def test_returning_through_entrance_first_invalidates_later_outside_loop():
    q = [[0,0,0],[-1,0,0],[3.3,2.5,0],[3.4,2.5,0]]
    assert not score_trajectory([0,1,2,3],q,EXIT,-.775)['exited']


def test_success_is_retained_if_robot_returns_after_first_valid_exit():
    q = [[3.3,2.5,0],[3.4,2.5,0],[-1,0,0]]
    assert score_trajectory([0,1,2],q,EXIT,-.775)['exited']


def test_interpolates_crossing_location_and_time():
    r = score_trajectory([0,2],[[3.3,3.,0],[3.45,3.2,0]],EXIT)
    assert r['exited']
    assert r['exit_time']==pytest.approx(1.)


def test_rejects_nonfinite_or_nonmonotonic_trace():
    with pytest.raises(ValueError):
        score_trajectory([1,0],np.zeros((2,3)),EXIT)
    with pytest.raises(ValueError):
        score_trajectory([0,1],[[0,0,0],[np.nan,0,0]],EXIT)
