tests:
	nosetests --with-coverage --cover-package=luqum --config=nose.cfg

quality:
	flake8 --max-line-length=100 --exclude=parser.py,parsetab.py luqum/*.py
