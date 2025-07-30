FROM python:3.13

RUN pip install poetry==2.0.1

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR app
# This may copy some dependencies this app doesn't need, but source should
# not be very large
#.dockerignore will exclude .venv and .git
COPY artifacts/staging .
COPY pyproject.toml poetry.lock projects/app/
RUN touch README.md

WORKDIR projects/app
RUN poetry install --with main --no-root && rm -rf $POETRY_CACHE_DIR

COPY src ./src/

RUN poetry install --with main --no-root

EXPOSE 8080
# bottlenck is memory
# one worker to handle external reuqests (max allowed = 1)
# one worker to do the liveness check
CMD ["poetry", "run", "uvicorn", "src.policyengine_api_simulation.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
