-include ../../terraform/.bootstrap_settings/project.env


# Helper for pretty output
HELPER := python ../../scripts/ensure_rich.py && python ../../scripts/make_helper.py

# Silent commands by default, use V=1 for verbose
Q = @
ifeq ($(V),1)
    Q =
endif

build: remove_artifacts install checkformat pyright generate test 

remove_artifacts:
	$(Q)$(HELPER) subtask "Removing artifacts" "rm -rf artifacts"

install:
	$(Q)$(HELPER) subtask "Installing dependencies" "uv sync --active --extra test --extra build"

checkformat:
	$(Q)dirs=""; \
	[ -d "src" ] && dirs="$$dirs src"; \
	[ -d "tests" ] && dirs="$$dirs tests"; \
	if [ -n "$$dirs" ]; then \
		$(HELPER) subtask "Checking code format" "black --check $$dirs"; \
	else \
		$(HELPER) subtask "Checking code format" "echo 'No source directories found'"; \
	fi

format:
	$(Q)dirs=""; \
	[ -d "src" ] && dirs="$$dirs src"; \
	[ -d "tests" ] && dirs="$$dirs tests"; \
	if [ -n "$$dirs" ]; then \
		$(HELPER) subtask "Formatting code" "black $$dirs"; \
	else \
		$(HELPER) subtask "Formatting code" "echo 'No source directories found'"; \
	fi

# Default targets that can be overridden - defined only if not already defined
ifndef HAS_CUSTOM_PYRIGHT
pyright:
	$(Q)$(HELPER) subtask "Type checking" "pyright"
endif

ifndef HAS_CUSTOM_TEST
test:
	$(Q)$(HELPER) subtask "Running tests" "pytest"
endif

ifndef HAS_CUSTOM_GENERATE
generate:
	$(Q)$(HELPER) subtask "Code generation" "echo 'No generation target defined'"
endif

update:
	$(Q)$(HELPER) subtask "Updating lockfile" "uv lock --upgrade"
