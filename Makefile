LIBDIRS := libs/policyengine-fastapi 
SERVICEDIRS := projects/policyengine-api-full projects/policyengine-api-simulation projects/policyengine-api-tagger
SUBDIRS := $(LIBDIRS) $(SERVICEDIRS)

# Ensure rich is installed before using make_helper
ENSURE_RICH := $(shell python3 ../../scripts/ensure_rich.py 2>&1)
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
	$(Q)echo "→ Testing policyengine-api-full on port 8081..."
	$(Q)docker run -d --name test-api-full \
		-v $$HOME/.config/gcloud/application_default_credentials.json:/root/.config/gcloud/application_default_credentials.json:ro \
		-e GOOGLE_APPLICATION_CREDENTIALS=/root/.config/gcloud/application_default_credentials.json \
		-e GOOGLE_CLOUD_PROJECT=beta-api-v2 \
		-p 8081:8080 policyengine-api-full:test > /dev/null
	$(Q)sleep 15
	$(Q)curl -s http://127.0.0.1:8081/docs > /dev/null 2>&1; echo "✓ policyengine-api-full responding"
	$(Q)docker stop test-api-full > /dev/null && docker rm test-api-full > /dev/null
	$(Q)echo "→ Testing policyengine-api-simulation on port 8082..."
	$(Q)docker run -d --name test-api-sim \
		-v $$HOME/.config/gcloud/application_default_credentials.json:/root/.config/gcloud/application_default_credentials.json:ro \
		-e GOOGLE_APPLICATION_CREDENTIALS=/root/.config/gcloud/application_default_credentials.json \
		-e GOOGLE_CLOUD_PROJECT=beta-api-v2 \
		-p 8082:8080 policyengine-api-simulation:test > /dev/null
	$(Q)sleep 15
	$(Q)curl -s http://127.0.0.1:8082/docs > /dev/null 2>&1; echo "✓ policyengine-api-simulation responding"
	$(Q)docker stop test-api-sim > /dev/null && docker rm test-api-sim > /dev/null
	$(Q)echo "→ Testing policyengine-api-tagger on port 8083..."
	$(Q)docker run -d --name test-api-tag \
		-v $$HOME/.config/gcloud/application_default_credentials.json:/root/.config/gcloud/application_default_credentials.json:ro \
		-e GOOGLE_APPLICATION_CREDENTIALS=/root/.config/gcloud/application_default_credentials.json \
		-e GOOGLE_CLOUD_PROJECT=beta-api-v2 \
		-p 8083:8080 policyengine-api-tagger:test > /dev/null
	$(Q)sleep 15
	$(Q)curl -s http://127.0.0.1:8083/docs > /dev/null 2>&1; echo "✓ policyengine-api-tagger responding"
	$(Q)docker stop test-api-tag > /dev/null && docker rm test-api-tag > /dev/null
	$(Q)$(HELPER) complete "Docker tests completed"

docker-check: docker-build docker-test
	$(Q)$(HELPER) complete "Docker build and test completed"

docker-debug:
	$(Q)$(HELPER) section "Docker container diagnostics"
	@echo "Active containers:"
	@docker ps --format "table {{.Names}}\t{{.Ports}}\t{{.Status}}"
	@echo ""
	@if [ -n "$$(docker ps -q -f name=test-custom)" ]; then \
		echo "test-custom container logs:"; \
		docker logs test-custom --tail 30; \
		echo ""; \
		echo "Test endpoints:"; \
		echo "  curl http://localhost:8090/docs"; \
		curl -s -o /dev/null -w "  Response: %{http_code}\n" http://localhost:8090/docs || true; \
	else \
		echo "No test-custom container running"; \
	fi

docker-test-custom:
	$(Q)$(HELPER) section "Testing custom Docker image"
	@if [ -z "$(IMAGE)" ]; then \
		echo "Error: IMAGE variable not set"; \
		echo "Usage: make docker-test-custom IMAGE=<image:tag> [PORT=8090]"; \
		echo "Examples:"; \
		echo "  make docker-test-custom IMAGE=my-image:latest"; \
		echo "  make docker-test-custom IMAGE=gcr.io/project/image:tag PORT=8091"; \
		exit 1; \
	fi
	@# Clean up any existing container
	@docker rm -f test-custom 2>/dev/null || true
	@# Set default port if not provided
	$(eval PORT ?= 8090)
	$(Q)$(HELPER) stream "Testing $(IMAGE) on port $(PORT)" "\
		trap 'echo \"\" && echo \"→ Stopping container...\" && docker stop test-custom > /dev/null && docker rm test-custom > /dev/null && echo \"✓ Container stopped and removed\" && exit 0' INT && \
		echo '→ Pulling image...' && \
		docker pull $(IMAGE) && \
		echo '→ Starting container mapping localhost:$(PORT) -> container:8080...' && \
		docker run -d --name test-custom \
			-v $$HOME/.config/gcloud/application_default_credentials.json:/root/.config/gcloud/application_default_credentials.json:ro \
			-e GOOGLE_APPLICATION_CREDENTIALS=/root/.config/gcloud/application_default_credentials.json \
			-e GOOGLE_CLOUD_PROJECT=beta-api-v2 \
			-p $(PORT):8080 \
			--platform linux/amd64 \
			$(IMAGE) && \
		echo '→ Container started. Access at http://localhost:$(PORT)' && \
		echo '→ Waiting for service to start...' && \
		for i in 1 2 3 4 5 6; do \
			sleep 5; \
			echo '  Checking http://localhost:$(PORT)/docs (attempt' \$$i'/6)...' && \
			if curl -s http://127.0.0.1:$(PORT)/docs > /dev/null 2>&1; then \
				echo '✓ Service responding on port $(PORT)'; \
				echo '→ Access at: http://localhost:$(PORT)/docs'; \
				echo '→ Press Ctrl+C to stop the container'; \
				echo ''; \
				docker logs -f test-custom; \
				break; \
			elif [ \$$i = 6 ]; then \
				echo '✗ Service not responding after 30s on port $(PORT). Showing logs:'; \
				echo '→ Press Ctrl+C to stop the container'; \
				docker logs -f test-custom; \
			fi; \
		done"
	$(Q)$(HELPER) complete "Custom image test completed"
