### Defensive settings for make:
#     https://tech.davis-hansson.com/p/make/
SHELL:=bash
.ONESHELL:
# No -x: the recipes below are long, and tracing every line buries the
# actual diff output that check-emails exists to show.
.SHELLFLAGS:=-eu -o pipefail -O inherit_errexit -c
.SILENT:
.DELETE_ON_ERROR:
MAKEFLAGS+=--warn-undefined-variables
MAKEFLAGS+=--no-builtin-rules

# We like colors
# From: https://coderwall.com/p/izxssa/colored-makefile-for-golang-projects
RED=`tput setaf 1`
GREEN=`tput setaf 2`
RESET=`tput sgr0`
YELLOW=`tput setaf 3`

# Python checks
UV?=uv

# installed?
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

# Environment variables to be exported
export PYTHONWARNINGS := ignore
export DOCKER_BUILDKIT := 1

# ---------------------------------------------------------------------------
# Email build (SPEC §5 in its Phase 1 Makefile form -- see §9's sequencing note:
# `imio.emailkit` authors its own templates long before `imio.recipe.emailkit`
# exists, and `bin/preview-emails` in Phase 4 is this generalised, not new
# invention).
#
# NODE IS A DEVELOPER/CI TOOL ONLY (SPEC §1). No target below is a dependency of
# `install`, `sync`, `test`, `start` or `create-site`, and none of them may ever
# become one: making Node reachable from a deployment path would put it in front
# of ~350 production applications.
# ---------------------------------------------------------------------------

NPM?=npm
NPX?=npx

EMAILS_FOLDER=$(BACKEND_FOLDER)/emails
# Hand-authored plaintext twins: source, copied into the package by build-emails
# because `maizzle build` empties its own output directory.
TWINS_FOLDER=$(BACKEND_FOLDER)/emails/twins

# Where the committed build output lives. Two destinations because the two kinds
# of artifact are addressed differently at runtime: templates are looked up by
# name through the entry point (§4), overrides by the dotted path of the file
# they shadow (§8.1).
#
# `emails/maizzle.config.js` writes here directly -- `output.path` for templates,
# `useOutputPath()` + `emailkit.overridesPath` for the two jbot overrides -- and
# emits `.pt` straight away via `output.extension` (docs/DECISIONS.md, §10.2), so
# there is no intermediate `dist/` and no rename step. These paths are therefore
# *duplicated* between the two files; keep them in step.
PACKAGE_FOLDER=$(BACKEND_FOLDER)/src/imio/emailkit
TEMPLATES_FOLDER=$(PACKAGE_FOLDER)/templates
OVERRIDES_FOLDER=$(PACKAGE_FOLDER)/browser/overrides

PREVIEW_FOLDER?=$(BACKEND_FOLDER)/var/preview
PREVIEW_PORT?=8090

all: build

# Add the following 'help' target to your Makefile
# And add help text after each target name starting with '\#\#'
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
	# setuptools artefacts: a stale build/ silently keeps shipping files that
	# have since been deleted from the source tree.
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

# Explicit paths: ruff invoked with no path walks the whole repo, which is how a
# formatter got into SPEC.md and reflowed the approved API example.
RUFF_TARGETS=src tests scripts

# Hand-written markup and configuration only: the compiled .pt files under
# templates/ and browser/overrides/ are generated artifacts (see lint target).
ZPRETTY_TARGETS=$(shell find src -name '*.zcml' -o -name '*.xml' | sort)

# QA
.PHONY: lint
lint: ## Check code base according to Plone standards
	@echo "$(GREEN)==> Lint codebase$(RESET)"
	# No --fix here: a lint target that rewrites files exits non-zero *because*
	# it fixed something, so a clean tree fails on the first run and passes on
	# the second. Checking is `lint`, rewriting is `format`.
	@uvx ruff@latest check --no-fix --config $(BACKEND_FOLDER)/pyproject.toml $(RUFF_TARGETS)
	@uvx pyroma@latest -d .
	@uvx check-python-versions@latest .
	# zpretty must never see the compiled .pt files. They are Maizzle build
	# output, and zpretty's formatting is not Maizzle's, so reformatting them
	# would make `check-emails` fail forever: the two gates would fight, and the
	# staleness gate is the one that protects production. Only hand-written
	# templates and ZCML/XML are linted.
	@uvx zpretty@latest --check $(ZPRETTY_TARGETS)

.PHONY: format
format: ## Fix code base according to Plone standards
	@echo "$(GREEN)==> Format codebase$(RESET)"
	@uvx ruff@latest check --select I --fix --config $(BACKEND_FOLDER)/pyproject.toml $(RUFF_TARGETS)
	@uvx ruff@latest format --config $(BACKEND_FOLDER)/pyproject.toml $(RUFF_TARGETS)
	@uvx zpretty@latest -i $(ZPRETTY_TARGETS)

.PHONY: check
check: format lint ## Check and fix code base according to Plone standards

# SPEC §5's `bin/check-emails`, gate (2): the authoring lint.
#
# The `.vue` sources, not the compiled output -- these are the §3 authoring rules,
# and every one of them catches a mistake that produced a *successful* Maizzle
# build. Two of them (`style-placeholder`, `comment-double-dash`) are invisible
# until a mail client or Chameleon sees the result, which is why this is a gate
# rather than a style preference. `--list-rules` explains all eight.
#
# Deliberately Node-free and dependency-free: it is plain-regex text processing in
# the egg (`imio.emailkit.lint`), so `bin/check-emails` can call the very same
# module and the two gates cannot drift. It runs through the venv only because
# `python -m imio.emailkit.lint` imports the package; the module itself needs
# nothing but the standard library, so `python src/imio/emailkit/lint.py <paths>`
# works with a bare interpreter too.
LINT_EMAILS_TARGETS?=$(EMAILS_FOLDER)/src/templates $(PACKAGE_FOLDER)/kit

.PHONY: lint-emails
lint-emails: $(VENV_FOLDER) ## Authoring lint (SPEC §5 gate 2) of the .vue sources
	@echo "$(GREEN)==> Linting email sources against SPEC §3's authoring rules$(RESET)"
	@$(BIN_FOLDER)/python -m imio.emailkit.lint $(LINT_EMAILS_TARGETS)

# i18n
.PHONY: i18n
i18n: $(VENV_FOLDER) ## Update locales
	@echo "$(GREEN)==> Updating locales$(RESET)"
	@$(BIN_FOLDER)/python -m imio.emailkit.locales

# Tests
.PHONY: test
test: $(VENV_FOLDER) ## run tests
	@$(BIN_FOLDER)/pytest

.PHONY: test-coverage
test-coverage: $(VENV_FOLDER) ## run tests with coverage
	@$(BIN_FOLDER)/pytest --cov=imio.emailkit --cov-report term-missing

.PHONY: update-golden
update-golden: $(VENV_FOLDER) ## Regenerate the golden snapshots (deliberate, never automatic)
	@echo "$(YELLOW)==> Regenerating golden files -- review the diff before committing$(RESET)"
	# Both harnesses: this package's own templates and the two dummy consumer
	# add-ons. Leaving the dummies out meant their snapshots silently went stale,
	# which is precisely the failure golden files exist to catch.
	@EMAILKIT_UPDATE_GOLDEN=1 $(BIN_FOLDER)/pytest tests/test_golden.py tests/dummies -q -rs

# ---------------------------------------------------------------------------
# Emails (Node)
# ---------------------------------------------------------------------------

.PHONY: node-check
node-check:
	@if ! command -v $(NPM) >/dev/null 2>&1; then
		echo "$(RED)==> $(NPM) not found. Node is required for the email targets only;$(RESET)"
		echo "$(RED)    installing, testing and running this add-on never needs it.$(RESET)"
		exit 1
	fi

.PHONY: emails-deps
emails-deps: node-check ## Install the Maizzle toolchain (npm ci when a lockfile exists)
	# SPEC §5: `npm ci` "only if node_modules is stale vs. lockfile". `npm ci`
	# needs a lockfile, so fall back to `npm install` while there is none -- which
	# also creates it, after which every later run is the reproducible path.
	@cd $(EMAILS_FOLDER)
	@if [[ -e node_modules && -f package-lock.json && node_modules -nt package-lock.json ]]; then
		echo "$(YELLOW)==> node_modules is up to date$(RESET)"
	elif [[ -f package-lock.json ]]; then
		echo "$(GREEN)==> npm ci$(RESET)"
		$(NPM) ci
	else
		echo "$(YELLOW)==> No package-lock.json yet; running npm install to create it$(RESET)"
		$(NPM) install
	fi

.PHONY: build-emails
build-emails: emails-deps ## Compile emails/ into the package (templates/ + browser/overrides/)
	# The build writes straight into the package: `output.path` for the
	# discovered templates, `useOutputPath()` for the two jbot overrides. The
	# resulting `.pt` files are the runtime artifact and are committed.
	@echo "$(GREEN)==> Compiling email templates$(RESET)"
	@mkdir -p $(TEMPLATES_FOLDER) $(OVERRIDES_FOLDER)
	@cd $(EMAILS_FOLDER) && $(NPX) maizzle build
	# `maizzle build` EMPTIES its output directory, silently, and 6.0.7 has no
	# option to stop it -- it deleted a committed hand-authored twin. So the
	# twins live in emails/twins/ as source and are copied in afterwards. SPEC §4
	# resolves them as <directory>/<name>.txt.pt, which is what this produces.
	@if compgen -G "$(TWINS_FOLDER)/*.txt.pt" > /dev/null; then \
		cp -a $(TWINS_FOLDER)/*.txt.pt $(TEMPLATES_FOLDER)/; \
		echo "$(GREEN)==> Copied hand-authored plaintext twins$(RESET)"; \
	fi
	@echo "$(GREEN)==> Done. Commit the .pt files -- they are what production renders.$(RESET)"

.PHONY: check-emails
check-emails: emails-deps lint-emails ## SPEC §5's two gates: authoring lint, then staleness
	# SPEC §5's `bin/check-emails`, both gates in one target.
	#
	# Gate (2), the authoring lint, runs FIRST -- as a prerequisite -- because it
	# reads the sources and a source-level mistake explains a stale or broken
	# build, not the other way round. Several of its rules describe failures that
	# compile cleanly and only surface at runtime, so hearing about them before
	# the diff is the useful order.
	#
	# Gate (1), staleness. Phase 0 verified the build is deterministic (two
	# consecutive builds byte-identical) with `html.format: true`, which is what
	# makes a byte diff meaningful and keeps the diff line-granular.
	#
	# The build has no configurable alternate destination -- it writes into the
	# package by design -- so the committed output is snapshotted to a tmpdir,
	# the build runs in place, the two are compared, and the snapshot is restored.
	# The restore is on a trap: a `check` target that leaves your working tree
	# holding a build you did not ask for is a target people stop running.
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
	# The two-stage dev loop of SPEC §5, minus the file watcher.
	#
	# Maizzle's own --watch is explicitly rejected by §5: it shows *build-time*
	# output -- raw ${item/title}, unexpanded tal:repeat -- "a miserable
	# authoring loop". So this renders through render() with the committed
	# fixtures (§7), which is what the mail will actually look like.
	#
	# DEFERRED, on purpose: watching sources + live reload. Re-run the target
	# after `make build-emails`. Wiring a watcher to a process that has to hold a
	# ZODB connection open is the part with real design in it, and it belongs with
	# `bin/preview-emails` in Phase 4 rather than half-built here.
	@echo "$(GREEN)==> Rendering previews into $(PREVIEW_FOLDER)$(RESET)"
	@EMAILKIT_PREVIEW_DIR=$(PREVIEW_FOLDER) EMAILKIT_PREVIEW_PORT=$(PREVIEW_PORT) \
		$(BIN_FOLDER)/zconsole run instance/etc/zope.conf ./scripts/preview_emails.py

# ---------------------------------------------------------------------------
# imio.recipe.emailkit -- the second distribution in this repository, and the
# SPEC §9 phase 4 acceptance test that runs it through a real buildout.
#
# Nothing below is a prerequisite of install / sync / test / start / create-site,
# and nothing below may become one. `buildout-test` deliberately runs buildout
# with node, npm and npx removed from PATH, because SPEC §5's "Explicitly
# rejected" section is a hard boundary: compiling at buildout time would make
# Node a production dependency across ~350 applications.
# ---------------------------------------------------------------------------

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
	# Run twice, in two environments, because no single one has everything and a
	# skipped test proves nothing:
	#
	#  1. recipe/.venv has zc.buildout and zc.recipe.egg, so the recipe class is
	#     exercised against the real pkg_resources types. It has no Plone, so the
	#     two tests that need the runtime skip there.
	#  2. .venv has the runtime, so those two run: the entry-point-group drift
	#     check (the one string this distribution duplicates on purpose) and the
	#     theme-token check. test_recipe.py skips there for lack of buildout.
	#
	# The union covers every test. Neither run alone does, so both run in full and
	# the skip counts are the record of which half covered what.
	@echo "$(GREEN)==> imio.recipe.emailkit tests (buildout environment)$(RESET)"
	@$(RECIPE_VENV)/bin/python -m pytest $(RECIPE_FOLDER)/tests -q -rs
	@echo "$(GREEN)==> imio.recipe.emailkit tests (Plone runtime environment)$(RESET)"
	@PYTHONPATH=$(RECIPE_FOLDER)/src $(BIN_FOLDER)/python -m pytest $(RECIPE_FOLDER)/tests \
		-q -rs -p no:cacheprovider -c $(RECIPE_FOLDER)/pyproject.toml

$(BUILDOUT_VENV): $(VENV_FOLDER) ## Bootstrap zc.buildout for the acceptance test
	# Built from the SAME interpreter as .venv, deliberately. The harness resolves
	# eggs out of .venv's site-packages, and buildout's own generated scripts run
	# under this interpreter -- so a version mismatch puts 3.12 C extensions on a
	# 3.10 path and the scripts die with `No module named '_cffi_backend'`, which
	# names nothing recognisable. Measured, not hypothetical.
	@echo "$(GREEN)==> Bootstrap zc.buildout$(RESET)"
	@mkdir -p $(BACKEND_FOLDER)/var
	@if [[ ! -d "$(BUILDOUT_VENV)" ]]; then uv venv --python $(BIN_FOLDER)/python $(BUILDOUT_VENV); fi
	@VIRTUAL_ENV=$(BUILDOUT_VENV) uv pip install --python $(BUILDOUT_VENV)/bin/python -q \
		"zc.buildout" "zc.recipe.egg" "setuptools"

.PHONY: buildout-test
buildout-test: $(VENV_FOLDER) $(BUILDOUT_VENV) node-check ## SPEC §9 phase 4 acceptance: buildout, then bin/compile-emails
	# `git clone && buildout && bin/compile-emails`, which is what §9 asks for.
	#
	# Eggs are resolved offline from the development virtualenv's site-packages
	# rather than downloaded: same recipe, same working set, same generated
	# scripts, no network. `test-buildout-pypi.cfg` is the from-PyPI variant for
	# anyone who wants to check the download path too.
	@set -euo pipefail
	@site_packages="$$($(BIN_FOLDER)/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
	@echo "$(GREEN)==> buildout, with node/npm/npx REMOVED from PATH$(RESET)"
	# The hard boundary of SPEC §5, tested rather than asserted: with
	# `compile-on-install` at its default the whole run must succeed on a machine
	# that has no Node at all.
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
	@echo "$(GREEN)==> bin/compile-emails --kit-mode copy (SPEC §5's other mode)$(RESET)"
	@$(BACKEND_FOLDER)/bin/compile-emails --kit-mode copy
	# Both packages, both gates. The external consumer addon is what proves the
	# wiring end to end; imio.emailkit is its own first consumer (SPEC §4), so it
	# goes through the identical generated script rather than being trusted
	# because `make lint-emails` covers it separately.
	@echo "$(GREEN)==> bin/check-emails --package emailkitdemo (both gates)$(RESET)"
	@$(BACKEND_FOLDER)/bin/check-emails --package emailkitdemo
	@echo "$(GREEN)==> bin/check-emails --package imio.emailkit (both gates)$(RESET)"
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
