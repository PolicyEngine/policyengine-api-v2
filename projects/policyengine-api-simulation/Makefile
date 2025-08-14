include ./makefile.env
include ../../server_common.local.mk

generate:
	mkdir -p artifacts
	cd src && python -m policyengine_api_simulation.generate_openapi > ../artifacts/openapi.json
	python ./generate_clients.py

test:
	echo "No tests to run"
