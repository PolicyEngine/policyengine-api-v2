# For github action deployes we use environment variables to configure terraform
# on desktop we use apply files generated either by the infra-policyengine-api bootstrap
# or manual user config
REPO_URL := $(shell git remote get-url origin | sed 's/\.git$$//' | sed 's/git@github.com:/https:\/\/github.com\//')
COMMIT_SHA := $(shell git rev-parse HEAD)
COMMIT_URL := $(REPO_URL)/commit/$(COMMIT_SHA)

# get the project ID
-include ../.bootstrap_settings/project.env
TAG?=desktop
REPO?=api-v2
REGION?=us-central1


#we have to find the sha of the latest images because terraform doesn't know
#that a label got a new sha between deployments
deploy: .terraform
	@echo "Attempting to get the latest docker images with the '${TAG}' tag"
	$(eval FULL_SHA := $(shell gcloud artifacts docker images describe $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO)/policyengine-api-full:$(TAG) --format='value(image_summary.digest)'))
	$(eval SIM_SHA := $(shell gcloud artifacts docker images describe $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO)/policyengine-api-simulation:$(TAG) --format='value(image_summary.digest)'))
	$(eval TAGGER_SHA := $(shell gcloud artifacts docker images describe $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO)/policyengine-api-tagger:$(TAG) --format='value(image_summary.digest)'))
	@echo "Latest Full API SHA: ${FULL_SHA}"
	@echo "Latest Simulation API SHA: ${SIM_SHA}"
	@echo "Running terraform apply with ../.bootstrap_settings/apply.tfvars"
	terraform apply -var-file ../.bootstrap_settings/apply.tfvars -var "full_container_tag=${TAG}@${FULL_SHA}" -var "simulation_container_tag=${TAG}@${SIM_SHA}" -var "tagger_container_tag=${TAG}@${TAGGER_SHA}" -var "commit_url=${COMMIT_URL}" -var "policyengine-us-package-version=desktop" -var "policyengine-uk-package-version=desktop"

attach: .terraform
	@echo "attached"

detach:
	rm -rf .terraform

destroy:
	terraform plan -destroy -var-file ../.bootstrap_settings/apply.tfvars --var "full_container_tag=IGNORED" -var "simulation_container_tag=IGNORED" -var "tagger_container_tag=IGNORE" -var "commit_url=IGNORE" -var "policyengine-us-package-version=IGNORED" -var "policyengine-uk-package-version=IGNORED"
	@echo 'please confirm this IS NOT a production project and then run terraform destroy -var-file ../.bootstrap_settings/apply.tfvars --var "full_container_tag=IGNORED" -var "simulation_container_tag=IGNORED" -var "tagger_container_tag=IGNORE" -var "commit_url=IGNORE" -var "policyengine-us-package-version=IGNORED" -var "policyengine-uk-package-version=IGNORED"'

.terraform: ../.bootstrap_settings/backend.tfvars
	@echo "Initializing terraform"
	terraform init -backend-config ../.bootstrap_settings/backend.tfvars

bootstrap_beta:
	cd ../infra-policyengine-api && make bootstrap_beta
