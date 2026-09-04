.PHONY: install init serve verify test lint typecheck backup restore-verify

PYTHON ?= python3

install:
	./install.sh
init:
	alembic upgrade head
serve:
	$(PYTHON) -m zomega serve
verify:
	./verify.sh
test:
	$(PYTHON) -m unittest discover -s tests -v
lint:
	ruff check zomega tests
typecheck:
	mypy zomega/security.py zomega/audit.py zomega/key_service.py zomega/commercial.py zomega/registry.py zomega/marketplace.py
backup:
	./backup.sh
restore-verify:
	./restore-verify.sh
