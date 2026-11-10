from copy import deepcopy
import pytest
from tools.check_native_episode import validate, REQUIRED_CHECKS


def test_native_gate_rejects_startup_only_disabled_checks_and_transient_actual_findings():
    report = dict(status='within_limits', reason=None, safety_checks=True, control_path='submission',
        control_ready=True, commands=1000, seconds=60., policy_handoff_at_secs=2.,
        checks={name: True for name in REQUIRED_CHECKS}, warnings={})
    builder = dict(status='simulation_checks_complete')
    validate(report, builder)
    for changes in (dict(seconds=5), dict(control_ready=False), dict(safety_checks=False),
                    dict(control_path='example'), dict(warnings={'ankle': {'limits': [{'reason': 'torque'}]}})):
        with pytest.raises(ValueError):
            validate(dict(report, **changes), builder)
    weakened = deepcopy(report)
    weakened['checks']['thrash_enforcement'] = False
    with pytest.raises(ValueError):
        validate(weakened, builder)
    with pytest.raises(ValueError):
        validate(report, {'status': 'review_required'})
