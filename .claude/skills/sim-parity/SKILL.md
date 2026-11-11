---
name: sim-parity
description: Use in racecar-sim when the car hardware boundary changes - docs/sensor_contract.md rows, rccar_msgs, a topic, type, frame or QoS, the ESP32 firmware grammar, tuning keys, repos/racecar.repos. This is a stub. The full table is in the car repo skill.
---

# Sim parity (sim side)

The full checklist and the table of changed paths are in the car repo: `.claude/skills/sim-parity/SKILL.md` (pinned checkout: `src/racecar/` in the sim images). This stub lists the sim-side steps.

## Steps
1. Read the car PR "Sim impact" section. It lists the contract rows and the sim artifacts to change.
2. Bump the pin (skill `sim-bump-pin`).
3. For each changed contract row, change the matching sim artifact:
   - ESP32 control, grammar or keys: `rccar_sim_mcu` (planned: sim-mcu PR)
   - Mapper topic, type, frame, QoS or protocol: `rccar_sim_mapper` (planned: sim-mapper PR)
   - URDF or TF: sim wrapper xacro and gz sensor files (planned: sim-gz PR)
   - supervisor inputs: sim safety check (planned: sim-mcu PR)
4. Run `make sim-test`, `make unit` and `make pin-check`.
5. Report as "not verified" every step that you did not run.

## Rules
- The car `docs/sensor_contract.md` is the source of truth.
- Do not change the car `tuning.toml` for the sim. Sim-only values stay here.
- Only the car supervisor publishes `/rccar/mcu/drive`.
