# Define custom targets before including common.mk
HAS_CUSTOM_GENERATE := 1
HAS_CUSTOM_PYRIGHT := 1

include ./makefile.env
include ../../server_common.local.mk

generate:
	cd src && python -m policyengine_api_full.generate_openapi
	python ./generate_clients.py

pyright:
	$(Q)$(HELPER) subtask "Type checking" "echo 'Skipping - see issue #271'"
