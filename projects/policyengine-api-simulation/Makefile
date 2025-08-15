# Define custom targets before including common.mk
HAS_CUSTOM_GENERATE := 1
HAS_CUSTOM_TEST := 1

include ./makefile.env
include ../../server_common.local.mk

generate:
	cd src && python -m policyengine_api_simulation.generate_openapi
	python ./generate_clients.py

test:
	$(Q)$(HELPER) subtask "Running tests" "echo 'No tests configured for simulation API'"
