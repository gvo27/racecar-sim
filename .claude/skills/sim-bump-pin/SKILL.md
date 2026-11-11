---
name: sim-bump-pin
description: Use when you change the car repo pin in repos/racecar.repos in racecar-sim - make bump-racecar, a new car SHA, a car PR that merged, a sensor_contract.md change. Gives the steps and the checks.
---

# Bump the car pin

## Steps
1. Get the new SHA in the car repo: `git -C <racecar checkout> rev-parse <ref>`. The SHA has 40 hex characters.
2. Show the contract diff: `git -C <racecar checkout> diff <old SHA> <new SHA> -- docs/sensor_contract.md`. Also show the diff of `rccar_msgs`, `rccar_drivers`, `rccar_supervisor` and `firmware/esp32/src/main.cpp`.
3. Run `make bump-racecar SHA=<new SHA>`.
4. Run `make sim-image`, then `make sim-test`, `make pin-check`, `make unit`.
5. For each changed contract row, change the sim (skill `sim-parity`).
6. Write the PR body: old SHA, new SHA, contract diff summary, command results. Use the PR template.

## Rules
- Use a SHA or a tag. Do not use a branch name.
- If a command fails, do not change the test to make it pass. Find the cause (superpowers systematic-debugging).
- Report a step that you did not run as "not verified".
