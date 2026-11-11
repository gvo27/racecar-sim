"""sim_guard.py PreToolUse hook: deny the real Mapper, ask for car hardware targets."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / '.claude' / 'hooks' / 'sim_guard.py'
spec = importlib.util.spec_from_file_location('sim_guard', HOOK)
sim_guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim_guard)


def kind(command):
    out = sim_guard.decide(command)
    return out['hookSpecificOutput']['permissionDecision'] if out else None


@pytest.mark.parametrize('command', [
    'ros2 launch rccar_drivers drivers.launch.py mapper_host:=192.168.11.1',
    'curl http://192.168.11.1:1445',
    'ping 192.168.11.1',
])
def test_real_mapper_denied(command):
    assert kind(command) == 'deny'


@pytest.mark.parametrize('command', [
    'make car-up',
    'make drivers-start',
    'make flash',
    'cd ../racecar && make car-up',
    'make FW_ENV=esp32s3 flash',
    'true; make drivers-start',
])
def test_car_hardware_asks(command):
    assert kind(command) == 'ask'


@pytest.mark.parametrize('command', [
    'make sim-test',
    'make pin-check',
    'make setup',
    'ros2 launch rccar_drivers drivers.launch.py mapper_host:=127.0.0.1',
    'git commit -m "flash the car"',
    'ls',
])
def test_other_commands_silent(command):
    assert kind(command) is None


def test_subprocess_contract():
    """Real invocation: JSON on stdin, JSON on stdout, exit 0; silent allow prints nothing."""
    def run(command):
        return subprocess.run(
            [sys.executable, '-I', str(HOOK)], capture_output=True, text=True, check=False,
            input=json.dumps({'tool_name': 'Bash', 'tool_input': {'command': command}}))

    res = run('make car-up')
    assert res.returncode == 0
    body = json.loads(res.stdout)['hookSpecificOutput']
    assert body['hookEventName'] == 'PreToolUse'
    assert body['permissionDecision'] == 'ask'
    res = run('ls')
    assert res.returncode == 0 and res.stdout == ''
    res = subprocess.run([sys.executable, '-I', str(HOOK)], input='not json',
                         capture_output=True, text=True, check=False)
    assert res.returncode == 0 and res.stdout == ''
