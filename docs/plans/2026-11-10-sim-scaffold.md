# Sim scaffold plan (racecar-sim, approved 2026-11-10)

This file is the plan and the handoff record. The work started in a Claude Code session in the car repo. The next sessions work in this repo. The status section is current. The sections after it are the approved plan, with three updates from 2026-11-11 (ros-gz version, ros2-sim, two plugins).

## Status and handoff (2026-11-11)

| # | Repo / branch | Base | State |
|---|---|---|---|
| 1 | car `sim-contract` | `lidar` | PR gvo27/racecar#9. CI green (colcon 320 tests, 0 failures; `make unit` 125 passed). Head c483e39 |
| 2 | car `dev-lsp` | `main` | not started. Do it in the car repo |
| 3 | sim `main` | — | pushed (README, .gitignore; no LICENSE, because the car repo has none) |
| 4 | sim `scaffold` | `main` | merged: PR gvo27/racecar-sim#1 (main 6746bb3). CI was green (pin check 13 passed, unit 40 passed, colcon 0 tests: expected) |
| 5 | sim `sim-mcu` | `main` | in progress (PR to be opened). Plan: `docs/plans/2026-11-11-sim-mcu.md` |
| 6–9 | sim `sim-mapper`, `sim-gz` (Gazebo), `gym` (f1tenth_gym), `racing` | `main` | not started. Each is a separate PR |

Merge order: racecar #5 → #6 (`lidar`) → #9 (`sim-contract`); racecar-sim #1 at any time. After the car merges, re-pin `repos/racecar.repos` to the car `main` merge SHA with the `sim-bump-pin` skill (`make bump-racecar SHA=<sha>`, then `make pin-check`). The current pin is 3623d3b. It is on a stacked branch, so its history can change before the merge.

Facts the next PRs need (details in the plan below):
- `sim-mcu` is next. The virtual ESP32 serves `/rccar/mcu/{drive,command,telemetry,event}`. It ports the `main.cpp` drive math (`headingToSteerDeg`, `steerDegToUs`, `throttleToUs`), the slew, the double-tap reverse, the `cmd_timeout_ms` failsafe and the `handleLine` grammar. Golden vectors and drift tests read the pinned `main.cpp` and `FIRMWARE_KEYS`.
- `car.launch.py sim:=true` keeps `mcu_bridge`. The bridge pushes `tuning.toml` to the virtual ESP32. The firmware defaults are different (`maxSteerDeg` 25 vs 30, `headingGain` 1.0 vs 2.0, `speedLimit` 0.30 vs 0.7), so a test must show that `GET` returns the tuning values after READY.
- One clock (sim time), one `robot_state_publisher` (car `drivers.launch.py urdf_file:=`). Gazebo ground truth never goes on `/tf` odom→base_link or on `/rccar/*`.
- The supervisor is the only publisher of `/rccar/mcu/drive`. Policies publish only on `/rccar/cmd/captain`.
- Virtual Mapper device facts: result code 1, camelCase health flags, ≈920 raw points per scan binned to 1080 by the driver, IMU orientation only (bitmap 131), pose 10 Hz with ≈100 ms delay, walls of 30 cm or more.
- The contract is `docs/sensor_contract.md` in the car repo, with the drift test `deploy/tests/test_contract.py`. Boundary changes follow the car `sim-parity` skill.

Open items:
- Staging host (Debian, 3550H, 8 GB): the user `callisto` is not in the `docker` group, so local image builds and tests cannot run. Fix: `sudo usermod -aG docker callisto`, then log in again. Disk: 12 GB, about 6 GB free. The sim image is large, so prune often (`docker system df`).
- Node is not installed on the staging host, so the caveman hooks do nothing there. Use `/caveman` to start the mode by hand.
- CI: on 2026-11-11 the GitHub runner could not resolve `archive.ubuntu.com` in the apt step of both repos. A re-run of the failed jobs passed. If `Could not resolve` shows in the apt step again, re-run before you change code.
- The LSP shim is not verified with the Claude Code LSP client. Run `make lsp` on a host with docker access first.
- Isaac Sim / Isaac Lab: postponed until far later: after `racing` and after the camera.


## Context
The sensors arrive late, but sim training starts now. This plan follows the sim-training plan (2026-10-29/31).
- Compute:
  - **Win11 workstation** (RTX 5070 Ti, 32 GB, WSL2 + Docker Desktop): runs all sim and training.
  - **Linux server** (this Debian box, 3550H, 8 GB): a temporary staging host only. It builds the foundation and runs the first CPU-only checks (image builds, tests, headless smoke).
  - The Jetson Orin Nano is removed.
- **Isaac Sim / Isaac Lab are out of scope.** They come in a later PR, so the scaffold has no `isaac/` folder, no `isaac` profile and no Isaac skill.
- Parity goes through the existing ROS 2 contract.
- Everything runs in Docker. The host needs only git, make and Docker (car-repo rule).

Car-repo facts (branch `lidar`):
- `rccar_description` exists, with frames `base_link`, `lidar_link` and `lidar_imu_link`. The mount offsets are UNMEASURED.
- `mapper_driver` publishes:
  - `/rccar/lidar/scan`, `/rccar/lidar/imu`
  - `/rccar/mapper/pose`, `/rccar/mapper/map`
  - TF map→odom→base_link
- The ESP32 publishes `/rccar/rangefinder/range`.
- The writing convention is STE.
- `hw_guard.py` is a PreToolUse hook.

Targets:
- Remote `https://github.com/gvo27/racecar-sim.git`: it exists and is empty (ls-remote rc 0, no refs).
- Local `~/projects/racecar-sim/`: it does not exist yet.

## Verified state (2026-11-10)
**Plugins: all 6 car-repo plugins are installed, project scope, enabled (`claude plugin list`).**

| Plugin | Version / commit | Hooks |
|---|---|---|
| superpowers | 7.0.0 / bb92a77 | SessionStart (`run-hook.cmd session-start`) |
| pyright-lsp | 1.0.0 / 43fd1f9 | none |
| clangd-lsp | 1.0.0 / 43fd1f9 | none |
| embedded-skills | 1.0.0 / 022ce31 | none |
| ros2-engineering | 1.7.2 / f0de84d | PreToolUse (Edit/Write/Bash) + Stop: `claude_hook.py`. It runs bounded validators and is advisory (never `decision=block`, as `dependencies.md` says). Opt out with `ROS2_SKILL_DISABLE_HOOKS=all`. |
| asd-ste100 | a4905d9 | none |

- **Not loaded in this session yet.** My skill list shows only the built-ins. Run `/reload-plugins` or restart, then I re-check the list.
- **Gap:** `pyright-langserver` and `clangd` are not on PATH, so the LSP plugins do nothing. The plugins start the bare command names from PATH (`pyright-langserver --stdio`, `clangd --background-index`). Fix: the dockerized `make lsp`, which `make setup` runs (below).
- **Rules scoping (checked):**
  - All 16 `.claude/rules/*.md` have a `paths:` frontmatter, and every glob matches at least one file.
  - Gap: `ros2-reviewer.md` lists only 9 rules. Change it to "every rule whose `paths:` match the diff", with no hard-coded list, so new rules (drivers, hw-testing, rangefinder, writing, …) apply.
  - Gap: `pyrightconfig.json` `include` lacks `rccar_drivers` and `rccar_description`. Add them.
  - The sim repo gets the same check as a test: every rule has `paths:`, and every glob matches.
- **Car-repo bug:**
  - `.claude/settings.json` pins asd-ste100 `"ref": "main"`, but the repo has only `master`.
  - The marketplace was added without a ref, so it currently tracks `master`.
  - Fix: `ref` = `a4905d922500dd7530ca8a0eb9e4940494255709` (the repo has no tags), plus a `dependencies.md` entry.

**Versions (checked against upstream 2026-11-10):**

| Item | Pin | Check |
|---|---|---|
| ROS base | `ros:jazzy-ros-base@sha256:8eed0a46…b617` | same as the car repo; it is still the latest digest |
| Gazebo | Harmonic through `ros-jazzy-ros-gz` 1.0.24 / `gz_sim_vendor` 0.0.13 from packages.ros.org (rosdistro lists 1.0.25; the apt sync is behind) | first CI build, 2026-11-11 |
| Fast DDS | 2.14.7 (Jazzy fastrtps) | discovery server: the `fastdds discovery` CLI. Not 3.x |
| rosbag2 / slam_toolbox / robot_localization | 0.26.11 / 2.8.5 / 3.8.4 | rosdistro jazzy |
| ros_gz upstream 4.x | do not use | Kilted/Rolling only |
| PyTorch (gym image) | `pytorch/pytorch:2.15.0-cuda13.2-cudnn9-runtime@sha256:924707fa…ffcde5` | Blackwell sm_120 needs cu128+; the image ships CUDA 13.2, so the Windows NVIDIA driver must support CUDA 13.2 (sanity check in setup.md) |
| f1tenth_gym | branch `v1.0.0` @ `5a301bd` (gymnasium API) | `main` is the old gym 0.19 API, so do not use it. The v1.0.0 branch is unmaintained since 2024-09 and needs `gymnasium` ^0.29, so pin `gymnasium==0.29.1` (not 1.4.0). Risk noted: we may vendor or fork it later |
| stable-baselines3 | 2.x version that supports gymnasium 0.29 | resolved and pinned during the scaffold (lock file) |
| Isaac (later PR, note only) | Isaac Sim v6.2.0 / Isaac Lab v3.0.0 are current | not pinned now |
| pyright (dev image) | npm `pyright` pinned version (resolved at build, in the lock) | runs in the ROS-based dev image, so it sees rclpy and rccar_msgs (no more missing-import warnings) |
| clangd (car dev image) | Ubuntu 24.04 apt `clangd` pinned version | uses `compile_commands.json` from `make compiledb` + the `.pio-core` path |
| ros2-sim skill | v1.0.0 | single tag |
| Host tools (this Debian box) | Docker 29.9.3, Compose v5.7.0, buildx 0.38.1 | — |

## Cross-check with PR gvo27/racecar#6 (lidar, DRAFT, base `rangefinder` → #5 OPEN → main; CI green at d14a250)
The plan changes as follows:

| PR #6 fact | Plan impact |
|---|---|
| Device success code is **1**, health flags are **camelCase** (fix 93cf2c0, inside the pin d14a250) | The virtual Mapper reuses the pinned `fake_mapper.py`, so it gets both. A round-trip test against the real `MapperClient` asserts code 1 and camelCase. A sim test fails if the pin goes back before 93cf2c0. |
| Driver output: scan 10 Hz, **`n_bins` 1080**, `range_min` 0.15, `range_max` 40, finite fraction ≈0.45; device sends ≈920 pts per scan | The virtual Mapper sends ≈920 raw points per scan at 10 Hz. The driver bins them to 1080, so the sim tests check 1080 bins. The gym obs = 1080 beams over 360°, range 40 m, 10 Hz. "~920 pts" is the raw device count only. |
| **IMU = orientation only** on firmware 2.6.0_dev (bitmap 131; acc/gyro 0, covariance[0] = -1), 50 Hz; IMU units unknown | Sim IMU default `imu_mode: orientation_only` (bitmap 131, zeros). `full` mode is only for the planned dedicated IMU. The policies must not depend on yaw rate/accel from `/rccar/lidar/imu`. |
| Pose 10 Hz, ≈100 ms late, jumps on relocalization; stationary drift 0–0.22 m / 4.6° | The virtual Mapper pose = ground truth + noise + 100 ms delay + random relocalization jumps (parameters; ranges from these bench numbers, marked "not verified"). The Mapper's onboard SLAM cannot be simulated. |
| Bench-TBD: `scan_angle_sign`, `map_transpose`, mount offsets; mapping not accepted yet | The sim uses the driver defaults (`scan_angle_sign` 1, `map_transpose` False, `map_free_is_high` False) and randomizes the mount offsets. A sim test sets `scan_angle_sign` -1 and expects the agreement to fall, so the bench check is rehearsed. |
| **2D lidar needs a walled track (≥30 cm barriers)**; scan plane ≈15–25 cm; ±3° tilt shifts the plane (3° → 16 cm at 3 m) | `rccar_sim_gz/worlds/`: walled F1TENTH-style tracks only (barrier height a parameter, default 0.30 m). The lidar height is randomized 0.15–0.25 m. Body pitch under acceleration is modelled. gym maps are walled maps. Tape tracks = camera-only, deferred. |
| Roadmap: encoder (ESP32 GPIO15/16 PCNT) → IMU 100 Hz+ → EKF (`robot_localization`) → **captain: follow-the-gap / wall following first**, developed in F1TENTH gym → saved map + pure pursuit → camera | The first training/benchmark target is **follow-the-gap and wall following** on a walled track, then pure pursuit on a saved map. `autonomous-racing-algorithms` moves to **P0**. Encoder/IMU rows stay "planned" in the contract; the virtual ESP32 gets an encoder stub that is off by default. |
| Captain = car-side node on `/rccar/cmd/captain` (phase 5, car repo) | The algorithms are pure Python libraries in the sim repo (`rccar_racing/`, no rclpy), with a thin sim node. A later car PR moves or vendors them into `rccar_captain`, so the code that runs on the car is the code that was benchmarked. |
| foxglove_bridge **3.6.0** (SDK subprotocol `foxglove.sdk.v1`), read-only capabilities | The sim reuses the car's `viz.launch.py` (read-only), not a new bridge. setup.md notes the subprotocol troubleshooting. |
| Isaac: camera-only value, defer until the camera | Matches "Isaac out of scope". |
| #6 is a draft stacked on #5; history may change before merge | Pin to d14a250 now. Re-pin to the `main` merge SHA once #5/#6 merge (sim-bump-pin skill). `sim-contract` is a PR stacked on `lidar` (base `lidar`). |
| `logs/` gitignored (maps/bags are floor plans; the repo is public) | The sim `runs/`, `data/` and bag outputs are gitignored. Datasets are never committed. |

## Design decisions (unchanged core)
1. **The sim replaces the hardware at the device boundary.**
   - **Virtual ESP32** (`rccar_sim_mcu`): a pure `model.py` that ports the `main.cpp` drive math, slew, double-tap reverse, failsafe and grammar. Golden-vector and drift tests check it against the pinned `main.cpp` and `FIRMWARE_KEYS`.
   - **Virtual Mapper** (`rccar_sim_mapper`): a TCP JSON server on port 1445 that feeds the real `mapper_driver` (unchanged). It reuses the pinned `fake_mapper.py` encoder and has jitter/drop parameters. `direct:=true` is the fast RL mode.
2. **The car repo comes in through the pinned `.repos`.** It runs the real `car.launch.py sim:=true` and `drivers.launch.py`.
3. **The sim URDF includes the car URDF.** Unmeasured values are randomized sim parameters. They never go into `tuning.toml`.
4. **The sensor contract lives in the car repo**, with a drift test. Sim CI checks the bridged topics against the pinned SHA.
5. **gym uses the same contract.** All actuation goes through the virtual ESP32 model, so a later Isaac PR plugs into the same boundary.

## Docker + Makefile (everything containerized)
Images (sim repo, multi-stage, pinned by digest, no `:latest`):
- `rccar-sim:<sha>`: `docker/sim.Dockerfile` (ROS base digest + ros-gz + vcs import of racecar + colcon). Stages: `builder`, `test`, `runtime`, `gui` (adds the WSLg/Mesa libs only).
- `rccar-gym:<sha>`: `docker/gym.Dockerfile` (PyTorch digest + pinned pip lock via `uv`, f1tenth_gym@5a301bd, `rccar_sim_mcu.model`). Training needs no ROS.
- `rccar-dev:<sha>`: `docker/dev.Dockerfile`, FROM the repo's ROS image. It adds pyright (pinned), ruff and the STE lint, and in the car repo also clangd.

**Dockerized LSP (`make lsp`, part of `make setup`; both repos; clangd in the car repo only):**
- `tools/lsp/pyright-langserver` and `tools/lsp/clangd` are shell shims. Each does:

  `exec docker run -i --rm --user $(id -u):$(id -g) -v "$REPO":"$REPO":ro -w "$PWD" rccar-dev:local <server> "$@"`

  - The repo is mounted at the **same absolute path**, so the file URIs match.
  - Car clangd also mounts `.pio-core` at its host path, so the xtensa headers resolve.
- `make lsp`:
  - builds `rccar-dev`
  - symlinks the shims into `~/.local/bin` (on PATH; nothing else goes on the host)
  - in the car repo, runs `make compiledb`
  - runs a smoke test that sends an LSP `initialize` request through each shim and expects a reply
- `make check-dev` stays as the PATH report. It now also says whether a shim or a native binary is in use.
- Risk: container start time (~1 s) on every LSP start. It is acceptable, because the LSP is long-lived for the session.
- Shared caches are named volumes (pip/uv, colcon build, gz assets). Bind mounts: the repo (ro), `runs/` and `data/` (rw).

Makefile (sim repo). `make help` groups the targets:
- **Quick setup:**
  - `make setup`: host prereq check (git, make, docker, compose, buildx; on WSL also `nvidia-smi`, WSLg), then it builds the sim + dev images, then it runs `make lsp` **only when `claude` is on PATH or `LSP=1`**.
  - The gym image (several GB) builds on `make gym-image` or the first `make train`, not in `setup`.
  - Car repo: `make setup` runs `make lsp` the same way. It is skipped on the Pi by default, because there it would waste disk and `hw_guard.py` denies image builds while `drivers` runs.
  - `make doctor`: all sanity checks (below), with pass/fail lines.
- **Sim:**
  - `make sim-up PROFILE=gui|headless`, `make sim-down`, `make sim-logs`, `make sim-ps`
  - `make teleop`, `make viz` (foxglove_bridge), `make record SECS=`
- **Train:**
  - `make gym-shell`, `make gym-check` (env_checker)
  - `make train CFG=configs/<x>.yaml`, `make tensorboard`
  - `make eval RUN=`, `make export RUN=` (ONNX)
- **Test:** `make sim-test` (colcon test), `make unit` (pure pytest in the gym image), `make lint` (STE lint + ruff in rccar-dev)
- **Pins:** `make pin-check` (car SHA contains every bridged topic), `make bump-racecar SHA=`
Car repo: `make lsp` (in `make setup`) is added. The rest of the car changes stay small (below).

## Car repo changes (branch `sim-contract` off `lidar`)
- **README.md "Quick reference"** at the top. Keep the existing sections; it adds a compact block:
  1. One-time setup: `make setup`, `make config`, `make install-host`
  2. Daily car commands: `car-up`/`car-down`/`car-ps`, `teleop`, `viz`, `lidar-snapshot`, `ros-test`/`unit`
  3. Sim pointer: the racecar-sim repo + `make sim-up` / `make train`
  4. Claude Code: the 6 plugins and how to install them (`claude plugin install … --scope project`, then `/reload-plugins`)
- `docs/sensor_contract.md` + `rccar_drivers/test/test_contract.py`.
- `.claude/skills/sim-parity/SKILL.md`, a "Sim impact" section in the PR template, a sim line in `ros2-reviewer`.
- The asd-ste100 ref fix; `claude-md-management@claude-plugins-official` (no hooks) added to enabledPlugins.
- `make lsp` (dev image + shims) goes in the separate car PR `dev-lsp` (see the PR split), not in `sim-contract`. `sim-contract` also gets:
  - `pyrightconfig.json` adds `rccar_drivers` and `rccar_description`
  - `ros2-reviewer.md` applies every rule whose `paths:` match the diff
  - a `deploy/tests/test_rules_paths.py` (runs via `make unit`) checks that every rule has `paths:` and that every glob matches
- Pointers in `docker_ros_plan.md` phase 6, `layout.yaml` and `CLAUDE.md`.
- The sandbox write-protects `.claude/skills`, `.claude/hooks` and `.claude/settings.json`. You approve those writes.

## Sim repo layout
```
racecar-sim/
├── README.md                 quick reference (setup, sim, train, test), STE
├── Makefile                  targets above
├── repos/racecar.repos       racecar @ <sim-contract SHA>
├── docker/{sim,gym,dev}.Dockerfile, docker/entrypoint.sh
├── compose.yaml              gz, mcu-sim, mapper-sim, core (sim:=true), drivers (real), foxglove, gym; profiles gui/headless/gym
├── dds/                      Fast DDS 2.14 discovery-server profile + env
├── rccar_sim_mcu/ rccar_sim_mapper/ rccar_sim_gz/ rccar_sim_bringup/
├── rccar_gym/                gymnasium env (walled maps, 1080-beam obs, orientation-only IMU) + configs/ + train.py (SB3 PPO baseline); pure, no ROS
├── rccar_racing/             pure algorithms: follow_the_gap, wall_follow (first), pure_pursuit; benchmark harness; thin sim node → /rccar/cmd/captain
├── datasets/README.md        public datasets index; no data in git
├── docs/setup.md             WSL host setup + training + sanity checks (below)
├── docs/sensor_contract.md → link to the pinned car doc
├── docs/plans/2026-11-10-sim-scaffold.md
├── .github/workflows/sim.yml build + sim-test + unit + lint + pin-check (no GPU)
└── .claude/                  CLAUDE.md, layout.yaml, rules/, settings.json, skills/, hooks/sim_guard.py, agents/sim-reviewer.md
```

## `docs/setup.md` (sim repo, STE): training on the WSL host
1. **Windows prerequisites:**
   - Win11, WSL2 (`wsl --version` ≥ 2.x), Ubuntu 24.04 distro
   - NVIDIA Windows driver that supports CUDA 13.2 (do not install a Linux driver inside WSL)
   - Docker Desktop with the WSL2 backend + WSL integration for the distro
   - `.wslconfig`: memory (e.g. 24 GB), `networkingMode=mirrored` (only for cross-host DDS)
2. **Clone into the WSL filesystem** (`~/projects`), not `/mnt/c`, for file speed. `git`, `make` and Docker are the only host tools.
3. `make setup`, then `make doctor`.
4. **Train:**
   - `make gym-check`, then `make train CFG=configs/ppo_flat_track.yaml`
   - `make tensorboard` (http://localhost:6006)
   - runs go to `runs/<UTC>/` (gitignored)
   - `make eval RUN=…`, `make export RUN=…`
5. **Contract sim:** `make sim-up PROFILE=gui` (WSLg window) → `make teleop` → `make record`.
   - If ogre2 fails: `RENDER_ENGINE=ogre make sim-up`.
6. **Cross-host (optional):** start the discovery server, then set `ROS_DOMAIN_ID` (the sim uses a domain ≠ the car's) and the firewall rule for UDP 7400–7600.
7. **Troubleshooting table:** GPU missing, WSLg black window, DDS discovery, disk usage (`docker system df`).

**Sanity checks** (each also runs in `make doctor`, with the expected output in the doc):
- `wsl.exe --version`, `uname -r` (contains `microsoft-standard-WSL2`)
- `docker version`, `docker compose version`, `docker buildx version`
- `docker run --rm --gpus all <pytorch digest> nvidia-smi` → shows the RTX 5070 Ti and a CUDA version ≥ 13.2
- `docker run --rm --gpus all <gym image> python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_capability())"` → `2.15.0 True (12, 0)`
- `docker run --rm <gym image> python -c "import gymnasium, f1tenth_gym; print(gymnasium.__version__)"` → `0.29.1`
- `docker run --rm <sim image> gz sim --versions` → 8.x (Harmonic); `ros2 pkg list | grep ros_gz_bridge`
- `ls /mnt/wslg /dev/dxg` (GUI path); `glxinfo -B` in the gui stage (renderer: D3D12 or llvmpipe is reported)
- `make sim-up PROFILE=headless && ros2 topic hz /rccar/lidar/scan` → ≈10 Hz; `ros2 topic list` has the contract topics
- `make pin-check` → OK

## Plugins
| Plugin | Car | Sim | Notes |
|---|---|---|---|
| superpowers, pyright-lsp | yes | ADOPT | LSP through `rccar-dev`, or a host binary |
| clangd-lsp, embedded-skills | yes | SKIP | no C++ in sim |
| ros2-engineering @ v1.7.2 | yes | ADOPT, same pin | already ships hooks (read: bounded advisory validators). Bump to v1.8.0 in both repos together |
| asd-ste100 @ a4905d9 | yes (fix ref) | ADOPT | STE for all project text, skills included |
| claude-md-management (official, no hooks) | ADD | ADOPT | keeps CLAUDE.md / layout current |
| ros2-sim (BaraaLazkani v1.0.0, MIT, no hooks) | — | COPY in sim-gz | not a plugin: v1.0.0 has only `SKILL.md`, no `.claude-plugin/`. Copy it at the tag into `.claude/skills/ros2-sim/` |
| code-simplifier (official, agent, no hooks) | ADDED | ADDED | user request 2026-11-11; project rules override its JS/React defaults |
| caveman @ v4.1.0 (hooks read: node only, local state, no network) | ADDED | ADDED | user request 2026-11-11; chat only, persisted text stays STE |
| code-review, github (official) | — | TRIAL | overlaps built-in `/code-review` and gh; github needs a fine-grained PAT |
| Isaac Lab skills, nvidia-skills | — | later Isaac PR | not in this scaffold |
| ros-mcp-server, bagel | — | TRIAL | MCP use on the sim rosbridge at localhost only |
| robotics-agent-skills, claude-code-robotics, claude-ros2-skills, robolearn, mcp-rosbags, huggingface-skills | — | SKIP | built-in duplicate / ros2-engineering overlap / heavy hooks / no license |

Pin every marketplace to a tag or SHA. Test a SHA `ref` with `claude plugin marketplace add`; if it fails, fall back to a tag.

## Skills (project skills, strict STE; `ste-lint` gives no findings outside code blocks)
Knowledge skills, scoped to the project contract:

| Pri | Skill | Content |
|---|---|---|
| P0 | wsl-docker-ros2 | WSL fs limits; Docker Desktop WSL integration; `gpus: all`; WSLg mounts; DDS discovery server; `ROS_DOMAIN_ID` isolation; Fast DDS 2.14 XML; GUI forwarding; healthchecks; pinned digests |
| P0 | gazebo-robotics | SDF/URDF/xacro (wrap the car URDF); Harmonic systems; `ros_gz_bridge` yaml + QoS; gpu_lidar set like the M2M1; IMU; render-engine fallback; worlds/tracks |
| P0 | robotics-simulation-validation | reset + seeds; `/clock` and `use_sim_time`; scan/IMU/odom/TF checks; physics sanity; mcap regression vs baseline; cross-sim comparison |
| P0 | autonomous-racing-algorithms | Follow-the-Gap and wall following first (#6 roadmap); then Pure Pursuit, Stanley, MPC, trajectory optimization, speed profile, benchmark protocol. Pure libraries; output only on `/rccar/cmd/captain` |
| P1 | f1tenth-racing | DriveCmd → virtual ESP32 mapping; kinematic and dynamic bicycle models; limits from `tuning.toml` and sysid; maps/waypoints/racelines; lap metrics; multi-agent |

Procedure skills:

| Pri | Skill | Repo | Codifies |
|---|---|---|---|
| P0 | sim-parity | car (+ sim stub) | boundary change → contract, vectors, bridge, "Sim impact", pin bump |
| P0 | sim-safety-check | sim | policies publish only `/rccar/cmd/captain`; supervisor in the loop; `Reset(incident)` |
| P0 | new-sim-sensor | sim | contract row → URDF link → gz xacro → bridge QoS → datasheet noise → test |
| P1 | sim-bump-pin, sysid-fit, policy-export-check | sim | pin diff + tests; plant params only in `plant/params.yaml`; ONNX parity |
| P2 | domain-randomization-review, dataset-ingest | sim | bounded DR ranges; datasets mapped to the contract |

- The scaffold PR writes all P0 skills plus sim-bump-pin.
- f1tenth-racing and autonomous-racing-algorithms come with `rccar_gym`.
- P2 skills are stubs.
- Each skill has a trigger-test prompt recorded in the PR.
- Enforcement:
  - pin-check, golden-vector and drift tests in CI
  - CI grep + launch test: only the supervisor publishes `/rccar/mcu/drive`
  - `sim_guard.py` denies `mapper_host` 192.168.11.1 (the real Mapper) and `make drivers-start` / `car-up` in a car checkout
  - `sim-reviewer` agent

## Review fixes (Fable 5.1 review, spot-checked)
**Blockers, now part of the design:**
1. **Tuning must reach the virtual ESP32.** `sim:=true` skips `mcu_bridge`, and the firmware defaults differ from `tuning.toml`: `maxSteerDeg` 25 vs 30, `headingGain` 1.0 vs 2.0, `speedLimit` 0.30 vs 0.7 (checked: `main.cpp:62-70`).
   - Fix (car `sim-contract`): `sim:=true` **keeps `mcu_bridge`** and skips only the micro-ROS agent. The bridge pushes `FIRMWARE_KEYS` to the virtual ESP32 through `/rccar/mcu/command`, exactly as on the car. The core healthcheck (2 heartbeat files) stays valid.
   - gym: the env constructor applies `firmware_commands(load_tuning(...))` to `model.py`.
   - Launch test: READY → push → `GET` returns the tuning values.
2. **One clock.**
   - `model.py` takes an injected clock, and the node steps it from a ROS timer (sim time).
   - gz starts with `-r`. `core` and `drivers` start after the `/clock` bridge is up.
   - `direct:=true` documents who publishes `/clock`.
   - Launch test with the real supervisor: arm → stream → stop → FAILSAFE event → supervisor latched (extends `rccar_bringup/test/test_supervisor_launch.py`).
3. **One `robot_state_publisher`.** Car `sim-contract` adds `urdf_file:=` to `drivers.launch.py` (default unchanged), and the sim passes its wrapper xacro. The gz ground-truth pose goes on an internal topic outside `/rccar/`. It never goes on `/tf` odom→base_link, which the driver owns. A test asserts this.
4. **`make setup` stays quick.** No gym image in setup; LSP gated (see the Makefile section).

**Should-fix, adopted:**
- **LSP shims:**
  - run through `docker/entrypoint.sh` (ROS sourced), so pyright sees rclpy/rccar_msgs
  - clangd gets an rw `.cache/` mount, and `.clangd` gets `--query-driver=<repo>/.pio-core/packages/toolchain-xtensa-esp32s3/bin/xtensa-esp32s3-elf-*`
  - the LSP `initialize` smoke test runs in `make doctor`
  - update `dependencies.md` (shims replace host LSP installs) and `hw-testing.md` (new host-side files)
  - not verified: Claude Code's LSP client with a shim; that is the first check
- **Docker Desktop:**
  - `network_mode: host` needs Docker Desktop's host-networking setting. setup.md has a step for it, and `make doctor` has a check.
  - cross-host DDS overrides `ROS_AUTOMATIC_DISCOVERY_RANGE` (the image bakes `LOCALHOST`, checked at `ros.Dockerfile:108`)
- **Gates before gym code**, on the staging host:
  - the `uv lock` resolves (f1tenth_gym v1.0.0 deps vs the image's Python)
  - the scan simulator accepts FOV 2π with 1080 beams
  - on failure: vendor or fork f1tenth_gym (decision noted in the PR)
- **One binning path:** gz lidar = ≈920 raw beams over 360°. `direct:=true` calls the same `convert.scan_to_ranges` as the driver.
- **ros-gz apt:** the first staging build confirms whether `ros-jazzy-ros-gz` needs the OSRF Gazebo apt repo in `sim.Dockerfile`.
- **Settings:** the `.claude/settings.json` working-tree diff (key reorder from the plugin install) is committed with the asd-ste100 ref fix.
- **`ros2-sim` plugin:** read its tree before enabling (claude-tooling rule).
- **Docs:** TT-02 plant values in `plant/params.yaml` are marked "not verified".

## PR split (Sonnet workers per task, reviewed per task)
1. **car `sim-contract`** (base `lidar`, small, rebase-friendly; re-pin after #5/#6 merge):
   - contract doc + `test_contract.py`
   - `drivers.launch.py` `urdf_file:=`
   - `sim:=true` keeps `mcu_bridge`
   - README quick reference
   - asd-ste100 ref fix + settings diff
   - `pyrightconfig.json` includes
   - ros2-reviewer by `paths:`
   - `test_rules_paths.py`
   - "Sim impact" PR-template section
   - `sim-parity` skill, pointers
2. **car `dev-lsp`** (base `main`, independent): `rccar-dev` image, shims, `make lsp`/`check-dev`/`doctor`, `.clangd` query-driver, rule updates.
3. **sim `main`:** README, LICENSE, .gitignore.
4. **sim `scaffold`:**
   - `.claude/`
   - `sim.Dockerfile` + `dev.Dockerfile`
   - Makefile `setup/doctor/help/lint/pin-check/lsp`
   - `repos/racecar.repos`
   - CI skeleton
   - **`docs/setup.md`** (WSL prerequisites, training steps, sanity checks, versions)
   - `wsl-docker-ros2` skill
5. **sim `sim-mcu`:** model + golden vectors + node + READY/tuning-push/FAILSAFE launch tests with the real supervisor + mcu_bridge (no gz); `sim-safety-check`.
6. **sim `sim-mapper`:** TCP server + real `mapper_driver` round trip + `direct` mode; `new-sim-sensor`.
7. **sim `sim-gz`:**
   - walled world, URDF wrap, bridge, compose profiles
   - `make sim-up/teleop/viz/record`
   - `gazebo-robotics` + `robotics-simulation-validation` skills
8. **sim `gym`:** `gym.Dockerfile`, lock, `rccar_gym`, `train.py`, the setup.md training section completed, `f1tenth-racing`.
9. **sim `racing`:** `rccar_racing` (follow-the-gap, wall following) + benchmark + thin captain node; `autonomous-racing-algorithms`, `sim-bump-pin`.

Each PR is green on its own (`make sim-test`/`unit`/`lint`, CI) before the next starts. PRs 1–4 are this session's target. PRs 5–9 follow in order.

## Verification
- Car: `make ros-test`, `make unit` green; the contract test passes; `claude plugin list` shows asd-ste100 from the pinned ref.
- Sim, on the Linux staging host (this Debian box, no GPU; first checks only, no training):
  - `make setup`
  - `make sim-test`, `make unit`, `make lint`, `make pin-check`
  - `make sim-up PROFILE=headless`: contract topics present, one rsp, `GET` shows the tuning values, `make teleop` drives, failsafe after `cmd_timeout_ms` (sim time), supervisor latches
  - `make doctor`: LSP `initialize` through each shim answers
  - `make gym-check` (CPU)
- CI `sim.yml` green.
- User-run on the WSL host: `make doctor` (GPU lines), `make sim-up PROFILE=gui`, `make train` smoke run (≈5 min) shows learning in TensorBoard.
- After `/reload-plugins`, the plugin skills appear in my skill list.
