.PHONY: install init serve verify test lint typecheck backup restore-verify

PYTHON ?= python3

install:
	./install.sh
init:
	alembic upgrade head
serve:
	$(PYTHON) -m omega serve
verify:
	./verify.sh
test:
	$(PYTHON) -m unittest discover -s tests -v
lint:
	ruff check omega tests
typecheck:
	mypy omega/security.py omega/audit.py omega/key_service.py omega/commercial.py omega/registry.py omega/marketplace.py
backup:
	./backup.sh
restore-verify:
	./restore-verify.sh
