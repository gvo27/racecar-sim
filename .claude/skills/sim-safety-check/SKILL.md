---
name: sim-safety-check
description: Use when you write or test a policy, planner, fault test or launch file that drives the virtual ESP32 in racecar-sim - /rccar/mcu/drive, /rccar/cmd/captain, supervisor arm, Reset incident, FAILSAFE, fault_drop_drive, fault_reboot, tuning.toml. Gives the safety checks.
---

# Sim safety check

## Steps
1. Policies and planners publish only `/rccar/cmd/captain`. They do not publish `/rccar/mcu/drive`.
2. Make sure that only the car supervisor publishes `/rccar/mcu/drive`:
   - In a running sim, run `ros2 topic info -v /rccar/mcu/drive`. The list of publishers has only the node `supervisor`.
   - In the repo, run `make unit`. The test `tests/test_drive_publisher.py` fails if `rccar_sim_*` code publishes the topic.
3. Keep the supervisor and `mcu_bridge` in the loop. Start the car stack with `car.launch.py sim:=true`. Do not send drive commands around the supervisor.
4. Start the virtual ESP32 with `ros2 launch rccar_sim_mcu sim_mcu.launch.py`. The node is `rccar_mcu`.
5. Arm in this order:
   1. Send the neutral admin command first.
   2. Call the service `/supervisor/arm` (`rccar_msgs/srv/Reset`). Put the current incident from `/rccar/supervisor/state` in the request.
6. After a FAILSAFE event or a reboot of the virtual ESP32, the supervisor latches. It needs `Reset(incident)` with the current incident before it arms again.
7. Use the fault services only in sim tests: `/rccar_mcu/fault_drop_drive` and `/rccar_mcu/fault_reboot`. They are in the private namespace of the node. Never put a fault service on `/rccar/`.
8. Put sim-only parameters in this repo. Never put an unconfirmed value in the car `tuning.toml`.
9. Never connect to the real Mapper `192.168.11.1`.
10. Report as "not verified" every step that you did not run.

## Rules
- The virtual ESP32 subscribes to `/rccar/mcu/drive`. It never publishes it.
- Gazebo ground truth never goes on `/tf` odom->base_link or on a `/rccar/*` topic.
- If a check fails, do not change the test to make it pass. Find the cause (superpowers systematic-debugging).
