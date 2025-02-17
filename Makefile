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

# Remove the -s in the last line if it does not work out of the blue.
# Also add the jurismarches password for PyPI via the -p twine upload option,
# just in case.
# This gives 'twine upload -u jurismarches -p <password>  dist/*'.
distribute:
	[ -z $(ls dist/) ] || rm dist/*
	python3 setup.py bdist
	python3 setup.py bdist_wheel
	twine upload -u jurismarches -s dist/*

.PHONY: tests quality distribute
