---
paths:
  - "docs/setup.md"
  - "tools/doctor.sh"
  - ".claude/skills/wsl-docker-ros2/SKILL.md"
---

# WSL host rules

The training host is Windows 11 with WSL2 and Docker Desktop. Details: skill `wsl-docker-ros2`, steps: `docs/setup.md`.

## Rules
1. Keep the repo in the WSL file system (`~/projects`). Never use `/mnt/c`.
2. Do not install a Linux NVIDIA driver in WSL. The Windows driver gives the GPU.
3. Use `gpus: all` or `--gpus all` for GPU containers. Test with `nvidia-smi` in a container.
4. A GUI container mounts `/mnt/wslg`, `/dev/dxg` and `/usr/lib/wsl`. These mounts come in the sim-gz PR.
5. Every command in `docs/setup.md` "Sanity checks" has a check in `tools/doctor.sh`. Keep both in step.
6. The "Versions" table in `docs/setup.md` agrees with `.claude/rules/dependencies.md`.
7. Mark a step that needs a later PR: "available after the <name> PR".
