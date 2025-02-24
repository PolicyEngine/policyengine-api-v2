build:
	cd libs/policyengine-fastapi && make build
	cd libs/policyengine-api && make build
	cd projects/policyengine-api-full && make build
	cd projects/policyengine-api-simulation && make build

dev-api-full:
	echo "Starting API (full) in dev mode"
	cd projects/policyengine-api-full && make dev

dev-api-simulation:
	echo "Starting API (simulation) in dev mode"
	cd projects/policyengine-api-simulation && make dev

dev:
	echo "Starting APIs (full+simulation) in dev mode"
	make dev-api-full & make dev-api-simulation
	
deploy-infra: terraform/.bootstrap_settings
	echo "Deploying infrastructure"
	cd terraform/infra-policyengine-api && make deploy

deploy-api-full: terraform/.bootstrap_settings
	echo "Publishing API (full) image"
	cd projects/policyengine-api-full && make deploy
	echo "Deploying API (full)"
	cd terraform/project-policyengine-api-full && make deploy

deploy-api-simulation: terraform/.bootstrap_settings
	echo "Deploying API (simulation)"
	cd projects/policyengine-api-simulation && make deploy
	echo "Deploying API (full)"
	cd terraform/project-policyengine-api-simulation && make deploy

deploy: deploy-infra deploy-api-full deploy-services