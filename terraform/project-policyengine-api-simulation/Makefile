# For github action deployes we use environment variables to configure terraform
# on desktop we use apply files generated either by the project-policyengine-api bootstrap
# or manual user config

# get the project ID
include ../.bootstrap_settings/project.env
TAG?=desktop
REPO?=api-v2
REGION?=us-central1

#we have to find the sha of the latest image because terraform doesn't know
#that a label got a new sha between deployments so if you just said "desktop"
#it would never update again
deploy: .terraform
	@echo "attempting to get the latest docker simulation API image with the 'desktop' tag"
	$(eval SHA := $(shell gcloud artifacts docker images describe $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO)/policyengine-api-simulation:desktop --format='value(image_summary.digest)'))
	@echo "latest SHA is ${SHA}"
	@echo "Running terraform apply with ../.bootstrap_settings/apply.tfvars"
	@echo "Fetching workflow file contents"
	$(eval WORKFLOW := $(shell cat ../../projects/policyengine-api-simulation/workflow.yaml))
	terraform apply -var-file ../.bootstrap_settings/apply.tfvars -var "container_tag=${SHA}"

.terraform: ../.bootstrap_settings/backend.tfvars
	@echo "initializing terraform"
	terraform init -backend-config ../.bootstrap_settings/backend.tfvars
