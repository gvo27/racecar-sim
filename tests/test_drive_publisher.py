"""No sim code publishes /rccar/mcu/drive. Run: make unit (dev image).

Rules (sim.md 1 and 2), checked on the AST:
1. No rccar_sim_* file creates a publisher on '/rccar/mcu/drive'. No YAML under
   rccar_sim_*/ names it (future ros_gz_bridge configs).
2. No file outside rccar_sim_mcu/test publishes a /rccar/cmd/ topic other than
   /rccar/cmd/captain. Exception: the launch tests in rccar_sim_mcu/test publish
   /rccar/cmd/admin, because they act as the teleop.
A topic that is not a str constant, a module constant or an f-string is unknown and passes.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRIVE = '/rccar/mcu/drive'
CAPTAIN = '/rccar/cmd/captain'
EXCEPTION_DIR = ROOT / 'rccar_sim_mcu' / 'test'


def sim_files():
    found = set(ROOT.glob('rccar_sim_*/**/*.py'))
    return sorted(p for p in found if '/build/' not in str(p))


def yaml_files():
    found = set(ROOT.glob('rccar_sim_*/**/*.yaml')) | set(ROOT.glob('rccar_sim_*/**/*.yml'))
    return sorted(p for p in found if '/build/' not in str(p))


def _str_const(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _fstring_text(node):
    """Literal parts of an f-string, with '{}' for each value."""
    return ''.join(v.value if isinstance(v, ast.Constant) else '{}' for v in node.values)


def publisher_topics(source):
    """Return the resolved topics of every create_publisher call. None = unknown."""
    tree = ast.parse(source)
    consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and _str_const(node.value) is not None:
            for t in node.targets:
                if isinstance(t, ast.Name):
                    consts[t.id] = node.value.value
    topics = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, 'id', None)
        if name != 'create_publisher':
            continue
        arg = node.args[1] if len(node.args) > 1 else None
        for kw in node.keywords:
            if kw.arg == 'topic':
                arg = kw.value
        topic = None
        if arg is not None:
            if _str_const(arg) is not None:
                topic = arg.value
            elif isinstance(arg, ast.Name):
                topic = consts.get(arg.id)
            elif isinstance(arg, ast.JoinedStr):
                topic = _fstring_text(arg)
        topics.append(topic)
    return topics


def violations(source, allow_cmd=False):
    bad = []
    for topic in publisher_topics(source):
        if topic is None:
            continue
        if topic == DRIVE:
            bad.append(topic)
        elif topic.startswith('/rccar/cmd/') and topic != CAPTAIN and not allow_cmd:
            bad.append(topic)
    return bad


def test_files_found():
    assert sim_files(), 'no rccar_sim_*/**/*.py found'


def test_no_forbidden_publisher():
    bad = []
    for p in sim_files():
        allow = EXCEPTION_DIR in p.parents
        bad += [f'{p.relative_to(ROOT)}: {t}' for t in violations(p.read_text(), allow)]
    assert not bad, f'forbidden publisher: {bad}'


def test_no_drive_in_yaml():
    bad = [str(p.relative_to(ROOT)) for p in yaml_files() if DRIVE in p.read_text()]
    assert not bad, f'{DRIVE} in YAML: {bad}'


def test_checker_catches_publishers():
    assert violations("self.create_publisher(DriveCmd, '/rccar/mcu/drive', q)")
    assert violations("T = '/rccar/mcu/drive'\nn.create_publisher(DriveCmd, T, q)")
    assert violations("n.create_publisher(DriveCmd, topic='/rccar/mcu/drive', qos_profile=q)")
    assert violations("n.create_publisher(DriveCmd, f'/rccar/mcu/drive', q)")
    assert violations("n.create_publisher(DriveCmd, '/rccar/cmd/admin', q)")
    assert not violations("n.create_publisher(DriveCmd, '/rccar/cmd/admin', q)", allow_cmd=True)
    assert not violations("n.create_publisher(DriveCmd, '/rccar/cmd/captain', q)")
    assert not violations("n.create_publisher(DriveCmd, name, q)")
