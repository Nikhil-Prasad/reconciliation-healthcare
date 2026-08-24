.PHONY: reproduce

UV ?= uv
PROJECT_DIR := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
export HCL_PROJECT_ROOT := $(PROJECT_DIR)

reproduce:
	$(UV) sync --directory "$(PROJECT_DIR)" --locked --dev
	$(UV) run --directory "$(PROJECT_DIR)" --locked --no-sync hcl-download
	$(UV) run --directory "$(PROJECT_DIR)" --locked --no-sync hcl-inspect
	$(UV) run --directory "$(PROJECT_DIR)" --locked --no-sync hcl-build
	$(UV) run --directory "$(PROJECT_DIR)" --locked --no-sync pytest -q
