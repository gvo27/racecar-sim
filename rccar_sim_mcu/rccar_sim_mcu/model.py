"""Pure-Python model of the virtual ESP32 (car firmware 0.3.0).

Source: firmware/esp32/src/main.cpp in the car repo, at the SHA in repos/racecar.repos.
There is no ROS code here. The caller injects the time as integer milliseconds
(monotonic, like esp_timer). The firmware uses float32 and lroundf. This file keeps
both, so the pulse widths match the firmware to the microsecond.
"""

from __future__ import annotations

import enum
import math
import re
import struct
from dataclasses import dataclass, fields, replace

FW_VERSION = '0.3.0'

# McuEvent codes (rccar_msgs/msg/McuEvent)
EVT_READY = 1
EVT_FAILSAFE = 2
EVT_ARMED = 3
EVT_DISARMED = 4

# Hard limits from the datasheets (main.cpp:41-48). Never exceeded, even in RAW.
SERVO_ABS_MIN_US = 500
SERVO_ABS_MAX_US = 2500
SERVO_MAX_HZ = 330
ESC_ABS_MIN_US = 900
ESC_ABS_MAX_US = 2100
ESC_MAX_HZ = 400

# Pins (firmware/esp32/include/pins.h)
PIN_STEER_PWM = 4
PIN_THROTTLE_PWM = 5

CMD_CAP = 64      # longest command, bytes (contract)
REPLY_CAP = 384   # longest reply, bytes (contract)

_MASK64 = (1 << 64) - 1
_EOL = '\r\n'  # Arduino println ends with CR LF; printf lines in the firmware end with LF only


# ---------------------------------------------------------------------------
# float32 and C helpers
# ---------------------------------------------------------------------------
def f32(x: float) -> float:
    """Round a Python float to the nearest float32 (C float)."""
    try:
        return struct.unpack('<f', struct.pack('<f', x))[0]
    except OverflowError:
        return math.copysign(math.inf, x)


def lroundf(x: float) -> int:
    """C lroundf: round half away from zero. A non-finite value gives 0 (undefined in C)."""
    if not math.isfinite(x):
        return 0
    return int(math.copysign(math.floor(abs(x) + 0.5), x))


def clampv(v: float, lo: float, hi: float) -> float:
    """C++ clampv from main.cpp: NaN passes through."""
    return lo if v < lo else (hi if v > hi else v)


def _clamp_int(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else (hi if v > hi else v)


def _trunc(x: float) -> int:
    """C cast float -> integer (toward zero). NaN and inf give 0 (undefined in C)."""
    return int(x) if math.isfinite(x) else 0


def _fdiv(a: float, b: float) -> float:
    if b == 0.0:
        if a == 0.0 or math.isnan(a):
            return math.nan
        return math.copysign(math.inf, a) * math.copysign(1.0, b)
    return f32(a / b)


_FLOAT_RE = re.compile(
    r'[+-]?(?:'
    r'0x[0-9a-f]+(?:\.[0-9a-f]*)?(?:p[+-]?\d+)?'
    r'|inf(?:inity)?'
    r'|nan(?:\([a-z0-9_]*\))?'
    r'|(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?'
    r')',
    re.IGNORECASE,
)
_INT_RE = re.compile(r'[ \t\n\v\f\r]*([+-]?\d+)')


def strtof(s: str) -> float:
    """C strtof(s, nullptr): read the longest valid prefix. No number gives 0."""
    m = _FLOAT_RE.match(s)
    if not m:
        return 0.0
    t = m.group(0).lower()
    neg = t.startswith('-')
    body = t.lstrip('+-')
    if body.startswith('inf'):
        return -math.inf if neg else math.inf
    if body.startswith('nan'):
        return math.nan
    try:
        v = float.fromhex(t) if body.startswith('0x') else float(t)
    except (ValueError, OverflowError):
        return 0.0
    return f32(v)


def atoi(s: str) -> int:
    """C atoi. The result saturates at the int32 range."""
    m = _INT_RE.match(s)
    if not m:
        return 0
    return _clamp_int(int(m.group(1)), -(1 << 31), (1 << 31) - 1)


def _lower(s: str) -> str:
    """ASCII-only lower case, like strcasecmp."""
    return ''.join(c.lower() if c < '\x80' else c for c in s)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@dataclass
class Config:
    """The firmware Config struct (main.cpp:63-94), with its defaults.

    Each field lists the C++ name and the SET key. Float fields hold float32 values.
    """

    steer_center_us: int = 1500    # steerCenterUs; CAL CENTER
    steer_left_us: int = 1800      # steerLeftUs; CAL LEFT
    steer_right_us: int = 1200     # steerRightUs; CAL RIGHT
    max_steer_deg: float = 25.0    # maxSteerDeg; SET maxdeg
    heading_gain: float = 1.0      # headingGain; SET gain
    speed_limit: float = 0.30      # speedLimit; SET limit
    deadband_us: int = 0           # deadbandUs; SET deadband
    accel_per_sec: float = 2.0     # accelPerSec; SET accel
    timeout_ms: int = 300          # timeoutMs; SET timeout
    double_tap_rev: int = 1        # doubleTapRev; SET revmode
    brake_ms: int = 150            # brakeMs; SET brake_ms
    gap_ms: int = 150              # gapMs; SET gap_ms
    brake_level: float = 0.5       # brakeLevel; SET brake_level
    esc_min_us: int = 1000         # escMinUs; SET esc_min
    esc_neutral_us: int = 1500     # escNeutralUs; SET esc_neutral
    esc_max_us: int = 2000         # escMaxUs; SET esc_max
    servo_hz: int = 50             # servoHz; SET servo_hz
    esc_hz: int = 50               # escHz; SET esc_hz
    control_hz: int = 100          # controlHz; SET control_hz
    rf_driver: int = 1             # rfDriver; SET rf_driver
    rf_i2c_addr: int = 0x62        # rfI2cAddr; SET rf_addr
    rf_period_ms: int = 20         # rfPeriodMs; SET rf_period_ms
    rf_scale_m: float = 0.01       # rfScaleM; SET rf_scale_m
    rf_no_return_raw: int = 1      # rfNoReturnRaw; SET rf_no_return
    rf_min_m: float = 0.05         # rfMinM; SET rf_min_m
    rf_max_m: float = 10.0         # rfMaxM; SET rf_max_m
    rf_fov_rad: float = 0.0833     # rfFovRad; SET rf_fov_rad
    rf_radiation: int = 1          # rfRadiation; SET rf_radiation

    def __post_init__(self) -> None:
        for f in fields(self):
            if f.type == 'float':
                setattr(self, f.name, f32(getattr(self, f.name)))


# Constants that are not exact in float32
_F_0_001 = f32(0.001)
_F_0_1 = f32(0.1)
_F_1E_4 = f32(1e-4)
_F_3_14 = f32(3.14)
_F_0_01 = f32(0.01)
_F_RAD_TO_DEG = f32(57.29577951)
_F_DEG_TO_RAD = f32(0.01745329252)


# ---------------------------------------------------------------------------
# Drive math (main.cpp:172-192)
# ---------------------------------------------------------------------------
def heading_to_steer_deg(deg: float, cfg: Config) -> float:
    """Heading (deg) to road-wheel angle (deg): gain, then clamp to +-max_steer_deg."""
    deg = f32(deg)
    return clampv(f32(deg * cfg.heading_gain), -cfg.max_steer_deg, cfg.max_steer_deg)


def steer_deg_to_us(deg: float, cfg: Config) -> int:
    """Road-wheel angle (deg) to servo pulse (us). Piecewise linear, clamped to left/right."""
    frac = _fdiv(f32(deg), cfg.max_steer_deg)  # -1 (right) .. +1 (left)
    if frac >= 0:
        us = f32(cfg.steer_center_us + f32(frac * (cfg.steer_left_us - cfg.steer_center_us)))
    else:
        us = f32(cfg.steer_center_us + f32(-frac * (cfg.steer_right_us - cfg.steer_center_us)))
    lo = min(cfg.steer_left_us, cfg.steer_right_us)
    hi = max(cfg.steer_left_us, cfg.steer_right_us)
    return _clamp_int(lroundf(us) & 0xFFFF, lo, hi)


def throttle_to_us(u: float, cfg: Config) -> int:
    """Throttle fraction (-1..1, already speed-limited) to ESC pulse (us)."""
    u = f32(u)
    if abs(u) < _F_0_001:
        return cfg.esc_neutral_us
    span_int = (cfg.esc_max_us - cfg.esc_neutral_us if u > 0
                else cfg.esc_neutral_us - cfg.esc_min_us) - cfg.deadband_us
    span = f32(span_int)
    sign = 1 if u > 0 else -1
    us = f32(cfg.esc_neutral_us
             + f32(sign * f32(cfg.deadband_us + f32(abs(u) * span))))
    return _clamp_int(lroundf(us) & 0xFFFF, cfg.esc_min_us, cfg.esc_max_us)


@dataclass
class Outputs:
    """What one control tick drives."""

    steer_us: int
    throttle_us: int
    steer_deg: float
    u: float  # throttle fraction after the speed limit and the reverse logic


@dataclass
class Telemetry:
    """Snapshot with the fields of rccar_msgs/msg/Telemetry (main.cpp:717-730)."""

    mcu_ms: int
    heading_rad: float  # last accepted command, not the output
    throttle: float     # last accepted command, not the output
    steer_rad: float
    steer_us: int
    throttle_us: int
    armed: bool
    time_synced: bool


class RevState(enum.IntEnum):
    """Double-tap reverse state (main.cpp:197)."""

    FORWARD = 0
    BRAKE = 1
    GAP = 2
    REVERSE = 3


# ---------------------------------------------------------------------------
# setKey (main.cpp:376-404)
# ---------------------------------------------------------------------------
def _u16(v: float, lo: float, hi: float) -> int:
    return _trunc(clampv(v, f32(lo), f32(hi))) & 0xFFFF


def _set_key(c: Config, key: str, v: float) -> bool:
    """Apply one SET. Return False for an unknown key."""
    k = _lower(key)
    if k == 'maxdeg':
        c.max_steer_deg = clampv(v, 1.0, 60.0)
    elif k == 'gain':
        c.heading_gain = clampv(v, 0.0, 10.0)
    elif k == 'limit':
        c.speed_limit = clampv(v, 0.0, 1.0)
    elif k == 'deadband':
        c.deadband_us = _u16(v, 0, 200)
    elif k == 'accel':
        c.accel_per_sec = clampv(v, _F_0_1, 100.0)
    elif k == 'timeout':
        c.timeout_ms = _u16(v, 50, 2000)
    elif k == 'revmode':
        c.double_tap_rev = 1 if v != 0 else 0
    elif k == 'brake_ms':
        c.brake_ms = _u16(v, 0, 1000)
    elif k == 'gap_ms':
        c.gap_ms = _u16(v, 0, 1000)
    elif k == 'brake_level':
        c.brake_level = clampv(v, 0.0, 1.0)
    elif k == 'esc_min':
        c.esc_min_us = _u16(v, ESC_ABS_MIN_US, 1500)
    elif k == 'esc_neutral':
        c.esc_neutral_us = _u16(v, 1300, 1700)
    elif k == 'esc_max':
        c.esc_max_us = _u16(v, 1500, ESC_ABS_MAX_US)
    elif k == 'servo_hz':
        c.servo_hz = _u16(v, 50, SERVO_MAX_HZ)
    elif k == 'esc_hz':
        c.esc_hz = _u16(v, 50, ESC_MAX_HZ)
    elif k == 'control_hz':
        c.control_hz = _u16(v, 20, 500)
    elif k == 'rf_driver':
        c.rf_driver = lroundf(clampv(v, 0.0, 1.0)) & 0xFF
    elif k == 'rf_addr':
        c.rf_i2c_addr = lroundf(clampv(v, 8.0, 119.0)) & 0xFF
    elif k == 'rf_period_ms':
        c.rf_period_ms = lroundf(clampv(v, 20.0, 1000.0)) & 0xFFFF
    elif k == 'rf_scale_m':
        c.rf_scale_m = clampv(v, _F_1E_4, 1.0)
    elif k == 'rf_no_return':
        c.rf_no_return_raw = lroundf(clampv(v, 0.0, 65535.0))
    elif k == 'rf_min_m':
        c.rf_min_m = clampv(v, 0.0, 100.0)
    elif k == 'rf_max_m':
        c.rf_max_m = clampv(v, _F_0_01, 100.0)
    elif k == 'rf_fov_rad':
        c.rf_fov_rad = clampv(v, _F_0_001, _F_3_14)
    elif k == 'rf_radiation':
        c.rf_radiation = 1 if v != 0 else 0
    else:
        return False
    return True


def config_line(c: Config) -> str:
    """The CFG line (printConfig, main.cpp:366-373), with the final LF."""
    return (
        'CFG center=%u left=%u right=%u maxdeg=%.1f gain=%.2f limit=%.2f '
        'deadband=%u accel=%.2f timeout=%u revmode=%u brake_ms=%u gap_ms=%u '
        'brake_level=%.2f esc_min=%u esc_neutral=%u esc_max=%u servo_hz=%u '
        'esc_hz=%u control_hz=%u\n'
        % (c.steer_center_us, c.steer_left_us, c.steer_right_us, c.max_steer_deg,
           c.heading_gain, c.speed_limit, c.deadband_us, c.accel_per_sec,
           c.timeout_ms, c.double_tap_rev, c.brake_ms, c.gap_ms, c.brake_level,
           c.esc_min_us, c.esc_neutral_us, c.esc_max_us, c.servo_hz, c.esc_hz,
           c.control_hz))


# ---------------------------------------------------------------------------
# The model
# ---------------------------------------------------------------------------
class McuModel:
    """The virtual ESP32: control task, command grammar and event logic.

    The caller drives it: on_drive() for each /rccar/mcu/drive message, step() at
    cfg.control_hz, service_command() for each McuCommand request, pop_events() and
    telemetry() on the node timers. All time arguments are integer ms.
    """

    def __init__(self, now_ms: int = 0) -> None:
        self.cfg = Config()
        self._nvs: Config | None = None  # what SAVE stored
        # Rangefinder stub sample: a present sensor with a no-return reading. SENS and
        # range_m() both read it. The node may set these.
        self.rf_present = True
        self.rf_raw = self.cfg.rf_no_return_raw
        self.rf_status = 0
        self.rf_stamp_ms = now_ms
        self.rf_seq = 1
        self.time_synced = True
        self._events: list[tuple[int, str]] = []
        self._boot(now_ms)

    def _boot(self, now_ms: int) -> None:
        self._armed = False
        self._raw_steer_us = -1
        self._cmd_heading_deg = 0.0
        self._cmd_speed = 0.0
        self._cmd_stamp = 0
        self._speed_out = 0.0
        self._rs = RevState.FORWARD
        self._rs_since = 0
        self._out = Outputs(1500, 1500, 0.0, 0.0)
        self._failsafe_evt = False
        self._last_armed = False
        self._tel_hz = 10
        self._events = [(EVT_READY, 'fw=' + FW_VERSION)]

    # -- read-only state ----------------------------------------------------
    @property
    def armed(self) -> bool:
        return self._armed

    @property
    def raw_steer_us(self) -> int:
        """RAW override in us, or -1 when off."""
        return self._raw_steer_us

    @property
    def reverse_state(self) -> RevState:
        return self._rs

    @property
    def telemetry_hz(self) -> int:
        """Telemetry rate in Hz (TEL command). 0 = off."""
        return self._tel_hz

    def range_m(self) -> float:
        """Range for /rccar/rangefinder/range, from the sample (main.cpp:745)."""
        if self.rf_raw == self.cfg.rf_no_return_raw:
            return math.inf
        return self.rf_raw * self.cfg.rf_scale_m

    # -- inputs -------------------------------------------------------------
    def on_drive(self, heading_rad: float, throttle: float, now_ms: int) -> None:
        """Same as driveCb: clamp, store, refresh the stamp. A non-finite value is dropped."""
        h = f32(f32(heading_rad) * _F_RAD_TO_DEG)
        t = f32(throttle)
        if not (math.isfinite(h) and math.isfinite(t)):
            return  # no stamp refresh, so the failsafe can fire
        self._cmd_heading_deg = clampv(h, -180.0, 180.0)
        self._cmd_speed = clampv(t, -1.0, 1.0)
        self._cmd_stamp = now_ms

    def reboot(self, now_ms: int) -> None:
        """Power cycle. Config = last SAVEd config or the defaults. Disarmed, READY queued."""
        self.cfg = replace(self._nvs) if self._nvs is not None else Config()
        self._boot(now_ms)

    # -- control task -------------------------------------------------------
    def step(self, now_ms: int) -> Outputs:
        """One controlTask tick (main.cpp:199-274)."""
        cfg = self.cfg
        stale = ((now_ms - self._cmd_stamp) & _MASK64) > cfg.timeout_ms
        armed = self._armed
        if armed and stale:
            armed = False
            self._armed = False
            self._failsafe_evt = True

        # Speed: slew-limited toward the target. Disarm snaps to neutral.
        target = clampv(self._cmd_speed, -1.0, 1.0) if armed else 0.0
        step = _fdiv(cfg.accel_per_sec, float(cfg.control_hz))
        if armed:
            delta = clampv(f32(target - self._speed_out), -step, step)
            self._speed_out = f32(self._speed_out + delta)
        else:
            self._speed_out = 0.0
        u = f32(self._speed_out * cfg.speed_limit)

        if cfg.double_tap_rev:
            u = self._reverse_logic(u, now_ms, cfg)

        # Steering follows the command also when disarmed.
        steer_deg = heading_to_steer_deg(self._cmd_heading_deg, cfg)
        if self._raw_steer_us > 0:
            steer_us = _clamp_int(self._raw_steer_us, SERVO_ABS_MIN_US, SERVO_ABS_MAX_US)
        else:
            steer_us = steer_deg_to_us(steer_deg, cfg)
        thr_us = throttle_to_us(u, cfg)
        self._out = Outputs(steer_us, thr_us, steer_deg, u)
        return replace(self._out)

    def _reverse_logic(self, u: float, now: int, cfg: Config) -> float:
        """Brake, neutral gap, then reverse (many brushed ESCs need it)."""
        rs = self._rs
        since = (now - self._rs_since) & _MASK64
        if rs == RevState.FORWARD:
            if u < 0:
                self._rs = RevState.BRAKE
                self._rs_since = now
                u = -cfg.brake_level
        elif rs == RevState.BRAKE:
            if u >= 0:
                self._rs = RevState.FORWARD
            elif since >= cfg.brake_ms:
                self._rs = RevState.GAP
                self._rs_since = now
                u = 0.0
            else:
                u = -cfg.brake_level
        elif rs == RevState.GAP:
            if u >= 0:
                self._rs = RevState.FORWARD
            elif since >= cfg.gap_ms:
                self._rs = RevState.REVERSE
            else:
                u = 0.0
        else:  # REVERSE: u == 0 stays in REVERSE
            if u > 0:
                self._rs = RevState.FORWARD
        return u

    # -- outputs ------------------------------------------------------------
    def pop_events(self) -> list[tuple[int, str]]:
        """Events since the last call, in firmware order: READY, FAILSAFE, ARMED or DISARMED.

        ARMED or DISARMED comes from a change of the armed flag since the last call.
        """
        if self._failsafe_evt:
            self._failsafe_evt = False
            self._events.append((EVT_FAILSAFE, 'command timeout -> disarmed'))
        if self._armed != self._last_armed:
            self._last_armed = self._armed
            self._events.append((EVT_ARMED if self._armed else EVT_DISARMED, ''))
        ev, self._events = self._events, []
        return ev

    def telemetry(self, now_ms: int) -> Telemetry:
        """Snapshot for /rccar/mcu/telemetry (publishTelemetry)."""
        return Telemetry(
            mcu_ms=now_ms,
            heading_rad=f32(self._cmd_heading_deg * _F_DEG_TO_RAD),
            throttle=self._cmd_speed,
            steer_rad=f32(self._out.steer_deg * _F_DEG_TO_RAD),
            steer_us=self._out.steer_us,
            throttle_us=self._out.throttle_us,
            armed=self._armed,
            time_synced=self.time_synced,
        )

    # -- command grammar ----------------------------------------------------
    def service_command(self, command: str, now_ms: int) -> tuple[bool, str]:
        """Same as commandCb: cap the line, refuse D, run it, strip the trailing CR/LF.

        Return (ok, reply). ok is False when the reply starts with ERR.
        """
        raw = command.encode('utf-8')[:CMD_CAP]
        line = raw.decode('utf-8', errors='replace').split('\0', 1)[0]
        m = re.match(r'[ \t\n\v\f\r]*([^ \t\n\v\f\r]{1,3})', line)
        first = m.group(1) if m else ''
        if _lower(first) == 'd':
            reply = 'ERR D refused: drive is /rccar/mcu/drive' + _EOL
        else:
            reply = self.handle_line(line, now_ms)
        reply = reply.encode('utf-8')[:REPLY_CAP].decode('utf-8', errors='ignore')
        reply = reply.rstrip('\r\n')
        return (not reply.startswith('ERR'), reply)

    def handle_line(self, line: str, now_ms: int) -> str:
        """Run one command line (handleLine, main.cpp:406-501). Return the reply text."""
        line = line.split('\0', 1)[0]
        toks = [t for t in re.split(r'[ \t\r]+', line) if t]
        if not toks:
            return ''
        tok = _lower(toks[0])
        a1 = toks[1] if len(toks) > 1 else None
        a2 = toks[2] if len(toks) > 2 else None
        c = self.cfg

        if tok == 'd':
            if a1 is None or a2 is None:
                return 'ERR usage: D <heading_deg> <speed>' + _EOL
            self._cmd_heading_deg = clampv(strtof(a1), -180.0, 180.0)
            self._cmd_speed = clampv(strtof(a2), -1.0, 1.0)
            self._cmd_stamp = now_ms
            return ''  # no reply: telemetry is the feedback
        if tok == 'arm':
            self._cmd_speed = 0.0
            self._cmd_stamp = now_ms
            self._armed = True
            return 'OK ARM' + _EOL
        if tok in ('disarm', 'stop'):
            self._armed = False
            self._cmd_speed = 0.0
            return 'OK DISARM' + _EOL
        if tok == 'ping':
            return 'PONG %s %d\n' % (a1 if a1 is not None else '0', now_ms)
        if tok == 'time':
            return 'ERR TIME unsupported: micro-ROS syncs the clock with the agent' + _EOL
        if tok == 'raw':
            if a1 is None:
                return 'ERR usage: RAW <us>|OFF' + _EOL
            if _lower(a1) == 'off':
                us = -1
            else:
                us = _clamp_int(atoi(a1), SERVO_ABS_MIN_US, SERVO_ABS_MAX_US)
            self._raw_steer_us = us
            return 'OK RAW %d\n' % us
        if tok == 'cal':
            if a1 is None or a2 is None:
                return config_line(c)
            us = _clamp_int(atoi(a2), SERVO_ABS_MIN_US, SERVO_ABS_MAX_US)
            which = _lower(a1)
            if which == 'left':
                c.steer_left_us = us
            elif which == 'center':
                c.steer_center_us = us
            elif which == 'right':
                c.steer_right_us = us
            else:
                return 'ERR CAL LEFT|CENTER|RIGHT <us>' + _EOL
            return config_line(c)
        if tok == 'set':
            if a1 is None or a2 is None:
                return 'ERR usage: SET <key> <value>' + _EOL
            nc = replace(c)
            if not _set_key(nc, a1, strtof(a2)):
                return 'ERR unknown key %s\n' % a1
            if not (nc.esc_min_us < nc.esc_neutral_us < nc.esc_max_us):
                return 'ERR need esc_min < esc_neutral < esc_max' + _EOL
            if not (nc.rf_min_m < nc.rf_max_m):
                return 'ERR rf_min_m must be < rf_max_m' + _EOL
            self.cfg = nc
            return config_line(nc)
        if tok == 'get':
            return config_line(c)
        if tok == 'save':
            lo = min(c.steer_left_us, c.steer_right_us)
            hi = max(c.steer_left_us, c.steer_right_us)
            if not (lo < c.steer_center_us < hi):
                return 'ERR center must lie between left and right' + _EOL
            self._nvs = replace(c)
            return 'OK SAVE' + _EOL
        if tok == 'defaults':
            self.cfg = Config()  # not saved until SAVE
            return config_line(self.cfg)
        if tok == 'tel':
            self._tel_hz = _clamp_int(atoi(a1), 0, 50) if a1 is not None else 10
            return 'OK TEL %u\n' % self._tel_hz
        if tok == 'sens':
            if a1 is not None and _lower(a1) == 'rangefinder':
                return self._sens_line(now_ms)
            return 'ERR SENS %s not implemented\n' % (a1 if a1 is not None else '?')
        if tok == 'info':
            return ('INFO fw=%s chip=sim rev=0 psram=0 flash=0 steer_pin=%d throttle_pin=%d\n'
                    % (FW_VERSION, PIN_STEER_PWM, PIN_THROTTLE_PWM))
        return 'ERR unknown command %s\n' % toks[0]

    def _sens_line(self, now_ms: int) -> str:
        c = self.cfg
        raw = self.rf_raw if self.rf_present else 0
        if not self.rf_present:
            m = math.nan
        elif self.rf_raw == c.rf_no_return_raw:
            m = math.inf
        else:
            m = self.rf_raw * c.rf_scale_m
        age = ((now_ms - self.rf_stamp_ms) & 0xFFFFFFFF) if self.rf_present else 0
        return (
            'SENS rangefinder present=%d driver=%u addr=0x%02x period_ms=%u scale_m=%.4f '
            'no_return=%u min_m=%.2f max_m=%.2f fov_rad=%.4f radiation=%u '
            'raw=%u range_m=%.3f status=0x%02x age_ms=%u seq=%u\n'
            % (1 if self.rf_present else 0, c.rf_driver, c.rf_i2c_addr, c.rf_period_ms,
               c.rf_scale_m, c.rf_no_return_raw, c.rf_min_m, c.rf_max_m, c.rf_fov_rad,
               c.rf_radiation, raw, m, self.rf_status, age, self.rf_seq & 0xFFFFFFFF))
