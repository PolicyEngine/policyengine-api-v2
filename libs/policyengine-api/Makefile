build: test

install:
	poetry install
	poetry update

test: install
	poetry run pytest

format: 
	black . -l 79