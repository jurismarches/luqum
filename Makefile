tests:
	nosetests --with-coverage --cover-package=luqum

quality:
	flake8 --max-line-length=100 --exclude=parser.py,parsetab.py luqum/*.py
