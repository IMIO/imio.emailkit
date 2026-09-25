### Defensive make settings: https://tech.davis-hansson.com/p/make/
SHELL:=bash
.ONESHELL:
.SHELLFLAGS:=-eu -o pipefail -O inherit_errexit -c
.SILENT:
.DELETE_ON_ERROR:
MAKEFLAGS+=--warn-undefined-variables
MAKEFLAGS+=--no-builtin-rules

RED=`tput setaf 1`
GREEN=`tput setaf 2`
RESET=`tput sgr0`
YELLOW=`tput setaf 3`

UV?=uv

ifeq (, $(shell which $(UV) ))
  $(error "UV=$(UV) not found in $(PATH)")
endif

BACKEND_FOLDER=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

ifdef PLONE_VERSION
PLONE_VERSION := $(PLONE_VERSION)
else
PLONE_VERSION := 6.2.1
endif

ifdef CI
UV_VENV_ARGS :=
else
UV_VENV_ARGS := --python=3.10
endif

VENV_FOLDER=$(BACKEND_FOLDER)/.venv
export VIRTUAL_ENV=$(VENV_FOLDER)
BIN_FOLDER=$(VENV_FOLDER)/bin

export PYTHONWARNINGS := ignore
export DOCKER_BUILDKIT := 1

# NODE IS A DEVELOPER/CI TOOL ONLY. It must never become reachable from a
# deployment path, in front of ~350 production applications.

NPM?=npm
NPX?=npx

EMAILS_FOLDER=$(BACKEND_FOLDER)/emails
# Hand-authored plaintext twins, copied in by `build-emails`.
TWINS_FOLDER=$(BACKEND_FOLDER)/emails/twins

# Duplicated in `emails/maizzle.config.js`; keep both in step.
PACKAGE_FOLDER=$(BACKEND_FOLDER)/src/imio/emailkit
TEMPLATES_FOLDER=$(PACKAGE_FOLDER)/templates
OVERRIDES_FOLDER=$(PACKAGE_FOLDER)/browser/overrides

PREVIEW_FOLDER?=$(BACKEND_FOLDER)/var/preview
PREVIEW_PORT?=8090

all: build

.PHONY: help
help: ## This help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

requirements-mxdev.txt: pyproject.toml mx.ini ## Generate constraints file
	@echo "$(GREEN)==> Generate constraints file$(RESET)"
	@echo '-c https://dist.plone.org/release/$(PLONE_VERSION)/constraints.txt' > requirements.txt
	@uvx --from "mxdev[uv]" mxdev -c mx.ini

$(VENV_FOLDER): requirements-mxdev.txt ## Install dependencies
	@echo "$(GREEN)==> Install environment$(RESET)"
	@if [[ -d "$(VENV_FOLDER)" ]]; then echo "$(YELLOW)==> Environment already exists at $(VENV_FOLDER)$(RESET)"; else uv venv $(UV_VENV_ARGS) $(VENV_FOLDER); fi
	@uv pip install -r requirements-mxdev.txt

.PHONY: sync
sync: $(VENV_FOLDER) ## Sync project dependencies
	@echo "$(GREEN)==> Sync project dependencies$(RESET)"
	@uv pip install -r requirements-mxdev.txt

instance/etc/zope.ini instance/etc/zope.conf: instance.yaml ## Create instance configuration
	@echo "$(GREEN)==> Create instance configuration$(RESET)"
	@uvx cookiecutter -f --no-input -c 2.4.1 --config-file instance.yaml gh:plone/cookiecutter-zope-instance

.PHONY: config
config: instance/etc/zope.ini

.PHONY: install
install: $(VENV_FOLDER) config ## Install Plone and dependencies

.PHONY: build
build: install ## Alias of install (Node is deliberately not part of this)

.PHONY: clean
clean: ## Clean installation and instance (data left intact)
	@echo "$(RED)==> Cleaning environment and build$(RESET)"
	@rm -rf $(VENV_FOLDER) pyvenv.cfg .installed.cfg instance/etc .venv .pytest_cache .ruff_cache constraints* requirements*
	@rm -rf build dist src/*.egg-info
	@rm -rf $(PREVIEW_FOLDER)

.PHONY: remove-data
remove-data: ## Remove all content
	@echo "$(RED)==> Removing all content$(RESET)"
	rm -rf $(VENV_FOLDER) instance/var

.PHONY: start
start: $(VENV_FOLDER) instance/etc/zope.ini ## Start a Plone instance on localhost:8080
	@$(BIN_FOLDER)/runwsgi instance/etc/zope.ini

.PHONY: console
console: $(VENV_FOLDER) instance/etc/zope.ini ## Start a console into a Plone instance
	@$(BIN_FOLDER)/zconsole debug instance/etc/zope.conf

.PHONY: create-site
create-site: $(VENV_FOLDER) instance/etc/zope.ini ## Create a new site from scratch
	@$(BIN_FOLDER)/zconsole run instance/etc/zope.conf ./scripts/create_site.py

# Explicit paths: an unscoped ruff would reflow API examples in docs/.
RUFF_TARGETS=src tests scripts

# --include, not a file list, so this same value also works as a CI env var.
ZPRETTY_ROOT=src
ZPRETTY_INCLUDE=--include '\.(xml|zcml)$$'

.PHONY: lint
lint: ## Check code base according to Plone standards
	@echo "$(GREEN)==> Lint codebase$(RESET)"
	@uvx ruff@latest check --no-fix --config $(BACKEND_FOLDER)/pyproject.toml $(RUFF_TARGETS)
	@uvx ruff@latest format --check
	@uvx pyroma@latest -d .
	@uvx check-python-versions@latest .
	# zpretty must never see the compiled .pt files: it would fight the
	# staleness check in check-emails.
	@uvx zpretty@latest --check $(ZPRETTY_ROOT) $(ZPRETTY_INCLUDE)

.PHONY: format
format: ## Fix code base according to Plone standards
	@echo "$(GREEN)==> Format codebase$(RESET)"
	@uvx ruff@latest check --select I --fix --config $(BACKEND_FOLDER)/pyproject.toml $(RUFF_TARGETS)
	@uvx ruff@latest format
	@uvx zpretty@latest -i $(ZPRETTY_ROOT) $(ZPRETTY_INCLUDE)

.PHONY: check
check: format lint ## Check and fix code base according to Plone standards

# The authoring lint checks the `.vue` sources, not the compiled output.
# `--list-rules` explains all eight rules.
LINT_EMAILS_TARGETS?=$(EMAILS_FOLDER)/src/templates $(PACKAGE_FOLDER)/kit

.PHONY: lint-emails
lint-emails: $(VENV_FOLDER) ## Authoring lint of the .vue sources
	@echo "$(GREEN)==> Linting email sources against the authoring rules$(RESET)"
	@$(BIN_FOLDER)/python -m imio.emailkit.lint $(LINT_EMAILS_TARGETS)

.PHONY: i18n
i18n: $(VENV_FOLDER) ## Update locales
	@echo "$(GREEN)==> Updating locales$(RESET)"
	@$(BIN_FOLDER)/python -m imio.emailkit.locales

.PHONY: test
test: $(VENV_FOLDER) ## run tests
	@$(BIN_FOLDER)/pytest

.PHONY: test-coverage
test-coverage: $(VENV_FOLDER) ## run tests with coverage
	@$(BIN_FOLDER)/pytest --cov=imio.emailkit --cov-report term-missing

.PHONY: update-golden
update-golden: $(VENV_FOLDER) ## Regenerate the golden snapshots (deliberate, never automatic)
	@echo "$(YELLOW)==> Regenerating golden files -- review the diff before committing$(RESET)"
	# Covers this package's templates and the two dummy consumer add-ons.
	@EMAILKIT_UPDATE_GOLDEN=1 $(BIN_FOLDER)/pytest tests/test_golden.py tests/dummies -q -rs

.PHONY: node-check
node-check:
	@if ! command -v $(NPM) >/dev/null 2>&1; then
		echo "$(RED)==> $(NPM) not found. Node is required for the email targets only;$(RESET)"
		echo "$(RED)    installing, testing and running this add-on never needs it.$(RESET)"
		exit 1
	fi

.PHONY: emails-deps
emails-deps: node-check ## Install the Maizzle toolchain (npm ci when a lockfile exists)
	@cd $(EMAILS_FOLDER)
	@if [[ -e node_modules && -f package-lock.json && node_modules -nt package-lock.json ]]; then
		echo "$(YELLOW)==> node_modules is up to date$(RESET)"
	elif [[ -f package-lock.json ]]; then
		# No `npm install` fallback: it would resolve a different toolchain
		# than the lockfile pins. If this fails with `Missing: ... from lock
		# file`, regenerate: `rm -rf node_modules package-lock.json && npm install`.
		echo "$(GREEN)==> npm ci$(RESET)"
		$(NPM) ci
	else
		echo "$(YELLOW)==> No package-lock.json yet; running npm install to create it$(RESET)"
		$(NPM) install
	fi

.PHONY: build-emails
build-emails: emails-deps ## Compile emails/ into the package (templates/ + browser/overrides/)
	@echo "$(GREEN)==> Compiling email templates$(RESET)"
	@mkdir -p $(TEMPLATES_FOLDER) $(OVERRIDES_FOLDER)
	@cd $(EMAILS_FOLDER) && $(NPX) maizzle build
	# `maizzle build` empties its output directory, silently. Twins are
	# copied back in from emails/twins/ afterwards.
	@if compgen -G "$(TWINS_FOLDER)/*.txt.pt" > /dev/null; then \
		cp -a $(TWINS_FOLDER)/*.txt.pt $(TEMPLATES_FOLDER)/; \
		echo "$(GREEN)==> Copied hand-authored plaintext twins$(RESET)"; \
	fi
	@echo "$(GREEN)==> Done. Commit the .pt files -- they are what production renders.$(RESET)"

.PHONY: check-emails
check-emails: emails-deps lint-emails ## Authoring lint, then staleness check
	# The build writes into the package with no alternate destination, so the
	# committed output is snapshotted first and restored on a trap.
	@echo "$(GREEN)==> Checking committed email templates against a fresh build$(RESET)"
	@snapshot="$$(mktemp -d)"
	@trap 'cp -a "$$snapshot/templates/." "$(TEMPLATES_FOLDER)/" 2>/dev/null || true; cp -a "$$snapshot/overrides/." "$(OVERRIDES_FOLDER)/" 2>/dev/null || true; rm -rf "$$snapshot"' EXIT
	@mkdir -p "$$snapshot/templates" "$$snapshot/overrides" $(TEMPLATES_FOLDER) $(OVERRIDES_FOLDER)
	@cp -a $(TEMPLATES_FOLDER)/. "$$snapshot/templates/" 2>/dev/null || true
	@cp -a $(OVERRIDES_FOLDER)/. "$$snapshot/overrides/" 2>/dev/null || true
	@cd $(EMAILS_FOLDER) && $(NPX) maizzle build >/dev/null
	@if compgen -G "$(TWINS_FOLDER)/*.txt.pt" > /dev/null; then
		cp -a $(TWINS_FOLDER)/*.txt.pt $(TEMPLATES_FOLDER)/
	fi
	@stale=0
	@for pair in "$$snapshot/templates:$(TEMPLATES_FOLDER)" "$$snapshot/overrides:$(OVERRIDES_FOLDER)"; do
		committed="$${pair%%:*}"
		fresh="$${pair##*:}"
		for built in "$$fresh"/*.pt; do
			[[ -e "$$built" ]] || continue
			name="$$(basename "$$built")"
			if [[ ! -f "$$committed/$$name" ]]; then
				echo "$(RED)  MISSING   $$name (built, never committed)$(RESET)"
				stale=1
			elif ! diff -q "$$committed/$$name" "$$built" >/dev/null; then
				echo "$(RED)  STALE     $$name$(RESET)"
				diff -u "$$committed/$$name" "$$built" | head -20 || true
				stale=1
			else
				echo "$(GREEN)  ok        $$name$(RESET)"
			fi
		done
		for was in "$$committed"/*.pt; do
			[[ -e "$$was" ]] || continue
			name="$$(basename "$$was")"
			if [[ ! -f "$$fresh/$$name" ]]; then
				echo "$(RED)  ORPHAN    $$name (committed, no longer built)$(RESET)"
				stale=1
			fi
		done
	done
	@if [[ "$$stale" != "0" ]]; then
		echo "$(RED)==> Committed email templates are stale. Run 'make build-emails' and commit.$(RESET)"
		exit 1
	fi
	@echo "$(GREEN)==> Email build output is up to date$(RESET)"

.PHONY: preview-emails
preview-emails: $(VENV_FOLDER) instance/etc/zope.ini ## Render the committed templates with the committed fixtures and serve them
	# Not `maizzle --watch`: that shows build-time output, with raw
	# ${item/title} still in place. Re-run this target after `make build-emails`.
	@echo "$(GREEN)==> Rendering previews into $(PREVIEW_FOLDER)$(RESET)"
	@EMAILKIT_PREVIEW_DIR=$(PREVIEW_FOLDER) EMAILKIT_PREVIEW_PORT=$(PREVIEW_PORT) \
		$(BIN_FOLDER)/zconsole run instance/etc/zope.conf ./scripts/preview_emails.py

# imio.recipe.emailkit, the second distribution in this repository. Nothing
# below may become a prerequisite of install/sync/test/start/create-site.
RECIPE_FOLDER=$(BACKEND_FOLDER)/recipe
RECIPE_VENV=$(RECIPE_FOLDER)/.venv
BUILDOUT_VENV=$(BACKEND_FOLDER)/var/buildout-venv
BUILDOUT_CFG?=test-buildout.cfg

$(RECIPE_VENV): $(RECIPE_FOLDER)/pyproject.toml ## Environment for the recipe's own suite
	@echo "$(GREEN)==> Install the recipe test environment$(RESET)"
	@if [[ ! -d "$(RECIPE_VENV)" ]]; then uv venv $(UV_VENV_ARGS) $(RECIPE_VENV); fi
	@VIRTUAL_ENV=$(RECIPE_VENV) uv pip install --python $(RECIPE_VENV)/bin/python -q -e "$(RECIPE_FOLDER)[test]"

.PHONY: recipe-test
recipe-test: $(RECIPE_VENV) $(VENV_FOLDER) ## Run imio.recipe.emailkit's own test suite
	# Runs twice: recipe/.venv has buildout but no Plone; .venv has Plone but
	# no buildout. The union covers the whole suite.
	@echo "$(GREEN)==> imio.recipe.emailkit tests (buildout environment)$(RESET)"
	@$(RECIPE_VENV)/bin/python -m pytest $(RECIPE_FOLDER)/tests -q -rs
	@echo "$(GREEN)==> imio.recipe.emailkit tests (Plone runtime environment)$(RESET)"
	@PYTHONPATH=$(RECIPE_FOLDER)/src $(BIN_FOLDER)/python -m pytest $(RECIPE_FOLDER)/tests \
		-q -rs -p no:cacheprovider -c $(RECIPE_FOLDER)/pyproject.toml

$(BUILDOUT_VENV): $(VENV_FOLDER) ## Bootstrap zc.buildout for the acceptance test
	# Built from the same interpreter as .venv, so buildout's generated
	# scripts do not run C extensions built for a different Python version.
	@echo "$(GREEN)==> Bootstrap zc.buildout$(RESET)"
	@mkdir -p $(BACKEND_FOLDER)/var
	@if [[ ! -d "$(BUILDOUT_VENV)" ]]; then uv venv --python $(BIN_FOLDER)/python $(BUILDOUT_VENV); fi
	@VIRTUAL_ENV=$(BUILDOUT_VENV) uv pip install --python $(BUILDOUT_VENV)/bin/python -q \
		"zc.buildout" "zc.recipe.egg" "setuptools"

.PHONY: buildout-test
buildout-test: $(VENV_FOLDER) $(BUILDOUT_VENV) node-check ## Acceptance test: buildout, then bin/compile-emails
	# Eggs are resolved offline from the development virtualenv's
	# site-packages. `test-buildout-pypi.cfg` is the from-PyPI variant.
	@set -euo pipefail
	@site_packages="$$($(BIN_FOLDER)/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
	@echo "$(GREEN)==> buildout, with node/npm/npx REMOVED from PATH$(RESET)"
	@nonode="$$($(BIN_FOLDER)/python -c 'import os; print(os.pathsep.join(p for p in os.environ["PATH"].split(os.pathsep) if p and not any(os.path.exists(os.path.join(p, n)) for n in ("node", "npm", "npx"))))')"
	@env -u VIRTUAL_ENV PATH="$$nonode" PYTHONWARNINGS=ignore \
		$(BUILDOUT_VENV)/bin/buildout -c $(BUILDOUT_CFG) \
		"buildout:eggs-directory=$$site_packages" \
		buildout:eggs-directory-version= buildout:abi-tag-eggs=false
	@for script in compile-emails check-emails preview-emails; do
		test -x "$(BACKEND_FOLDER)/bin/$$script" || { echo "$(RED)bin/$$script was not generated$(RESET)"; exit 1; }
	done
	@echo "$(GREEN)==> bin/compile-emails (kit-mode = path, the default)$(RESET)"
	@$(BACKEND_FOLDER)/bin/compile-emails
	@echo "$(GREEN)==> bin/compile-emails --kit-mode copy (the other mode)$(RESET)"
	@$(BACKEND_FOLDER)/bin/compile-emails --kit-mode copy
	# Checks both packages: the external consumer addon, and imio.emailkit itself.
	@echo "$(GREEN)==> bin/check-emails --package emailkitdemo (lint + staleness)$(RESET)"
	@$(BACKEND_FOLDER)/bin/check-emails --package emailkitdemo
	@echo "$(GREEN)==> bin/check-emails --package imio.emailkit (lint + staleness)$(RESET)"
	@$(BACKEND_FOLDER)/bin/check-emails --package imio.emailkit
	@echo "$(GREEN)==> bin/preview-emails (renders through render() with the fixtures)$(RESET)"
	@$(BACKEND_FOLDER)/bin/preview-emails --no-compile --no-serve
	@echo "$(GREEN)==> Acceptance test passed$(RESET)"

.PHONY: buildout-clean
buildout-clean: ## Remove everything the acceptance test writes
	@echo "$(RED)==> Removing the buildout acceptance-test artifacts$(RESET)"
	@rm -rf $(BACKEND_FOLDER)/bin $(BACKEND_FOLDER)/develop-eggs $(BACKEND_FOLDER)/parts \
		$(BACKEND_FOLDER)/eggs $(BACKEND_FOLDER)/.installed.cfg $(BUILDOUT_VENV) $(RECIPE_VENV)
	@rm -rf $(RECIPE_FOLDER)/tests/consumer/src/emailkitdemo/templates \
		$(RECIPE_FOLDER)/tests/consumer/src/emailkitdemo/emails/node_modules \
		$(RECIPE_FOLDER)/tests/consumer/src/emailkitdemo/emails/.kit \
		$(RECIPE_FOLDER)/tests/consumer/src/emailkitdemo/emails/.maizzle \
		$(RECIPE_FOLDER)/tests/consumer/src/emailkitdemo/emails/package-lock.json \
		$(RECIPE_FOLDER)/tests/consumer/*.egg-info $(RECIPE_FOLDER)/src/*.egg-info

## Add bobtemplates features (check bobtemplates.plone's documentation to get the list of available features)
add: $(VENV_FOLDER)
	@uvx plonecli add $(filter-out $@,$(MAKECMDGOALS))

.PHONY: release
release: $(VENV_FOLDER) ## Create a release
	@echo "$(GREEN)==> Create a release$(RESET)"
	@uv pip install -e ".[release]"
	@uv run fullrelease
