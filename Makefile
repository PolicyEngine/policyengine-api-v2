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
	$(Q)$(HELPER) stream "Starting API (full) in dev mode" "cd projects/policyengine-api-full && make dev"

dev-api-simulation:
	$(Q)$(HELPER) stream "Starting API (simulation) in dev mode" "cd projects/policyengine-api-simulation && make dev"

dev-api-household:
	$(Q)$(HELPER) stream "Starting API (household) in dev mode" "cd projects/policyengine-household-api && make dev"

dev-api-tagger:
	$(Q)$(HELPER) stream "Starting API (tagger) in dev mode" "cd projects/policyengine-tagger-api && make dev"

dev:
	$(Q)$(HELPER) section "Starting development servers"
	$(Q)$(HELPER) stream "Starting APIs (full+simulation)" "make dev-api-full & make dev-api-simulation"

dev-setup:
	$(Q)$(HELPER) section "Setting up development environment"
	$(Q)set -e; \
	for dir in $(SUBDIRS); do \
		base=$$(basename $$dir); \
		$(HELPER) task "Installing $$base dependencies" "cd $$dir && uv sync --active --extra test --extra build"; \
	done
	$(Q)$(HELPER) complete "Development setup completed"

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

docker-build:
	$(Q)$(HELPER) section "Building Docker images"
	$(Q)$(HELPER) stream "Building policyengine-api-full image" "docker build -f projects/policyengine-api-full/Dockerfile -t policyengine-api-full:test ."
	$(Q)$(HELPER) stream "Building policyengine-api-simulation image" "docker build -f projects/policyengine-api-simulation/Dockerfile -t policyengine-api-simulation:test ."
	$(Q)$(HELPER) stream "Building policyengine-api-tagger image" "docker build -f projects/policyengine-api-tagger/Dockerfile -t policyengine-api-tagger:test ."
	$(Q)$(HELPER) complete "Docker images built"

docker-test:
	$(Q)$(HELPER) section "Testing Docker images"
	$(Q)$(HELPER) stream "Testing policyengine-api-full startup" "\
		echo '→ Starting container on port 8081...' && \
		docker run -p 8081:8080 policyengine-api-full:test && \
		echo '→ Waiting for startup (15 seconds)...' && \
		sleep 15 && \
		echo '→ Checking health endpoint...' && \
		curl -f http://localhost:8081/health && \
		echo && echo '→ Stopping container...' && \
		docker stop test-api-full && \
		echo '✓ policyengine-api-full test passed'"
	$(Q)$(HELPER) stream "Testing policyengine-api-simulation startup" "\
		echo '→ Starting container on port 8082...' && \
		docker run -p 8082:8080 policyengine-api-simulation:test && \
		echo '→ Waiting for startup (15 seconds)...' && \
		sleep 15 && \
		echo '→ Checking health endpoint...' && \
		curl -f http://localhost:8082/health && \
		echo && echo '→ Stopping container...' && \
		docker stop test-api-sim && \
		echo '✓ policyengine-api-simulation test passed'"
	$(Q)$(HELPER) stream "Testing policyengine-api-tagger startup" "\
		echo '→ Starting container on port 8083...' && \
		docker run -p 8083:8080 policyengine-api-tagger:test && \
		echo '→ Waiting for startup (15 seconds)...' && \
		sleep 15 && \
		echo '→ Checking health endpoint...' && \
		curl -f http://localhost:8083/health && \
		echo && echo '→ Stopping container...' && \
		docker stop test-api-tag && \
		echo '✓ policyengine-api-tagger test passed'"
	$(Q)$(HELPER) complete "Docker tests completed"

docker-check: docker-build docker-test
	$(Q)$(HELPER) complete "Docker build and test completed"
