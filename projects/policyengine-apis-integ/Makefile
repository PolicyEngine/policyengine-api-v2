include ../../common.mk
US_COUNTRY_PACKAGE_VERSION := $(shell ../../projects/policyengine-api-simulation/dump_package_version.sh policyengine-us)
UK_COUNTRY_PACKAGE_VERSION := $(shell ../../projects/policyengine-api-simulation/dump_package_version.sh policyengine-uk)

test: integ-test
	echo "Skipping default test target in favor of integ-test"

integ-test:
	echo "Running integration tests"
	$(if $(FULL_API_ACCESS_TOKEN),FULL_INTEG_TEST_ACCESS_TOKEN='$(FULL_API_ACCESS_TOKEN)') \
	$(if $(SIMULATION_API_ACCESS_TOKEN),SIMULATION_INTEG_TEST_ACCESS_TOKEN='$(SIMULATION_API_ACCESS_TOKEN)') \
	$(if $(FULL_API_URL),FULL_INTEG_TEST_BASE_URL='$(FULL_API_URL)') \
	$(if $(SIMULATION_API_URL),SIMULATION_INTEG_TEST_BASE_URL='$(SIMULATION_API_URL)') \
	$(if $(TF_VAR_project_id),WORKFLOW_INTEG_TEST_PROJECT_ID='$(TF_VAR_project_id)') \
	$(if $(PROJECT_ID),WORKFLOW_INTEG_TEST_PROJECT_ID='$(PROJECT_ID)') \
        WORKFLOW_INTEG_TEST_US_MODEL_VERSION='$(US_COUNTRY_PACKAGE_VERSION)' \
	pytest -n auto
