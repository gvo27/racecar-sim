"""repos/racecar.repos pin checks. Run: make pin-check (dev image).

1. The pinned version is a 40-hex SHA or a tag, not a branch.
2. When the car sources exist (src/racecar in the repo, /ws/src/racecar in the image, or
   $RACECAR_SRC), every "active" topic of docs/sensor_contract.md is a string in the car
   source file that the publisher column names. Simplified from the car deploy/tests/test_contract.py.
"""
import os
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPOS = ROOT / 'repos' / 'racecar.repos'
COLUMNS = ['topic', 'type', 'frame', 'publisher', 'qos', 'rate', 'status', 'sim source']

# publisher column -> car source files that hold the topic string
SOURCES = {
    'mapper_driver': ['rccar_drivers/rccar_drivers/mapper_node.py'],
    'esp32': ['firmware/esp32/src/main.cpp'],
    'esp32 (service)': ['firmware/esp32/src/main.cpp'],
    'supervisor': ['rccar_supervisor/rccar_supervisor/supervisor_node.py'],
    'captain': ['rccar_supervisor/rccar_supervisor/arbiter.py'],
    'teleop': ['rccar_supervisor/rccar_supervisor/arbiter.py'],
}


def pinned_version():
    """The `version:` value of the first repository, without PyYAML."""
    text = REPOS.read_text()
    try:
        import yaml
        repos = yaml.safe_load(text)['repositories']
        return str(next(iter(repos.values()))['version'])
    except ImportError:
        m = re.search(r'^\s+version:\s*(\S+)\s*$', text, re.M)
        assert m, 'no version: line in repos/racecar.repos'
        return m.group(1)


def racecar_dir():
    for cand in (os.environ.get('RACECAR_SRC'), ROOT / 'src' / 'racecar', '/ws/src/racecar'):
        if cand and (Path(cand) / 'docs' / 'sensor_contract.md').is_file():
            return Path(cand)
    return None


def active_rows(contract):
    rows, in_table = [], False
    for line in contract.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if cells == COLUMNS:
            in_table = True
            continue
        if in_table:
            if not line.startswith('|'):
                break
            if set(line) <= set('|- '):
                continue
            row = dict(zip(COLUMNS, cells))
            if row['status'] == 'active':
                rows.append(row)
    return rows


CAR = racecar_dir()
ROWS = active_rows(CAR / 'docs' / 'sensor_contract.md') if CAR else []


def test_version_is_sha_or_tag():
    version = pinned_version()
    is_sha = re.fullmatch(r'[0-9a-f]{40}', version) is not None
    is_tag = re.fullmatch(r'v?\d+\.\d+(\.\d+)?([-.\w]*)', version) is not None
    assert is_sha or is_tag, 'version %r is not a 40-hex SHA or a tag (no branches)' % version
    assert version not in ('main', 'master', 'HEAD')


@pytest.mark.skipif(CAR is None, reason='car sources not found (src/racecar, /ws/src/racecar, RACECAR_SRC)')
def test_contract_has_active_rows():
    assert ROWS, 'no active rows in docs/sensor_contract.md'


@pytest.mark.skipif(CAR is None, reason='car sources not found (src/racecar, /ws/src/racecar, RACECAR_SRC)')
@pytest.mark.parametrize('row', ROWS, ids=lambda r: r['topic'])
def test_active_topic_in_car_sources(row):
    files = SOURCES.get(row['publisher'])
    assert files, 'no source mapping for publisher %r (update SOURCES)' % row['publisher']
    hits = [f for f in files if row['topic'] in (CAR / f).read_text()]
    assert hits, '%s not found in %s' % (row['topic'], files)
