"""Helpers for the golden and drift tests: find and read the pinned firmware source.

This file is not a test. It reads main.cpp as text and cuts out functions and structs.
"""

from __future__ import annotations

import os
from pathlib import Path
import re

MAIN_CPP = Path('firmware') / 'esp32' / 'src' / 'main.cpp'

# C++ Config field -> model Config field. Drift tests fail when main.cpp has a field
# that is not here. 'magic' is the NVS layout tag. The model has no NVS image.
FIELD_MAP = {
    'steerCenterUs': 'steer_center_us',
    'steerLeftUs': 'steer_left_us',
    'steerRightUs': 'steer_right_us',
    'maxSteerDeg': 'max_steer_deg',
    'headingGain': 'heading_gain',
    'speedLimit': 'speed_limit',
    'deadbandUs': 'deadband_us',
    'accelPerSec': 'accel_per_sec',
    'timeoutMs': 'timeout_ms',
    'doubleTapRev': 'double_tap_rev',
    'brakeMs': 'brake_ms',
    'gapMs': 'gap_ms',
    'brakeLevel': 'brake_level',
    'escMinUs': 'esc_min_us',
    'escNeutralUs': 'esc_neutral_us',
    'escMaxUs': 'esc_max_us',
    'servoHz': 'servo_hz',
    'escHz': 'esc_hz',
    'controlHz': 'control_hz',
    'rfDriver': 'rf_driver',
    'rfI2cAddr': 'rf_i2c_addr',
    'rfPeriodMs': 'rf_period_ms',
    'rfScaleM': 'rf_scale_m',
    'rfNoReturnRaw': 'rf_no_return_raw',
    'rfMinM': 'rf_min_m',
    'rfMaxM': 'rf_max_m',
    'rfFovRad': 'rf_fov_rad',
    'rfRadiation': 'rf_radiation',
}
IGNORED_FIELDS = frozenset({'magic'})


def racecar_dir() -> Path | None:
    """The car repo: $RACECAR_SRC, /ws/src/racecar, or src/racecar above this file."""
    cands = [os.environ.get('RACECAR_SRC'), '/ws/src/racecar']
    for parent in Path(__file__).resolve().parents:
        cands.append(parent / 'src' / 'racecar')
    for cand in cands:
        if cand and (Path(cand) / MAIN_CPP).is_file():
            return Path(cand)
    return None


def main_cpp_text() -> str:
    root = racecar_dir()
    if root is None:
        raise FileNotFoundError('car repo not found: set RACECAR_SRC')
    return (root / MAIN_CPP).read_text()


def _match_brace(text: str, open_idx: int) -> int:
    """Index after the brace that closes the one at open_idx."""
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return i + 1
    raise ValueError('unbalanced braces in main.cpp')


def function_source(text: str, name: str) -> str:
    """The full definition of `static <type> name(...) { ... }`, with the signature."""
    m = re.search(r'^static\s+[\w:<>]+\s+%s\s*\(' % re.escape(name), text, re.M)
    if not m:
        raise ValueError(f'function {name} not found in main.cpp')
    return text[m.start():_match_brace(text, text.index('{', m.end()))]


def template_function_source(text: str, name: str) -> str:
    """Like function_source, with the `template <typename T>` line before it."""
    m = re.search(r'template\s*<typename T>\s*static\s+T\s+%s\s*\(' % re.escape(name), text)
    if not m:
        raise ValueError(f'template function {name} not found in main.cpp')
    return text[m.start():_match_brace(text, text.index('{', m.end()))]


def config_struct_source(text: str) -> str:
    """The text `struct Config { ... };`."""
    m = re.search(r'^struct Config\s*\{', text, re.M)
    if not m:
        raise ValueError('struct Config not found in main.cpp')
    end = _match_brace(text, text.index('{', m.start()))
    return text[m.start():end] + ';'


def config_fields(text: str) -> dict[str, tuple[str, str]]:
    """C++ field name -> (type, default text), in struct order."""
    body = config_struct_source(text)
    body = body[body.index('{') + 1:body.rindex('}')]
    body = re.sub(r'//[^\n]*', '', body)
    out = {}
    for m in re.finditer(r'(\w+)\s+(\w+)\s*=\s*([^;]+);', body):
        out[m.group(2)] = (m.group(1), m.group(3).strip())
    return out


def constexpr_ints(text: str) -> dict[str, int]:
    """Top-level `constexpr uintNN_t NAME = number;` values."""
    pat = r'^constexpr\s+(?:u?int\d+_t|size_t)\s+(\w+)\s*=\s*(\w+)\s*;'
    return {m.group(1): int(m.group(2), 0) for m in re.finditer(pat, text, re.M)}


def clamp_args(expr: str) -> tuple[str, str] | None:
    """The (lo, hi) texts of the first `clampv(v, lo, hi)` in expr, or None."""
    i = expr.find('clampv(v,')
    if i < 0:
        return None
    args, depth, cur = [], 0, ''
    for ch in expr[i + len('clampv('):]:
        if ch == '(':
            depth += 1
        elif ch == ')':
            if depth == 0:
                break
            depth -= 1
        if ch == ',' and depth == 0:
            args.append(cur.strip())
            cur = ''
        else:
            cur += ch
    args.append(cur.strip())
    return (args[1], args[2]) if len(args) == 3 else None


def parse_number(s: str, consts: dict[str, int] | None = None) -> float:
    """A C++ literal such as 25.0f, 0x62, 1e-4f, (float)NAME or NAME, as a Python number."""
    s = re.sub(r'\(\s*(?:float|uint\d+_t)\s*\)', '', s).strip()
    if consts and s in consts:
        return consts[s]
    if re.fullmatch(r'0[xX][0-9a-fA-F]+', s):
        return int(s, 16)
    return float(s.rstrip('fF'))
