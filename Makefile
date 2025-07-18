LIBDIRS := libs/policyengine-fastapi libs/policyengine-api libs/policyengine-simulation-api 
SERVICEDIRS := projects/policyengine-api-full projects/policyengine-api-simulation projects/policyengine-api-tagger
SUBDIRS := $(LIBDIRS) $(SERVICEDIRS)

build:
	for dir in $(SUBDIRS); do \
		$(MAKE) -C $$dir build; \
	done

update:
	for dir in $(SUBDIRS); do \
		$(MAKE) -C $$dir update; \
	done

test:
	for dir in $(SUBDIRS); do \
		$(MAKE) -C $$dir test; \
	done

dev-api-full:
	echo "Starting API (full) in dev mode"
	cd projects/policyengine-api-full && make dev

dev-api-simulation:
	echo "Starting API (simulation) in dev mode"
	cd projects/policyengine-api-simulation && make dev

dev-api-household:
	echo "Starting API (household) in dev mode"
	cd projects/policyengine-household-api && make dev

dev-api-tagger:
	echo "Starting API (tagger) in dev mode"
	cd projects/policyengine-tagger-api && make dev

dev:
	echo "Starting APIs (full+simulation) in dev mode"
	make dev-api-full & make dev-api-simulation

bootstrap:
	cd terraform/project-policyengine-api && make bootstrap
	
deploy-infra: terraform/.bootstrap_settings
	echo "Publishing API images"
	cd projects/policyengine-api-full && make deploy
	cd projects/policyengine-api-simulation && make deploy
	cd projects/policyengine-api-tagger && make deploy
	echo "Deploying infrastructure"
	cd terraform/infra-policyengine-api && make deploy

deploy-project: terraform/.bootstrap_settings
	echo "Deploying project"
	cd terraform/project-policyengine-api && make deploy

deploy: deploy-project deploy-infra

integ-test: 
	echo "Running integration tests"
	$(MAKE) -C projects/policyengine-apis-integ
