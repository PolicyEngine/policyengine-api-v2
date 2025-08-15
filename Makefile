LIBDIRS := libs/policyengine-fastapi 
SERVICEDIRS := projects/policyengine-api-full projects/policyengine-api-simulation projects/policyengine-api-tagger
SUBDIRS := $(LIBDIRS) $(SERVICEDIRS)

# Helper for pretty output
HELPER := python3 scripts/make_helper.py

# Silent commands by default, use V=1 for verbose
Q = @
ifeq ($(V),1)
    Q =
endif

build:
	$(Q)$(HELPER) section "Building all projects"
	$(Q)set -e; \
	for dir in $(SUBDIRS); do \
		base=$$(basename $$dir); \
		$(HELPER) task "Building $$base" "$(MAKE) -C $$dir build"; \
	done
	$(Q)$(HELPER) complete "Build completed"

update:
	$(Q)$(HELPER) section "Updating dependencies"
	$(Q)set -e; \
	for dir in $(SUBDIRS); do \
		base=$$(basename $$dir); \
		$(HELPER) task "Updating $$base" "$(MAKE) -C $$dir update"; \
	done
	$(Q)$(HELPER) complete "Dependencies updated"

test:
	$(Q)$(HELPER) section "Running tests"
	$(Q)for dir in $(SUBDIRS); do \
		base=$$(basename $$dir); \
		$(HELPER) task "Testing $$base" "$(MAKE) -C $$dir test"; \
	done
	$(Q)$(HELPER) complete "Tests completed"

dev-api-full:
	$(Q)$(HELPER) task "Starting API (full) in dev mode" "cd projects/policyengine-api-full && make dev"

dev-api-simulation:
	$(Q)$(HELPER) task "Starting API (simulation) in dev mode" "cd projects/policyengine-api-simulation && make dev"

dev-api-household:
	$(Q)$(HELPER) task "Starting API (household) in dev mode" "cd projects/policyengine-household-api && make dev"

dev-api-tagger:
	$(Q)$(HELPER) task "Starting API (tagger) in dev mode" "cd projects/policyengine-tagger-api && make dev"

dev:
	$(Q)$(HELPER) section "Starting development servers"
	$(Q)$(HELPER) task "Starting APIs (full+simulation)" "make dev-api-full & make dev-api-simulation"

bootstrap:
	$(Q)$(HELPER) task "Bootstrapping terraform" "cd terraform/project-policyengine-api && make bootstrap"

attach:
	$(Q)$(HELPER) section "Attaching terraform state"
	$(Q)$(HELPER) task "Attaching project state" "$(MAKE) -C terraform/project-policyengine-api attach"
	$(Q)$(HELPER) task "Attaching infrastructure state" "$(MAKE) -C terraform/infra-policyengine-api attach"
	$(Q)$(HELPER) complete "Terraform state attached"

detach:
	$(Q)$(HELPER) section "Detaching terraform state"
	$(Q)$(HELPER) task "Detaching project state" "$(MAKE) -C terraform/project-policyengine-api detach"
	$(Q)$(HELPER) task "Detaching infrastructure state" "$(MAKE) -C terraform/infra-policyengine-api detach"
	$(Q)$(HELPER) complete "Terraform state detached"

deploy-infra: terraform/.bootstrap_settings
	$(Q)$(HELPER) section "Deploying infrastructure"
	$(Q)$(HELPER) task "Publishing API (full) image" "cd projects/policyengine-api-full && make deploy"
	$(Q)$(HELPER) task "Publishing API (simulation) image" "cd projects/policyengine-api-simulation && make deploy"
	$(Q)$(HELPER) task "Publishing API (tagger) image" "cd projects/policyengine-api-tagger && make deploy"
	$(Q)$(HELPER) task "Deploying terraform infrastructure" "cd terraform/infra-policyengine-api && make deploy"
	$(Q)$(HELPER) complete "Infrastructure deployed"

deploy-project: terraform/.bootstrap_settings
	$(Q)$(HELPER) task "Deploying project configuration" "cd terraform/project-policyengine-api && make deploy"

deploy: 
	$(Q)$(HELPER) section "Full deployment"
	$(Q)$(MAKE) deploy-project
	$(Q)$(MAKE) deploy-infra
	$(Q)$(HELPER) complete "Deployment completed"

integ-test: 
	$(Q)$(HELPER) task "Running integration tests" "$(MAKE) -C projects/policyengine-apis-integ"
