"""Drift tests: the model constants and strings equal the pinned firmware main.cpp.

If the car repo pin moves and main.cpp changes, a test here fails and names the field.
The last test sends the car tuning.toml commands through the model.
"""

from __future__ import annotations

import re

import pytest

from firmware_src import (
    FIELD_MAP, IGNORED_FIELDS, clamp_args, config_fields, constexpr_ints, main_cpp_text,
    parse_number, racecar_dir)
from rccar_sim_mcu import model
from rccar_sim_mcu.model import Config, McuModel, f32

pytestmark = pytest.mark.skipif(racecar_dir() is None, reason='car repo not found')


@pytest.fixture(scope='module')
def text() -> str:
    return main_cpp_text()


def _literals(s: str) -> str:
    """Join adjacent C string literals and decode the escapes we use."""
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', s)
    return ''.join(parts).replace('\\n', '\n').replace('\\"', '"')


# -- versions, limits, caps -------------------------------------------------
def test_fw_version(text):
    m = re.search(r'FW_VERSION\s*=\s*"([^"]+)"', text)
    assert m, 'FW_VERSION not found in main.cpp'
    assert model.FW_VERSION == m.group(1), 'FW_VERSION differs from main.cpp'


def test_hard_limits(text):
    consts = constexpr_ints(text)
    for name in ('SERVO_ABS_MIN_US', 'SERVO_ABS_MAX_US', 'SERVO_MAX_HZ',
                 'ESC_ABS_MIN_US', 'ESC_ABS_MAX_US', 'ESC_MAX_HZ'):
        assert name in consts, f'{name} not found in main.cpp'
        assert getattr(model, name) == consts[name], f'{name} differs from main.cpp'


def test_pins_and_event_codes_and_caps(text):
    consts = constexpr_ints(text)
    assert model.CMD_CAP == consts['CMD_CAP'] - 1, 'CMD_CAP differs (main.cpp counts the NUL)'
    assert model.REPLY_CAP == consts['REPLY_CAP'] - 1, 'REPLY_CAP differs (main.cpp has NUL)'
    m = re.search(r'EVT_READY\s*=\s*(\d+),\s*EVT_FAILSAFE\s*=\s*(\d+),\s*EVT_ARMED\s*=\s*(\d+),'
                  r'\s*EVT_DISARMED\s*=\s*(\d+)', text)
    assert m, 'event codes not found in main.cpp'
    assert (model.EVT_READY, model.EVT_FAILSAFE, model.EVT_ARMED, model.EVT_DISARMED) == tuple(
        int(g) for g in m.groups()), 'event codes differ from main.cpp'


# -- Config -------------------------------------------------------------------
def test_config_fields_all_mapped(text):
    fields = config_fields(text)
    missing = [f for f in fields if f not in FIELD_MAP and f not in IGNORED_FIELDS]
    assert not missing, f'main.cpp Config has fields the model lacks: {missing}'
    gone = [f for f in FIELD_MAP if f not in fields]
    assert not gone, f'the model has Config fields that main.cpp lacks: {gone}'
    model_fields = set(Config.__dataclass_fields__)
    assert set(FIELD_MAP.values()) == model_fields, 'FIELD_MAP and model Config differ'


def test_config_defaults(text):
    cfg = Config()
    for cpp, (ctype, default) in config_fields(text).items():
        if cpp in IGNORED_FIELDS:
            continue
        want = parse_number(default)
        got = getattr(cfg, FIELD_MAP[cpp])
        if ctype == 'float':
            assert got == f32(want), f'default of {cpp}: model {got!r}, main.cpp {default}'
        else:
            assert got == int(want), f'default of {cpp}: model {got!r}, main.cpp {default}'


def test_config_line_format(text):
    m = re.search(r'static void printConfig\(.*?out\.printf\((.*?)\);\s*\}', text, re.S)
    assert m, 'printConfig not found in main.cpp'
    call = m.group(1)
    fmt = _literals(call[:call.rindex('"') + 1])
    args = [a.strip() for a in call[call.rindex('"') + 1:].lstrip(', \n').split(',')]
    fields = [FIELD_MAP[a[2:]] for a in args]  # 'c.steerCenterUs' -> model name
    cfg = Config(steer_center_us=1490, steer_left_us=1190, steer_right_us=1810,
                 max_steer_deg=33.3, heading_gain=2.5, speed_limit=0.65, deadband_us=12,
                 accel_per_sec=3.5, timeout_ms=450, double_tap_rev=0, brake_ms=111,
                 gap_ms=122, brake_level=0.25, esc_min_us=1010, esc_neutral_us=1490,
                 esc_max_us=1990, servo_hz=60, esc_hz=70, control_hz=110)
    want = fmt % tuple(getattr(cfg, f) for f in fields)
    assert model.config_line(cfg) == want, 'config_line differs from printConfig in main.cpp'


# -- setKey -----------------------------------------------------------------
def _set_keys(text: str) -> dict[str, tuple[str, str]]:
    """SET key -> (C++ field, expression)."""
    body = text[text.index('static bool setKey'):text.index('static void handleLine')]
    found = re.findall(r'strcasecmp\(key,\s*"(\w+)"\)\)\s*c\.(\w+)\s*=\s*([^;]+);', body)
    assert found, 'setKey keys not found in main.cpp'
    return {k: (field, expr) for k, field, expr in found}


def test_set_keys_and_bounds(text):
    consts = constexpr_ints(text)
    huge = 1e30
    for key, (cpp_field, expr) in _set_keys(text).items():
        assert cpp_field in FIELD_MAP, f'SET {key}: the model lacks field {cpp_field}'
        field = FIELD_MAP[cpp_field]
        reply = McuModel().handle_line(f'SET {key} 1', 0)
        assert not reply.startswith('ERR unknown key'), f'SET {key} is unknown to the model'
        bounds = clamp_args(expr)
        if bounds is None:  # `v != 0`: a flag
            assert 'v != 0' in expr, f'SET {key}: new expression form in main.cpp: {expr}'
            for v, want in ((0.0, 0), (5.0, 1), (-5.0, 1)):
                cfg = Config()
                assert model._set_key(cfg, key, v)
                assert getattr(cfg, field) == want, f'SET {key} {v}: flag differs'
            continue
        lo, hi = (parse_number(b, consts) for b in bounds)
        for v, bound in ((-huge, lo), (huge, hi)):
            cfg = Config()
            assert model._set_key(cfg, key, v)
            got = getattr(cfg, field)
            if '(uint' in expr or 'lroundf' in expr:
                bound = int(bound)
            else:
                bound = f32(bound)
            side = 'min' if v < 0 else 'max'
            assert got == bound, f'SET {key} {side}: model {got!r}, main.cpp {bound!r}'


def test_set_unknown_key_refused(text):
    assert _set_keys(text)
    reply = McuModel().handle_line('SET nosuchkey 1', 0)
    assert 'ERR unknown key nosuchkey' in reply
    assert '"ERR unknown key %s\\n"' in text


# -- strings ----------------------------------------------------------------
def test_event_texts(text):
    assert 'snprintf(text, sizeof(text), "fw=%s", FW_VERSION)' in text
    ready = McuModel().pop_events()
    assert ready == [(model.EVT_READY, 'fw=' + model.FW_VERSION)], 'READY event differs'
    assert 'publishEvent(EVT_FAILSAFE, "command timeout -> disarmed")' in text
    mdl = McuModel()
    mdl.pop_events()
    mdl.service_command('ARM', 0)
    mdl.pop_events()
    mdl.step(1000)
    assert (model.EVT_FAILSAFE, 'command timeout -> disarmed') in mdl.pop_events()


def test_d_refused(text):
    m = re.search(r'strcasecmp\(first,\s*"D"\)\)\s*g_reply\.println\(("(?:[^"\\]|\\.)*")\)', text)
    assert m, 'D refusal not found in main.cpp'
    ok, reply = McuModel().service_command('D 10 0.5', 0)
    assert not ok
    assert reply == _literals(m.group(1)), 'D refusal text differs from main.cpp'


def test_reply_strings(text):
    """Each fixed reply text of the model is a string literal in main.cpp."""
    cases = [  # (setup commands, command, reply)
        ([], 'ARM', 'OK ARM'),
        ([], 'DISARM', 'OK DISARM'),
        ([], 'TIME', 'ERR TIME unsupported: micro-ROS syncs the clock with the agent'),
        ([], 'RAW', 'ERR usage: RAW <us>|OFF'),
        ([], 'CAL FOO 1', 'ERR CAL LEFT|CENTER|RIGHT <us>'),
        ([], 'SET a', 'ERR usage: SET <key> <value>'),
        ([], 'SET esc_min 1500', 'ERR need esc_min < esc_neutral < esc_max'),
        ([], 'SET rf_min_m 100', 'ERR rf_min_m must be < rf_max_m'),
        (['CAL CENTER 2000'], 'SAVE', 'ERR center must lie between left and right'),
        ([], 'SAVE', 'OK SAVE'),
    ]
    for setup, cmd, want in cases:
        mdl = McuModel()
        for s in setup:
            mdl.service_command(s, 0)
        reply = mdl.service_command(cmd, 0)[1]
        assert reply == want, f'{cmd!r}: model reply {reply!r}, expected {want!r}'
        assert f'"{want}"' in text, f'reply text of {cmd!r} is not in main.cpp: {want}'
    for literal in ('"PONG %s %llu\\n"', '"OK RAW %d\\n"', '"OK TEL %u\\n"',
                    '"ERR SENS %s not implemented\\n"', '"ERR unknown command %s\\n"'):
        assert literal in text, f'{literal} is not in main.cpp'


def test_info_format(text):
    m = re.search(r'out\.printf\(("INFO fw=%s[^;]*?\\n")', text, re.S)
    assert m, 'INFO line not found in main.cpp'
    fmt = _literals(m.group(1))
    reply = McuModel().service_command('INFO', 0)[1]
    assert reply == (fmt % (model.FW_VERSION, 'sim', 0, 0, 0, model.PIN_STEER_PWM,
                            model.PIN_THROTTLE_PWM)).rstrip('\n'), 'INFO line differs'


# -- car tuning.toml ----------------------------------------------------------
def test_tuning_commands_run_through_the_model():
    tuning_mod = pytest.importorskip('rccar_mcu_bridge.tuning')
    toml = racecar_dir() / 'tuning.toml'
    if not toml.is_file():
        pytest.skip('tuning.toml not found in the car repo')
    cmds = tuning_mod.firmware_commands(tuning_mod.load_tuning(toml))
    assert cmds, 'firmware_commands gave no command'
    mdl = McuModel()
    for i, cmd in enumerate(cmds):
        ok, reply = mdl.service_command(cmd, 10 * i)
        assert ok, f'the model refused {cmd!r}: {reply}'
    ok, reply = mdl.service_command('GET', 1000)
    assert ok
    for want in ('maxdeg=30.0', 'gain=2.00', 'limit=0.70', 'left=1200', 'right=1800'):
        assert want in reply, f'{want} missing after the tuning commands: {reply}'
