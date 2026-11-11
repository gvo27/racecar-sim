---
paths:
  - "**/*.md"
  - ".github/**"
---

# Writing convention: ASD-STE100 Simplified Technical English

All new and changed project text follows ASD-STE100 (STE). The `asd-ste100` plugin supplies the rules (plugin source: `.claude/settings.json`, entry in `.claude/rules/dependencies.md`). This file is the project layer on top of the plugin. The car repo has the same rule.

## Scope
- Repo docs: `README.md`, `docs/**`, `repos/README.md`, `docs/plans/**`.
- Claude files: `.claude/CLAUDE.md`, `.claude/rules/*.md`, `.claude/agents/*.md`, `.claude/skills/*/SKILL.md`, hook messages in `.claude/hooks/*`.
- GitHub text: PR titles and bodies, review replies, issue text, commit messages.
- Strings that people or agents read: error messages, log lines, `--help` text, launch-file and parameter descriptions.

Out of scope: code identifiers, file paths, commands, quoted third-party text, and third-party files.

## Mode per text type
| Mode | Use for |
|---|---|
| Strict | `.claude/**`, procedures, safety text, error and log strings, hook messages, inter-agent instructions |
| STE-flavored | `README.md`, `docs/**` prose, plans, PR bodies, commit messages, review replies |

Strict applies every rule in the plugin. STE-flavored applies the structural rules in full and treats the lexical rules as advisory.

## Project rules
1. Keep every fact. Do not change numbers, units, topic names, `make` targets, versions, digests or links.
2. Keep every hedge. "May", "should", "not verified" and "bench pending" are content. Do not change them to a fact.
3. Keep safety conditions, scope limits and "never" rules. If a rule makes a sentence too long, keep the long sentence.
4. Do not change code blocks, inline code, commands or tables of measured values.
5. Use one name for one thing in a document. Examples: "ESP32", "Mapper", "sim", "car repo".
6. Domain terms are permitted (ROS 2, DDS, Gazebo, URDF, TF, LiDAR, IMU, WSL). Define a term one time if it is not common.
7. The terse `key: value` notation in `.claude/CLAUDE.md` and `.claude/layout.yaml` stays terse. Apply the rules to the prose fragments only. In this notation a semicolon separates items. Keep it.
8. Use simple tenses. Keep a compound tense only when it carries information.

## Check
- `make lint` runs the STE lint (`ste-lint.py` from the plugin) over the `*.md` files in the dev image. The lint is advisory and not in CI. Text in code blocks gives false findings, so read each finding before you act on it.
- The lint does not check rules 1 to 4. Compare the diff against the original text for those rules.
