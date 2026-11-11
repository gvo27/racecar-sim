"""Every .claude/rules/*.md has a paths: frontmatter, and every glob matches a file."""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
RULES = sorted((ROOT / '.claude' / 'rules').glob('*.md'))


def frontmatter_paths(path):
    text = path.read_text()
    if not text.startswith('---\n'):
        return None
    head = text[4:text.index('\n---', 4)]
    if not re.search(r'^paths:\s*$', head, re.M):
        return None
    return re.findall(r'^\s+-\s+"([^"]+)"\s*$', head, re.M)


def matches(glob):
    hits = ROOT.glob(glob)
    return any(not p.is_relative_to(ROOT / '.git') for p in hits)


def test_rules_exist():
    assert RULES, 'no .claude/rules/*.md'


@pytest.mark.parametrize('rule', RULES, ids=lambda p: p.name)
def test_rule_has_paths(rule):
    globs = frontmatter_paths(rule)
    assert globs, '%s: no paths: frontmatter (the rule never loads)' % rule.name


@pytest.mark.parametrize('rule', RULES, ids=lambda p: p.name)
def test_rule_globs_match(rule):
    dead = [g for g in frontmatter_paths(rule) or [] if not matches(g)]
    assert not dead, '%s: globs match no file: %s' % (rule.name, dead)
