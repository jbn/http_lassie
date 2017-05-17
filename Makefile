all:
	coverage run --source http_lassie setup.py nosetests
	coverage report
