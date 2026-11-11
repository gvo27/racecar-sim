---
name: wsl-docker-ros2
description: Use when you set up or debug the WSL2 + Docker Desktop host for racecar-sim - docs/setup.md, tools/doctor.sh, docker/*.Dockerfile, a future compose.yaml or dds/ profile, GPU (gpus all, nvidia-smi, CUDA 13.2), WSLg GUI (/mnt/wslg, /dev/dxg, ogre2, RENDER_ENGINE), Fast DDS discovery server, ROS_DOMAIN_ID, ROS_AUTOMATIC_DISCOVERY_RANGE, host networking, or cross-host ROS 2 between the WSL host and the car.
---

# WSL2 + Docker Desktop + ROS 2

Use this skill with `.claude/rules/wsl.md` and `docs/setup.md`. Rules are in strict STE. Items marked "not verified" were not run on a WSL host.

## File system
1. Keep the repo in the WSL file system (`~/projects`). A repo on `/mnt/c` is slow and has wrong file modes. File watchers do not work there.
2. Do not mount a `/mnt/c` path into a container.
3. Put build caches in named volumes, not in bind mounts of the repo.

## Docker Desktop
1. Use the WSL2 backend. Enable WSL integration for the Ubuntu 24.04 distro (Settings > Resources > WSL integration).
2. Compose files that use `network_mode: host` need the Docker Desktop host networking setting (Settings > Resources > Network > Enable host networking). Without it, host networking does not reach the WSL network. Compose files come in the sim-gz PR.
3. Docker Desktop must run before `make setup`. `make doctor` reports a missing daemon.

## GPU
1. Install the NVIDIA driver on Windows only. Do not install a Linux driver in WSL.
2. The Windows driver must support CUDA 13.2 (PyTorch image `cuda13.2`).
3. In a compose file use `gpus: all`. In `docker run` use `--gpus all`.
4. Test: `docker run --rm --gpus all <pytorch image> nvidia-smi`. It must show the RTX 5070 Ti.

## GUI (WSLg)
1. A GUI container mounts `/mnt/wslg`, `/dev/dxg` and `/usr/lib/wsl`. It sets `DISPLAY`, `WAYLAND_DISPLAY` and `XDG_RUNTIME_DIR` from the WSLg values, and `LD_LIBRARY_PATH=/usr/lib/wsl/lib`.
2. OpenGL goes through Mesa D3D12. If it fails, `glxinfo -B` shows `llvmpipe` (software rendering).
3. Gazebo Harmonic uses the ogre2 render engine by default. If ogre2 gives a black window or a crash, set `RENDER_ENGINE=ogre` (ogre1 fallback). Not verified on this host.
4. The headless profile needs no GUI mounts.

## DDS
1. Fast DDS 2.14.7 (Jazzy). Do not use 3.x.
2. Multicast discovery often fails between WSL and another host. Use a discovery server (`fastdds discovery -i 0 -p 11811`) and set `ROS_DISCOVERY_SERVER=<host>:11811` in each container.
3. For cross-host work, set WSL `networkingMode=mirrored` in `.wslconfig`. Open UDP 7400-7600 (and the discovery server port) in the Windows firewall.
4. The sim and the car use different `ROS_DOMAIN_ID` values. Do not share a domain.
5. The images bake `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` (same as the car image). For cross-host work, override it: `-e ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET`. Revert it for local-only work.

## Healthchecks and pins
1. Each long-running service has a healthcheck (heartbeat file or `ros2 topic` check). A service that depends on another uses `condition: service_healthy`.
2. Pin base images by digest. Use the same ROS digest as the car repo.

## Sanity commands
- `wsl.exe --version`
- `uname -r` (has `microsoft-standard-WSL2`)
- `docker version`, `docker compose version`, `docker buildx version`
- `ls /mnt/wslg /dev/dxg`
- `make doctor`

Expected output: `docs/setup.md`.
