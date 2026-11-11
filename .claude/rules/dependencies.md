---
paths:
  - "Makefile"
  - "docker/**"
  - "repos/**"
  - ".claude/settings.json"
  - "pyrightconfig.json"
---

# Dependencies

## Host prerequisites
- git, make, docker engine (Docker Desktop on WSL) + compose plugin + buildx. No host Python packages, no `.venv`, no `requirements.txt`.
- WSL host: the NVIDIA Windows driver. Do not install a Linux driver inside WSL.

## Rules
- Put new dependencies in a `package.xml` (rosdep) or a Dockerfile. Never install on the host.
- Pin versions: base images by digest, pip and npm by exact version, GitHub Actions by major tag, vcs by SHA. Never use `:latest`.
- Refresh a digest deliberately. Note it in the PR.

## Pins (checked 2026-11-10 unless a note says other)
| Item | Pin | Note |
|---|---|---|
| ROS base | `ros:jazzy-ros-base@sha256:8eed0a4669bbf43ee331878a4c39bd8ebddea8e3312a58b4fae8edb14526b617` | same as car `docker/ros.Dockerfile`; bump both together |
| Gazebo | `ros-jazzy-ros-gz` 1.0.25 with `gz_sim_vendor` 0.0.13 (Harmonic) | apt version not pinned in the Dockerfile; ros_gz 4.x is for Kilted/Rolling only: do not use |
| Fast DDS | 2.14.7 (Jazzy fastrtps) | discovery server: `fastdds discovery`; not 3.x |
| car repo | SHA in `repos/racecar.repos` | bump: `make bump-racecar SHA=` |
| pyright | npm `pyright` 1.1.414 (`docker/dev.Dockerfile`) | checked 2026-11-11 |
| ruff | pip `ruff` 0.17.4 (`docker/dev.Dockerfile`) | checked 2026-11-11 |
| PyTorch image | `pytorch/pytorch:2.15.0-cuda13.2-cudnn9-runtime@sha256:924707fa828f821c9a82d987b405675df6369eee5ce368aece6757b025ffcde5` | used in the gym PR; Blackwell sm_120 needs cu128 or newer; the Windows NVIDIA driver must support CUDA 13.2 |
| f1tenth_gym | branch `v1.0.0` @ `5a301bd` + `gymnasium==0.29.1` | gym PR. Risk: unmaintained since 2024-09; `main` is the old gym 0.19 API: do not use. May be vendored or forked later |
| Isaac | deferred | not pinned; later PR |

## Claude plugins (.claude/settings.json, usage: .claude/rules/claude-tooling.md)
- claude-plugins-official (anthropics/claude-plugins-official): superpowers, pyright-lsp, claude-md-management.
- ros2-engineering@ros2-engineering-skills: ref v1.7.2.
- asd-ste100@asd-ste100-skill: ref master (upstream has no tags).
- ros2-sim (BaraaLazkani/ros2-sim-skill v1.0.0): loose SKILL.md, no plugin manifest. Copy at the tag in the sim-gz PR (claude-tooling.md).
- To bump a plugin, change the ref to a tag. Never track a moving branch when a tag exists.
