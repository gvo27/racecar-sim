---
paths:
  - "repos/**"
  - "docker/**"
  - "Makefile"
  - ".claude/hooks/**"
  - "tests/**"
---

# Sim boundary rules

The sim replaces the car hardware at the device boundary. The car nodes run unchanged. The boundary is `docs/sensor_contract.md` in the car repo (pinned in `repos/racecar.repos`).

## Rules
1. The sim does not publish `/rccar/mcu/drive`. Only the car supervisor publishes it. The virtual ESP32 subscribes to it.
2. Policies and planners publish only `/rccar/cmd/captain`.
3. Gazebo ground truth goes on an internal topic outside `/rccar/`. It never goes on `/tf` odom->base_link (the driver owns that frame).
4. A sim topic has the same type, frame and QoS as its contract row. Do not rename a `/rccar/...` topic.
5. Never put an unconfirmed value in the car `tuning.toml`. A sim-only parameter stays in this repo. Mark plant values that nobody measured as "not verified".
6. The sim never connects to the real Mapper (`192.168.11.1`). `sim_guard.py` denies it.
7. `ROS_DOMAIN_ID` of the sim differs from the car domain. The images bake `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`. Cross-host DDS overrides it on purpose.
8. Data, runs and bags stay out of git (`runs/`, `data/`, `*.mcap`, `*.db3`). Maps are private floor plans.
9. A car boundary change needs a pin bump and a sim update (skill `sim-bump-pin`, skill `sim-parity`).
10. `make pin-check` must pass before you push a pin change.

## Images
- `docker/sim.Dockerfile` stages: `builder` (vcs import, rosdep, colcon), `test` (colcon test), `runtime`. The build covers the car packages `rccar_bringup`, `rccar_drivers`, `rccar_teleop` and `rccar_description` and their dependencies. Sim packages join in later PRs.
- `docker/dev.Dockerfile` builds from the `builder` stage. It adds pyright, ruff and pytest. The repo is mounted at run time, not copied.
- Compose files come in the sim-gz PR. No compose file exists now.
