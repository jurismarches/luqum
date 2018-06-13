tests:
	nosetests --with-coverage -s --cover-package=luqum --config=nose.cfg --with-doctest --cover-branches

quality:
	flake8 --max-line-length=100 --exclude=parser.py,parsetab.py luqum/*.py luqum/**/*.py
distribute:
	[ -z $(ls dist/)  ] || rm dist/*
	python3 setup.py bdist
	python3 setup.py bdist_wheel
	twine upload -u jurismarches -s dist/*
