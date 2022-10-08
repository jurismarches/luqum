ES_VERSION ?= 7.17.5

tests:
	pytest

# integration test with ES using docker
es_tests:
	docker run --name luqum_test_es --rm -d -ti -p 127.0.0.1:9200:9200  -e "discovery.type=single-node" -e  "ES_JAVA_OPTS=-Xms512m -Xmx512m" elasticsearch:${ES_VERSION}
# wait ES to be ready
	@echo "waiting for ES to be ready"
	@while ! curl -XGET "localhost:9200" >/dev/null 2>&1;do sleep 1; echo -n "."; done
	pytest
	docker stop luqum_test_es

quality:
	flake8 luqum tests

distribute:
	[ -z $(ls dist/) ] || rm dist/*
	python3 setup.py bdist
	python3 setup.py bdist_wheel
	twine upload -u jurismarches -s dist/*

.PHONY: tests quality distribute
