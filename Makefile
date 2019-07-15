
.PHONY: build
build:
	@docker build -t ghetto_bot .

.PHONY: lint
lint: build
	docker run --rm \
		-v $$(pwd):/opt/app \
		ghetto_bot \
			black . && \
			flake8

.PHONY: run
run:
	@docker run \
		-v $$(pwd):/opt/app \
		ghetto_bot \
			poetry run errbot

.PHONY: clean
clean:
	rm -rf data/*.db

.PHONY: mount
mount:
	docker run -it \
		-v $$(pwd):/opt/app \
		ghetto_bot \
		bash
