ES_VERSION ?= 8.17.1

tests:
	pytest

# integration test with ES using docker
es_tests:
	( docker ps |grep luqum_test_es ) || \
	docker run --name luqum_test_es --rm -d -ti -p 127.0.0.1:9200:9200 \
		-e "discovery.type=single-node" -e  "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
		-e "xpack.security.enabled=false" \
		elasticsearch:${ES_VERSION}
# wait ES to be ready
	@echo "waiting for ES to be ready"
	@while ! curl -XGET "localhost:9200" >/dev/null 2>&1;do sleep 1; echo -n "."; done
	pytest
	docker stop luqum_test_es

quality:
	flake8 luqum tests

# To upload files, you need to have a ~/.pypirc file locally.
# This file should contain all the necessary passwords and API-tokens.
distribute:
	rm -r build
	rm dist/*
	python -m build --wheel
	python -m build --sdist
	python -m twine upload --verbose --repository luqum dist/*

.PHONY: tests quality distribute
