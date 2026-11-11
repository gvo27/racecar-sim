# racecar-sim

Simulation and training for the [racecar](https://github.com/gvo27/racecar) 1:10 autonomous car (Tamiya TT-02, ROS 2 Jazzy).

The sim replaces the car hardware at the device boundary:
- A **virtual ESP32** serves the `/rccar/mcu/*` topics and the `/rccar/mcu/command` service with the firmware drive rules.
- A **virtual Mapper** speaks the Slamtec Mapper TCP protocol to the real `mapper_driver`.

The car nodes (supervisor, mcu_bridge, drivers) run without changes. The boundary is in the car repo: [`docs/sensor_contract.md`](https://github.com/gvo27/racecar/blob/sim-contract/docs/sensor_contract.md).

The car repo is pinned in `repos/racecar.repos` ([`repos/README.md`](repos/README.md)).

## Virtual ESP32
Package `rccar_sim_mcu`, node `rccar_mcu`, launch file `ros2 launch rccar_sim_mcu sim_mcu.launch.py`. Run the tests with `make sim-test`:
- Subscribes `/rccar/mcu/drive` (DriveCmd, best_effort). Only the car supervisor publishes it.
- Serves `/rccar/mcu/command` (McuCommand) with the firmware `handleLine` grammar.
- Publishes `/rccar/mcu/event` (reliable, depth 10), `/rccar/mcu/telemetry` (best_effort, depth 5, 10 Hz) and `/rccar/rangefinder/range` (best_effort, depth 5, `+inf` stub, frame `rangefinder_link`).
- Sim-only fault services `/rccar_mcu/fault_drop_drive` and `/rccar_mcu/fault_reboot`. They are outside `/rccar/`.

Safety checks for tests and policies: skill `sim-safety-check`.

## Quick reference
Host tools: git, make and Docker. Setup steps for the WSL host: [`docs/setup.md`](docs/setup.md). Run `make help` for the full list.

| Command | What it does |
|---|---|
| `make setup` | check host tools, build the sim and dev images |
| `make doctor` | sanity checks (PASS / FAIL / SKIP) |
| `make sim-test` | build the test image and run colcon test (no GPU) |
| `make unit` | run `tests/` in the dev image |
| `make pin-check` | test the car pin in `repos/racecar.repos` |
| `make bump-racecar SHA=<sha>` | change the car pin |
| `make lint` | ruff and STE lint (advisory) |
| `make lsp` | install the pyright LSP shim for Claude Code |

Coming in later PRs:

| Command | PR |
|---|---|
| `make sim-up PROFILE=gui\|headless`, `sim-down`, `teleop`, `viz`, `record` | sim-gz |
| `make gym-check`, `train`, `tensorboard`, `eval`, `export` | gym |

## Status
The `scaffold` PR added the Docker images, the Makefile, `docs/setup.md` and CI. The `sim-mcu` PR adds the package `rccar_sim_mcu`. Gazebo (`sim-gz`) and f1tenth_gym (`gym`) stay separate PRs. Isaac comes far later, after `racing` and after the camera. The work comes in this order:
1. `scaffold`: Docker images, Makefile, `docs/setup.md`, CI.
2. `sim-mcu`: the virtual ESP32 (this PR).
3. `sim-mapper`: the virtual Mapper.
4. `sim-gz`: Gazebo Harmonic world, walled track.
5. `gym`: gymnasium environment and training.
6. `racing`: follow-the-gap and wall following.

## Hosts
- **Training and sim:** Windows 11 workstation (RTX 5070 Ti) with WSL2 and Docker Desktop.
- **Staging:** a small Linux server. It builds the images and runs the first CPU-only checks only.
- Host tools: git, make and Docker. Everything else runs in containers.
