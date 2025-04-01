build:
	cd libs/policyengine-fastapi && make build
	cd libs/policyengine-api && make build
	cd libs/policyengine-simulation-api && make build
	cd projects/policyengine-api-full && make build
	cd projects/policyengine-api-simulation && make build

dev-api-full:
	echo "Starting API (full) in dev mode"
	cd projects/policyengine-api-full && make dev

dev-api-simulation:
	echo "Starting API (simulation) in dev mode"
	cd projects/policyengine-api-simulation && make dev

dev-api-household:
	echo "Starting API (household) in dev mode"
	cd projects/policyengine-household-api && make dev

dev:
	echo "Starting APIs (full+simulation) in dev mode"
	make dev-api-full & make dev-api-simulation

bootstrap:
	cd terraform/project-policyengine-api && make bootstrap
	
deploy-infra: terraform/.bootstrap_settings
	echo "Publishing API images"
	cd projects/policyengine-api-full && make deploy
	cd projects/policyengine-api-simulation && make deploy
	echo "Deploying infrastructure"
	cd terraform/infra-policyengine-api && make deploy

deploy-project: terraform/.bootstrap_settings
	echo "Deploying project"
	cd terraform/project-policyengine-api && make deploy

deploy: deploy-project deploy-infra

integ-test: 
	cd projects/policyengine-api-full-integ && make integ-test
