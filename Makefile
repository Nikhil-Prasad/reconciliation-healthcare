.PHONY: reproduce reproduce-stage1 reproduce-rulebook

UV ?= uv
PROJECT_DIR := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
export HCL_PROJECT_ROOT := $(PROJECT_DIR)

reproduce: reproduce-stage1 reproduce-rulebook

reproduce-stage1:
	$(UV) sync --directory "$(PROJECT_DIR)" --locked --dev
	$(UV) run --directory "$(PROJECT_DIR)" --locked --no-sync hcl-download
	$(UV) run --directory "$(PROJECT_DIR)" --locked --no-sync hcl-inspect
	$(UV) run --directory "$(PROJECT_DIR)" --locked --no-sync hcl-build

reproduce-rulebook:
	$(UV) sync --directory "$(PROJECT_DIR)" --locked --dev
	$(UV) run --directory "$(PROJECT_DIR)" --locked --no-sync hcl-rulebook-download
	$(UV) run --directory "$(PROJECT_DIR)" --locked --no-sync hcl-rulebook-build
	$(UV) run --directory "$(PROJECT_DIR)" --locked --no-sync hcl-rulebook-validate
	$(UV) run --directory "$(PROJECT_DIR)" --locked --no-sync pytest -q
