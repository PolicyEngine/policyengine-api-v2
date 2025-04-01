TAG?=desktop
REPO?=api-v2
REGION?=us-central1
ifdef LOG_DIR
  BUILD_ARGS=--gcs-log-dir ${LOG_DIR}
endif
PROJECT_ID?=

# Check if the depoyment project env file exists and include it if so. That way build target still works even if you haven't set up
# a gcp project (which usually you wouldn't bother doing)
ifneq (,$(wildcard ../../terraform/.bootstrap_settings/project.env))
    #load PROJECT_ID from the bootstrapped project
    include ../../terraform/.bootstrap_settings/project.env
endif

deploy:
	rm -rf artifacts/staging
	mkdir -p artifacts/staging/libs
	cp -R ../../libs/* artifacts/staging/libs/
	gcloud builds submit --region=${REGION} --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/policyengine-api-simulation:${TAG} ${BUILD_ARGS}

build:
	poetry install
	poetry update
	poetry run pytest tests

dev:
	poetry run fastapi dev src/policyengine_api_simulation/main.py --port 8001