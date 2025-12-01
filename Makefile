SHELL := /bin/bash


PYTHON_SHORT_VERSION := $(shell echo $(PYTHON_VERSION) | grep -o '[0-9].[0-9]*')

ifeq ($(USE_SYSTEM_PYTHON), true)
	PYTHON_PACKAGE_PATH:=$(shell python -c "import sys; print(sys.path[-1])")
	PYTHON_ENV :=
	PYTHON := python
	PYTHON_VENV :=
else
	PYTHON_PACKAGE_PATH:=.venv/lib/python$(PYTHON_SHORT_VERSION)/site-packages
	PYTHON_ENV :=  . .venv/bin/activate &&
	PYTHON := . .venv/bin/activate && python
	PYTHON_VENV := .venv
endif

# Used to confirm that pip has run at least once
PACKAGE_CHECK:=$(PYTHON_PACKAGE_PATH)/build
PYTHON_DEPS := $(PACKAGE_CHECK)

#
# Make the environement
#

.PHONY: env
env: .venv pip sandbox



.venv:
	uv venv .venv --python 3.14
	
.PHONY: pip
pip: $(PYTHON_VENV)
	uv pip install -e .[dev]

.PHONY: sandbox
sandbox: 
	. .venv/bin/activate && exec /bin/bash -i

#
# Formatting
#

.PHONY: check
check: format ruff_fixes ruff_check ty dapperdata_fixes tomlsort_fixes

.PHONY: format
format: ruff_format ruff_fixes

.PHONY: ruff_format
ruff_format:
	$(PYTHON) -m ruff format src

.PHONY: ruff_fixes
ruff_fixes:
	$(PYTHON) -m ruff check src --fix-only

.PHONY: ruff_check
ruff_check:
	$(PYTHON) -m ruff check src

.PHONY: ty
ty:
	$(PYTHON) -m ty check src

.PHONY: dapperdata_fixes
dapperdata_fixes:
	$(PYTHON) -m dapperdata.cli pretty . --no-dry-run

.PHONY: tomlsort_fixes
tomlsort_fixes:
	$(PYTHON_ENV) toml-sort $$(find . -not -path "./.venv/*" -name "*.toml") -i

.PHONY: spelling
spelling:
	$(PYTHON) -m pylint --load-plugins=pylint.extensions.spelling path/to/your/code

#
# Testing
#


.PHONY: coverage
test:
	$(PYTHON) -m coverage run --branch --source src -m unittest discover
	@$(PYTHON) -m coverage report -m


#
# Packaging
#

.PHONY: docker-build
docker-build:
	docker build -t companion .

.PHONY: docker-run
docker-run:
	docker run -

#
# Common commands
#

.PHONY: rmzone
rmzone:
	rm -rf resources/triaged_images/*/*Zone.Identifier*;
	rm -rf resources/triaged_images/*/*/*Zone.Identifier*;