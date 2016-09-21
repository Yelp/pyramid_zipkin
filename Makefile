.PHONY: all install test tests clean docs install-hooks

all: test

build:
	./setup.py bdist_egg

dev: clean
	./setup.py develop

install:
	pip install .

install-hooks:
	tox -e pre-commit -- install -f --install-hooks

test:
	tox

tests: test

docs:
	tox -e docs

clean:
	@rm -rf .tox build dist docs/build *.egg-info
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -delete
