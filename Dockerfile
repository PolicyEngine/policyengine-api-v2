#as per uv documentation
FROM python:3.12-slim-bookworm
ARG SERVICE_NAME=UNSET_SERVICE_NAME
ARG MODULE_NAME=UNSET_MODULE_NAME
ARG WORKER_COUNT=1
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV  ENVIRONMENT="production" \
    JWT_ISSUER=https://your_production_issuer/ \
    JWT_AUDIENCE=https://your_production_api/ \
    OT_SERVICE_NAME=${SERVICE_NAME}\
    OT_SERVICE_INSTANCE_ID=instance

WORKDIR /app
COPY . .
WORKDIR /app/projects/${SERVICE_NAME}
RUN uv sync --locked

EXPOSE 8080
ENV MODULE_NAME=$MODULE_NAME
ENV WORKER_COUNT=$WORKER_COUNT
CMD cd src && uvicorn $MODULE_NAME:app --host 0.0.0.0 --port 8080 --workers $WORKER_COUNT
