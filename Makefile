full-test: test

test:
	pytest --cov-report term-missing --cov=silver_braintree tests/

run:
	echo "TBA"

build:
	echo "No need to build someting"

lint:
	pep8 --max-line-length=100 --exclude=migrations,errors.py .

.PHONY: test full-test build lint run
