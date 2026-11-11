"""Unit tests for the firmware model. Hand-computed values; no ROS."""

import math

import pytest

from rccar_sim_mcu.model import (
    EVT_ARMED, EVT_DISARMED, EVT_FAILSAFE, EVT_READY, FW_VERSION, Config, McuModel,
    RevState, f32, heading_to_steer_deg, lroundf, steer_deg_to_us, throttle_to_us)

DEFAULT_CFG = (
    'CFG center=1500 left=1800 right=1200 maxdeg=25.0 gain=1.00 limit=0.30 deadband=0 '
    'accel=2.00 timeout=300 revmode=1 brake_ms=150 gap_ms=150 brake_level=0.50 '
    'esc_min=1000 esc_neutral=1500 esc_max=2000 servo_hz=50 esc_hz=50 control_hz=100\n')


def tuned() -> Config:
    return Config(steer_left_us=1200, steer_right_us=1800, max_steer_deg=30.0,
                  heading_gain=2.0, speed_limit=0.7)


def armed_model(t: int = 1000, **cfg) -> McuModel:
    m = McuModel()
    for k, v in cfg.items():
        setattr(m.cfg, k, v)
    m.pop_events()
    m.handle_line('ARM', t)
    m.pop_events()
    return m


def tick(m: McuModel, t: int, thr: float, heading: float = 0.0):
    m.on_drive(heading, thr, t)
    return m.step(t)


# --- rounding and math -------------------------------------------------------
def test_lroundf_half_away_from_zero():
    assert [lroundf(x) for x in (2.5, -2.5, 0.5, -0.5, 1.4, -1.6)] == [3, -3, 1, -1, 1, -2]


def test_heading_to_steer():
    c = tuned()
    assert heading_to_steer_deg(10, c) == 20
    assert heading_to_steer_deg(20, c) == 30
    assert heading_to_steer_deg(-20, c) == -30
    assert heading_to_steer_deg(0, c) == 0


def test_steer_us_tuned():
    c = tuned()
    assert steer_deg_to_us(30, c) == 1200
    assert steer_deg_to_us(-30, c) == 1800
    assert steer_deg_to_us(15, c) == 1350
    assert steer_deg_to_us(-15, c) == 1650
    assert steer_deg_to_us(7.5, c) == 1425
    assert steer_deg_to_us(0, c) == 1500
    assert steer_deg_to_us(90, c) == 1200  # clamped to the window


def test_steer_us_half_rounds_away():
    c = Config(steer_left_us=1501, steer_right_us=1499)
    assert steer_deg_to_us(12.5, c) == 1501   # 1500.5
    assert steer_deg_to_us(-12.5, c) == 1500  # 1499.5


def test_throttle_us():
    c = Config()
    assert throttle_to_us(0.0, c) == 1500
    assert throttle_to_us(0.0009, c) == 1500
    assert throttle_to_us(0.5, c) == 1750
    assert throttle_to_us(-0.5, c) == 1250
    assert throttle_to_us(1.0, c) == 2000
    assert throttle_to_us(-1.0, c) == 1000
    assert throttle_to_us(2.0, c) == 2000
    c.deadband_us = 50
    assert throttle_to_us(0.5, c) == 1775
    assert throttle_to_us(-0.5, c) == 1225
    assert throttle_to_us(-1.0, c) == 1000


def test_throttle_us_half_rounds_away():
    c = Config(esc_max_us=1501)
    assert throttle_to_us(0.5, c) == 1501  # 1500.5


def test_throttle_tuned_limit():
    c = tuned()
    assert throttle_to_us(f32(1.0 * c.speed_limit), c) == 1850
    assert throttle_to_us(f32(0.5 * c.speed_limit), c) == 1675


# --- boot, drive, step -------------------------------------------------------
def test_boot_event_and_defaults():
    m = McuModel()
    assert m.pop_events() == [(EVT_READY, 'fw=' + FW_VERSION)]
    assert m.pop_events() == []
    assert m.cfg == Config()
    assert not m.armed
    assert m.range_m() == math.inf


def test_steering_follows_when_disarmed():
    m = McuModel()
    m.on_drive(0.5, 0.0, 10)
    o = m.step(10)
    assert o.steer_us == 1800 and o.throttle_us == 1500
    m.on_drive(-0.5, 0.0, 20)
    assert m.step(20).steer_us == 1200


def test_steer_tuned_from_radians():
    m = McuModel()
    m.cfg = tuned()
    m.on_drive(math.radians(10), 0.0, 5)
    o = m.step(5)
    assert o.steer_deg == pytest.approx(20, abs=1e-4)
    assert o.steer_us == 1300


def test_slew_per_tick():
    m = armed_model()
    for n, exp in ((1, 1503), (2, 1506), (3, 1509)):
        o = tick(m, 1000 + n * 10, 1.0)
        assert o.u == pytest.approx(0.006 * n, rel=1e-5)
        assert o.throttle_us == exp


def test_disarm_snaps_to_zero():
    m = armed_model(accel_per_sec=100.0)
    m.cfg.accel_per_sec = 10.0
    tick(m, 1010, 1.0)
    assert tick(m, 1020, 1.0).u > 0
    m.handle_line('DISARM', 1030)
    o = m.step(1030)
    assert o.u == 0 and o.throttle_us == 1500
    m.handle_line('ARM', 1040)
    assert tick(m, 1040, 1.0).u == pytest.approx(0.3 * 0.1, rel=1e-5)  # ramps from 0


def test_non_finite_drive_dropped():
    m = armed_model(1000)
    m.on_drive(math.nan, 0.5, 1200)
    m.on_drive(0.1, math.inf, 1250)
    assert m.telemetry(1250).throttle == 0.0
    m.step(1300)
    assert m.armed
    m.step(1301)
    assert not m.armed


def test_drive_clamps():
    m = McuModel()
    m.on_drive(10.0, 5.0, 1)
    t = m.telemetry(1)
    assert t.throttle == 1.0
    assert t.heading_rad == pytest.approx(math.pi, abs=1e-5)


# --- failsafe ----------------------------------------------------------------
def test_failsafe_timing_and_order():
    m = armed_model(1000)
    m.step(1300)
    assert m.armed          # exactly timeout: not stale
    m.step(1301)
    assert not m.armed
    assert m.pop_events() == [(EVT_FAILSAFE, 'command timeout -> disarmed'),
                              (EVT_DISARMED, '')]
    assert m.pop_events() == []


def test_failsafe_not_while_disarmed():
    m = McuModel()
    m.pop_events()
    m.step(100000)
    assert m.pop_events() == []


def test_arm_refreshes_stamp():
    m = McuModel()
    m.pop_events()
    m.handle_line('ARM', 10000)
    assert m.pop_events() == [(EVT_ARMED, '')]
    m.step(10300)
    assert m.armed
    m.step(10301)
    assert not m.armed


def test_arm_and_disarm_events():
    m = armed_model()
    m.handle_line('STOP', 1100)
    assert m.pop_events() == [(EVT_DISARMED, '')]


# --- double-tap reverse ------------------------------------------------------
def rev_model(**cfg) -> McuModel:
    return armed_model(speed_limit=1.0, accel_per_sec=100.0, **cfg)


def test_double_tap_edges():
    m = rev_model()
    assert tick(m, 1000, -1.0).throttle_us == 1250
    assert m.reverse_state == RevState.BRAKE
    assert tick(m, 1149, -1.0).throttle_us == 1250
    o = tick(m, 1150, -1.0)           # brake_ms reached
    assert o.throttle_us == 1500 and m.reverse_state == RevState.GAP
    assert tick(m, 1299, -1.0).throttle_us == 1500
    o = tick(m, 1300, -1.0)           # gap_ms reached
    assert o.throttle_us == 1000 and m.reverse_state == RevState.REVERSE


def test_reverse_zero_stays_then_direct():
    m = rev_model()
    for t in (1000, 1150, 1300):
        tick(m, t, -1.0)
    assert tick(m, 1310, 0.0).throttle_us == 1500
    assert m.reverse_state == RevState.REVERSE
    assert tick(m, 1320, -1.0).throttle_us == 1000  # no brake again
    # Slew step is 1.0 per tick: -1 -> 0 (u == 0 stays in REVERSE) -> +1.
    assert tick(m, 1330, 1.0).throttle_us == 1500
    assert m.reverse_state == RevState.REVERSE
    assert tick(m, 1340, 1.0).throttle_us == 2000
    assert m.reverse_state == RevState.FORWARD
    assert tick(m, 1350, -1.0).throttle_us == 1500  # slew back to 0
    assert tick(m, 1360, -1.0).throttle_us == 1250  # brake again


def test_back_to_forward_from_brake_and_gap():
    m = rev_model()
    tick(m, 1000, -1.0)
    assert tick(m, 1010, 0.0).throttle_us == 1500
    assert m.reverse_state == RevState.FORWARD
    tick(m, 1020, -1.0)
    tick(m, 1170, -1.0)
    assert m.reverse_state == RevState.GAP
    tick(m, 1180, 1.0)
    assert m.reverse_state == RevState.FORWARD


def test_revmode_zero():
    m = rev_model()
    assert m.handle_line('SET revmode 0', 1000).startswith('CFG ')
    assert tick(m, 1010, -1.0).throttle_us == 1000
    assert m.reverse_state == RevState.FORWARD


# --- RAW ---------------------------------------------------------------------
def test_raw():
    m = McuModel()
    assert m.handle_line('RAW 1234', 1) == 'OK RAW 1234\n'
    assert m.step(1).steer_us == 1234
    assert m.handle_line('raw 100', 1) == 'OK RAW 500\n'
    assert m.handle_line('RAW 9999', 1) == 'OK RAW 2500\n'
    assert m.handle_line('RAW OFF', 1) == 'OK RAW -1\n'
    assert m.step(2).steer_us == 1500
    assert m.handle_line('RAW', 1) == 'ERR usage: RAW <us>|OFF\r\n'


# --- grammar -----------------------------------------------------------------
def test_simple_commands():
    m = McuModel()
    assert m.handle_line('ARM', 5) == 'OK ARM\r\n'
    assert m.handle_line('disarm', 5) == 'OK DISARM\r\n'
    assert m.handle_line('STOP', 5) == 'OK DISARM\r\n'
    assert m.handle_line('PING', 5000) == 'PONG 0 5000\n'
    assert m.handle_line('PING 42', 5000) == 'PONG 42 5000\n'
    assert m.handle_line('TIME 5', 1) == (
        'ERR TIME unsupported: micro-ROS syncs the clock with the agent\r\n')
    assert m.handle_line('INFO', 1) == (
        'INFO fw=0.3.0 chip=sim rev=0 psram=0 flash=0 steer_pin=4 throttle_pin=5\n')
    assert m.handle_line('FOO bar', 1) == 'ERR unknown command FOO\n'
    assert m.handle_line('   ', 1) == ''
    assert m.handle_line('', 1) == ''


def test_cfg_byte_exact_defaults():
    m = McuModel()
    assert m.handle_line('GET', 1) == DEFAULT_CFG
    assert m.handle_line('CAL', 1) == DEFAULT_CFG
    assert m.handle_line('get', 1) == DEFAULT_CFG


def test_d_line():
    m = McuModel()
    assert m.handle_line('D 10 0.5', 100) == ''
    t = m.telemetry(100)
    assert t.heading_rad == pytest.approx(math.radians(10), rel=1e-5)
    assert t.throttle == 0.5
    m.handle_line('D 500 5', 100)
    t = m.telemetry(100)
    assert t.throttle == 1.0 and t.heading_rad == pytest.approx(math.pi, abs=1e-5)
    assert m.handle_line('D 1', 1) == 'ERR usage: D <heading_deg> <speed>\r\n'


def test_cal():
    m = McuModel()
    assert 'left=1250 ' in m.handle_line('CAL LEFT 1250', 1)
    assert 'center=600 ' in m.handle_line('cal center 600', 1)
    assert 'right=2500 ' in m.handle_line('CAL RIGHT 99999', 1)
    assert 'left=500 ' in m.handle_line('CAL LEFT 0', 1)
    assert m.handle_line('CAL FOO 1500', 1) == 'ERR CAL LEFT|CENTER|RIGHT <us>\r\n'


def test_set_basic_and_errors():
    m = McuModel()
    r = m.handle_line('SET maxdeg 30', 1)
    assert r == DEFAULT_CFG.replace('maxdeg=25.0', 'maxdeg=30.0')
    assert m.handle_line('Set\tGAIN\t2', 1).count('gain=2.00') == 1
    assert m.handle_line('SET gain', 1) == 'ERR usage: SET <key> <value>\r\n'
    assert m.handle_line('SET bogus 1', 1) == 'ERR unknown key bogus\n'
    assert m.handle_line('SET gain abc', 1).count('gain=0.00') == 1  # strtof gives 0


@pytest.mark.parametrize('key,val,attr,exp', [
    ('maxdeg', '100', 'max_steer_deg', 60.0), ('maxdeg', '0', 'max_steer_deg', 1.0),
    ('gain', '11', 'heading_gain', 10.0), ('gain', '-1', 'heading_gain', 0.0),
    ('limit', '-1', 'speed_limit', 0.0), ('limit', '2', 'speed_limit', 1.0),
    ('deadband', '500', 'deadband_us', 200), ('deadband', '12.9', 'deadband_us', 12),
    ('accel', '0', 'accel_per_sec', f32(0.1)), ('accel', '500', 'accel_per_sec', 100.0),
    ('timeout', '10', 'timeout_ms', 50), ('timeout', '5000', 'timeout_ms', 2000),
    ('timeout', '123.9', 'timeout_ms', 123),
    ('revmode', '7', 'double_tap_rev', 1), ('revmode', '0', 'double_tap_rev', 0),
    ('brake_ms', '5000', 'brake_ms', 1000), ('gap_ms', '-5', 'gap_ms', 0),
    ('brake_level', '2', 'brake_level', 1.0),
    ('esc_min', '100', 'esc_min_us', 900), ('esc_neutral', '1000', 'esc_neutral_us', 1300),
    ('esc_neutral', '2000', 'esc_neutral_us', 1700), ('esc_max', '3000', 'esc_max_us', 2100),
    ('servo_hz', '1000', 'servo_hz', 330), ('servo_hz', '1', 'servo_hz', 50),
    ('esc_hz', '9999', 'esc_hz', 400), ('control_hz', '5', 'control_hz', 20),
    ('control_hz', '9999', 'control_hz', 500),
    ('rf_driver', '5', 'rf_driver', 1), ('rf_driver', '0', 'rf_driver', 0),
    ('rf_addr', '200', 'rf_i2c_addr', 119), ('rf_addr', '20.5', 'rf_i2c_addr', 21),
    ('rf_addr', '1', 'rf_i2c_addr', 8),
    ('rf_period_ms', '5', 'rf_period_ms', 20), ('rf_period_ms', '5000', 'rf_period_ms', 1000),
    ('rf_scale_m', '0', 'rf_scale_m', f32(1e-4)), ('rf_scale_m', '5', 'rf_scale_m', 1.0),
    ('rf_no_return', '-3', 'rf_no_return_raw', 0),
    ('rf_no_return', '99999', 'rf_no_return_raw', 65535),
    ('rf_min_m', '-1', 'rf_min_m', 0.0), ('rf_max_m', '500', 'rf_max_m', 100.0),
    ('rf_fov_rad', '9', 'rf_fov_rad', f32(3.14)), ('rf_fov_rad', '0', 'rf_fov_rad', f32(0.001)),
    ('rf_radiation', '3', 'rf_radiation', 1), ('RF_RADIATION', '0', 'rf_radiation', 0),
])
def test_set_clamps(key, val, attr, exp):
    m = McuModel()
    assert m.handle_line('SET %s %s' % (key, val), 1).startswith('CFG ')
    assert getattr(m.cfg, attr) == exp


def test_set_cross_checks():
    m = McuModel()
    assert m.handle_line('SET esc_min 1500', 1) == (
        'ERR need esc_min < esc_neutral < esc_max\r\n')
    assert m.cfg.esc_min_us == 1000  # unchanged
    assert m.handle_line('SET esc_max 1500', 1) == (
        'ERR need esc_min < esc_neutral < esc_max\r\n')
    assert m.handle_line('SET rf_min_m 20', 1) == 'ERR rf_min_m must be < rf_max_m\r\n'
    assert m.handle_line('SET rf_max_m 0.01', 1) == 'ERR rf_min_m must be < rf_max_m\r\n'
    assert m.cfg == Config()


def test_save_defaults_reboot():
    m = McuModel()
    m.handle_line('SET gain 2', 1)
    assert m.handle_line('SAVE', 1) == 'OK SAVE\r\n'
    m.handle_line('SET gain 3', 1)
    assert m.handle_line('DEFAULTS', 1) == DEFAULT_CFG
    assert m.cfg.heading_gain == 1.0
    m.handle_line('SET gain 3', 1)
    m.handle_line('ARM', 1)
    m.on_drive(0.3, 0.4, 1)
    m.handle_line('RAW 1000', 1)
    m.reboot(50)
    assert m.cfg.heading_gain == 2.0  # last SAVE
    assert not m.armed and m.raw_steer_us == -1
    t = m.telemetry(50)
    assert t.heading_rad == 0 and t.throttle == 0 and not t.armed
    assert m.pop_events() == [(EVT_READY, 'fw=0.3.0')]


def test_reboot_without_save_gives_defaults():
    m = McuModel()
    m.handle_line('SET gain 3', 1)
    m.handle_line('TEL 3', 1)
    m.reboot(5)
    assert m.cfg == Config() and m.telemetry_hz == 10


def test_save_center_check():
    m = McuModel()
    m.handle_line('CAL CENTER 1900', 1)
    assert m.handle_line('SAVE', 1) == 'ERR center must lie between left and right\r\n'
    m.handle_line('CAL CENTER 1800', 1)
    assert m.handle_line('SAVE', 1) == 'ERR center must lie between left and right\r\n'


def test_tel():
    m = McuModel()
    assert m.telemetry_hz == 10
    assert m.handle_line('TEL 100', 1) == 'OK TEL 50\n'
    assert m.handle_line('TEL -5', 1) == 'OK TEL 0\n'
    assert m.telemetry_hz == 0
    assert m.handle_line('TEL 25', 1) == 'OK TEL 25\n'
    assert m.handle_line('TEL', 1) == 'OK TEL 10\n'


def test_sens():
    m = McuModel()
    # Stub sample: a present sensor with no return (raw = no_return), stamped at boot.
    exp = ('SENS rangefinder present=1 driver=1 addr=0x62 period_ms=20 scale_m=0.0100 '
           'no_return=1 min_m=0.05 max_m=10.00 fov_rad=0.0833 radiation=1 raw=1 '
           'range_m=inf status=0x00 age_ms=1 seq=1\n')
    assert m.handle_line('SENS rangefinder', 1) == exp
    assert m.handle_line('SENS', 1) == 'ERR SENS ? not implemented\n'
    assert m.handle_line('SENS foo', 1) == 'ERR SENS foo not implemented\n'


# --- service level -----------------------------------------------------------
def test_service_refuses_d():
    m = McuModel()
    for cmd in ('D 1 1', 'd 1 1', '  D 1 1', 'D'):
        assert m.service_command(cmd, 1) == (False, 'ERR D refused: drive is /rccar/mcu/drive')
    assert m.telemetry(1).throttle == 0.0
    assert m.service_command('DISARM', 1) == (True, 'OK DISARM')


def test_service_ok_flag_and_strip():
    m = McuModel()
    assert m.service_command('ARM', 1) == (True, 'OK ARM')
    assert m.service_command('PING 7', 99) == (True, 'PONG 7 99')
    assert m.service_command('FOO', 1) == (False, 'ERR unknown command FOO')


def test_service_64_char_cap():
    m = McuModel()
    ok, reply = m.service_command('PING ' + 'x' * 100, 7)
    assert ok and reply == 'PONG ' + 'x' * 59 + ' 7'


def test_telemetry_fields():
    m = McuModel()
    m.handle_line('ARM', 1)
    m.on_drive(0.2, 0.5, 2)
    m.step(2)
    t = m.telemetry(2)
    assert (t.mcu_ms, t.armed, t.throttle) == (2, True, 0.5)
    assert t.steer_us == m.step(3).steer_us
    assert t.steer_rad == pytest.approx(0.2, abs=1e-4)
