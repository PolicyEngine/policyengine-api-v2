FROM python:3.11-slim

RUN pip install poetry==2.0.1

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR app
# This may copy some dependencies this app doesn't need, but source should
# not be very large
#.dockerignore will exclude .venv and .git
COPY build/staging .
COPY pyproject.toml poetry.lock projects/app/
RUN touch README.md

WORKDIR projects/app
RUN poetry install --with main --no-root && rm -rf $POETRY_CACHE_DIR

COPY src ./src/

RUN poetry install --with main --no-root

EXPOSE 8080
CMD ["poetry", "run", "fastapi", "run", "src/policyengine_simulation_api/main.py", "--port", "8080"]