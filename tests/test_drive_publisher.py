"""No sim code publishes /rccar/mcu/drive. Run: make unit (dev image).

Rules (sim.md 1 and 2):
1. No rccar_sim_* file creates a publisher on '/rccar/mcu/drive'.
2. No file outside rccar_sim_mcu/test publishes a /rccar/cmd/ topic other than
   /rccar/cmd/captain. Exception: the launch tests in rccar_sim_mcu/test publish
   /rccar/cmd/admin, because they act as the teleop.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DRIVE = '/rccar/mcu/drive'
EXCEPTION_DIR = ROOT / 'rccar_sim_mcu' / 'test'
# create_publisher( ... ) up to the matching close; a statement has no nested call with ')' in it
# for the sim code, so a non-greedy match to the first ')' is enough. A constant name counts too.
PUBLISHER = re.compile(r'create_publisher\((.*?)\)', re.S)
CMD_TOPIC = re.compile(r"""['"](/rccar/cmd/[A-Za-z0-9_]+)['"]""")


def sim_files():
    return sorted(p for p in ROOT.glob('rccar_sim_*/**/*.py') if '/build/' not in str(p))


def publisher_statements(text):
    return [m.group(1) for m in PUBLISHER.finditer(text)]


def test_files_found():
    assert sim_files(), 'no rccar_sim_*/**/*.py found'


def test_no_drive_publisher():
    bad = []
    for p in sim_files():
        text = p.read_text()
        consts = set(re.findall(r"^(\w+)\s*=\s*['\"]" + re.escape(DRIVE) + r"['\"]", text, re.M))
        for stmt in publisher_statements(text):
            if DRIVE in stmt or any(re.search(rf'\b{c}\b', stmt) for c in consts):
                bad.append(str(p.relative_to(ROOT)))
    assert not bad, f'publisher on {DRIVE}: {bad}'


def test_only_captain_outside_tests():
    bad = []
    for p in sim_files():
        if EXCEPTION_DIR in p.parents:
            continue
        for stmt in publisher_statements(p.read_text()):
            for topic in CMD_TOPIC.findall(stmt):
                if topic != '/rccar/cmd/captain':
                    bad.append(f'{p.relative_to(ROOT)}: {topic}')
    assert not bad, f'only /rccar/cmd/captain is allowed: {bad}'


def test_checker_catches_a_publisher():
    assert publisher_statements("self.create_publisher(DriveCmd, '/rccar/mcu/drive', q)")
    assert DRIVE in publisher_statements(
        "x.create_publisher(DriveCmd, '/rccar/mcu/drive', q)")[0]
