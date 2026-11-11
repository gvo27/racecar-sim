#!/bin/bash
# sim image entrypoint: source ROS + workspace overlay, then run the command.
set -e
# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash
if [ -f /ws/install/setup.bash ]; then
  # shellcheck disable=SC1091
  source /ws/install/setup.bash
fi
exec "$@"
