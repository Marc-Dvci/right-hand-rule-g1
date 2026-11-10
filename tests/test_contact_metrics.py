import numpy as np
import pytest
from harness.contact_metrics import LoadMetrics


def test_load_peak_impulse_and_trailing_means_have_physical_units():
    loads = LoadMetrics(.002)
    for _ in range(50):
        loads.observe([0., 0.])
    for _ in range(50):
        loads.observe([30., 60.])
    report = loads.report()
    np.testing.assert_allclose(report['peak_sum_contact_magnitudes_n'], [30, 60])
    np.testing.assert_allclose(report['accumulated_load_impulse_ns'], [3, 6])
    np.testing.assert_allclose(report['time_above_n_seconds']['40'], [0, .1])
    np.testing.assert_allclose(report['peak_window_mean_n']['0.1'], [30, 60])
    np.testing.assert_allclose(report['peak_window_mean_n']['0.25'], [15, 30])


def test_contact_load_metrics_reject_signed_or_nonfinite_force_inputs():
    loads = LoadMetrics(.002)
    for value in ([-1, 0], [0, np.nan], [1, 2, 3]):
        with pytest.raises(ValueError):
            loads.observe(value)
