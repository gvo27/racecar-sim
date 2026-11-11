# repos/

`racecar.repos` pins the car repo ([gvo27/racecar](https://github.com/gvo27/racecar)). The sim image runs `vcs import src < repos/racecar.repos`, then builds the car packages and the sim packages (`rccar_sim_mcu`) with colcon. The car nodes (supervisor, mcu_bridge, drivers) run unchanged in the sim.

The pin is a full 40-character commit SHA. A branch name is not permitted, because it moves.

## Current pin
The pin points at the car branch `sim-contract` (commit `3623d3b`). It holds `docs/sensor_contract.md`. Re-pin after the car PRs for that branch are merged to `main`.

## Bump procedure
1. In the car repo, find the SHA: `git -C <racecar checkout> rev-parse <ref>`.
2. Run `make bump-racecar SHA=<40-hex SHA>`. The target changes only the `version:` line.
3. Run `make sim-image`, `make sim-test` and `make pin-check`.
4. Read the diff of `docs/sensor_contract.md` between the old and the new SHA. Update the sim for each changed row (skill `sim-bump-pin`).
5. Put the old SHA, the new SHA and the result of step 3 in the PR body.
