include ./makefile.env
include ../../server_common.local.mk

generate:
	mkdir -p artifacts
	cd src && uv run python -m policyengine_api_full.generate_openapi > ../artifacts/openapi.json
	mvn -f ./generate_clients.pom.xml clean generate-sources

pyright:
	echo "policyengine_api/api is broken, but pyright exclude by directory is unusable. Skipping." # https://github.com/microsoft/pyright/issues/10159
	echo "https://github.com/PolicyEngine/policyengine-api-v2/issues/271 to address this"
