PYTHON ?= python3

.PHONY: deploy deploy-docker-desktop verify destroy

deploy:
	$(PYTHON) scripts/deploy.py

deploy-docker-desktop:
	$(PYTHON) scripts/deploy.py --docker-desktop

verify:
	$(PYTHON) scripts/verify.py

destroy:
	$(PYTHON) scripts/destroy.py