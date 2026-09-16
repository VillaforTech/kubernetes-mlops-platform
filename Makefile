.PHONY: help check render up demo smoke down
help:
	@echo 'check: lint, tests, manifest checks | up: build and deploy | demo: train and promote'
	@echo 'smoke: verify data flow and metrics | render: inspect manifests without secrets'
	@echo 'down: refuses unless CONFIRM=mlops-platform (deletes cluster data)'
check:
	ruff check .
	pytest -q
	python tools/validate.py
	git diff --check
render:
	kubectl kustomize k8s
up:
	mlops up
demo:
	mlops demo
smoke:
	mlops smoke
down:
	mlops down --confirm "$(CONFIRM)"
