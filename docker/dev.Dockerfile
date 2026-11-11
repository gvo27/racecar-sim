# dev tools: pyright (LSP), ruff, pytest, STE lint host. Notes: .claude/rules/claude-tooling.md
# Build: make dev-image (needs the sim builder image: make sim-image). Context = docker/.
# FROM the sim builder stage, so pyright sees rclpy and rccar_msgs. Secrets are never copied in.
# The repo is mounted at run time (read-only), not copied.
ARG SIM_BUILDER=rccar-sim-builder:local
FROM ${SIM_BUILDER}
LABEL org.racecar-sim.project=racecar-sim

# TODO(bump): check with `npm view pyright version` and `pip index versions ruff` (checked 2026-11-11)
ARG PYRIGHT_VERSION=1.1.414
ARG RUFF_VERSION=0.17.4
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
USER root

RUN test -n "${PYRIGHT_VERSION}" -a -n "${RUFF_VERSION}" \
      || { echo "ERROR: set PYRIGHT_VERSION and RUFF_VERSION (pins are required)"; exit 1; } \
 && apt-get update \
 && apt-get install -y --no-install-recommends nodejs npm python3-pytest python3-yaml python3-venv \
 && rm -rf /var/lib/apt/lists/* \
 && npm install -g "pyright@${PYRIGHT_VERSION}" \
 && python3 -m venv /opt/tools \
 && /opt/tools/bin/pip install --no-cache-dir "ruff==${RUFF_VERSION}" \
 && ln -s /opt/tools/bin/ruff /usr/local/bin/ruff \
 && npm cache clean --force

COPY entrypoint.sh /entrypoint.sh
RUN chmod 0755 /entrypoint.sh

# runs with the host uid/gid (--user), so HOME must be writable
ENV HOME=/tmp
WORKDIR /work
