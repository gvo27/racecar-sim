#!/usr/bin/env python3
"""
PreToolUse guard for Bash in the sim repo (stdlib only).

Rules: .claude/rules/sim.md. Registered in .claude/settings.json.
Output is the documented PreToolUse JSON on stdout (exit 0):
permissionDecision "deny" (the reason goes to the agent) or "ask" (a human must approve).
No output = no opinion (normal permission flow).

- deny: a command that contains 192.168.11.1 (the real Mapper) or mapper_host:=192.168.11.1.
  The sim must never talk to the real Mapper.
- ask: make car-up, make drivers-start, make flash (car checkout targets: they start hardware).
"""
import json
import re
import sys

REAL_MAPPER = '192.168.11.1'
ASK_MAKE = ('car-up', 'drivers-start', 'flash')
MAKE_RE = re.compile(r'(?:^|[;&|\s])make\s+(?:-\S+\s+|\S+=\S+\s+)*(%s)\b' % '|'.join(ASK_MAKE))


def decision(kind, reason):
    return {'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': kind,
        'permissionDecisionReason': reason,
    }}


def decide(command):
    """Return the hook output dict for a Bash command, or None for no opinion."""
    if REAL_MAPPER in command:
        return decision('deny', 'The command uses %s, the address of the real Mapper. '
                        'The sim must not connect to it. Use the virtual Mapper host.' % REAL_MAPPER)
    m = MAKE_RE.search(command)
    if m:
        return decision('ask', 'make %s starts car hardware. Run it only in the car checkout, '
                        'with the approval of a human.' % m.group(1))
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    command = (payload.get('tool_input') or {}).get('command') or ''
    out = decide(command)
    if out:
        print(json.dumps(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
