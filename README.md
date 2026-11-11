# racecar-sim

Simulation and training for the [racecar](https://github.com/gvo27/racecar) 1:10 autonomous car (Tamiya TT-02, ROS 2 Jazzy).

The sim replaces the car hardware at the device boundary:
- A **virtual ESP32** serves the `/rccar/mcu/*` topics and the `/rccar/mcu/command` service with the firmware drive rules.
- A **virtual Mapper** speaks the Slamtec Mapper TCP protocol to the real `mapper_driver`.

The car nodes (supervisor, mcu_bridge, drivers) run without changes. The boundary is in the car repo: [`docs/sensor_contract.md`](https://github.com/gvo27/racecar/blob/sim-contract/docs/sensor_contract.md).

## Status
Empty scaffold. The work comes in this order:
1. `scaffold`: Docker images, Makefile, `docs/setup.md`, CI.
2. `sim-mcu`: the virtual ESP32.
3. `sim-mapper`: the virtual Mapper.
4. `sim-gz`: Gazebo Harmonic world, walled track.
5. `gym`: gymnasium environment and training.
6. `racing`: follow-the-gap and wall following.

## Hosts
- **Training and sim:** Windows 11 workstation (RTX 5070 Ti) with WSL2 and Docker Desktop.
- **Staging:** a small Linux server. It builds the images and runs the first CPU-only checks only.
- Host tools: git, make and Docker. Everything else runs in containers.
