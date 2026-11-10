"""Prevent accidental tuning on holdouts and final evaluation override bypasses."""
import json
from pathlib import Path
import pytest
from harness.protocol import validate_episode, validate_cohort

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = json.loads((ROOT/'review/evaluation_v2_protocol.json').read_text())


def final_case(**overrides):
    values = dict(layout=PROTOCOL['holdout_topologies'][0], seed=PROTOCOL['holdout_seeds'][0],
        seconds=600, mode='navigate', delay=0, final=True, root=ROOT,
        parameters=ROOT/'config/navigation.json', control=ROOT/'config/control.json')
    values.update(overrides)
    return values


def test_final_accepts_declared_case_and_refuses_protocol_overrides():
    validate_episode(PROTOCOL, **final_case())
    for override in (dict(seconds=400), dict(seed=-1), dict(layout=0),
                     dict(control=ROOT/'review/candidates/turn-only.json'),
                     dict(parameters=ROOT/'unselected.json'), dict(mode='walk_test')):
        with pytest.raises(ValueError):
            validate_episode(PROTOCOL, **final_case(**override))


def test_development_cannot_open_heldout_geometry():
    with pytest.raises(ValueError, match='held-out'):
        validate_episode(PROTOCOL, **final_case(final=False))
    validate_episode(PROTOCOL, **final_case(final=False, layout=PROTOCOL['development_topologies'][0]))


def test_control_seed_cannot_escape_matched_subset():
    i = PROTOCOL['controls']['matched_first_n_seeds']
    with pytest.raises(ValueError, match='matched subset'):
        validate_episode(PROTOCOL, **final_case(layout=PROTOCOL['holdout_topologies'][i],
            seed=PROTOCOL['holdout_seeds'][i], mode='neutral'))


def test_final_cohort_cannot_select_only_favorable_cases_or_duplicate_strata():
    ids = PROTOCOL['holdout_topologies']
    validate_cohort(PROTOCOL, layouts=ids, delays=[0], mode='navigate', final=True)
    for selected, delays in ((ids[:-1], [0]), (ids, [0, 0]), (ids, [])):
        with pytest.raises(ValueError):
            validate_cohort(PROTOCOL, layouts=selected, delays=delays, mode='navigate', final=True)
