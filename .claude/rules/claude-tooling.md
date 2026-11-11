---
paths:
  - ".claude/**"
  - "pyrightconfig.json"
  - "tools/lsp/**"
  - "tests/**"
  - ".github/workflows/**"
---

# Claude tooling (plugins, LSP, hooks, tests)

## Inventory
- .claude/settings.json holds marketplaces and enabledPlugins. There are no project MCP servers.
- superpowers, pyright-lsp, claude-md-management: from `claude-plugins-official`.
- ros2-engineering @ v1.7.2 (dbwls99706/ros2-engineering-skills): same pin as the car repo. Bump both repos together. The plugin ships advisory hooks (opt out: `ROS2_SKILL_DISABLE_HOOKS=all`).
- asd-ste100 @ master (danyuchn/asd-ste100-skill): STE skill and `ste-lint.py`. Rule: `.claude/rules/writing.md`.
- ros2-sim @ v1.0.0 (BaraaLazkani/ros2-sim-skill): disabled (`false`). Read its tree (skills and hooks) before you enable it. Enable it after the review. The plugin name `ros2-sim` is not verified.
- Never enable a plugin with hooks before you read the hooks.

## LSP
- pyright-lsp needs `pyright-langserver` on PATH. The shim `tools/lsp/pyright-langserver` runs it in the dev image `rccar-sim-dev:local` through `docker/entrypoint.sh`. ROS is sourced, so pyright sees rclpy and `rccar_msgs`.
- The shim mounts the repo at the same absolute path (read-only), so file URIs match. It finds the repo from its own path, also through a symlink.
- `make lsp` builds the dev image, links the shim into `~/.local/bin` and runs `tools/lsp/smoke.py` (an LSP `initialize` request). `make setup` runs it only when `claude` is on PATH or `LSP=1`.
- Not verified: the Claude Code LSP client with the shim. Run `make lsp` first.
- Config: `pyrightconfig.json` stays at the repo root. Pyright finds its config only there.
- python3 on the host: the hooks and `make lsp` use it (stdlib only).

## Hooks
- `.claude/hooks/sim_guard.py` is a PreToolUse hook for Bash. Output: `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask|deny", "permissionDecisionReason": ...}}`, exit 0. No output = no opinion.
- It denies a command with `192.168.11.1` (the real Mapper). It asks before `make car-up`, `make drivers-start` and `make flash`.
- Tests: `tests/test_sim_guard.py` (`make unit`). `permissions.ask` in settings.json repeats the three targets.

## Workflow (summary in CLAUDE.md)
- Library API => read the upstream docs at the pinned version first. If the docs are for another major version, say so.
- Non-trivial change => superpowers: brainstorming -> writing-plans -> test-driven-development -> requesting-code-review -> verification-before-completion. Plans: `docs/plans/YYYY-MM-DD-<topic>.md`.
- Bug => systematic-debugging first.
- Tests: `make sim-test` (colcon test in the test stage), `make unit` and `make pin-check` (dev image), `make lint` (advisory). `tests/test_rules_paths.py` checks that every rule has `paths:` and that every glob matches a file now.
- Review: use `.claude/agents/sim-reviewer.md` before requesting-code-review.
- Project text => asd-ste100 skill. Mode: `.claude/rules/writing.md`.
- Plugin bumps: change the ref deliberately and note it in the PR.
- Every PR body has a user-run checklist (host setup, `make setup`, `make doctor`, feature checks). Agents do not tick boxes for steps they did not run.
