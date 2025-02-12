POETRY_DIRS = libs/policyengine-fastapi \
              libs/policyengine-api \
              projects/policyengine-api-main \
			  projects/policyengine-api-simulation \

install:
	@for dir in $(POETRY_DIRS); do \
		echo "Installing dependencies in $$dir..."; \
		cd $$dir && poetry install && cd -; \
	done

install-pip:
	uv pip install -e projects/policyengine-api-main
	uv pip install -e projects/policyengine-api-simulation
	uv pip install -e libs/policyengine-api
	uv pip install -e libs/policyengine-fastapi

dev-simulation-api:
	cd projects/policyengine-api-simulation && fastapi dev src/policyengine_simulation_api/main.py