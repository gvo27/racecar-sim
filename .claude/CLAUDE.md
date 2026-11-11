project: racecar_sim (simulation + training for the autonomous_rc_car_platform)
scope: sim + training; the car repo (gvo27/racecar) is pinned through repos/racecar.repos; no car firmware, no car tuning here
hosts: {train: win11 rtx5070ti wsl2 + docker desktop, staging: linux server (cpu-only checks, no training), isaac: later PR}
contract: car docs/sensor_contract.md (pinned SHA in repos/racecar.repos); sim publishes the same topics, types, frames, qos
phase: scaffold (images, make, ci, docs); next: sim-mcu, sim-mapper, sim-gz, gym, racing
stack: {ros: jazzy (ros:jazzy-ros-base by digest), gz: harmonic via ros-jazzy-ros-gz, dds: fast dds 2.14.7, images: [rccar-sim, rccar-sim-dev, rccar-gym (gym PR)]}
cmd: make help
hooks: .claude/hooks/sim_guard.py  # PreToolUse: denies the real Mapper 192.168.11.1; asks before make car-up|drivers-start|flash
plugins: .claude/settings.json  # superpowers, pyright-lsp, claude-md-management, ros2-engineering, asd-ste100, code-simplifier, caveman; ros2-sim = loose skill, copied in the sim-gz PR
rules: .claude/rules/{writing,claude-tooling,dependencies,sim,wsl}.md  # path-scoped, see paths: frontmatter
agents: .claude/agents/sim-reviewer.md
layout: .claude/layout.yaml
invariants:
  - sim never publishes /rccar/mcu/drive; only the car supervisor does
  - policies and planners publish only /rccar/cmd/captain
  - no unconfirmed value goes into the car tuning.toml; sim-only parameters stay in this repo
  - gz ground truth never goes on /tf odom->base_link or on any /rccar/* topic
  - everything runs in docker; host tools = git make docker
  - no data, runs or bags in git (public repo); runs/ and data/ are gitignored
  - pin everything: image digests, apt versions where known, npm/pip versions, vcs SHA; no :latest
  - sim never connects to the real Mapper (192.168.11.1)
  - boundary change in the car repo => bump the pin (skill sim-bump-pin) + update the sim
workflow:  # same as the car repo; details: .claude/rules/claude-tooling.md
  - library/framework API => check upstream docs/source at the pinned version before writing code
  - non-trivial change => superpowers brainstorming -> writing-plans (docs/plans/) -> test-driven-development -> requesting-code-review
  - bug => superpowers systematic-debugging first
  - tests: no host python; make sim-test (colcon), make unit and make pin-check (dev image); never claim a result without output
  - all project text (docs, .claude/*, PR/commit/review text, user-facing strings) => asd-ste100 STE: strict for .claude, ste-flavored for prose; .claude/rules/writing.md
  - after code edits => check lsp diagnostics (pyright)
  - agents do not run docker on hosts without a docker socket; report "not verified"
