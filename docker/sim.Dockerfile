# sim runtime: ROS 2 Jazzy + Gazebo Harmonic (ros-gz) + the pinned car packages. Notes: .claude/rules/dependencies.md
# Build: make sim-image    Test: make sim-test (builds target `test`, runs colcon test)
# Context = repo root, filtered by docker/sim.Dockerfile.dockerignore. Stages:
#   builder  vcs import of repos/racecar.repos + rosdep + colcon build --merge-install -> /ws/install
#   test     builder + `colcon test` entrypoint (CI, make sim-test)
#   runtime  ros-base + ros-gz + runtime deps + /ws/install only (default target)
# The car repo lands in /ws/src/racecar (read by tests/test_pin.py). The rccar_sim_mcu package is copied next to it; other rccar_sim_* packages come in later PRs.
# ros-gz comes from packages.ros.org (Harmonic, gz_sim_vendor 0.0.13; confirmed in CI 2026-11-11). No OSRF apt repo is needed.
# rosdep needs raw.githubusercontent.com + packages.ros.org. Offline builds only:
# --build-arg ROSDEP_INSTALL=0 skips rosdep install. Default 1 = real resolution, fails loudly on a bad key.

# Same digest as the car repo docker/ros.Dockerfile. Bump both together.
# TODO(bump): refresh with `docker pull ros:jazzy-ros-base && docker inspect --format '{{index .RepoDigests 0}}' ros:jazzy-ros-base`
ARG ROS_BASE=ros:jazzy-ros-base@sha256:8eed0a4669bbf43ee331878a4c39bd8ebddea8e3312a58b4fae8edb14526b617
ARG ROSDEP_INSTALL=1

FROM ${ROS_BASE} AS builder
# Label on every project image: make prune removes only dangling images with this label.
LABEL org.racecar-sim.project=racecar-sim
ARG ROSDEP_INSTALL
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /ws

# Gazebo Harmonic bridge (ros-jazzy-ros-gz 1.0.25 pairs with gz_sim_vendor 0.0.13) + vcstool
RUN apt-get update \
 && apt-get install -y --no-install-recommends ros-jazzy-ros-gz python3-vcstool git \
 && rm -rf /var/lib/apt/lists/*

COPY repos/ repos/
RUN mkdir -p src && vcs import src < repos/racecar.repos
COPY rccar_sim_mcu/ src/rccar_sim_mcu/

RUN if [ "${ROSDEP_INSTALL}" = "1" ]; then \
      rosdep update --rosdistro jazzy \
      && apt-get update \
      && rosdep install --from-paths src --ignore-src -y --rosdistro jazzy \
      && rm -rf /var/lib/apt/lists/*; \
    else echo "WARN: ROSDEP_INSTALL=0, skipping rosdep install (offline build)"; fi

# Car packages and rccar_sim_mcu. Other sim packages join this list in later PRs.
RUN source /opt/ros/jazzy/setup.bash \
 && colcon build --merge-install --event-handlers console_cohesion+ \
      --packages-up-to rccar_bringup rccar_drivers rccar_teleop rccar_description rccar_sim_mcu \
      --cmake-args -DCMAKE_BUILD_TYPE=Release

# package.xml files for the runtime stage (exec deps). Only the packages that colcon finds:
# colcon list honors COLCON_IGNORE (the car repo firmware/ has a second rccar_msgs for micro-ROS).
RUN mkdir -p /ws/pkgxml \
 && colcon list --base-paths src --paths-only \
    | while read -r p; do cp --parents "$p/package.xml" /ws/pkgxml; done

# --- test: colcon test + results (docker run exit code = test result; /out gets log + xml) --
FROM builder AS test
COPY docker/entrypoint.sh docker/sim-test.sh /
RUN chmod 0755 /entrypoint.sh /sim-test.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/sim-test.sh"]

# --- runtime ------------------------------------------------------------------------------
FROM ${ROS_BASE} AS runtime
LABEL org.racecar-sim.project=racecar-sim
ARG ROSDEP_INSTALL
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp
WORKDIR /ws

RUN apt-get update \
 && apt-get install -y --no-install-recommends ros-jazzy-ros-gz \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /ws/pkgxml /tmp/src
RUN if [ "${ROSDEP_INSTALL}" = "1" ]; then \
      rosdep update --rosdistro jazzy \
      && apt-get update \
      && rosdep install --from-paths /tmp/src --ignore-src -y --rosdistro jazzy \
           --dependency-types exec \
      && rm -rf /var/lib/apt/lists/* /root/.ros; \
    else echo "WARN: ROSDEP_INSTALL=0, skipping rosdep install (offline build)"; fi \
 && rm -rf /tmp/src

COPY --from=builder /ws/install /ws/install
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod 0755 /entrypoint.sh

USER ubuntu
# The image bakes LOCALHOST like the car image. Cross-host DDS overrides it (docs/setup.md).
ENV ROS_LOG_DIR=/tmp/roslog \
    ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
