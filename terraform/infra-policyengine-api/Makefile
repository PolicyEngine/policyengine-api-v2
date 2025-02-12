PROJECT_ID?=PROVIDE PROJECT ID
REGION?=us-central1
REPO?=api-v2
TAG?=desktop
us-central1-docker.pkg.dev/api-v2-dev-450717/api-v2/policyengine-api-household:desktop

deploy:
	terraform apply -var-file=apply.tfvars -var container_image=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/policyengine-api-household:${TAG}

init:
	terraform init -backend-config=backend.tfvars