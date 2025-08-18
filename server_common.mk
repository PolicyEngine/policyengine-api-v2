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

dev:
	echo "Running ${SERVICE_NAME} dev instance"
	cd src && uv run uvicorn ${MODULE_NAME}:app --reload --port ${DEV_PORT} --workers ${WORKER_COUNT}
