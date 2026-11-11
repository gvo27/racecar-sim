"""The rangefinder stub: SENS and range_m() read the same sample (main.cpp:483, :745)."""
import math

from rccar_sim_mcu.model import McuModel


def test_stub_is_present_with_no_return():
    m = McuModel(0)
    assert m.rf_present
    assert m.rf_raw == m.cfg.rf_no_return_raw
    assert m.range_m() == math.inf
    line = m.handle_line('SENS rangefinder', 5)
    assert 'present=1' in line
    assert 'range_m=inf' in line


def test_range_follows_the_sample():
    m = McuModel(0)
    m.rf_raw = 250
    assert m.range_m() == 250 * m.cfg.rf_scale_m
    assert 'range_m=2.500' in m.handle_line('SENS rangefinder', 5)
