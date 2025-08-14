-include ../../terraform/.bootstrap_settings/project.env

build: remove_artifacts install checkformat pyright generate test 

remove_artifacts:
	echo "Removing artifacts directory"
	rm -rf artifacts

install:
	echo "Downloading dependencies including test and build"
	uv sync --extra test --extra build --active

checkformat:
	echo "Checking python code formatting"
	@dirs=""; \
	[ -d "src" ] && dirs="$$dirs src"; \
	[ -d "tests" ] && dirs="$$dirs tests"; \
	if [ -n "$$dirs" ]; then \
		black --check $$dirs; \
	else \
		echo "Neither 'src' nor 'tests' directory found. Skipping Black formatting."; \
	fi

format:
	echo "Updating python code formatting"
	@dirs=""; \
	[ -d "src" ] && dirs="$$dirs src"; \
	[ -d "tests" ] && dirs="$$dirs tests"; \
	if [ -n "$$dirs" ]; then \
		echo "Running Black on:$$dirs"; \
		black $$dirs; \
	else \
		echo "Neither 'src' nor 'tests' directory found. Skipping Black formatting."; \
	fi

pyright:
	echo "Checking python type usage"
	pyright 

test:
	echo "Running unit tests"
	pytest

generate:
	echo "No code generation target defined"

update:
	uv lock --upgrade
