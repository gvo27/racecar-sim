# racecar-sim: simulation and training for the racecar. Run `make help`. Setup steps: docs/setup.md
# Host needs only git, make, docker (+compose, buildx). Everything else runs in containers.
# python3 on the host is used only by the Claude hooks (.claude/hooks) and the LSP smoke test (make lsp).
SIM_IMAGE         ?= rccar-sim:local
SIM_BUILDER_IMAGE ?= rccar-sim-builder:local
SIM_TEST_IMAGE    ?= rccar-sim-test:local
DEV_IMAGE         ?= rccar-sim-dev:local
SIM_TEST_OUT      ?= build/sim-test
SIM_BUILD_ARGS    ?=
# pytorch image for the GPU check in make doctor (used by the gym image in the gym PR)
PYTORCH_IMAGE     ?= pytorch/pytorch:2.15.0-cuda13.2-cudnn9-runtime@sha256:924707fa828f821c9a82d987b405675df6369eee5ce368aece6757b025ffcde5
# STE lint script from the asd-ste100 plugin (advisory); override with STE_LINT=<path>
STE_LINT          ?= $(firstword $(wildcard $(HOME)/.claude/plugins/cache/asd-ste100-skill/*/*/scripts/ste-lint.py))
LSP_BIN_DIR       ?= $(HOME)/.local/bin
DEV_RUN := docker run --rm -e PYTHONDONTWRITEBYTECODE=1 --user $(shell id -u):$(shell id -g) -v "$(CURDIR)":/work:ro -w /work $(DEV_IMAGE) /entrypoint.sh
IS_WSL  := $(shell grep -qi microsoft /proc/version 2>/dev/null && echo 1)

.DEFAULT_GOAL := help
.PHONY: help setup doctor sim-image dev-image sim-test sim-test-image sim-test-run unit lint pin-check bump-racecar lsp _need-dev-image

help:            ## list targets (grouped in README.md)
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-21s %s\n", $$1, $$2}'

# ---- setup ---------------------------------------------------------------------------------
setup:           ## check host prereqs (git, make, docker + compose/buildx; on WSL also nvidia-smi, WSLg), build the sim + dev images; LSP=1 or claude on PATH also runs make lsp
	@for c in git make docker; do command -v $$c >/dev/null || { echo "MISSING host prerequisite: $$c"; exit 1; }; done
	@docker compose version >/dev/null 2>&1 || echo "WARN: docker compose plugin missing (needed in a later PR)"
	@docker buildx version >/dev/null 2>&1 || { echo "MISSING host prerequisite: docker buildx"; exit 1; }
	@if [ -n "$(IS_WSL)" ]; then \
	  command -v nvidia-smi >/dev/null || echo "WARN: nvidia-smi missing in WSL (install the NVIDIA Windows driver, not a Linux driver)"; \
	  [ -d /mnt/wslg ] || echo "WARN: /mnt/wslg missing (WSLg GUI will not work)"; \
	fi
	$(MAKE) sim-image
	$(MAKE) dev-image
	@if [ "$(LSP)" = "1" ] || command -v claude >/dev/null 2>&1; then $(MAKE) lsp; else echo "setup: skip make lsp (claude not on PATH; use LSP=1 to force)"; fi

doctor:          ## sanity checks with PASS/FAIL/SKIP lines (docs/setup.md "Sanity checks")
	@IS_WSL="$(IS_WSL)" SIM_IMAGE="$(SIM_IMAGE)" DEV_IMAGE="$(DEV_IMAGE)" PYTORCH_IMAGE="$(PYTORCH_IMAGE)" \
	  LSP_BIN_DIR="$(LSP_BIN_DIR)" bash tools/doctor.sh

# ---- images --------------------------------------------------------------------------------
sim-image:       ## build the sim image (docker/sim.Dockerfile -> rccar-sim:local; builder stage also tagged)
	docker build -f docker/sim.Dockerfile --target builder $(SIM_BUILD_ARGS) -t $(SIM_BUILDER_IMAGE) .
	docker build -f docker/sim.Dockerfile --target runtime $(SIM_BUILD_ARGS) -t $(SIM_IMAGE) .

dev-image:       ## build the dev image (pyright, ruff, pytest; FROM the sim builder stage)
	@docker image inspect $(SIM_BUILDER_IMAGE) >/dev/null 2>&1 || { echo "image $(SIM_BUILDER_IMAGE) missing: run make sim-image"; exit 1; }
	docker build -f docker/dev.Dockerfile --build-arg SIM_BUILDER=$(SIM_BUILDER_IMAGE) -t $(DEV_IMAGE) docker/

# ---- tests ---------------------------------------------------------------------------------
sim-test-image:  ## build the sim test image (target test: colcon build, all test deps)
	docker build -f docker/sim.Dockerfile --target test $(SIM_BUILD_ARGS) -t $(SIM_TEST_IMAGE) .

sim-test-run:    ## run colcon test in an already built test image; results in build/sim-test
	mkdir -p $(SIM_TEST_OUT)
	docker run --rm -e HOST_UID=$(shell id -u) -e HOST_GID=$(shell id -g) -v "$(CURDIR)/$(SIM_TEST_OUT)":/out $(SIM_TEST_IMAGE)

sim-test: sim-test-image sim-test-run  ## build the test image + colcon test + test-result (no hardware, no GPU)

unit:            ## run tests/ (pytest) in the dev image
	@$(MAKE) _need-dev-image
	$(DEV_RUN) python3 -m pytest -q -p no:cacheprovider tests

pin-check:       ## test repos/racecar.repos: version is a SHA or tag, contract topics are in the car sources
	@$(MAKE) _need-dev-image
	$(DEV_RUN) python3 -m pytest -q -p no:cacheprovider tests/test_pin.py

lint:            ## ruff + STE lint over *.md (advisory: findings never fail the target)
	@$(MAKE) _need-dev-image
	$(DEV_RUN) ruff check --no-cache .
	@if [ -n "$(STE_LINT)" ] && [ -f "$(STE_LINT)" ]; then \
	  echo "STE lint (advisory): $(STE_LINT)"; \
	  for f in $$(git ls-files '*.md'); do \
	    docker run --rm --user $(shell id -u):$(shell id -g) -v "$(CURDIR)":/work:ro -v "$(STE_LINT)":/ste-lint.py:ro -w /work $(DEV_IMAGE) \
	      python3 /ste-lint.py "$$f" || true; \
	  done; \
	else echo "STE lint skipped: ste-lint.py not found (install the asd-ste100 plugin or set STE_LINT=<path>)"; fi

bump-racecar:    ## set the car pin in repos/racecar.repos: make bump-racecar SHA=<40-hex sha>
	@echo "$(SHA)" | grep -Eq '^[0-9a-f]{40}$$' || { echo "usage: make bump-racecar SHA=<40-hex commit sha>"; exit 1; }
	sed -i -E 's|^(    version: ).*$$|\1$(SHA)|' repos/racecar.repos
	@grep -n 'version:' repos/racecar.repos
	@echo "bump-racecar: now run make sim-image sim-test pin-check (repos/README.md)"

# ---- claude tooling ------------------------------------------------------------------------
lsp:             ## build the dev image, link tools/lsp/pyright-langserver into ~/.local/bin, run the LSP initialize smoke test
	$(MAKE) dev-image
	chmod +x tools/lsp/pyright-langserver
	mkdir -p $(LSP_BIN_DIR)
	ln -sf "$(CURDIR)/tools/lsp/pyright-langserver" "$(LSP_BIN_DIR)/pyright-langserver"
	python3 tools/lsp/smoke.py "$(LSP_BIN_DIR)/pyright-langserver" --stdio
	@echo "lsp: ok. Make sure $(LSP_BIN_DIR) is on PATH."

_need-dev-image:
	@docker image inspect $(DEV_IMAGE) >/dev/null 2>&1 || { echo "image $(DEV_IMAGE) missing: run make dev-image"; exit 1; }
