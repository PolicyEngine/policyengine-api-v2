include ../../common.mk

TAG?=desktop
REPO?=api-v2
REGION?=us-central1
ifdef LOG_DIR
  BUILD_ARGS=--gcs-log-dir ${LOG_DIR}
endif
PROJECT_ID?=PROJECT_ID_NOT_SPECIFIED
WORKER_COUNT?=1

deploy:
	echo "Building ${SERVICE_NAME} docker image"
	cd ../../ && gcloud builds submit --region=${REGION} --substitutions=_IMAGE_TAG=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE_NAME}:${TAG},_SERVICE_NAME=${SERVICE_NAME},_MODULE_NAME=${MODULE_NAME},_WORKER_COUNT=${WORKER_COUNT} ${BUILD_ARGS}

# Always run with a single worker in dev mode to match local desktop environment.
# Sets WORKER_COUNT=1 just for this target.
# Also set ENVIRONMENT=desktop in src/.env file for the app to pick up the correct config.
dev: WORKER_COUNT=1
dev:
	echo "Running ${SERVICE_NAME} dev instance"
	cd src && uv run uvicorn ${MODULE_NAME}:app --reload --port ${DEV_PORT} --workers ${WORKER_COUNT}
