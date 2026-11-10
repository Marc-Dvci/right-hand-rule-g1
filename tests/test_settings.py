"""The no-argument API must run the same selected policy as explicit deployment."""
from dataclasses import asdict
import numpy as np
import pytest
from policy.controller import Controller
from policy.networks import DEFAULT
from policy.settings import load_settings


def test_default_api_and_explicit_configuration_produce_identical_actions():
    implicit = Controller()
    explicit = Controller(parameters=load_settings('navigation'), control=load_settings('control'))
    assert asdict(implicit.parameters) == load_settings('navigation')
    assert asdict(implicit.control) == load_settings('control')
    rng = np.random.default_rng(261110)
    for _ in range(300):
        obs = dict(q=DEFAULT+rng.normal(0, .001, 29), dq=rng.normal(0, .005, 29),
                   quat=[1., 0, 0, 0], gyro=rng.normal(0, .001, 3))
        a, b = implicit.act(obs), explicit.act(obs)
        for key in ('q', 'dq', 'kp', 'kd', 'tau'):
            np.testing.assert_array_equal(a[key], b[key])


def test_missing_configuration_fails_instead_of_silently_using_generic_defaults(tmp_path, monkeypatch):
    import policy.settings as settings
    monkeypatch.setattr(settings, 'CONFIG', tmp_path)
    with pytest.raises(FileNotFoundError):
        Controller()
