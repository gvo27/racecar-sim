"""Golden tests: the model drive math equals the firmware C++ code, bit for bit.

The test cuts clampv, Config, headingToSteerDeg, steerDegToUs and throttleToUs out of the
pinned main.cpp. It builds them with g++ in a small harness and runs a grid of inputs.
Pulse widths must match exactly. Angles must match as float32.
"""

from __future__ import annotations

import math
from pathlib import Path
import shutil
import struct
import subprocess

import pytest

from firmware_src import (
    FIELD_MAP, config_struct_source, function_source, main_cpp_text, racecar_dir,
    template_function_source)
from rccar_sim_mcu.model import (
    Config, f32, heading_to_steer_deg, steer_deg_to_us, throttle_to_us)

pytestmark = pytest.mark.skipif(racecar_dir() is None, reason='car repo not found')

CXX_FLAGS = ['-std=c++17', '-O0', '-ffp-contract=off']
SHIM = """\
#include <cmath>
#include <math.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <algorithm>
using std::min;
using std::max;
constexpr uint32_t CFG_MAGIC = 0xC0FFEE03;
"""

# Model field names, as Config(**overrides). An empty dict keeps the firmware defaults.
CONFIGS = {
    'defaults': {},
    'tuning': dict(steer_left_us=1200, steer_right_us=1800, max_steer_deg=30.0,
                   heading_gain=2.0, speed_limit=0.7, deadband_us=0),
    'deadband_asym': dict(steer_center_us=1450, steer_left_us=1900, steer_right_us=1100,
                          max_steer_deg=40.0, heading_gain=1.5, deadband_us=30,
                          esc_min_us=1100, esc_neutral_us=1480, esc_max_us=1950),
}
CPP_NAME = {v: k for k, v in FIELD_MAP.items()}


def _bump(x: float, n: int) -> float:
    """The float32 value n steps from x (away from zero for n > 0)."""
    if x == 0:
        return f32(n * 1e-30)
    if x < 0:
        return -_bump(-x, -n)
    bits = struct.unpack('<i', struct.pack('<f', x))[0]
    return struct.unpack('<f', struct.pack('<i', bits + n))[0]


def _near(x: float) -> list[float]:
    """x and its two float32 neighbours, for rounding edges."""
    x = f32(x)
    return sorted({x, _bump(x, -1), _bump(x, 1)})


def _inputs() -> tuple[list[float], list[float]]:
    """Heading/angle grid and throttle grid, with the half-microsecond edges of all configs."""
    degs = {f32(i * 0.05) for i in range(-4000, 4001)}
    degs |= {f32(d) for d in (-200, -180, -179.5, -60, -25, -1, 0, 1, 25, 60, 180, 179.5, 200)}
    thr = {f32(i / 100) for i in range(-100, 101)}
    thr |= {f32(v) for v in (-0.0009, 0.0009, -0.001, 0.001, -0.00099999, 0.00100001, 1.0, -1.0)}
    for overrides in CONFIGS.values():
        c = Config(**overrides)
        for lock_us, sign in ((c.steer_left_us, 1), (c.steer_right_us, -1)):
            span = lock_us - c.steer_center_us
            if span == 0:
                continue
            lo, hi = sorted((c.steer_center_us, lock_us))
            for k in range(lo - 1, hi + 1):
                deg = sign * (k + 0.5 - c.steer_center_us) / span * c.max_steer_deg
                for sd in {deg, deg / c.heading_gain}:
                    degs.update(_near(sd))
        for sign, end in ((1, c.esc_max_us), (-1, c.esc_min_us)):
            span = abs(end - c.esc_neutral_us) - c.deadband_us
            for k in range(min(c.esc_neutral_us, end) - 1, max(c.esc_neutral_us, end) + 1):
                dist = sign * (k + 0.5 - c.esc_neutral_us)  # pulse offset, away from neutral
                if dist <= c.deadband_us:
                    continue
                u = sign * (dist - c.deadband_us) / span
                for lim in (1.0, c.speed_limit):
                    thr.update(_near(u / lim))
    thr = {t for t in thr if -1.5 <= t <= 1.5}
    return sorted(degs), sorted(thr)


def _lit(x: float) -> str:
    return float.hex(float(x)) + 'f'


def _config_code(overrides: dict) -> str:
    """C++ lines that set the Config fields by name."""
    lines = []
    for name, val in overrides.items():
        if isinstance(val, float):
            lines.append(f'  c.{CPP_NAME[name]} = {_lit(f32(val))};')
        else:
            lines.append(f'  c.{CPP_NAME[name]} = {int(val)};')
    return '\n'.join(lines)


def _harness(text: str) -> str:
    parts = [
        SHIM,
        template_function_source(text, 'clampv'),
        config_struct_source(text),
        function_source(text, 'headingToSteerDeg'),
        function_source(text, 'steerDegToUs'),
        function_source(text, 'throttleToUs'),
    ]
    cfgs = []
    for idx, overrides in enumerate(CONFIGS.values()):
        cfgs.append(f'  {{ Config c;\n{_config_code(overrides)}\n  cfgs[{idx}] = c; }}')
    parts.append(f"""
int main() {{
  Config cfgs[{len(CONFIGS)}];
{chr(10).join(cfgs)}
  char kind;
  float x;
  while (scanf(" %c %a", &kind, &x) == 2) {{
    for (int i = 0; i < {len(CONFIGS)}; i++) {{
      const Config &c = cfgs[i];
      if (kind == 'H') {{
        float sd = headingToSteerDeg(x, c);
        printf("%d H %a %a %u %u\\n", i, (double)x, (double)sd,
               (unsigned)steerDegToUs(x, c), (unsigned)steerDegToUs(sd, c));
      }} else {{
        printf("%d T %a %u\\n", i, (double)x, (unsigned)throttleToUs(x, c));
      }}
    }}
  }}
  return 0;
}}
""")
    return '\n'.join(parts)


@pytest.fixture(scope='module')
def firmware_results(tmp_path_factory):
    cxx = shutil.which('g++') or shutil.which('c++')
    if cxx is None:
        pytest.skip('no C++ compiler (g++) in this environment')
    tmp = tmp_path_factory.mktemp('golden')
    src, exe = tmp / 'harness.cpp', tmp / 'harness'
    src.write_text(_harness(main_cpp_text()))
    build = subprocess.run([cxx, *CXX_FLAGS, str(src), '-o', str(exe)],
                           capture_output=True, text=True)
    assert build.returncode == 0, f'harness build failed:\n{build.stderr}'
    degs, thr = _inputs()
    stdin = ''.join(f'H {float.hex(d)}\n' for d in degs) + ''.join(
        f'T {float.hex(t)}\n' for t in thr)
    run = subprocess.run([str(exe)], input=stdin, capture_output=True, text=True)
    assert run.returncode == 0, f'harness failed:\n{run.stderr}'
    return [ln.split() for ln in run.stdout.splitlines()], len(degs), len(thr)


def test_harness_ran_whole_grid(firmware_results):
    rows, n_deg, n_thr = firmware_results
    assert len(rows) == len(CONFIGS) * (n_deg + n_thr)
    assert n_deg > 8000 and n_thr > 200


def test_drive_math_equals_firmware(firmware_results):
    rows, _, _ = firmware_results
    cfgs = [Config(**o) for o in CONFIGS.values()]
    names = list(CONFIGS)
    bad = []
    for row in rows:
        cfg, name = cfgs[int(row[0])], names[int(row[0])]
        x = float.fromhex(row[2])
        if row[1] == 'H':
            fw_sd, fw_us_in, fw_us_sd = float.fromhex(row[3]), int(row[4]), int(row[5])
            sd = heading_to_steer_deg(x, cfg)
            if not (sd == fw_sd or (math.isnan(sd) and math.isnan(fw_sd))):
                bad.append(f'{name}: heading {x!r}: steer deg model {sd!r} fw {fw_sd!r}')
            if steer_deg_to_us(x, cfg) != fw_us_in:
                bad.append(f'{name}: deg {x!r}: steer us model {steer_deg_to_us(x, cfg)} '
                           f'fw {fw_us_in}')
            if steer_deg_to_us(fw_sd, cfg) != fw_us_sd:
                bad.append(f'{name}: deg {fw_sd!r}: steer us model '
                           f'{steer_deg_to_us(fw_sd, cfg)} fw {fw_us_sd}')
        else:
            fw_us = int(row[3])
            if throttle_to_us(x, cfg) != fw_us:
                bad.append(f'{name}: throttle {x!r}: us model {throttle_to_us(x, cfg)} '
                           f'fw {fw_us}')
    assert not bad, f'{len(bad)} mismatches, first 10:\n' + '\n'.join(bad[:10])


def test_grid_reaches_every_pulse_width(firmware_results):
    """The grid is dense enough: it hits all steer and throttle widths of each config."""
    rows, _, _ = firmware_results
    for idx, (name, overrides) in enumerate(CONFIGS.items()):
        c = Config(**overrides)
        steer = {int(r[4]) for r in rows if int(r[0]) == idx and r[1] == 'H'}
        lo, hi = sorted((c.steer_left_us, c.steer_right_us))
        assert steer >= set(range(lo, hi + 1)), f'{name}: steer widths missing'
        thr = {int(r[3]) for r in rows if int(r[0]) == idx and r[1] == 'T'}
        assert {c.esc_min_us, c.esc_neutral_us, c.esc_max_us} <= thr, f'{name}: esc ends'

