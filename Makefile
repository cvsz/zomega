.PHONY: install init serve verify test backup

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
backup:
	./backup.sh
