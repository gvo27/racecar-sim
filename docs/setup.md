# Setup: training on the WSL host

This page is in STE-flavored style. A step marked "available after the <name> PR" does not work yet. A result that is marked "not verified" was not run by the author.

Host tools: git, make and Docker. Python, ROS and PyTorch run in containers.

## 1. Windows prerequisites
1. Windows 11 with WSL2. Check: `wsl.exe --version` (WSL version 2.x).
2. An Ubuntu 24.04 distro in WSL2: `wsl --install -d Ubuntu-24.04`.
3. The NVIDIA Windows driver. It must support CUDA 13.2 (the PyTorch image uses CUDA 13.2, and the RTX 5070 Ti needs CUDA 12.8 or newer). Do not install a Linux NVIDIA driver in WSL.
4. Docker Desktop with the WSL2 backend. Enable WSL integration for the Ubuntu 24.04 distro (Settings > Resources > WSL integration).
5. Docker Desktop host networking: Settings > Resources > Network > Enable host networking. The compose stacks (sim-gz PR) use `network_mode: host`.
6. `.wslconfig` in `C:\Users\<you>\.wslconfig`. Run `wsl --shutdown` after you change it.

```ini
[wsl2]
memory=24GB
# only for cross-host DDS (section 6):
networkingMode=mirrored
```

## 2. Clone the repo into the WSL file system
Do this inside WSL. Do not use `/mnt/c` (slow, wrong file modes).

```bash
mkdir -p ~/projects && cd ~/projects
git clone https://github.com/gvo27/racecar-sim.git
cd racecar-sim
```

## 3. Build and check
```bash
make setup    # checks host tools, builds the sim and dev images, removes old project images
make doctor   # PASS / FAIL / SKIP lines
```
- `make setup` builds `rccar-sim:local` and `rccar-sim-dev:local`. The first build downloads the ROS image and `ros-jazzy-ros-gz`. It takes several minutes.
- After the build, `make setup` runs `make prune`. It removes the dangling images of this project (label `org.racecar-sim.project=racecar-sim`), so old builds do not fill the disk. It does not touch other images. You can also run `make prune` at any time.
  - With the classic image store, a rebuild leaves the old image as a dangling image, and `make prune` removes it.
  - With the containerd image store (the default for new Docker Engine 29 and Docker Desktop installs), a rebuild leaves no dangling image, so `make prune` removes nothing. The old layers stay in the BuildKit build cache. BuildKit garbage collection limits the cache size. `docker info` shows the store: `driver-type io.containerd.snapshotter.v1` is the containerd store.
  - The build cache is shared by all projects on the host. If you must free it, run `docker builder prune` yourself. It affects every project, so `make` never runs it.
- `make setup` runs `make lsp` only if `claude` is on PATH, or if you set `LSP=1`.
- The gym image (several GB) is not part of `make setup`.

## 4. Train (available after the gym PR)
1. `make gym-check`, then `make train CFG=configs/ppo_flat_track.yaml`.
2. `make tensorboard` and open http://localhost:6006.
3. Runs go to `runs/<UTC>/`. Git ignores this folder.
4. `make eval RUN=<run>` and `make export RUN=<run>` (ONNX).

## 5. Contract sim (available after the sim-gz PR)
1. `make sim-up PROFILE=gui` opens a WSLg window.
2. `make teleop`, then `make record`.
3. If ogre2 fails, run `RENDER_ENGINE=ogre make sim-up PROFILE=gui`.

## 6. Cross-host DDS (optional, available after the sim-gz PR)
Use this to connect the sim to the car or to another host.
1. Set `networkingMode=mirrored` in `.wslconfig`.
2. Open UDP 7400-7600 and the discovery server port in the Windows firewall.
3. Start a Fast DDS discovery server: `fastdds discovery -i 0 -p 11811`.
4. Set `ROS_DISCOVERY_SERVER=<host>:11811` in each container.
5. Use a `ROS_DOMAIN_ID` for the sim that is not the car domain.
6. The images set `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`. Override it with `SUBNET` for cross-host work.

## 7. Staging host (Linux server, no GPU)
Use the staging host for CPU checks only. Training never runs there.
```bash
make setup      # LSP=1 only if you use Claude Code there
make sim-test
make pin-check
make lint       # advisory
```
The WSL and GPU lines of `make doctor` print SKIP on this host.

## 8. Troubleshooting
| Symptom | Cause | Action |
|---|---|---|
| `docker: command not found` in WSL | WSL integration is off | Enable it in Docker Desktop (section 1) |
| `make doctor` FAIL on `nvidia-smi` | Windows driver too old or missing | Update the NVIDIA Windows driver. Do not install a Linux driver |
| `docker run --gpus all` fails | GPU support is off in Docker Desktop | Update Docker Desktop. Run `wsl --update` and `wsl --shutdown` |
| WSLg window is black | ogre2 render engine | `RENDER_ENGINE=ogre` (after the sim-gz PR) |
| No `/dev/dxg` | old WSL kernel | `wsl --update` |
| Nodes do not see each other across hosts | multicast blocked, wrong domain | Use the discovery server (section 6). Check the firewall and `ROS_DOMAIN_ID` |
| Build is very slow | repo is on `/mnt/c` | Clone into `~/projects` in WSL |
| Disk is full | Docker images and cache | `docker system df`, then `make prune` (this project only). If "Build Cache" is large: `docker builder prune` (all projects, see section 3) |
| `ros-jazzy-ros-gz` not found in the build | Harmonic is not in packages.ros.org | Add the OSRF Gazebo apt repo to `docker/sim.Dockerfile` (not verified) |

## 9. Sanity checks
`make doctor` runs these checks. Expected output is in the second column. Outputs marked "not verified" are from the plan and nobody has run them.

| Command | Expected output |
|---|---|
| `wsl.exe --version` | WSL version 2.x |
| `uname -r` | contains `microsoft-standard-WSL2` |
| `docker version` | client and server sections |
| `docker compose version` | `Docker Compose version v2.x` or newer |
| `docker buildx version` | `github.com/docker/buildx v0.x` |
| `docker run --rm --gpus all pytorch/pytorch:2.15.0-cuda13.2-cudnn9-runtime@sha256:924707fa828f821c9a82d987b405675df6369eee5ce368aece6757b025ffcde5 nvidia-smi` | table with the RTX 5070 Ti and CUDA version 13.2 or newer (not verified) |
| `docker run --rm rccar-sim:local gz sim --versions` | 8.x (Harmonic) (not verified) |
| `docker run --rm rccar-sim:local bash -c 'ros2 pkg list \| grep ros_gz_bridge'` | `ros_gz_bridge` (not verified) |
| `docker run --rm rccar-sim:local bash -c 'ros2 pkg list \| grep rccar_sim_mcu'` | `rccar_sim_mcu` (not verified) |
| `ls /mnt/wslg /dev/dxg` | both paths exist |
| `make pin-check` | `passed` for all tests |
| `make doctor` | no `FAIL` line |
| Gym image: `docker run --rm --gpus all <gym image> python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_capability())"` | `2.15.0 True (12, 0)` (available after the gym PR) |
| Gym image: `python -c "import gymnasium, f1tenth_gym; print(gymnasium.__version__)"` | `0.29.1` (available after the gym PR) |
| `make sim-up PROFILE=headless` then `ros2 topic hz /rccar/lidar/scan` | about 10 Hz (available after the sim-gz PR) |

## 10. Versions (checked 2026-11-10)
| Item | Pin |
|---|---|
| ROS base | `ros:jazzy-ros-base@sha256:8eed0a4669bbf43ee331878a4c39bd8ebddea8e3312a58b4fae8edb14526b617` (same as the car repo) |
| Gazebo | Harmonic through `ros-jazzy-ros-gz` 1.0.24 (apt, CI 2026-11-11; rosdistro has 1.0.25, not synced yet) and `gz_sim_vendor` 0.0.13 |
| Fast DDS | 2.14.7 (not 3.x) |
| PyTorch image | `pytorch/pytorch:2.15.0-cuda13.2-cudnn9-runtime@sha256:924707fa828f821c9a82d987b405675df6369eee5ce368aece6757b025ffcde5` (gym PR) |
| f1tenth_gym | branch `v1.0.0` @ `5a301bd` with `gymnasium==0.29.1` (gym PR). Risk: unmaintained since 2024-09 |
| pyright / ruff | 1.1.414 / 0.17.4 (checked 2026-11-11) |
| Isaac | deferred (later PR) |
| Host tools on the staging host | Docker 29.9.3, Compose v5.7.0, buildx 0.38.1 |

Details and notes: `.claude/rules/dependencies.md`.
